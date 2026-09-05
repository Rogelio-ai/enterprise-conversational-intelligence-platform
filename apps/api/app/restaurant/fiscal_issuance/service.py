from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ExecutionContext
from app.models import (
    BillingDocument,
    BillingDocumentLine,
    BillingDocumentLineTax,
    BillingIssuance,
    BillingIssuanceAttempt,
)
from app.restaurant.fiscal_issuance import errors
from app.restaurant.fiscal_issuance.contracts import (
    BillingIssuanceAttemptProjection,
    BillingIssuanceProjection,
    InitiateFiscalIssuanceCommand,
    RecoverFiscalIssuanceCommand,
    RetryFiscalIssuanceCommand,
)
from app.restaurant.integrations.fiscal import errors as integration_errors
from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalIssuanceLine,
    FiscalIssuanceLineTax,
    FiscalIssuanceOutcome,
    FiscalIssuanceRecoveryRequest,
    FiscalIssuanceRequest,
    FiscalIssuanceResult,
    FiscalProviderErrorKind,
    FiscalRecoveryOutcome,
    FiscalRecoveryResult,
    FrozenFiscalPartySnapshot,
)
from app.restaurant.integrations.fiscal.credentials import (
    FiscalProviderCredentialBinding,
    FiscalProviderCredentialResolver,
)
from app.restaurant.integrations.fiscal.ports import FiscalIssuancePort
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry


REQUEST_SCHEMA_VERSION = 1
CLAIM_LEASE = timedelta(seconds=30)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sha(value: object) -> str:
    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def _decimal(value: Decimal) -> str:
    return format(Decimal(value), 'f')


def _actor_scope(context: ExecutionContext) -> str:
    identity = (
        str(context.principal_id)
        if context.principal_id is not None
        else context.principal_reference
    )
    return f'{context.actor_type.value}:{identity}'


def _validate_command(command: InitiateFiscalIssuanceCommand) -> None:
    identifiers = (
        command.organization_id,
        command.location_id,
        command.billing_document_id,
    )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in identifiers
    ):
        raise errors.FiscalIssuanceRequestInvalidError(
            'Fiscal issuance identifiers must be positive integers'
        )
    if (
        not command.provider_key
        or command.provider_key != command.provider_key.strip()
        or len(command.provider_key) > 128
    ):
        raise errors.FiscalIssuanceRequestInvalidError(
            'Fiscal provider key is invalid'
        )
    if command.credential_binding is not None and (
        not command.credential_binding
        or command.credential_binding != command.credential_binding.strip()
        or len(command.credential_binding) > 200
    ):
        raise errors.FiscalIssuanceRequestInvalidError(
            'Fiscal credential binding is invalid'
        )
    if (
        not command.idempotency_key
        or command.idempotency_key != command.idempotency_key.strip()
        or len(command.idempotency_key) > 128
        or not command.idempotency_key.isascii()
    ):
        raise errors.FiscalIssuanceRequestInvalidError(
            'Fiscal issuance idempotency key is invalid'
        )


def _validate_existing_command(
    command: RecoverFiscalIssuanceCommand | RetryFiscalIssuanceCommand,
) -> None:
    identifiers = (
        command.organization_id,
        command.location_id,
        command.billing_issuance_id,
    )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in identifiers
    ):
        raise errors.FiscalIssuanceRequestInvalidError(
            'Fiscal issuance identifiers must be positive integers'
        )


def _party_snapshot(
    value: object,
    *,
    recipient: bool,
) -> FrozenFiscalPartySnapshot:
    if not isinstance(value, dict):
        raise errors.FiscalCanonicalEvidenceInvalidError(
            'Canonical fiscal party evidence is malformed'
        )
    required = (
        'legal_name',
        'tax_identifier',
        'tax_regime',
        'fiscal_postal_code',
    )
    if recipient:
        required += ('invoice_usage',)
    if any(
        not isinstance(value.get(name), str)
        or not value[name]
        or value[name] != value[name].strip()
        for name in required
    ):
        raise errors.FiscalCanonicalEvidenceInvalidError(
            'Canonical fiscal party evidence is incomplete'
        )
    return FrozenFiscalPartySnapshot(
        legal_name=value['legal_name'],
        tax_identifier=value['tax_identifier'],
        tax_regime=value['tax_regime'],
        postal_code=value['fiscal_postal_code'],
        document_usage=value['invoice_usage'] if recipient else None,
    )


def _provider_operation_identity(
    document: BillingDocument,
    *,
    provider_key: str,
    credential_binding: str | None,
) -> tuple[str, str]:
    operation_reference = (
        f'fiscal-issuance-v1:{document.tenant_id}:{document.id}'
    )
    binding_fingerprint = _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'tenant_id': document.tenant_id,
        'billing_document_id': document.id,
        'provider_key': provider_key,
        'credential_binding': credential_binding,
    })
    provider_idempotency_key = (
        f'fiscal-issue-v1:{document.tenant_id}:{document.id}:'
        f'{binding_fingerprint[:32]}'
    )
    return operation_reference, provider_idempotency_key


async def _canonical_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    command: InitiateFiscalIssuanceCommand,
    lock_document: bool,
) -> tuple[BillingDocument, FiscalIssuanceRequest]:
    document_statement = select(BillingDocument).where(
        BillingDocument.id == command.billing_document_id,
        BillingDocument.tenant_id == tenant_id,
        BillingDocument.organization_id == command.organization_id,
        BillingDocument.location_id == command.location_id,
    )
    if lock_document:
        document_statement = document_statement.with_for_update()
    document = await db.scalar(document_statement)
    if document is None:
        raise errors.FiscalBillingDocumentNotFoundError()
    if document.status != 'DRAFT':
        raise errors.FiscalCanonicalEvidenceInvalidError(
            'Billing Document is not eligible for fiscal issuance'
        )

    lines = tuple((await db.execute(
        select(BillingDocumentLine)
        .where(BillingDocumentLine.billing_document_id == document.id)
        .order_by(BillingDocumentLine.id)
    )).scalars().all())
    if not lines:
        raise errors.FiscalCanonicalEvidenceInvalidError(
            'Canonical Billing Document line evidence is empty'
        )
    line_ids = tuple(line.id for line in lines)
    taxes = tuple((await db.execute(
        select(BillingDocumentLineTax)
        .where(BillingDocumentLineTax.billing_document_line_id.in_(line_ids))
        .order_by(
            BillingDocumentLineTax.billing_document_line_id,
            BillingDocumentLineTax.id,
        )
    )).scalars().all())
    taxes_by_line: dict[int, list[BillingDocumentLineTax]] = {
        line_id: [] for line_id in line_ids
    }
    for tax in taxes:
        taxes_by_line[tax.billing_document_line_id].append(tax)
    if any(not taxes_by_line[line_id] for line_id in line_ids):
        raise errors.FiscalCanonicalEvidenceInvalidError(
            'Canonical Billing Document tax evidence is incomplete'
        )

    operation_reference, provider_idempotency_key = _provider_operation_identity(
        document,
        provider_key=command.provider_key,
        credential_binding=command.credential_binding,
    )
    canonical_lines = tuple(
        {
            'billing_document_line_id': line.id,
            'source_restaurant_order_id': line.source_restaurant_order_id,
            'source_restaurant_order_item_id': line.source_restaurant_order_item_id,
            'description': line.description,
            'quantity': _decimal(line.quantity),
            'unit_price': _decimal(line.unit_price),
            'base_amount': _decimal(line.base_amount),
            'discount_amount': _decimal(line.discount_amount),
            'total': _decimal(line.commercial_total),
            'taxes': tuple({
                'billing_document_line_tax_id': tax.id,
                'category': tax.tax_category,
                'treatment': tax.tax_treatment,
                'rate': _decimal(tax.tax_rate),
                'taxable_base': _decimal(tax.taxable_base),
                'amount': _decimal(tax.tax_amount),
            } for tax in taxes_by_line[line.id]),
        }
        for line in lines
    )
    fingerprint = _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'tenant_id': document.tenant_id,
        'organization_id': document.organization_id,
        'location_id': document.location_id,
        'billing_document_id': document.id,
        'billing_request_fingerprint': document.request_fingerprint,
        'source_check_version': document.source_check_version,
        'source_check_fingerprint': document.source_check_fingerprint,
        'document_type': document.document_type,
        'currency': document.currency,
        'subtotal': _decimal(document.subtotal),
        'discount_total': _decimal(document.discount_total),
        'tax_total': _decimal(document.tax_total),
        'total': _decimal(document.total),
        'issuer_snapshot': document.issuer_snapshot,
        'recipient_snapshot': document.recipient_snapshot,
        'lines': canonical_lines,
        'operation_reference': operation_reference,
        'provider_key': command.provider_key,
        'credential_binding': command.credential_binding,
        'provider_idempotency_key': provider_idempotency_key,
    })
    try:
        request = FiscalIssuanceRequest(
            tenant_id=document.tenant_id,
            organization_id=document.organization_id,
            location_id=document.location_id,
            billing_document_id=document.id,
            operation_reference=operation_reference,
            provider_idempotency_key=provider_idempotency_key,
            request_fingerprint=fingerprint,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            document_type=document.document_type,
            currency=document.currency,
            subtotal=Decimal(document.subtotal),
            discount_total=Decimal(document.discount_total),
            tax_total=Decimal(document.tax_total),
            total=Decimal(document.total),
            issuer=_party_snapshot(document.issuer_snapshot, recipient=False),
            recipient=_party_snapshot(document.recipient_snapshot, recipient=True),
            lines=tuple(FiscalIssuanceLine(
                billing_document_line_id=line.id,
                description=line.description,
                quantity=Decimal(line.quantity),
                unit_price=Decimal(line.unit_price),
                base_amount=Decimal(line.base_amount),
                discount_amount=Decimal(line.discount_amount),
                total=Decimal(line.commercial_total),
                taxes=tuple(FiscalIssuanceLineTax(
                    billing_document_line_tax_id=tax.id,
                    category=tax.tax_category,
                    treatment=tax.tax_treatment,
                    rate=Decimal(tax.tax_rate),
                    taxable_base=Decimal(tax.taxable_base),
                    amount=Decimal(tax.tax_amount),
                ) for tax in taxes_by_line[line.id]),
            ) for line in lines),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise errors.FiscalCanonicalEvidenceInvalidError(
            'Canonical Billing Document evidence is malformed'
        ) from None
    return document, request


async def _issuance_by_key(
    db: AsyncSession,
    *,
    tenant_id: int,
    actor_scope: str,
    idempotency_key: str,
) -> BillingIssuance | None:
    return await db.scalar(select(BillingIssuance).where(
        BillingIssuance.tenant_id == tenant_id,
        BillingIssuance.actor_scope == actor_scope,
        BillingIssuance.idempotency_key == idempotency_key,
    ))


async def _projection(
    db: AsyncSession,
    issuance: BillingIssuance,
) -> BillingIssuanceProjection:
    attempts = tuple((await db.execute(
        select(BillingIssuanceAttempt)
        .where(BillingIssuanceAttempt.billing_issuance_id == issuance.id)
        .order_by(
            BillingIssuanceAttempt.attempt_sequence,
            BillingIssuanceAttempt.id,
        )
    )).scalars().all())
    return BillingIssuanceProjection(
        id=issuance.id,
        tenant_id=issuance.tenant_id,
        organization_id=issuance.organization_id,
        location_id=issuance.location_id,
        billing_document_id=issuance.billing_document_id,
        provider_key=issuance.provider_key,
        state=issuance.state,
        idempotency_key=issuance.idempotency_key,
        request_schema_version=issuance.request_schema_version,
        request_fingerprint=issuance.request_fingerprint,
        provider_idempotency_key=issuance.provider_idempotency_key,
        external_reference=issuance.external_reference,
        external_status=issuance.external_status,
        attempt_count=issuance.attempt_count,
        last_error_kind=issuance.last_error_kind,
        last_error_message=issuance.last_error_message,
        requested_at=issuance.requested_at,
        completed_at=issuance.completed_at,
        attempts=tuple(BillingIssuanceAttemptProjection(
            sequence=attempt.attempt_sequence,
            attempt_type=attempt.attempt_type,
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            result=attempt.result,
            external_reference=attempt.external_reference,
            external_status=attempt.external_status,
            error_kind=attempt.error_kind,
            error_message=attempt.error_message,
            result_fingerprint=attempt.result_fingerprint,
            actor_type=attempt.actor_type,
            actor_id=attempt.actor_id,
            actor_reference=attempt.actor_reference,
            correlation_id=attempt.correlation_id,
        ) for attempt in attempts),
    )


def _assert_same_request(
    issuance: BillingIssuance,
    request: FiscalIssuanceRequest,
    *,
    idempotency_match: bool,
) -> None:
    if issuance.request_fingerprint != request.request_fingerprint:
        if idempotency_match:
            raise errors.FiscalIssuanceIdempotencyConflictError()
        raise errors.FiscalIssuanceStateConflictError(
            'Billing Document already has a different fiscal issuance binding'
        )


async def _reserve(
    db: AsyncSession,
    *,
    execution: ExecutionContext,
    command: InitiateFiscalIssuanceCommand,
) -> tuple[BillingIssuance, FiscalIssuanceRequest, bool]:
    actor_scope = _actor_scope(execution)
    try:
        document, request = await _canonical_request(
            db,
            tenant_id=execution.tenant_id,
            command=command,
            lock_document=True,
        )
        existing = await _issuance_by_key(
            db,
            tenant_id=execution.tenant_id,
            actor_scope=actor_scope,
            idempotency_key=command.idempotency_key,
        )
        if existing is not None:
            _assert_same_request(existing, request, idempotency_match=True)
            await db.commit()
            return existing, request, True

        existing = await db.scalar(select(BillingIssuance).where(
            BillingIssuance.billing_document_id == document.id,
        ))
        if existing is not None:
            _assert_same_request(existing, request, idempotency_match=False)
            await db.commit()
            return existing, request, True

        issuance = BillingIssuance(
            tenant_id=document.tenant_id,
            organization_id=document.organization_id,
            location_id=document.location_id,
            billing_document_id=document.id,
            provider_key=command.provider_key,
            credential_binding=command.credential_binding,
            state='PENDING',
            actor_scope=actor_scope,
            idempotency_key=command.idempotency_key,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=request.request_fingerprint,
            provider_idempotency_key=request.provider_idempotency_key,
            attempt_count=0,
            requested_at=_now(),
        )
        db.add(issuance)
        await db.flush()
        await db.commit()
        return issuance, request, False
    except IntegrityError as exc:
        await db.rollback()
        winner = await _issuance_by_key(
            db,
            tenant_id=execution.tenant_id,
            actor_scope=actor_scope,
            idempotency_key=command.idempotency_key,
        )
        if winner is None:
            winner = await db.scalar(select(BillingIssuance).where(
                BillingIssuance.billing_document_id == command.billing_document_id,
                BillingIssuance.tenant_id == execution.tenant_id,
            ))
        if winner is None:
            raise errors.FiscalIssuanceConcurrencyConflictError() from exc
        _, request = await _canonical_request(
            db,
            tenant_id=execution.tenant_id,
            command=command,
            lock_document=False,
        )
        _assert_same_request(
            winner,
            request,
            idempotency_match=(
                winner.actor_scope == actor_scope
                and winner.idempotency_key == command.idempotency_key
            ),
        )
        await db.commit()
        return winner, request, True
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise


async def _claim_initial(
    db: AsyncSession,
    *,
    issuance_id: int,
    execution: ExecutionContext,
) -> tuple[BillingIssuance, str | None]:
    try:
        issuance = await db.scalar(
            select(BillingIssuance)
            .where(
                BillingIssuance.id == issuance_id,
                BillingIssuance.tenant_id == execution.tenant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if issuance is None:
            raise errors.FiscalIssuanceStateConflictError(
                'Fiscal issuance reservation no longer exists'
            )
        if issuance.state != 'PENDING':
            await db.commit()
            return issuance, None
        if issuance.attempt_count != 0:
            raise errors.FiscalIssuanceStateConflictError(
                'Pending fiscal issuance already contains attempt evidence'
            )

        token = str(uuid4())
        now = _now()
        issuance.state = 'IN_PROGRESS'
        issuance.claim_token = token
        issuance.claim_expires_at = now + CLAIM_LEASE
        issuance.attempt_count = 1
        issuance.last_error_kind = None
        issuance.last_error_message = None
        db.add(BillingIssuanceAttempt(
            tenant_id=issuance.tenant_id,
            organization_id=issuance.organization_id,
            location_id=issuance.location_id,
            billing_issuance_id=issuance.id,
            attempt_sequence=1,
            attempt_type='ISSUE',
            claim_token=token,
            started_at=now,
            completed_at=None,
            result=None,
            actor_type=execution.actor_type.value,
            actor_id=execution.principal_id,
            actor_reference=execution.principal_reference,
            correlation_id=execution.correlation_id,
        ))
        await db.commit()
        return issuance, token
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise


def _safe_result_values(
    result: FiscalIssuanceResult,
) -> tuple[str, str | None, str | None]:
    state = {
        FiscalIssuanceOutcome.SUCCEEDED: 'SUCCEEDED',
        FiscalIssuanceOutcome.DEFINITE_FAILURE: 'FAILED',
        FiscalIssuanceOutcome.REJECTED: 'REJECTED',
        FiscalIssuanceOutcome.UNCERTAIN: 'UNCERTAIN',
    }[result.outcome]
    error_kind = None if result.error_kind is None else result.error_kind.value
    error_message = {
        'SUCCEEDED': None,
        'FAILED': 'Fiscal provider reported a definite technical failure',
        'REJECTED': 'Fiscal provider rejected fiscal issuance',
        'UNCERTAIN': 'Fiscal provider result is uncertain',
    }[state]
    return state, error_kind, error_message


async def _finish(
    db: AsyncSession,
    *,
    tenant_id: int,
    issuance_id: int,
    token: str,
    state: str,
    external_reference: str | None,
    external_status: str | None,
    error_kind: str | None,
    error_message: str | None,
) -> BillingIssuance:
    try:
        issuance = await db.scalar(
            select(BillingIssuance)
            .where(
                BillingIssuance.id == issuance_id,
                BillingIssuance.tenant_id == tenant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if issuance is None:
            raise errors.FiscalIssuanceStateConflictError()
        if (
            issuance.claim_token != token
            or issuance.state != 'IN_PROGRESS'
            or issuance.claim_expires_at is None
            or issuance.claim_expires_at <= _now()
        ):
            raise errors.FiscalIssuanceStaleFenceError(
                'Fiscal issuance result lost ownership of its attempt'
            )
        attempt = await db.scalar(
            select(BillingIssuanceAttempt)
            .where(
                BillingIssuanceAttempt.billing_issuance_id == issuance.id,
                BillingIssuanceAttempt.claim_token == token,
            )
            .with_for_update()
        )
        if attempt is None or attempt.result is not None:
            raise errors.FiscalIssuanceStateConflictError(
                'Fiscal issuance attempt is not current'
            )

        now = _now()
        issuance.state = state
        issuance.claim_token = None
        issuance.claim_expires_at = None
        issuance.external_reference = external_reference
        issuance.external_status = external_status
        issuance.last_error_kind = error_kind
        issuance.last_error_message = error_message
        issuance.completed_at = now if state in ('SUCCEEDED', 'REJECTED') else None
        attempt.completed_at = now
        attempt.result = state
        attempt.external_reference = external_reference
        attempt.external_status = external_status
        attempt.error_kind = error_kind
        attempt.error_message = error_message
        attempt.result_fingerprint = _sha({
            'schema_version': 1,
            'result': state,
            'external_reference': external_reference,
            'external_status': external_status,
            'error_kind': error_kind,
        })
        await db.commit()
        return issuance
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise


async def _credential(
    *,
    issuance: BillingIssuance,
    resolver: FiscalProviderCredentialResolver | None,
) -> EphemeralFiscalProviderCredential | None:
    if issuance.credential_binding is None:
        return None
    if resolver is None or not isinstance(resolver, FiscalProviderCredentialResolver):
        raise errors.FiscalCredentialResolutionError()
    binding = FiscalProviderCredentialBinding(
        tenant_id=issuance.tenant_id,
        organization_id=issuance.organization_id,
        location_id=issuance.location_id,
        provider_key=issuance.provider_key,
        credential_binding=issuance.credential_binding,
        operation_reference=(
            f'fiscal-issuance-v1:{issuance.tenant_id}:{issuance.billing_document_id}'
        ),
    )
    try:
        credential = await resolver.resolve(binding=binding)
    except Exception:
        raise errors.FiscalCredentialResolutionError() from None
    if not isinstance(credential, EphemeralFiscalProviderCredential):
        raise errors.FiscalCredentialResolutionError()
    return credential


async def _fail_resolution(
    db: AsyncSession,
    *,
    issuance: BillingIssuance,
    token: str,
    error_kind: str,
    error_message: str,
) -> None:
    await _finish(
        db,
        tenant_id=issuance.tenant_id,
        issuance_id=issuance.id,
        token=token,
        state='FAILED',
        external_reference=None,
        external_status=None,
        error_kind=error_kind,
        error_message=error_message,
    )


def _recovery_request(issuance: BillingIssuance) -> FiscalIssuanceRecoveryRequest:
    return FiscalIssuanceRecoveryRequest(
        tenant_id=issuance.tenant_id,
        organization_id=issuance.organization_id,
        location_id=issuance.location_id,
        billing_document_id=issuance.billing_document_id,
        operation_reference=(
            f'fiscal-issuance-v1:{issuance.tenant_id}:'
            f'{issuance.billing_document_id}'
        ),
        provider_idempotency_key=issuance.provider_idempotency_key,
        request_fingerprint=issuance.request_fingerprint,
        request_schema_version=issuance.request_schema_version,
        external_reference=issuance.external_reference,
        external_status=issuance.external_status,
    )


async def _retry_request(
    db: AsyncSession,
    *,
    issuance: BillingIssuance,
) -> FiscalIssuanceRequest:
    command = InitiateFiscalIssuanceCommand(
        organization_id=issuance.organization_id,
        location_id=issuance.location_id,
        billing_document_id=issuance.billing_document_id,
        provider_key=issuance.provider_key,
        credential_binding=issuance.credential_binding,
        idempotency_key=issuance.idempotency_key,
    )
    _, request = await _canonical_request(
        db,
        tenant_id=issuance.tenant_id,
        command=command,
        lock_document=False,
    )
    if (
        request.request_fingerprint != issuance.request_fingerprint
        or request.provider_idempotency_key != issuance.provider_idempotency_key
        or request.request_schema_version != issuance.request_schema_version
    ):
        raise errors.FiscalProviderBindingMismatchError(
            'Durable fiscal issuance evidence no longer matches its provider binding'
        )
    return request


def _complete_stale_attempt(
    issuance: BillingIssuance,
    attempt: BillingIssuanceAttempt,
    *,
    now: datetime,
) -> None:
    attempt.completed_at = now
    attempt.result = 'UNCERTAIN'
    attempt.external_reference = issuance.external_reference
    attempt.external_status = 'CLAIM_EXPIRED'
    attempt.error_kind = FiscalProviderErrorKind.AMBIGUOUS_RESULT.value
    attempt.error_message = 'Claim expired after provider interaction may have begun'
    attempt.result_fingerprint = _sha({
        'schema_version': 1,
        'result': attempt.result,
        'external_reference': attempt.external_reference,
        'external_status': attempt.external_status,
        'error_kind': attempt.error_kind,
    })
    issuance.state = 'UNCERTAIN'
    issuance.claim_token = None
    issuance.claim_expires_at = None
    issuance.external_status = attempt.external_status
    issuance.last_error_kind = attempt.error_kind
    issuance.last_error_message = attempt.error_message
    issuance.completed_at = None


async def _claim_operation(
    db: AsyncSession,
    *,
    execution: ExecutionContext,
    organization_id: int,
    location_id: int,
    issuance_id: int,
    attempt_type: str,
) -> tuple[BillingIssuance, str | None]:
    try:
        issuance = await db.scalar(
            select(BillingIssuance)
            .where(
                BillingIssuance.id == issuance_id,
                BillingIssuance.tenant_id == execution.tenant_id,
                BillingIssuance.organization_id == organization_id,
                BillingIssuance.location_id == location_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if issuance is None:
            raise errors.FiscalIssuanceStateConflictError(
                'Fiscal issuance does not exist in the requested scope'
            )

        now = _now()
        latest = await db.scalar(
            select(BillingIssuanceAttempt)
            .where(BillingIssuanceAttempt.billing_issuance_id == issuance.id)
            .order_by(BillingIssuanceAttempt.attempt_sequence.desc())
            .limit(1)
            .with_for_update()
        )
        if issuance.attempt_count != (latest.attempt_sequence if latest else 0):
            raise errors.FiscalIssuanceStateConflictError(
                'Fiscal issuance attempt sequence evidence is inconsistent'
            )

        if issuance.state == 'IN_PROGRESS':
            if (
                issuance.claim_expires_at is not None
                and issuance.claim_expires_at > now
            ):
                raise errors.FiscalIssuanceConcurrencyConflictError(
                    'Fiscal issuance has an active provider-interaction claim'
                )
            if (
                latest is None
                or latest.claim_token != issuance.claim_token
                or latest.result is not None
            ):
                raise errors.FiscalIssuanceStateConflictError(
                    'Expired fiscal issuance claim has inconsistent attempt evidence'
                )
            _complete_stale_attempt(issuance, latest, now=now)

        if attempt_type == 'RECOVER':
            if issuance.state == 'SUCCEEDED':
                await db.commit()
                return issuance, None
            if issuance.state != 'UNCERTAIN':
                raise errors.FiscalIssuanceRecoveryNotAllowedError(
                    f'Recovery is not allowed from fiscal issuance state {issuance.state}'
                )
        elif attempt_type == 'RETRY':
            safe_recovery = (
                latest is not None
                and latest.attempt_type == 'RECOVER'
                and latest.result is not None
                and latest.external_status == FiscalRecoveryOutcome.DEFINITE_ABSENCE.value
            )
            definite_retryable_failure = (
                issuance.state == 'FAILED'
                and issuance.last_error_kind
                != FiscalProviderErrorKind.BUSINESS_REJECTION.value
            )
            if not (safe_recovery or definite_retryable_failure):
                raise errors.FiscalIssuanceRetryNotAllowedError(
                    f'Retry is not allowed from fiscal issuance state {issuance.state}'
                )
        else:
            raise errors.FiscalIssuanceStateConflictError(
                'Unsupported fiscal issuance attempt type'
            )

        token = str(uuid4())
        sequence = issuance.attempt_count + 1
        issuance.state = 'IN_PROGRESS'
        issuance.claim_token = token
        issuance.claim_expires_at = now + CLAIM_LEASE
        issuance.attempt_count = sequence
        issuance.last_error_kind = None
        issuance.last_error_message = None
        issuance.completed_at = None
        db.add(BillingIssuanceAttempt(
            tenant_id=issuance.tenant_id,
            organization_id=issuance.organization_id,
            location_id=issuance.location_id,
            billing_issuance_id=issuance.id,
            attempt_sequence=sequence,
            attempt_type=attempt_type,
            claim_token=token,
            started_at=now,
            completed_at=None,
            result=None,
            actor_type=execution.actor_type.value,
            actor_id=execution.principal_id,
            actor_reference=execution.principal_reference,
            correlation_id=execution.correlation_id,
        ))
        await db.commit()
        return issuance, token
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise


def _safe_recovery_values(
    result: FiscalRecoveryResult,
) -> tuple[str, str | None, str | None]:
    state = {
        FiscalRecoveryOutcome.RECOVERED_SUCCESS: 'SUCCEEDED',
        FiscalRecoveryOutcome.DEFINITE_ABSENCE: 'FAILED',
        FiscalRecoveryOutcome.DEFINITE_FAILURE: 'FAILED',
        FiscalRecoveryOutcome.REJECTED: 'REJECTED',
        FiscalRecoveryOutcome.STILL_UNCERTAIN: 'UNCERTAIN',
    }[result.outcome]
    error_kind = None if result.error_kind is None else result.error_kind.value
    error_message = {
        FiscalRecoveryOutcome.RECOVERED_SUCCESS: None,
        FiscalRecoveryOutcome.DEFINITE_ABSENCE:
            'Fiscal recovery proved definite absence; explicit retry is authorized',
        FiscalRecoveryOutcome.DEFINITE_FAILURE:
            'Fiscal provider reported a definite recovery failure',
        FiscalRecoveryOutcome.REJECTED:
            'Fiscal provider reported a definite rejection during recovery',
        FiscalRecoveryOutcome.STILL_UNCERTAIN:
            'Fiscal recovery remains inconclusive',
    }[result.outcome]
    return state, error_kind, error_message


def _translate_operational(exc: OperationalError) -> None:
    code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
    if code in (1205, 1213):
        raise errors.FiscalIssuanceConcurrencyConflictError(
            'Concurrent fiscal issuance operation lost serialization'
        ) from exc
    raise exc


async def initiate_fiscal_issuance(
    db: AsyncSession,
    *,
    execution: ExecutionContext,
    command: InitiateFiscalIssuanceCommand,
    provider_registry: FiscalProviderRegistry,
    credential_resolver: FiscalProviderCredentialResolver | None = None,
) -> tuple[BillingIssuanceProjection, bool]:
    """Reserve, commit, and execute exactly one initial fiscal ISSUE attempt."""

    _validate_command(command)
    issuance, request, replay = await _reserve(
        db,
        execution=execution,
        command=command,
    )
    issuance, token = await _claim_initial(
        db,
        issuance_id=issuance.id,
        execution=execution,
    )
    if token is None:
        return await _projection(db, issuance), True

    try:
        provider = provider_registry.resolve(issuance.provider_key)
        if not isinstance(provider, FiscalIssuancePort):
            raise integration_errors.FiscalProviderNotRegisteredError(
                'Bound fiscal provider does not implement issuance'
            )
    except integration_errors.FiscalProviderRegistryError:
        await _fail_resolution(
            db,
            issuance=issuance,
            token=token,
            error_kind='PROVIDER_UNAVAILABLE',
            error_message='Bound fiscal provider is unavailable',
        )
        raise errors.FiscalProviderUnavailableError() from None

    try:
        credential = await _credential(
            issuance=issuance,
            resolver=credential_resolver,
        )
    except errors.FiscalCredentialResolutionError:
        await _fail_resolution(
            db,
            issuance=issuance,
            token=token,
            error_kind='CREDENTIAL_RESOLUTION_FAILED',
            error_message='Fiscal provider credential could not be resolved',
        )
        raise

    try:
        result = await provider.issue(request=request, credential=credential)
        if not isinstance(result, FiscalIssuanceResult):
            raise TypeError('Invalid fiscal provider result')
    except Exception:
        result = FiscalIssuanceResult(
            outcome=FiscalIssuanceOutcome.UNCERTAIN,
            error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
            error_message='Fiscal provider result is uncertain',
        )

    state, error_kind, error_message = _safe_result_values(result)
    issuance = await _finish(
        db,
        tenant_id=issuance.tenant_id,
        issuance_id=issuance.id,
        token=token,
        state=state,
        external_reference=result.external_reference,
        external_status=result.external_status,
        error_kind=error_kind,
        error_message=error_message,
    )
    return await _projection(db, issuance), replay


async def recover_fiscal_issuance(
    db: AsyncSession,
    *,
    execution: ExecutionContext,
    command: RecoverFiscalIssuanceCommand,
    provider_registry: FiscalProviderRegistry,
    credential_resolver: FiscalProviderCredentialResolver | None = None,
) -> BillingIssuanceProjection:
    """Recover one uncertain issuance without ever invoking issue()."""

    _validate_existing_command(command)
    issuance, token = await _claim_operation(
        db,
        execution=execution,
        organization_id=command.organization_id,
        location_id=command.location_id,
        issuance_id=command.billing_issuance_id,
        attempt_type='RECOVER',
    )
    if token is None:
        return await _projection(db, issuance)

    request = _recovery_request(issuance)
    try:
        provider = provider_registry.resolve(issuance.provider_key)
        if not isinstance(provider, FiscalIssuancePort):
            raise integration_errors.FiscalProviderNotRegisteredError(
                'Bound fiscal provider does not implement recovery'
            )
    except integration_errors.FiscalProviderRegistryError:
        await _finish(
            db,
            tenant_id=issuance.tenant_id,
            issuance_id=issuance.id,
            token=token,
            state='UNCERTAIN',
            external_reference=issuance.external_reference,
            external_status='PROVIDER_UNAVAILABLE',
            error_kind='PROVIDER_UNAVAILABLE',
            error_message='Bound fiscal provider is unavailable for recovery',
        )
        raise errors.FiscalProviderUnavailableError() from None

    try:
        credential = await _credential(
            issuance=issuance,
            resolver=credential_resolver,
        )
    except errors.FiscalCredentialResolutionError:
        await _finish(
            db,
            tenant_id=issuance.tenant_id,
            issuance_id=issuance.id,
            token=token,
            state='UNCERTAIN',
            external_reference=issuance.external_reference,
            external_status='CREDENTIAL_RESOLUTION_FAILED',
            error_kind='CREDENTIAL_RESOLUTION_FAILED',
            error_message='Fiscal provider credential could not be resolved',
        )
        raise

    try:
        result = await provider.recover(request=request, credential=credential)
        if not isinstance(result, FiscalRecoveryResult):
            raise TypeError('Invalid fiscal provider recovery result')
    except Exception:
        result = FiscalRecoveryResult(
            outcome=FiscalRecoveryOutcome.STILL_UNCERTAIN,
            error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
            error_message='Fiscal recovery remains inconclusive',
        )

    state, error_kind, error_message = _safe_recovery_values(result)
    issuance = await _finish(
        db,
        tenant_id=issuance.tenant_id,
        issuance_id=issuance.id,
        token=token,
        state=state,
        external_reference=result.external_reference,
        external_status=(
            result.outcome.value
            if result.outcome is FiscalRecoveryOutcome.DEFINITE_ABSENCE
            else result.external_status or result.outcome.value
        ),
        error_kind=error_kind,
        error_message=error_message,
    )
    return await _projection(db, issuance)


async def retry_fiscal_issuance(
    db: AsyncSession,
    *,
    execution: ExecutionContext,
    command: RetryFiscalIssuanceCommand,
    provider_registry: FiscalProviderRegistry,
    credential_resolver: FiscalProviderCredentialResolver | None = None,
) -> BillingIssuanceProjection:
    """Explicitly retry the original provider operation when durable evidence is safe."""

    _validate_existing_command(command)
    issuance, token = await _claim_operation(
        db,
        execution=execution,
        organization_id=command.organization_id,
        location_id=command.location_id,
        issuance_id=command.billing_issuance_id,
        attempt_type='RETRY',
    )
    assert token is not None
    issuance_tenant_id = issuance.tenant_id
    issuance_id = issuance.id
    prior_external_reference = issuance.external_reference

    try:
        request = await _retry_request(db, issuance=issuance)
        await db.commit()
    except Exception:
        await db.rollback()
        await _finish(
            db,
            tenant_id=issuance_tenant_id,
            issuance_id=issuance_id,
            token=token,
            state='FAILED',
            external_reference=prior_external_reference,
            external_status='PROVIDER_BINDING_MISMATCH',
            error_kind='PROVIDER_BINDING_MISMATCH',
            error_message='Durable fiscal issuance evidence failed binding validation',
        )
        raise

    try:
        provider = provider_registry.resolve(issuance.provider_key)
        if not isinstance(provider, FiscalIssuancePort):
            raise integration_errors.FiscalProviderNotRegisteredError(
                'Bound fiscal provider does not implement issuance'
            )
    except integration_errors.FiscalProviderRegistryError:
        await _finish(
            db,
            tenant_id=issuance.tenant_id,
            issuance_id=issuance.id,
            token=token,
            state='FAILED',
            external_reference=issuance.external_reference,
            external_status='PROVIDER_UNAVAILABLE',
            error_kind='PROVIDER_UNAVAILABLE',
            error_message='Bound fiscal provider is unavailable',
        )
        raise errors.FiscalProviderUnavailableError() from None

    try:
        credential = await _credential(
            issuance=issuance,
            resolver=credential_resolver,
        )
    except errors.FiscalCredentialResolutionError:
        await _finish(
            db,
            tenant_id=issuance.tenant_id,
            issuance_id=issuance.id,
            token=token,
            state='FAILED',
            external_reference=issuance.external_reference,
            external_status='CREDENTIAL_RESOLUTION_FAILED',
            error_kind='CREDENTIAL_RESOLUTION_FAILED',
            error_message='Fiscal provider credential could not be resolved',
        )
        raise

    try:
        result = await provider.issue(request=request, credential=credential)
        if not isinstance(result, FiscalIssuanceResult):
            raise TypeError('Invalid fiscal provider result')
    except Exception:
        result = FiscalIssuanceResult(
            outcome=FiscalIssuanceOutcome.UNCERTAIN,
            error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
            error_message='Fiscal provider result is uncertain',
        )

    state, error_kind, error_message = _safe_result_values(result)
    issuance = await _finish(
        db,
        tenant_id=issuance.tenant_id,
        issuance_id=issuance.id,
        token=token,
        state=state,
        external_reference=result.external_reference,
        external_status=result.external_status,
        error_kind=error_kind,
        error_message=error_message,
    )
    return await _projection(db, issuance)
