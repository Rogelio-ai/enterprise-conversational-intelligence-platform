from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from decimal import ROUND_HALF_DOWN, Decimal, localcontext

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Promotion
from app.restaurant.commercial.contracts import (
    AppliedPromotion,
    CheckoutPreview,
    CheckoutPreviewLine,
    CommercialResolutionStatus,
    TaxMode,
)
from app.restaurant.commercial.errors import (
    CurrencyConflictError,
    DraftNotCommerciallyReadyError,
    PriceUnavailableError,
    UnsupportedPromotionSemanticsError,
)
from app.restaurant.orders import service as order_draft_service
from app.restaurant.orders.contracts import DraftReadiness
from app.restaurant.pricing import service as pricing_service


logger = logging.getLogger('ecip.commercial')
_WHOLE_UNIT = Decimal('1')
_DISPLAY_SCALE = Decimal('0.01')


def round_payable_total(value: Decimal) -> Decimal:
    """Apply the Restaurant whole-unit HALF_DOWN policy once."""
    if isinstance(value, float) or not isinstance(value, Decimal):
        raise TypeError('Commercial rounding requires an exact Decimal')
    if not value.is_finite() or value < 0:
        raise ValueError('Commercial total must be finite and non-negative')
    return value.quantize(_WHOLE_UNIT, rounding=ROUND_HALF_DOWN).quantize(_DISPLAY_SCALE)


def _selected_promotions(candidates: tuple[Promotion, ...]) -> tuple[Promotion, ...]:
    ordered = tuple(sorted(candidates, key=lambda value: (value.priority, value.id)))
    if not ordered:
        return ()
    if not ordered[0].is_combinable:
        return (ordered[0],)
    return tuple(value for value in ordered if value.is_combinable)


def _apply_promotions(
    *, candidates: tuple[Promotion, ...], base_amount: Decimal, currency: str
) -> tuple[tuple[AppliedPromotion, ...], Decimal, Decimal]:
    remaining = base_amount
    applied: list[AppliedPromotion] = []
    for promotion in _selected_promotions(candidates):
        if promotion.promotion_type == 'PERCENTAGE_DISCOUNT':
            discount = remaining * promotion.benefit_value / Decimal('100')
        elif promotion.promotion_type == 'FIXED_AMOUNT_DISCOUNT':
            if promotion.currency != currency:
                raise CurrencyConflictError(
                    f'Promotion {promotion.id} currency does not match Product Price currency'
                )
            discount = promotion.benefit_value
        else:
            raise UnsupportedPromotionSemanticsError(
                f'Promotion {promotion.id} uses unsupported calculation semantics'
            )
        actual_discount = min(discount, remaining)
        remaining -= actual_discount
        applied.append(
            AppliedPromotion(
                promotion_id=promotion.id,
                name=promotion.name,
                promotion_type=promotion.promotion_type,
                promotion_value=promotion.benefit_value,
                currency=promotion.currency,
                priority=promotion.priority,
                is_combinable=promotion.is_combinable,
                calculated_discount=actual_discount,
            )
        )
    return tuple(applied), base_amount - remaining, remaining


def _decimal(value: Decimal) -> str:
    return format(value, 'f')


def _fingerprint(preview_values: dict[str, object]) -> str:
    encoded = json.dumps(
        preview_values, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


async def resolve_checkout_preview(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    correlation_id: str | None = None,
) -> CheckoutPreview:
    draft = await order_draft_service.get_draft(
        db,
        tenant_id=tenant_id,
        draft_id=draft_id,
        correlation_id=correlation_id,
    )
    if draft.readiness is not DraftReadiness.READY:
        raise DraftNotCommerciallyReadyError(
            f'Order Draft is {draft.readiness.value}, not READY'
        )

    resolved_at = datetime.now(UTC)
    effective_at = resolved_at.replace(tzinfo=None)
    lines: list[CheckoutPreviewLine] = []
    fingerprint_lines: list[dict[str, object]] = []
    currencies: set[str] = set()

    with localcontext() as context:
        context.prec = 50
        for item in draft.items:
            try:
                price = await pricing_service.get_canonical_current_price(
                    db,
                    tenant_id=draft.tenant_id,
                    product_id=item.product_id,
                    location_id=draft.location_id,
                )
            except pricing_service.PricingReadContextError as exc:
                raise PriceUnavailableError(str(exc)) from exc
            if price is None:
                raise PriceUnavailableError(
                    f'Current Product Price is unavailable for Product {item.product_id}'
                )
            currencies.add(price.currency)
            if len(currencies) > 1:
                raise CurrencyConflictError('Checkout Preview contains incompatible currencies')

            candidates = await pricing_service.find_canonical_applicable_promotions(
                db,
                tenant_id=draft.tenant_id,
                product_id=item.product_id,
                location_id=draft.location_id,
                effective_at=effective_at,
            )
            base_amount = price.amount * item.quantity
            promotions, discount, commercial_amount = _apply_promotions(
                candidates=candidates,
                base_amount=base_amount,
                currency=price.currency,
            )
            line = CheckoutPreviewLine(
                draft_item_id=item.item_id,
                product_id=item.product_id,
                product_name=item.product_name,
                composition_id=item.composition_id,
                quantity=item.quantity,
                price_id=price.id,
                price_source=price.source,
                unit_price=price.amount,
                base_amount=base_amount,
                applied_promotions=promotions,
                discount_amount=discount,
                commercial_amount=commercial_amount,
            )
            lines.append(line)
            fingerprint_lines.append(
                {
                    'draft_item_id': item.item_id,
                    'product_id': item.product_id,
                    'composition_id': item.composition_id,
                    'quantity': _decimal(item.quantity),
                    'choice_option_ids': [value.choice_option_id for value in item.selections],
                    'price_id': price.id,
                    'price_source': price.source,
                    'unit_price': _decimal(price.amount),
                    'base_amount': _decimal(base_amount),
                    'promotions': [
                        {
                            'id': value.promotion_id,
                            'type': value.promotion_type,
                            'value': _decimal(value.promotion_value),
                            'currency': value.currency,
                            'priority': value.priority,
                            'is_combinable': value.is_combinable,
                            'discount': _decimal(value.calculated_discount),
                        }
                        for value in promotions
                    ],
                    'commercial_amount': _decimal(commercial_amount),
                }
            )

        subtotal = sum((line.base_amount for line in lines), start=Decimal('0'))
        total_discount = sum(
            (line.discount_amount for line in lines), start=Decimal('0')
        )
        pre_round_total = subtotal - total_discount
        payable_total = round_payable_total(pre_round_total)
        rounding_adjustment = payable_total - pre_round_total

    currency = next(iter(currencies))
    fingerprint_values: dict[str, object] = {
        'draft_id': draft.draft_id,
        'draft_version': draft.version,
        'tenant_id': draft.tenant_id,
        'organization_id': draft.organization_id,
        'location_id': draft.location_id,
        'currency': currency,
        'tax_mode': TaxMode.INCLUDED.value,
        'lines': fingerprint_lines,
        'subtotal': _decimal(subtotal),
        'total_discount': _decimal(total_discount),
        'pre_round_total': _decimal(pre_round_total),
        'rounding_adjustment': _decimal(rounding_adjustment),
        'payable_total': _decimal(payable_total),
    }
    preview = CheckoutPreview(
        status=CommercialResolutionStatus.COMPLETE,
        draft_id=draft.draft_id,
        draft_version=draft.version,
        tenant_id=draft.tenant_id,
        organization_id=draft.organization_id,
        location_id=draft.location_id,
        resolved_at=resolved_at,
        currency=currency,
        tax_mode=TaxMode.INCLUDED,
        lines=tuple(lines),
        subtotal=subtotal,
        total_discount=total_discount,
        pre_round_total=pre_round_total,
        rounding_adjustment=rounding_adjustment,
        payable_total=payable_total,
        commercial_fingerprint=_fingerprint(fingerprint_values),
    )
    logger.info(
        'Checkout Preview resolved',
        extra={
            'event': 'checkout_preview_resolved',
            'operation': 'resolve_checkout_preview',
            'tenant_id': preview.tenant_id,
            'organization_id': preview.organization_id,
            'location_id': preview.location_id,
            'draft_id': preview.draft_id,
            'draft_version': preview.draft_version,
            'currency': preview.currency,
            'commercial_status': preview.status.value,
            'correlation_id': correlation_id,
        },
    )
    return preview
