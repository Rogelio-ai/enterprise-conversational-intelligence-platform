from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from app.core.intelligence import TrustedIntelligenceContext


RESTAURANT_INTENT_SCHEMA_KEY = 'restaurant.message_intents'
RESTAURANT_INTENT_SCHEMA_VERSION = '1'


class RestaurantIntentCode(StrEnum):
    MENU_QUERY = 'MENU_QUERY'
    PRODUCT_QUERY = 'PRODUCT_QUERY'
    PRICE_QUERY = 'PRICE_QUERY'
    PROMOTION_QUERY = 'PROMOTION_QUERY'
    ORDER_EXPRESSION = 'ORDER_EXPRESSION'
    HUMAN_ASSISTANCE_REQUEST = 'HUMAN_ASSISTANCE_REQUEST'
    UNKNOWN = 'UNKNOWN'


def _required_text(value: str, *, name: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f'{name} must contain between 1 and {maximum} characters')
    return normalized


@dataclass(frozen=True, slots=True)
class ConversationMessageEvidence:
    message_id: int
    participant_id: int
    sequence_number: int
    modality: str
    content_text: str
    language: str | None
    language_source: str | None

    def __post_init__(self) -> None:
        if min(self.message_id, self.participant_id, self.sequence_number) <= 0:
            raise ValueError('Message evidence identifiers and sequence must be positive')
        if self.modality not in {'TEXT', 'VOICE', 'TOUCH'}:
            raise ValueError('Message evidence modality is unsupported')
        if not self.content_text.strip() or len(self.content_text) > 10_000:
            raise ValueError('Message evidence content is invalid')
        if (self.language is None) != (self.language_source is None):
            raise ValueError('Message evidence language metadata must be paired')


@dataclass(frozen=True, slots=True)
class RestaurantUnderstandingRequest:
    context: TrustedIntelligenceContext
    source_message: ConversationMessageEvidence
    history: tuple[ConversationMessageEvidence, ...]

    def __post_init__(self) -> None:
        if self.source_message.message_id != self.context.source_message_id:
            raise ValueError('Source evidence does not match trusted message context')
        if self.source_message.participant_id != self.context.participant_id:
            raise ValueError('Source evidence does not match trusted participant context')
        sequences = tuple(item.sequence_number for item in self.history)
        if sequences != tuple(sorted(sequences)) or len(sequences) != len(set(sequences)):
            raise ValueError('History evidence must be uniquely ordered')
        if any(item.sequence_number >= self.source_message.sequence_number for item in self.history):
            raise ValueError('History evidence must precede the source message')


@dataclass(frozen=True, slots=True)
class RestaurantIntentCandidate:
    intent_code: RestaurantIntentCode
    confidence: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.intent_code, RestaurantIntentCode):
            raise ValueError('Intent code is not part of Restaurant taxonomy v1')
        if self.confidence is not None:
            if not isinstance(self.confidence, Decimal):
                raise ValueError('Intent confidence must be an exact Decimal')
            if not self.confidence.is_finite() or not Decimal('0') <= self.confidence <= Decimal('1'):
                raise ValueError('Intent confidence must be within [0,1]')
            if self.confidence.as_tuple().exponent < -4:
                raise ValueError('Intent confidence supports at most four fractional digits')


@dataclass(frozen=True, slots=True)
class RestaurantUnderstandingResult:
    schema_key: str
    schema_version: str
    producer_key: str
    producer_version: str
    intents: tuple[RestaurantIntentCandidate, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'schema_key', _required_text(self.schema_key, name='schema_key', maximum=100)
        )
        object.__setattr__(
            self,
            'schema_version',
            _required_text(self.schema_version, name='schema_version', maximum=64),
        )
        object.__setattr__(
            self,
            'producer_key',
            _required_text(self.producer_key, name='producer_key', maximum=128),
        )
        object.__setattr__(
            self,
            'producer_version',
            _required_text(self.producer_version, name='producer_version', maximum=128),
        )
        if not self.intents:
            raise ValueError('At least one Restaurant intent candidate is required')
        codes = tuple(candidate.intent_code for candidate in self.intents)
        if len(codes) != len(set(codes)):
            raise ValueError('Restaurant intent candidates must not repeat an intent code')


@runtime_checkable
class RestaurantMessageUnderstandingPort(Protocol):
    async def understand(
        self, request: RestaurantUnderstandingRequest
    ) -> RestaurantUnderstandingResult: ...
