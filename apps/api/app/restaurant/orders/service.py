from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    Location,
    OrderDraft,
    OrderDraftItem,
    OrderDraftItemSelection,
    Organization,
    Product,
    ProductChoiceGroup,
    ProductChoiceOption,
    ProductComposition,
)
from app.restaurant.catalog import resolution, structure
from app.restaurant.orders.contracts import (
    DraftIssue,
    DraftItemProjection,
    DraftProjection,
    DraftReadiness,
    FixedComponentProjection,
    MissingChoiceGroupProjection,
    SelectionProjection,
)
from app.restaurant.orders.errors import (
    DraftConcurrencyConflictError,
    DraftContextError,
    DraftItemNotFoundError,
    DraftNotFoundError,
    DraftNotMutableError,
    InvalidDraftCompositionError,
    InvalidDraftQuantityError,
    InvalidDraftSelectionError,
    ProductNotOrderableError,
)
from app.restaurant.service_sessions import service as diner_authority_service


logger = logging.getLogger('ecip.order_drafts')
MAX_QUANTITY = Decimal('999999999999999.9999')
_INCOMPLETE_CODES = {
    structure.SelectionViolationCode.REQUIRED_GROUP_MISSING,
    structure.SelectionViolationCode.TOO_FEW_SELECTIONS,
}


def validate_quantity(value: object) -> Decimal:
    if isinstance(value, float) or not isinstance(value, Decimal):
        raise InvalidDraftQuantityError('Quantity must be an exact Decimal')
    if not value.is_finite() or value <= 0:
        raise InvalidDraftQuantityError('Quantity must be finite and greater than zero')
    if value.as_tuple().exponent < -4:
        raise InvalidDraftQuantityError('Quantity supports at most four fractional digits')
    if value > MAX_QUANTITY:
        raise InvalidDraftQuantityError('Quantity exceeds DECIMAL(19,4)')
    return value


def _event(name: str, draft: OrderDraft, *, correlation_id: str | None, **values: object) -> None:
    logger.info(
        name.replace('_', ' ').capitalize(),
        extra={
            'event': name,
            'tenant_id': draft.tenant_id,
            'organization_id': draft.organization_id,
            'location_id': draft.location_id,
            'conversation_id': draft.conversation_id,
            'draft_id': draft.id,
            'version': draft.version,
            'correlation_id': correlation_id,
            **values,
        },
    )


async def _conversation(
    db: AsyncSession, *, tenant_id: int, conversation_id: int, lock: bool
) -> Conversation:
    query = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
    )
    if lock:
        query = query.with_for_update()
    conversation = await db.scalar(query)
    if conversation is None:
        raise DraftNotFoundError('Conversation not found')
    return conversation


async def _valid_location(db: AsyncSession, conversation: Conversation) -> Location:
    if conversation.location_id is None:
        raise DraftContextError('Conversation requires a Location before opening a Draft')
    location = await db.scalar(
        select(Location)
        .join(
            Organization,
            (Organization.id == Location.organization_id)
            & (Organization.tenant_id == Location.tenant_id),
        )
        .where(
            Location.id == conversation.location_id,
            Location.tenant_id == conversation.tenant_id,
            Location.organization_id == conversation.organization_id,
            Location.status == 'ACTIVE',
            Organization.status == 'ACTIVE',
        )
    )
    if location is None:
        raise DraftContextError('Conversation Location is not active in its trusted scope')
    return location


async def get_or_create_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    conversation_id: int,
    correlation_id: str | None = None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> DraftProjection:
    try:
        if owner_diner_session_id is not None:
            if owned_conversation_id != conversation_id:
                raise DraftNotFoundError('Conversation not found')
            await diner_authority_service.lock_diner_write_context(
                db,
                tenant_id=tenant_id,
                diner_session_id=owner_diner_session_id,
                conversation_id=conversation_id,
            )
        conversation = await _conversation(
            db, tenant_id=tenant_id, conversation_id=conversation_id, lock=True
        )
        if owner_diner_session_id is not None:
            if owned_conversation_id != conversation.id:
                raise DraftNotFoundError('Conversation not found')
        if conversation.status != 'ACTIVE':
            raise DraftNotMutableError('Conversation is closed')
        await _valid_location(db, conversation)
        draft = await db.scalar(
            select(OrderDraft)
            .where(
                OrderDraft.tenant_id == tenant_id,
                OrderDraft.conversation_id == conversation.id,
                OrderDraft.status == 'OPEN',
                OrderDraft.current_slot == 1,
            )
            .with_for_update()
        )
        created = False
        if draft is None:
            draft = OrderDraft(
                tenant_id=tenant_id,
                organization_id=conversation.organization_id,
                location_id=conversation.location_id,
                conversation_id=conversation.id,
                version=1,
                status='OPEN',
                current_slot=1,
                terminal_at=None,
            )
            db.add(draft)
            await db.flush()
            created = True
        await db.commit()
        await db.refresh(draft)
    except Exception:
        await db.rollback()
        raise
    if created:
        _event('order_draft_created', draft, correlation_id=correlation_id, outcome='created')
    return await evaluate_draft(db, tenant_id=tenant_id, draft_id=draft.id, correlation_id=correlation_id)


async def _draft(db: AsyncSession, *, tenant_id: int, draft_id: int) -> OrderDraft:
    draft = await db.scalar(
        select(OrderDraft).where(OrderDraft.id == draft_id, OrderDraft.tenant_id == tenant_id)
    )
    if draft is None:
        raise DraftNotFoundError('Order Draft not found')
    return draft


async def _locked_mutable_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    expected_version: int,
    correlation_id: str | None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> OrderDraft:
    conversation_id = await db.scalar(
        select(OrderDraft.conversation_id).where(
            OrderDraft.id == draft_id, OrderDraft.tenant_id == tenant_id
        )
    )
    if conversation_id is None:
        raise DraftNotFoundError('Order Draft not found')
    if owner_diner_session_id is not None:
        if owned_conversation_id != conversation_id:
            raise DraftNotFoundError('Order Draft not found')
        await diner_authority_service.lock_diner_write_context(
            db,
            tenant_id=tenant_id,
            diner_session_id=owner_diner_session_id,
            conversation_id=conversation_id,
        )
    conversation = await _conversation(
        db,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        lock=True,
    )
    draft = await db.scalar(
        select(OrderDraft)
        .where(OrderDraft.id == draft_id, OrderDraft.tenant_id == tenant_id)
        .with_for_update()
    )
    if draft is None:
        raise DraftNotFoundError('Order Draft not found')
    if (
        conversation.organization_id != draft.organization_id
        or conversation.location_id != draft.location_id
    ):
        raise DraftContextError('Draft no longer matches its Conversation scope')
    if conversation.status != 'ACTIVE':
        raise DraftNotMutableError('Conversation is closed')
    if draft.status != 'OPEN' or draft.current_slot != 1 or draft.terminal_at is not None:
        raise DraftNotMutableError('Order Draft is terminal and cannot be mutated')
    if draft.version != expected_version:
        _event(
            'order_draft_concurrency_conflict',
            draft,
            correlation_id=correlation_id,
            expected_version=expected_version,
            outcome='rejected',
        )
        raise DraftConcurrencyConflictError(
            f'Expected Draft version {expected_version}, current version is {draft.version}'
        )
    return draft


async def get_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    correlation_id: str | None = None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> DraftProjection:
    draft = await _draft(db, tenant_id=tenant_id, draft_id=draft_id)
    if owner_diner_session_id is not None:
        if owned_conversation_id != draft.conversation_id:
            raise DraftNotFoundError('Order Draft not found')
        await diner_authority_service.validate_diner_authority(
            db,
            tenant_id=tenant_id,
            diner_session_id=owner_diner_session_id,
            conversation_id=draft.conversation_id,
        )
    return await evaluate_draft(
        db, tenant_id=tenant_id, draft_id=draft_id, correlation_id=correlation_id
    )


async def get_draft_for_conversation(
    db: AsyncSession,
    *,
    tenant_id: int,
    conversation_id: int,
    correlation_id: str | None = None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> DraftProjection:
    if owner_diner_session_id is not None:
        if owned_conversation_id != conversation_id:
            raise DraftNotFoundError('Order Draft not found')
        await diner_authority_service.validate_diner_authority(
            db,
            tenant_id=tenant_id,
            diner_session_id=owner_diner_session_id,
            conversation_id=conversation_id,
        )
    draft = await db.scalar(
        select(OrderDraft).where(
            OrderDraft.tenant_id == tenant_id,
            OrderDraft.conversation_id == conversation_id,
            OrderDraft.status == 'OPEN',
            OrderDraft.current_slot == 1,
        )
    )
    if draft is None:
        raise DraftNotFoundError('Order Draft not found')
    return await evaluate_draft(
        db, tenant_id=tenant_id, draft_id=draft.id, correlation_id=correlation_id
    )


async def _selection_projection(
    db: AsyncSession, item: OrderDraftItem
) -> tuple[tuple[SelectionProjection, ...], dict[int, tuple[int, ...]]]:
    rows = (
        await db.execute(
            select(
                OrderDraftItemSelection,
                ProductChoiceGroup,
                ProductChoiceOption,
                Product,
            )
            .join(
                ProductChoiceGroup,
                (ProductChoiceGroup.id == OrderDraftItemSelection.choice_group_id)
                & (ProductChoiceGroup.tenant_id == OrderDraftItemSelection.tenant_id)
                & (ProductChoiceGroup.organization_id == OrderDraftItemSelection.organization_id),
            )
            .join(
                ProductChoiceOption,
                (ProductChoiceOption.id == OrderDraftItemSelection.choice_option_id)
                & (ProductChoiceOption.group_id == OrderDraftItemSelection.choice_group_id)
                & (ProductChoiceOption.tenant_id == OrderDraftItemSelection.tenant_id)
                & (ProductChoiceOption.organization_id == OrderDraftItemSelection.organization_id),
            )
            .join(
                Product,
                (Product.id == ProductChoiceOption.option_product_id)
                & (Product.tenant_id == ProductChoiceOption.tenant_id)
                & (Product.organization_id == ProductChoiceOption.organization_id),
            )
            .where(
                OrderDraftItemSelection.tenant_id == item.tenant_id,
                OrderDraftItemSelection.draft_id == item.draft_id,
                OrderDraftItemSelection.draft_item_id == item.id,
            )
            .order_by(
                ProductChoiceGroup.display_order,
                ProductChoiceGroup.id,
                ProductChoiceOption.display_order,
                ProductChoiceOption.id,
            )
        )
    ).all()
    selected: dict[int, list[int]] = defaultdict(list)
    projected: list[SelectionProjection] = []
    for row, group, option, product in rows:
        selected[group.id].append(option.id)
        projected.append(
            SelectionProjection(
                group_id=group.id,
                group_name=group.name,
                choice_option_id=option.id,
                selected_product_id=product.id,
                selected_product_name=product.name,
            )
        )
    return tuple(projected), {
        group_id: tuple(option_ids) for group_id, option_ids in selected.items()
    }


async def _evaluate_item(
    db: AsyncSession, draft: OrderDraft, item: OrderDraftItem
) -> DraftItemProjection:
    product = await db.scalar(
        select(Product).where(
            Product.id == item.product_id,
            Product.tenant_id == draft.tenant_id,
            Product.organization_id == draft.organization_id,
        )
    )
    if product is None:
        raise DraftContextError('Draft Product is missing from its canonical scope')
    projected_selections, selected_by_group = await _selection_projection(db, item)
    issues: list[DraftIssue] = []
    fixed_components: tuple[FixedComponentProjection, ...] = ()
    missing_groups: tuple[MissingChoiceGroupProjection, ...] = ()

    orderable = await resolution.is_product_orderable(
        db,
        tenant_id=draft.tenant_id,
        organization_id=draft.organization_id,
        location_id=draft.location_id,
        product_id=item.product_id,
    )
    if not orderable:
        issues.append(DraftIssue('PRODUCT_NOT_ORDERABLE', product_id=item.product_id))

    current_composition = await db.scalar(
        select(ProductComposition).where(
            ProductComposition.tenant_id == draft.tenant_id,
            ProductComposition.organization_id == draft.organization_id,
            ProductComposition.product_id == item.product_id,
        )
    )
    if item.composition_id is None:
        if current_composition is not None or projected_selections:
            issues.append(DraftIssue('COMPOSITION_IDENTITY_CHANGED', product_id=item.product_id))
        item_readiness = DraftReadiness.INVALID if issues else DraftReadiness.READY
    elif (
        current_composition is None
        or current_composition.id != item.composition_id
        or current_composition.status != 'ACTIVE'
    ):
        issues.append(DraftIssue('COMPOSITION_NOT_ACTIVE', product_id=item.product_id))
        item_readiness = DraftReadiness.INVALID
    else:
        selections = tuple(
            structure.ChoiceSelection(group_id=group_id, option_ids=option_ids)
            for group_id, option_ids in sorted(selected_by_group.items())
        )
        validation = await structure.validate_selection(
            db,
            tenant_id=draft.tenant_id,
            product_id=item.product_id,
            selections=selections,
        )
        issues.extend(
            DraftIssue(
                violation.code.value,
                group_id=violation.group_id,
                option_id=violation.option_id,
                product_id=violation.product_id,
            )
            for violation in validation.violations
        )
        names = {
            value.id: value.name
            for value in (
                await db.execute(
                    select(Product).where(
                        Product.tenant_id == draft.tenant_id,
                        Product.organization_id == draft.organization_id,
                        Product.id.in_(
                            tuple(component.product_id for component in validation.fixed_components)
                            or (-1,)
                        ),
                    )
                )
            )
            .scalars()
            .all()
        }
        fixed_components = tuple(
            FixedComponentProjection(component.product_id, names[component.product_id], component.quantity)
            for component in validation.fixed_components
        )
        groups = tuple(
            (
                await db.execute(
                    select(ProductChoiceGroup)
                    .where(
                        ProductChoiceGroup.tenant_id == draft.tenant_id,
                        ProductChoiceGroup.organization_id == draft.organization_id,
                        ProductChoiceGroup.composition_id == item.composition_id,
                    )
                    .order_by(ProductChoiceGroup.display_order, ProductChoiceGroup.id)
                )
            )
            .scalars()
            .all()
        )
        incomplete_group_ids = {
            issue.group_id for issue in issues if issue.code in {code.value for code in _INCOMPLETE_CODES}
        }
        missing_groups = tuple(
            MissingChoiceGroupProjection(
                group_id=group.id,
                group_name=group.name,
                min_selections=group.min_selections,
                max_selections=group.max_selections,
                selected_option_ids=selected_by_group.get(group.id, ()),
            )
            for group in groups
            if group.id in incomplete_group_ids
        )
        structural = [issue for issue in issues if issue.code not in {code.value for code in _INCOMPLETE_CODES}]
        if structural:
            item_readiness = DraftReadiness.INVALID
        elif issues:
            item_readiness = DraftReadiness.INCOMPLETE
        else:
            item_readiness = DraftReadiness.READY

    return DraftItemProjection(
        item_id=item.id,
        product_id=item.product_id,
        product_name=product.name,
        composition_id=item.composition_id,
        quantity=item.quantity,
        position=item.position,
        readiness=item_readiness,
        issues=tuple(issues),
        selections=projected_selections,
        missing_choice_groups=missing_groups,
        fixed_components=fixed_components,
    )


async def evaluate_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    correlation_id: str | None = None,
) -> DraftProjection:
    draft = await _draft(db, tenant_id=tenant_id, draft_id=draft_id)
    items = tuple(
        (
            await db.execute(
                select(OrderDraftItem)
                .where(
                    OrderDraftItem.tenant_id == tenant_id,
                    OrderDraftItem.draft_id == draft.id,
                )
                .order_by(OrderDraftItem.position, OrderDraftItem.id)
            )
        )
        .scalars()
        .all()
    )
    projected = tuple([await _evaluate_item(db, draft, item) for item in items])
    if not projected:
        readiness = DraftReadiness.EMPTY
    elif any(item.readiness == DraftReadiness.INVALID for item in projected):
        readiness = DraftReadiness.INVALID
    elif any(item.readiness == DraftReadiness.INCOMPLETE for item in projected):
        readiness = DraftReadiness.INCOMPLETE
    else:
        readiness = DraftReadiness.READY
    _event(
        'order_draft_readiness_evaluated',
        draft,
        correlation_id=correlation_id,
        outcome=readiness.value,
    )
    return DraftProjection(
        draft_id=draft.id,
        tenant_id=draft.tenant_id,
        organization_id=draft.organization_id,
        location_id=draft.location_id,
        conversation_id=draft.conversation_id,
        version=draft.version,
        status=draft.status,
        readiness=readiness,
        items=projected,
    )


async def add_item(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    product_id: int,
    quantity: Decimal,
    expected_version: int,
    correlation_id: str | None = None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> DraftProjection:
    quantity = validate_quantity(quantity)
    try:
        draft = await _locked_mutable_draft(
            db,
            tenant_id=tenant_id,
            draft_id=draft_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            owner_diner_session_id=owner_diner_session_id,
            owned_conversation_id=owned_conversation_id,
        )
        if not await resolution.is_product_orderable(
            db,
            tenant_id=tenant_id,
            organization_id=draft.organization_id,
            location_id=draft.location_id,
            product_id=product_id,
        ):
            raise ProductNotOrderableError('Product is not orderable at the Draft Location')
        product = await db.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
                Product.organization_id == draft.organization_id,
                Product.status == 'ACTIVE',
            )
        )
        if product is None:
            raise ProductNotOrderableError('Product is not orderable at the Draft Location')
        composition = await db.scalar(
            select(ProductComposition).where(
                ProductComposition.tenant_id == tenant_id,
                ProductComposition.organization_id == draft.organization_id,
                ProductComposition.product_id == product_id,
            )
        )
        if composition is not None and composition.status != 'ACTIVE':
            raise InvalidDraftCompositionError('Product Composition is not active')
        if composition is not None:
            validation = await structure.validate_selection(
                db, tenant_id=tenant_id, product_id=product_id, selections=()
            )
            structural = tuple(
                violation
                for violation in validation.violations
                if violation.code not in _INCOMPLETE_CODES
            )
            if structural:
                raise InvalidDraftCompositionError(
                    'Product Composition is not valid for a Draft item'
                )
        position = int(
            await db.scalar(
                select(func.coalesce(func.max(OrderDraftItem.position), -1)).where(
                    OrderDraftItem.tenant_id == tenant_id,
                    OrderDraftItem.draft_id == draft.id,
                )
            )
        ) + 1
        item = OrderDraftItem(
            tenant_id=tenant_id,
            organization_id=draft.organization_id,
            draft_id=draft.id,
            product_id=product.id,
            composition_id=composition.id if composition else None,
            quantity=quantity,
            position=position,
        )
        db.add(item)
        draft.version += 1
        await db.commit()
        await db.refresh(item)
        await db.refresh(draft)
    except Exception:
        await db.rollback()
        raise
    _event(
        'order_draft_item_added',
        draft,
        correlation_id=correlation_id,
        item_id=item.id,
        product_id=item.product_id,
        outcome='added',
    )
    return await evaluate_draft(db, tenant_id=tenant_id, draft_id=draft.id, correlation_id=correlation_id)


async def _item(
    db: AsyncSession, *, draft: OrderDraft, item_id: int
) -> OrderDraftItem:
    item = await db.scalar(
        select(OrderDraftItem).where(
            OrderDraftItem.id == item_id,
            OrderDraftItem.tenant_id == draft.tenant_id,
            OrderDraftItem.organization_id == draft.organization_id,
            OrderDraftItem.draft_id == draft.id,
        )
    )
    if item is None:
        raise DraftItemNotFoundError('Order Draft Item not found')
    return item


async def set_item_quantity(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    item_id: int,
    quantity: Decimal,
    expected_version: int,
    correlation_id: str | None = None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> DraftProjection:
    quantity = validate_quantity(quantity)
    try:
        draft = await _locked_mutable_draft(
            db,
            tenant_id=tenant_id,
            draft_id=draft_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            owner_diner_session_id=owner_diner_session_id,
            owned_conversation_id=owned_conversation_id,
        )
        item = await _item(db, draft=draft, item_id=item_id)
        item.quantity = quantity
        draft.version += 1
        await db.commit()
        await db.refresh(draft)
    except Exception:
        await db.rollback()
        raise
    _event(
        'order_draft_item_quantity_changed',
        draft,
        correlation_id=correlation_id,
        item_id=item.id,
        product_id=item.product_id,
        outcome='updated',
    )
    return await evaluate_draft(db, tenant_id=tenant_id, draft_id=draft.id, correlation_id=correlation_id)


async def remove_item(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    item_id: int,
    expected_version: int,
    correlation_id: str | None = None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> DraftProjection:
    try:
        draft = await _locked_mutable_draft(
            db,
            tenant_id=tenant_id,
            draft_id=draft_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            owner_diner_session_id=owner_diner_session_id,
            owned_conversation_id=owned_conversation_id,
        )
        item = await _item(db, draft=draft, item_id=item_id)
        product_id = item.product_id
        await db.execute(
            delete(OrderDraftItemSelection).where(
                OrderDraftItemSelection.tenant_id == tenant_id,
                OrderDraftItemSelection.draft_id == draft.id,
                OrderDraftItemSelection.draft_item_id == item.id,
            )
        )
        await db.delete(item)
        draft.version += 1
        await db.commit()
        await db.refresh(draft)
    except Exception:
        await db.rollback()
        raise
    _event(
        'order_draft_item_removed',
        draft,
        correlation_id=correlation_id,
        item_id=item_id,
        product_id=product_id,
        outcome='removed',
    )
    return await evaluate_draft(db, tenant_id=tenant_id, draft_id=draft.id, correlation_id=correlation_id)


async def replace_group_selections(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft_id: int,
    item_id: int,
    group_id: int,
    option_ids: tuple[int, ...],
    expected_version: int,
    correlation_id: str | None = None,
    owner_diner_session_id: int | None = None,
    owned_conversation_id: int | None = None,
) -> DraftProjection:
    if len(option_ids) != len(set(option_ids)):
        raise InvalidDraftSelectionError('Choice option IDs must be distinct')
    if any(option_id <= 0 for option_id in option_ids):
        raise InvalidDraftSelectionError('Choice option IDs must be positive')
    try:
        draft = await _locked_mutable_draft(
            db,
            tenant_id=tenant_id,
            draft_id=draft_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            owner_diner_session_id=owner_diner_session_id,
            owned_conversation_id=owned_conversation_id,
        )
        item = await _item(db, draft=draft, item_id=item_id)
        if item.composition_id is None:
            raise InvalidDraftCompositionError('Simple Product does not accept Choice selections')
        group = await db.scalar(
            select(ProductChoiceGroup).where(
                ProductChoiceGroup.id == group_id,
                ProductChoiceGroup.tenant_id == tenant_id,
                ProductChoiceGroup.organization_id == draft.organization_id,
                ProductChoiceGroup.composition_id == item.composition_id,
                ProductChoiceGroup.status == 'ACTIVE',
            )
        )
        if group is None:
            raise InvalidDraftSelectionError('Choice Group is not active in the item Composition')
        options = tuple(
            (
                await db.execute(
                    select(ProductChoiceOption)
                    .join(
                        Product,
                        (Product.id == ProductChoiceOption.option_product_id)
                        & (Product.tenant_id == ProductChoiceOption.tenant_id)
                        & (Product.organization_id == ProductChoiceOption.organization_id),
                    )
                    .where(
                        ProductChoiceOption.id.in_(option_ids or (-1,)),
                        ProductChoiceOption.tenant_id == tenant_id,
                        ProductChoiceOption.organization_id == draft.organization_id,
                        ProductChoiceOption.group_id == group.id,
                        ProductChoiceOption.status == 'ACTIVE',
                        Product.status == 'ACTIVE',
                    )
                )
            )
            .scalars()
            .all()
        )
        if {option.id for option in options} != set(option_ids):
            raise InvalidDraftSelectionError('Choice Option is not active in the requested Group')
        current = tuple(
            (
                await db.execute(
                    select(OrderDraftItemSelection).where(
                        OrderDraftItemSelection.tenant_id == tenant_id,
                        OrderDraftItemSelection.draft_id == draft.id,
                        OrderDraftItemSelection.draft_item_id == item.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        by_group: dict[int, list[int]] = defaultdict(list)
        for selection in current:
            if selection.choice_group_id != group.id:
                by_group[selection.choice_group_id].append(selection.choice_option_id)
        by_group[group.id] = list(option_ids)
        validation = await structure.validate_selection(
            db,
            tenant_id=tenant_id,
            product_id=item.product_id,
            selections=tuple(
                structure.ChoiceSelection(group_id=value, option_ids=tuple(ids))
                for value, ids in sorted(by_group.items())
            ),
        )
        structural = tuple(
            violation for violation in validation.violations if violation.code not in _INCOMPLETE_CODES
        )
        if structural:
            _event(
                'order_draft_validation_rejected',
                draft,
                correlation_id=correlation_id,
                item_id=item.id,
                product_id=item.product_id,
                choice_group_id=group.id,
                option_count=len(option_ids),
                outcome='rejected',
            )
            raise InvalidDraftSelectionError(
                'Draft selection is structurally invalid: '
                + ', '.join(violation.code.value for violation in structural)
            )
        await db.execute(
            delete(OrderDraftItemSelection).where(
                OrderDraftItemSelection.tenant_id == tenant_id,
                OrderDraftItemSelection.draft_id == draft.id,
                OrderDraftItemSelection.draft_item_id == item.id,
                OrderDraftItemSelection.choice_group_id == group.id,
            )
        )
        db.add_all(
            [
                OrderDraftItemSelection(
                    tenant_id=tenant_id,
                    organization_id=draft.organization_id,
                    draft_id=draft.id,
                    draft_item_id=item.id,
                    composition_id=item.composition_id,
                    choice_group_id=group.id,
                    choice_option_id=option_id,
                )
                for option_id in option_ids
            ]
        )
        draft.version += 1
        await db.commit()
        await db.refresh(draft)
    except Exception:
        await db.rollback()
        raise
    _event(
        'order_draft_group_selections_replaced',
        draft,
        correlation_id=correlation_id,
        item_id=item.id,
        product_id=item.product_id,
        choice_group_id=group.id,
        option_count=len(option_ids),
        outcome='replaced',
    )
    return await evaluate_draft(db, tenant_id=tenant_id, draft_id=draft.id, correlation_id=correlation_id)
