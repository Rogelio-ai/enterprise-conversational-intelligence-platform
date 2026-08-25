from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.intelligence import TrustedIntelligenceContext
from app.models import (
    Conversation,
    ConversationMessage,
    ConversationParticipant,
    IntelligenceDerivation,
    RestaurantMessageIntent,
)
from app.restaurant.intelligence.contracts import (
    RESTAURANT_INTENT_SCHEMA_KEY,
    RESTAURANT_INTENT_SCHEMA_VERSION,
    ConversationMessageEvidence,
    RestaurantMessageUnderstandingPort,
    RestaurantUnderstandingRequest,
    RestaurantUnderstandingResult,
)
from app.restaurant.intelligence.errors import (
    InvalidUnderstandingResultError,
    RestaurantIntelligenceError,
    UnderstandingUnavailableError,
)

logger = logging.getLogger('ecip.restaurant_intelligence')
MAX_HISTORY_MESSAGES = 50


@dataclass(frozen=True, slots=True)
class PersistedIntentResult:
    id: int
    ordinal: int
    intent_code: str
    confidence: Decimal | None


@dataclass(frozen=True, slots=True)
class UnderstandingExecutionResult:
    derivation_id: int
    tenant_id: int
    conversation_id: int
    source_message_id: int
    schema_key: str
    schema_version: str
    producer_key: str
    producer_version: str
    correlation_id: str
    intents: tuple[PersistedIntentResult, ...]


def _evidence(message: ConversationMessage) -> ConversationMessageEvidence:
    return ConversationMessageEvidence(
        message_id=message.id,
        participant_id=message.participant_id,
        sequence_number=message.sequence_number,
        modality=message.modality,
        content_text=message.content_text,
        language=message.language,
        language_source=message.language_source,
    )


def _validate_result(
    result: object, *, correlation_id: str
) -> RestaurantUnderstandingResult:
    if not isinstance(result, RestaurantUnderstandingResult):
        raise InvalidUnderstandingResultError(
            'Understanding provider returned an invalid result type',
            correlation_id=correlation_id,
        )
    if (
        result.schema_key != RESTAURANT_INTENT_SCHEMA_KEY
        or result.schema_version != RESTAURANT_INTENT_SCHEMA_VERSION
    ):
        raise InvalidUnderstandingResultError(
            'Understanding result uses an unsupported Restaurant taxonomy',
            correlation_id=correlation_id,
        )
    return result


async def understand_message(
    db: AsyncSession,
    port: RestaurantMessageUnderstandingPort,
    *,
    tenant_id: int,
    conversation_id: int,
    source_message_id: int,
    correlation_id: str,
    history_limit: int = 10,
) -> UnderstandingExecutionResult:
    if min(tenant_id, conversation_id, source_message_id) <= 0:
        raise ValueError('Trusted intelligence identifiers must be positive')
    if not 0 <= history_limit <= MAX_HISTORY_MESSAGES:
        raise ValueError(f'history_limit must be between 0 and {MAX_HISTORY_MESSAGES}')

    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
        )
    )
    if conversation is None:
        raise InvalidUnderstandingResultError(
            'Trusted Conversation was not found', correlation_id=correlation_id
        )
    source_message = await db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.id == source_message_id,
            ConversationMessage.tenant_id == tenant_id,
            ConversationMessage.conversation_id == conversation_id,
        )
    )
    if source_message is None:
        raise InvalidUnderstandingResultError(
            'Source message was not found in the trusted Conversation',
            correlation_id=correlation_id,
        )
    participant = await db.scalar(
        select(ConversationParticipant.id).where(
            ConversationParticipant.id == source_message.participant_id,
            ConversationParticipant.tenant_id == tenant_id,
            ConversationParticipant.conversation_id == conversation_id,
        )
    )
    if participant is None:
        raise InvalidUnderstandingResultError(
            'Source participant was not found in the trusted Conversation',
            correlation_id=correlation_id,
        )

    history: tuple[ConversationMessageEvidence, ...] = ()
    if history_limit:
        result = await db.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.tenant_id == tenant_id,
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.sequence_number < source_message.sequence_number,
            )
            .order_by(ConversationMessage.sequence_number.desc())
            .limit(history_limit)
        )
        history = tuple(_evidence(message) for message in reversed(result.scalars().all()))

    context = TrustedIntelligenceContext(
        tenant_id=tenant_id,
        organization_id=conversation.organization_id,
        location_id=conversation.location_id,
        resource_id=conversation.resource_id,
        conversation_id=conversation.id,
        source_message_id=source_message.id,
        participant_id=source_message.participant_id,
        correlation_id=correlation_id,
    )
    request = RestaurantUnderstandingRequest(
        context=context,
        source_message=_evidence(source_message),
        history=history,
    )
    try:
        provider_result = await port.understand(request)
    except RestaurantIntelligenceError:
        raise
    except Exception as exc:
        raise UnderstandingUnavailableError(
            'Restaurant understanding is unavailable', correlation_id=context.correlation_id
        ) from exc
    understood = _validate_result(provider_result, correlation_id=context.correlation_id)

    derivation = IntelligenceDerivation(
        tenant_id=context.tenant_id,
        conversation_id=context.conversation_id,
        source_message_id=context.source_message_id,
        schema_key=understood.schema_key,
        schema_version=understood.schema_version,
        producer_key=understood.producer_key,
        producer_version=understood.producer_version,
        correlation_id=context.correlation_id,
    )
    db.add(derivation)
    try:
        await db.flush()
        intent_rows = tuple(
            RestaurantMessageIntent(
                tenant_id=context.tenant_id,
                derivation_id=derivation.id,
                ordinal=ordinal,
                intent_code=candidate.intent_code.value,
                confidence=candidate.confidence,
            )
            for ordinal, candidate in enumerate(understood.intents, start=1)
        )
        db.add_all(intent_rows)
        await db.commit()
        for row in intent_rows:
            await db.refresh(row)
    except Exception:
        await db.rollback()
        raise

    logger.info(
        'Restaurant message understanding persisted',
        extra={
            'event': 'restaurant_message_understood',
            'operation': 'understand_message',
            'tenant_id': context.tenant_id,
            'organization_id': context.organization_id,
            'location_id': context.location_id,
            'conversation_id': context.conversation_id,
            'source_message_id': context.source_message_id,
            'derivation_id': derivation.id,
            'producer_key': derivation.producer_key,
            'producer_version': derivation.producer_version,
            'correlation_id': context.correlation_id,
            'outcome': 'persisted',
        },
    )
    return UnderstandingExecutionResult(
        derivation_id=derivation.id,
        tenant_id=derivation.tenant_id,
        conversation_id=derivation.conversation_id,
        source_message_id=derivation.source_message_id,
        schema_key=derivation.schema_key,
        schema_version=derivation.schema_version,
        producer_key=derivation.producer_key,
        producer_version=derivation.producer_version,
        correlation_id=derivation.correlation_id,
        intents=tuple(
            PersistedIntentResult(
                id=row.id,
                ordinal=row.ordinal,
                intent_code=row.intent_code,
                confidence=row.confidence,
            )
            for row in intent_rows
        ),
    )
