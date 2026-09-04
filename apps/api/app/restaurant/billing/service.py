from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ExecutionContext
from app.models import (
    BillingDocument,
    BillingDocumentLine,
    BillingDocumentLineTax,
    CustomerFiscalProfile,
    IssuerFiscalProfile,
    RestaurantCheck,
    RestaurantCheckAllocation,
    RestaurantCheckVersion,
    RestaurantOrder,
    RestaurantOrderItem,
)
from app.restaurant.billing import errors
from app.restaurant.billing.contracts import (
    BillingDocumentDetailProjection,
    BillingDocumentLineProjection,
    BillingDocumentLineTaxProjection,
    BillingDocumentProjection,
    CreateBillingDocumentCommand,
)
from app.restaurant.payments import service as payment_service


ZERO = Decimal('0.0000')
REQUEST_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class _CommercialLineEvidence:
    source_restaurant_order_id: int
    source_restaurant_order_item_id: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    base_amount: Decimal
    discount_amount: Decimal
    commercial_total: Decimal


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    ).hexdigest()


def _actor_scope(context: ExecutionContext) -> str:
    identity = (
        str(context.principal_id)
        if context.principal_id is not None
        else context.principal_reference
    )
    return f'{context.actor_type.value}:{identity}'


def _request_fingerprint(command: CreateBillingDocumentCommand) -> str:
    return _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'document_type': 'INVOICE',
        'restaurant_check_id': command.restaurant_check_id,
        'organization_id': command.organization_id,
        'location_id': command.location_id,
        'issuer_fiscal_profile_id': command.issuer_fiscal_profile_id,
        'recipient_fiscal_profile_id': command.recipient_fiscal_profile_id,
        'scope': 'WHOLE_CHECK',
    })


def _validate_command(command: CreateBillingDocumentCommand) -> None:
    identifiers = (
        command.restaurant_check_id,
        command.organization_id,
        command.location_id,
        command.issuer_fiscal_profile_id,
        command.recipient_fiscal_profile_id,
    )
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in identifiers):
        raise errors.BillingRequestInvalidError('Billing identifiers must be positive integers')
    if (
        not command.idempotency_key
        or command.idempotency_key != command.idempotency_key.strip()
        or len(command.idempotency_key) > 128
        or not command.idempotency_key.isascii()
    ):
        raise errors.BillingRequestInvalidError('Billing idempotency key is invalid')


def _document_projection(document: BillingDocument) -> BillingDocumentProjection:
    return BillingDocumentProjection(
        id=document.id,
        tenant_id=document.tenant_id,
        organization_id=document.organization_id,
        location_id=document.location_id,
        restaurant_check_id=document.restaurant_check_id,
        source_check_version=document.source_check_version,
        source_check_fingerprint=document.source_check_fingerprint,
        document_type=document.document_type,
        status=document.status,
        currency=document.currency,
        subtotal=Decimal(document.subtotal),
        discount_total=Decimal(document.discount_total),
        tax_total=Decimal(document.tax_total),
        total=Decimal(document.total),
        issuer_snapshot=dict(document.issuer_snapshot),
        recipient_snapshot=dict(document.recipient_snapshot),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


async def get_billing_document(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int,
    document_id: int,
) -> BillingDocumentDetailProjection:
    document = await db.scalar(select(BillingDocument).where(
        BillingDocument.id == document_id,
        BillingDocument.tenant_id == tenant_id,
        BillingDocument.organization_id == organization_id,
        BillingDocument.location_id == location_id,
    ))
    if document is None:
        raise errors.BillingDocumentNotFoundError()

    lines = tuple((await db.execute(select(BillingDocumentLine).where(
        BillingDocumentLine.billing_document_id == document.id,
    ).order_by(BillingDocumentLine.id))).scalars().all())
    line_ids = tuple(line.id for line in lines)
    taxes = tuple((await db.execute(select(BillingDocumentLineTax).where(
        BillingDocumentLineTax.billing_document_line_id.in_(line_ids or (-1,)),
    ).order_by(
        BillingDocumentLineTax.billing_document_line_id,
        BillingDocumentLineTax.id,
    ))).scalars().all())
    taxes_by_line: dict[int, list[BillingDocumentLineTaxProjection]] = {
        line_id: [] for line_id in line_ids
    }
    for tax in taxes:
        taxes_by_line[tax.billing_document_line_id].append(
            BillingDocumentLineTaxProjection(
                id=tax.id,
                tax_category=tax.tax_category,
                tax_rate=Decimal(tax.tax_rate),
                taxable_base=Decimal(tax.taxable_base),
                tax_amount=Decimal(tax.tax_amount),
                tax_treatment=tax.tax_treatment,
                created_at=tax.created_at,
            )
        )
    return BillingDocumentDetailProjection(
        **asdict(_document_projection(document)),
        lines=tuple(BillingDocumentLineProjection(
            id=line.id,
            source_restaurant_order_id=line.source_restaurant_order_id,
            source_restaurant_order_item_id=line.source_restaurant_order_item_id,
            description=line.description,
            quantity=Decimal(line.quantity),
            unit_price=Decimal(line.unit_price),
            base_amount=Decimal(line.base_amount),
            discount_amount=Decimal(line.discount_amount),
            commercial_total=Decimal(line.commercial_total),
            created_at=line.created_at,
            taxes=tuple(taxes_by_line[line.id]),
        ) for line in lines),
    )


async def _document_by_key(
    db: AsyncSession,
    *,
    context: ExecutionContext,
    idempotency_key: str,
    lock: bool = False,
) -> BillingDocument | None:
    query = select(BillingDocument).where(
        BillingDocument.tenant_id == context.tenant_id,
        BillingDocument.actor_scope == _actor_scope(context),
        BillingDocument.idempotency_key == idempotency_key,
    )
    if lock:
        query = query.with_for_update()
    return await db.scalar(query)


def _assert_replay(
    document: BillingDocument,
    *,
    request_fingerprint: str,
) -> BillingDocumentProjection:
    if document.request_fingerprint != request_fingerprint:
        raise errors.BillingIdempotencyConflictError()
    return _document_projection(document)


def _issuer_snapshot(profile: IssuerFiscalProfile) -> dict[str, str]:
    return {
        'legal_name': profile.legal_name.strip(),
        'tax_identifier': profile.tax_identifier.strip(),
        'tax_regime': profile.tax_regime.strip(),
        'fiscal_postal_code': profile.fiscal_postal_code.strip(),
    }


def _recipient_snapshot(profile: CustomerFiscalProfile) -> dict[str, str]:
    return {
        'legal_name': profile.legal_name.strip(),
        'tax_identifier': profile.tax_identifier.strip(),
        'tax_regime': profile.tax_regime.strip(),
        'fiscal_postal_code': profile.fiscal_postal_code.strip(),
        'invoice_usage': profile.invoice_usage.strip(),
    }


def _profile_has_values(snapshot: dict[str, str]) -> bool:
    return all(snapshot.values())


def _translate_operational(exc: OperationalError) -> None:
    code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
    if code in (1205, 1213):
        raise errors.BillingConcurrencyConflictError(
            'Concurrent billing operation lost serialization'
        ) from exc
    raise exc


async def _settlement_is_final(db: AsyncSession, check: RestaurantCheck) -> None:
    confirmed, reserved, uncertain = await payment_service._totals(
        db, check_id=check.id, lock=True
    )
    if (
        confirmed != Decimal(check.liability_total)
        or reserved != ZERO
        or uncertain != ZERO
    ):
        raise errors.BillingSourceNotEligibleError(
            'Restaurant Check does not have final, exposure-free settlement truth'
        )


async def _current_check_version(
    db: AsyncSession,
    check: RestaurantCheck,
) -> RestaurantCheckVersion:
    version = await db.scalar(
        select(RestaurantCheckVersion).where(
            RestaurantCheckVersion.tenant_id == check.tenant_id,
            RestaurantCheckVersion.organization_id == check.organization_id,
            RestaurantCheckVersion.location_id == check.location_id,
            RestaurantCheckVersion.check_id == check.id,
            RestaurantCheckVersion.version == check.version,
            RestaurantCheckVersion.fingerprint == check.current_fingerprint,
        ).with_for_update()
    )
    if version is None:
        raise errors.BillingSourceNotEligibleError(
            'Final Restaurant Check version evidence is unavailable'
        )
    if (
        version.currency != check.currency
        or Decimal(version.liability_total) != Decimal(check.liability_total)
    ):
        raise errors.BillingSourceNotEligibleError(
            'Final Restaurant Check version contradicts current settlement identity'
        )
    return version


async def _active_issuer(
    db: AsyncSession,
    *,
    check: RestaurantCheck,
    profile_id: int,
) -> IssuerFiscalProfile:
    profile = await db.scalar(
        select(IssuerFiscalProfile).where(
            IssuerFiscalProfile.id == profile_id,
            IssuerFiscalProfile.tenant_id == check.tenant_id,
            IssuerFiscalProfile.organization_id == check.organization_id,
            IssuerFiscalProfile.status == 'ACTIVE',
        ).with_for_update()
    )
    if profile is None or not _profile_has_values(_issuer_snapshot(profile)):
        raise errors.BillingIssuerProfileMissingError()
    return profile


async def _active_recipient(
    db: AsyncSession,
    *,
    check: RestaurantCheck,
    profile_id: int,
) -> CustomerFiscalProfile:
    profile = await db.scalar(
        select(CustomerFiscalProfile).where(
            CustomerFiscalProfile.id == profile_id,
            CustomerFiscalProfile.tenant_id == check.tenant_id,
            CustomerFiscalProfile.status == 'ACTIVE',
        ).with_for_update()
    )
    if profile is None or not _profile_has_values(_recipient_snapshot(profile)):
        raise errors.BillingRecipientInvalidError()
    return profile


async def _commercial_evidence(
    db: AsyncSession,
    *,
    check: RestaurantCheck,
) -> tuple[_CommercialLineEvidence, ...]:
    allocations = tuple((await db.execute(
        select(RestaurantCheckAllocation).where(
            RestaurantCheckAllocation.tenant_id == check.tenant_id,
            RestaurantCheckAllocation.organization_id == check.organization_id,
            RestaurantCheckAllocation.location_id == check.location_id,
            RestaurantCheckAllocation.check_id == check.id,
            RestaurantCheckAllocation.ownership_slot == 1,
        ).order_by(
            RestaurantCheckAllocation.restaurant_order_id,
            RestaurantCheckAllocation.id,
        ).with_for_update()
    )).scalars().all())
    if not allocations or any(allocation.state != 'SETTLED' for allocation in allocations):
        raise errors.BillingSourceNotEligibleError(
            'Settled Restaurant Check allocations are unavailable or contradictory'
        )

    order_ids = tuple(allocation.restaurant_order_id for allocation in allocations)
    orders = tuple((await db.execute(
        select(RestaurantOrder).where(
            RestaurantOrder.tenant_id == check.tenant_id,
            RestaurantOrder.organization_id == check.organization_id,
            RestaurantOrder.location_id == check.location_id,
            RestaurantOrder.id.in_(order_ids),
            RestaurantOrder.status == 'ACCEPTED',
        ).order_by(RestaurantOrder.id).with_for_update()
    )).scalars().all())
    orders_by_id = {order.id: order for order in orders}
    if set(orders_by_id) != set(order_ids):
        raise errors.BillingSourceNotEligibleError(
            'An allocated accepted Restaurant Order could not be resolved'
        )
    for allocation in allocations:
        order = orders_by_id[allocation.restaurant_order_id]
        if (
            allocation.accepted_currency != check.currency
            or order.currency != check.currency
            or allocation.accepted_commercial_fingerprint != order.commercial_fingerprint
            or Decimal(allocation.accepted_payable_amount) != Decimal(order.payable_total)
        ):
            raise errors.BillingSourceNotEligibleError(
                'Allocated Restaurant Order evidence contradicts the settled Check'
            )

    items = tuple((await db.execute(
        select(RestaurantOrderItem).where(
            RestaurantOrderItem.order_id.in_(order_ids),
            RestaurantOrderItem.tenant_id == check.tenant_id,
            RestaurantOrderItem.organization_id == check.organization_id,
        ).order_by(
            RestaurantOrderItem.order_id,
            RestaurantOrderItem.position,
            RestaurantOrderItem.id,
        ).with_for_update()
    )).scalars().all())
    if not items or {item.order_id for item in items} != set(order_ids):
        raise errors.BillingSourceNotEligibleError(
            'Allocated Restaurant Order line evidence is incomplete'
        )
    return tuple(
        _CommercialLineEvidence(
            source_restaurant_order_id=item.order_id,
            source_restaurant_order_item_id=item.id,
            description=item.product_name,
            quantity=Decimal(item.quantity),
            unit_price=Decimal(item.unit_price),
            base_amount=Decimal(item.base_amount),
            discount_amount=Decimal(item.discount_amount),
            commercial_total=Decimal(item.commercial_amount),
        )
        for item in items
    )


def _require_authoritative_tax_evidence(
    lines: tuple[_CommercialLineEvidence, ...],
) -> None:
    if not lines:
        raise errors.BillingSourceNotEligibleError('Billing commercial evidence is empty')
    raise errors.BillingTaxEvidenceUnavailableError(
        'Accepted Restaurant Orders do not contain authoritative line-tax decomposition'
    )


async def create_billing_document(
    db: AsyncSession,
    *,
    context: ExecutionContext,
    command: CreateBillingDocumentCommand,
) -> tuple[BillingDocumentProjection, bool]:
    """Create a whole-check invoice, or reject until authoritative taxes exist."""

    _validate_command(command)
    fingerprint = _request_fingerprint(command)
    existing = await _document_by_key(
        db,
        context=context,
        idempotency_key=command.idempotency_key,
    )
    if existing is not None:
        return _assert_replay(existing, request_fingerprint=fingerprint), True

    try:
        check = await db.scalar(
            select(RestaurantCheck).where(
                RestaurantCheck.id == command.restaurant_check_id,
                RestaurantCheck.tenant_id == context.tenant_id,
                RestaurantCheck.organization_id == command.organization_id,
                RestaurantCheck.location_id == command.location_id,
            ).with_for_update()
        )
        if check is None:
            raise errors.BillingSourceNotEligibleError('Restaurant Check was not found in scope')

        replay = await _document_by_key(
            db,
            context=context,
            idempotency_key=command.idempotency_key,
            lock=True,
        )
        if replay is not None:
            projection = _assert_replay(replay, request_fingerprint=fingerprint)
            await db.commit()
            return projection, True

        if check.status != 'SETTLED':
            raise errors.BillingCheckNotSettledError()

        await _settlement_is_final(db, check)
        await _current_check_version(db, check)
        issuer = await _active_issuer(
            db, check=check, profile_id=command.issuer_fiscal_profile_id
        )
        recipient = await _active_recipient(
            db, check=check, profile_id=command.recipient_fiscal_profile_id
        )
        _issuer_snapshot(issuer)
        _recipient_snapshot(recipient)
        lines = await _commercial_evidence(db, check=check)
        _require_authoritative_tax_evidence(lines)
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise

    raise AssertionError('Authoritative tax evidence gate must terminate billing creation')
