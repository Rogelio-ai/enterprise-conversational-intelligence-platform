from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Product,
    ProductCategory,
    ProductChoiceGroup,
    ProductChoiceOption,
    ProductComponent,
    ProductComposition,
)


class StructureNotFoundError(LookupError):
    pass


class StructureConflictError(RuntimeError):
    pass


async def _lock_category_scope(
    db: AsyncSession, *, tenant_id: int, organization_id: int
) -> tuple[ProductCategory, ...]:
    result = await db.execute(
        select(ProductCategory)
        .where(
            ProductCategory.tenant_id == tenant_id,
            ProductCategory.organization_id == organization_id,
        )
        .order_by(ProductCategory.id)
        .with_for_update()
    )
    return tuple(result.scalars().all())


async def validate_new_category_parent(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    parent_id: int,
) -> None:
    categories = await _lock_category_scope(
        db, tenant_id=tenant_id, organization_id=organization_id
    )
    if parent_id not in {category.id for category in categories}:
        raise StructureNotFoundError('Parent Product Category not found')


async def set_category_parent(
    db: AsyncSession,
    *,
    tenant_id: int,
    category_id: int,
    parent_id: int | None,
) -> ProductCategory:
    category = await db.scalar(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.tenant_id == tenant_id,
        )
    )
    if category is None:
        raise StructureNotFoundError('Product Category not found')
    categories = await _lock_category_scope(
        db,
        tenant_id=tenant_id,
        organization_id=category.organization_id,
    )
    by_id = {item.id: item for item in categories}
    category = by_id[category_id]
    if parent_id is None:
        category.parent_id = None
        return category
    if parent_id == category.id:
        raise StructureConflictError('Product Category cannot be its own parent')
    parent = by_id.get(parent_id)
    if parent is None:
        raise StructureNotFoundError('Parent Product Category not found')

    visited = {category.id}
    cursor: ProductCategory | None = parent
    while cursor is not None:
        if cursor.id in visited:
            raise StructureConflictError('Product Category hierarchy cycle is not allowed')
        visited.add(cursor.id)
        cursor = by_id.get(cursor.parent_id) if cursor.parent_id is not None else None
    category.parent_id = parent.id
    return category


async def _lock_product_scope(
    db: AsyncSession, *, tenant_id: int, organization_id: int
) -> dict[int, Product]:
    result = await db.execute(
        select(Product)
        .where(
            Product.tenant_id == tenant_id,
            Product.organization_id == organization_id,
        )
        .order_by(Product.id)
        .with_for_update()
    )
    return {product.id: product for product in result.scalars().all()}


async def _is_referenced_child(
    db: AsyncSession, *, tenant_id: int, organization_id: int, product_id: int
) -> bool:
    component = await db.scalar(
        select(ProductComponent.id)
        .where(
            ProductComponent.tenant_id == tenant_id,
            ProductComponent.organization_id == organization_id,
            ProductComponent.component_product_id == product_id,
        )
        .limit(1)
        .with_for_update()
    )
    if component is not None:
        return True
    option = await db.scalar(
        select(ProductChoiceOption.id)
        .where(
            ProductChoiceOption.tenant_id == tenant_id,
            ProductChoiceOption.organization_id == organization_id,
            ProductChoiceOption.option_product_id == product_id,
        )
        .limit(1)
        .with_for_update()
    )
    return option is not None


async def create_composition(
    db: AsyncSession, *, tenant_id: int, product_id: int
) -> ProductComposition:
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    if product is None:
        raise StructureNotFoundError('Product not found')
    products = await _lock_product_scope(
        db, tenant_id=tenant_id, organization_id=product.organization_id
    )
    product = products[product_id]
    if await _is_referenced_child(
        db,
        tenant_id=tenant_id,
        organization_id=product.organization_id,
        product_id=product.id,
    ):
        raise StructureConflictError('A component or option Product cannot own a composition')
    existing = await db.scalar(
        select(ProductComposition.id).where(
            ProductComposition.tenant_id == tenant_id,
            ProductComposition.organization_id == product.organization_id,
            ProductComposition.product_id == product.id,
        ).with_for_update()
    )
    if existing is not None:
        raise StructureConflictError('Product Composition already exists')
    composition = ProductComposition(
        tenant_id=tenant_id,
        organization_id=product.organization_id,
        product_id=product.id,
        status='INACTIVE',
    )
    db.add(composition)
    await db.flush()
    return composition


async def require_composition(
    db: AsyncSession,
    *,
    tenant_id: int,
    product_id: int,
    for_update: bool = False,
) -> ProductComposition:
    statement = (
        select(ProductComposition)
        .join(
            Product,
            (Product.id == ProductComposition.product_id)
            & (Product.tenant_id == ProductComposition.tenant_id)
            & (Product.organization_id == ProductComposition.organization_id),
        )
        .where(
            ProductComposition.tenant_id == tenant_id,
            ProductComposition.product_id == product_id,
        )
    )
    if for_update:
        statement = statement.with_for_update()
    composition = await db.scalar(statement)
    if composition is None:
        raise StructureNotFoundError('Product Composition not found')
    return composition


async def validate_child_product(
    db: AsyncSession,
    *,
    composition: ProductComposition,
    child_product_id: int,
) -> Product:
    products = await _lock_product_scope(
        db,
        tenant_id=composition.tenant_id,
        organization_id=composition.organization_id,
    )
    parent = products.get(composition.product_id)
    child = products.get(child_product_id)
    if parent is None or child is None:
        raise StructureNotFoundError('Component Product not found')
    if parent.id == child.id:
        raise StructureConflictError('Product cannot contain itself')
    child_composition = await db.scalar(
        select(ProductComposition.id).where(
            ProductComposition.tenant_id == composition.tenant_id,
            ProductComposition.organization_id == composition.organization_id,
            ProductComposition.product_id == child.id,
        ).with_for_update()
    )
    if child_composition is not None:
        raise StructureConflictError('Nested Product composition is not allowed')
    if await _is_referenced_child(
        db,
        tenant_id=composition.tenant_id,
        organization_id=composition.organization_id,
        product_id=parent.id,
    ):
        raise StructureConflictError('A component or option Product cannot own a composition')
    return child


@dataclass(frozen=True, slots=True)
class ComponentRecord:
    component: ProductComponent
    product: Product


@dataclass(frozen=True, slots=True)
class OptionRecord:
    option: ProductChoiceOption
    product: Product


@dataclass(frozen=True, slots=True)
class GroupRecord:
    group: ProductChoiceGroup
    options: tuple[OptionRecord, ...]


@dataclass(frozen=True, slots=True)
class CompositionGraph:
    composition: ProductComposition
    product: Product
    components: tuple[ComponentRecord, ...]
    groups: tuple[GroupRecord, ...]


async def load_composition_graph(
    db: AsyncSession,
    *,
    tenant_id: int,
    product_id: int,
    active_only: bool,
) -> CompositionGraph | None:
    composition_query = (
        select(ProductComposition, Product)
        .join(
            Product,
            (Product.id == ProductComposition.product_id)
            & (Product.tenant_id == ProductComposition.tenant_id)
            & (Product.organization_id == ProductComposition.organization_id),
        )
        .where(
            ProductComposition.tenant_id == tenant_id,
            ProductComposition.product_id == product_id,
        )
    )
    if active_only:
        composition_query = composition_query.where(
            ProductComposition.status == 'ACTIVE', Product.status == 'ACTIVE'
        )
    row = (await db.execute(composition_query)).first()
    if row is None:
        return None
    composition, product = row

    component_query = (
        select(ProductComponent, Product)
        .join(
            Product,
            (Product.id == ProductComponent.component_product_id)
            & (Product.tenant_id == ProductComponent.tenant_id)
            & (Product.organization_id == ProductComponent.organization_id),
        )
        .where(
            ProductComponent.tenant_id == tenant_id,
            ProductComponent.organization_id == composition.organization_id,
            ProductComponent.composition_id == composition.id,
        )
    )
    group_query = select(ProductChoiceGroup).where(
        ProductChoiceGroup.tenant_id == tenant_id,
        ProductChoiceGroup.organization_id == composition.organization_id,
        ProductChoiceGroup.composition_id == composition.id,
    )
    if active_only:
        component_query = component_query.where(
            ProductComponent.status == 'ACTIVE', Product.status == 'ACTIVE'
        )
        group_query = group_query.where(ProductChoiceGroup.status == 'ACTIVE')
    component_rows = (
        await db.execute(
            component_query.order_by(ProductComponent.display_order, ProductComponent.id)
        )
    ).all()
    groups = tuple(
        (
            await db.execute(
                group_query.order_by(ProductChoiceGroup.display_order, ProductChoiceGroup.id)
            )
        )
        .scalars()
        .all()
    )
    group_records: list[GroupRecord] = []
    for group in groups:
        option_query = (
            select(ProductChoiceOption, Product)
            .join(
                Product,
                (Product.id == ProductChoiceOption.option_product_id)
                & (Product.tenant_id == ProductChoiceOption.tenant_id)
                & (Product.organization_id == ProductChoiceOption.organization_id),
            )
            .where(
                ProductChoiceOption.tenant_id == tenant_id,
                ProductChoiceOption.organization_id == composition.organization_id,
                ProductChoiceOption.group_id == group.id,
            )
        )
        if active_only:
            option_query = option_query.where(
                ProductChoiceOption.status == 'ACTIVE', Product.status == 'ACTIVE'
            )
        option_rows = (
            await db.execute(
                option_query.order_by(
                    ProductChoiceOption.display_order, ProductChoiceOption.id
                )
            )
        ).all()
        group_records.append(
            GroupRecord(
                group=group,
                options=tuple(OptionRecord(option=option, product=value) for option, value in option_rows),
            )
        )
    return CompositionGraph(
        composition=composition,
        product=product,
        components=tuple(
            ComponentRecord(component=component, product=value)
            for component, value in component_rows
        ),
        groups=tuple(group_records),
    )


async def activate_composition(
    db: AsyncSession, *, tenant_id: int, product_id: int
) -> ProductComposition:
    composition = await require_composition(
        db, tenant_id=tenant_id, product_id=product_id
    )
    products = await _lock_product_scope(
        db,
        tenant_id=tenant_id,
        organization_id=composition.organization_id,
    )
    composition = await require_composition(
        db, tenant_id=tenant_id, product_id=product_id, for_update=True
    )
    parent = products.get(composition.product_id)
    if parent is None or parent.status != 'ACTIVE':
        raise StructureConflictError('Active composition requires an active parent Product')
    if await _is_referenced_child(
        db,
        tenant_id=tenant_id,
        organization_id=composition.organization_id,
        product_id=parent.id,
    ):
        raise StructureConflictError('A component or option Product cannot own a composition')

    components = tuple(
        (
            await db.execute(
                select(ProductComponent).where(
                    ProductComponent.tenant_id == tenant_id,
                    ProductComponent.organization_id == composition.organization_id,
                    ProductComponent.composition_id == composition.id,
                    ProductComponent.status == 'ACTIVE',
                )
            )
        )
        .scalars()
        .all()
    )
    groups = tuple(
        (
            await db.execute(
                select(ProductChoiceGroup).where(
                    ProductChoiceGroup.tenant_id == tenant_id,
                    ProductChoiceGroup.organization_id == composition.organization_id,
                    ProductChoiceGroup.composition_id == composition.id,
                    ProductChoiceGroup.status == 'ACTIVE',
                )
            )
        )
        .scalars()
        .all()
    )
    referenced_ids = {component.component_product_id for component in components}
    for group in groups:
        options = tuple(
            (
                await db.execute(
                    select(ProductChoiceOption).where(
                        ProductChoiceOption.tenant_id == tenant_id,
                        ProductChoiceOption.organization_id == composition.organization_id,
                        ProductChoiceOption.group_id == group.id,
                        ProductChoiceOption.status == 'ACTIVE',
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(options) < group.min_selections:
            raise StructureConflictError(
                'Active choice group does not have enough active options'
            )
        referenced_ids.update(option.option_product_id for option in options)
    for referenced_id in sorted(referenced_ids):
        referenced = products.get(referenced_id)
        if referenced is None or referenced.status != 'ACTIVE':
            raise StructureConflictError('Active composition references an inactive Product')
        nested = await db.scalar(
            select(ProductComposition.id).where(
                ProductComposition.tenant_id == tenant_id,
                ProductComposition.organization_id == composition.organization_id,
                ProductComposition.product_id == referenced_id,
            )
        )
        if nested is not None:
            raise StructureConflictError('Nested Product composition is not allowed')
    composition.status = 'ACTIVE'
    return composition


class SelectionViolationCode(StrEnum):
    COMPOSITION_NOT_FOUND = 'COMPOSITION_NOT_FOUND'
    COMPOSITION_NOT_ACTIVE = 'COMPOSITION_NOT_ACTIVE'
    REQUIRED_GROUP_MISSING = 'REQUIRED_GROUP_MISSING'
    TOO_FEW_SELECTIONS = 'TOO_FEW_SELECTIONS'
    TOO_MANY_SELECTIONS = 'TOO_MANY_SELECTIONS'
    INVALID_GROUP = 'INVALID_GROUP'
    INVALID_OPTION = 'INVALID_OPTION'
    INACTIVE_GROUP = 'INACTIVE_GROUP'
    INACTIVE_OPTION = 'INACTIVE_OPTION'
    INACTIVE_PRODUCT = 'INACTIVE_PRODUCT'
    DUPLICATE_OPTION = 'DUPLICATE_OPTION'
    DUPLICATE_GROUP = 'DUPLICATE_GROUP'


@dataclass(frozen=True, slots=True)
class ChoiceSelection:
    group_id: int
    option_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ResolvedProductQuantity:
    product_id: int
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class ResolvedSelectedOption:
    group_id: int
    option_id: int
    product_id: int
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class SelectionViolation:
    code: SelectionViolationCode
    group_id: int | None = None
    option_id: int | None = None
    product_id: int | None = None


@dataclass(frozen=True, slots=True)
class SelectionValidationResult:
    is_valid: bool
    fixed_components: tuple[ResolvedProductQuantity, ...]
    selected_options: tuple[ResolvedSelectedOption, ...]
    violations: tuple[SelectionViolation, ...]


async def validate_selection(
    db: AsyncSession,
    *,
    tenant_id: int,
    product_id: int,
    selections: tuple[ChoiceSelection, ...],
) -> SelectionValidationResult:
    composition = await db.scalar(
        select(ProductComposition).where(
            ProductComposition.tenant_id == tenant_id,
            ProductComposition.product_id == product_id,
        )
    )
    if composition is None:
        violation = SelectionViolation(SelectionViolationCode.COMPOSITION_NOT_FOUND)
        return SelectionValidationResult(False, (), (), (violation,))
    if composition.status != 'ACTIVE':
        violation = SelectionViolation(SelectionViolationCode.COMPOSITION_NOT_ACTIVE)
        return SelectionValidationResult(False, (), (), (violation,))

    component_rows = (
        await db.execute(
            select(ProductComponent, Product)
            .join(
                Product,
                (Product.id == ProductComponent.component_product_id)
                & (Product.tenant_id == ProductComponent.tenant_id)
                & (Product.organization_id == ProductComponent.organization_id),
            )
            .where(
                ProductComponent.tenant_id == tenant_id,
                ProductComponent.organization_id == composition.organization_id,
                ProductComponent.composition_id == composition.id,
                ProductComponent.status == 'ACTIVE',
            )
            .order_by(ProductComponent.display_order, ProductComponent.id)
        )
    ).all()
    fixed: list[ResolvedProductQuantity] = []
    violations: list[SelectionViolation] = []
    for component, product in component_rows:
        if product.status != 'ACTIVE':
            violations.append(
                SelectionViolation(
                    SelectionViolationCode.INACTIVE_PRODUCT, product_id=product.id
                )
            )
        else:
            fixed.append(ResolvedProductQuantity(product.id, component.quantity))

    groups = tuple(
        (
            await db.execute(
                select(ProductChoiceGroup)
                .where(
                    ProductChoiceGroup.tenant_id == tenant_id,
                    ProductChoiceGroup.organization_id == composition.organization_id,
                    ProductChoiceGroup.composition_id == composition.id,
                )
                .order_by(ProductChoiceGroup.display_order, ProductChoiceGroup.id)
            )
        )
        .scalars()
        .all()
    )
    group_by_id = {group.id: group for group in groups}
    option_rows = (
        await db.execute(
            select(ProductChoiceOption, Product)
            .join(
                Product,
                (Product.id == ProductChoiceOption.option_product_id)
                & (Product.tenant_id == ProductChoiceOption.tenant_id)
                & (Product.organization_id == ProductChoiceOption.organization_id),
            )
            .where(
                ProductChoiceOption.tenant_id == tenant_id,
                ProductChoiceOption.organization_id == composition.organization_id,
                ProductChoiceOption.group_id.in_(tuple(group_by_id) or (-1,)),
            )
        )
    ).all()
    options_by_group: dict[int, dict[int, tuple[ProductChoiceOption, Product]]] = {}
    for option, product in option_rows:
        options_by_group.setdefault(option.group_id, {})[option.id] = (option, product)

    selections_by_group: dict[int, ChoiceSelection] = {}
    for selection in selections:
        if selection.group_id in selections_by_group:
            violations.append(
                SelectionViolation(
                    SelectionViolationCode.DUPLICATE_GROUP, group_id=selection.group_id
                )
            )
            continue
        selections_by_group[selection.group_id] = selection

    resolved: list[ResolvedSelectedOption] = []
    for group_id, selection in selections_by_group.items():
        group = group_by_id.get(group_id)
        if group is None:
            violations.append(
                SelectionViolation(SelectionViolationCode.INVALID_GROUP, group_id=group_id)
            )
            continue
        if group.status != 'ACTIVE':
            violations.append(
                SelectionViolation(SelectionViolationCode.INACTIVE_GROUP, group_id=group_id)
            )
            continue
        seen: set[int] = set()
        valid_count = 0
        for option_id in selection.option_ids:
            if option_id in seen:
                violations.append(
                    SelectionViolation(
                        SelectionViolationCode.DUPLICATE_OPTION,
                        group_id=group_id,
                        option_id=option_id,
                    )
                )
                continue
            seen.add(option_id)
            row = options_by_group.get(group_id, {}).get(option_id)
            if row is None:
                violations.append(
                    SelectionViolation(
                        SelectionViolationCode.INVALID_OPTION,
                        group_id=group_id,
                        option_id=option_id,
                    )
                )
                continue
            option, option_product = row
            if option.status != 'ACTIVE':
                violations.append(
                    SelectionViolation(
                        SelectionViolationCode.INACTIVE_OPTION,
                        group_id=group_id,
                        option_id=option_id,
                    )
                )
                continue
            if option_product.status != 'ACTIVE':
                violations.append(
                    SelectionViolation(
                        SelectionViolationCode.INACTIVE_PRODUCT,
                        group_id=group_id,
                        option_id=option_id,
                        product_id=option_product.id,
                    )
                )
                continue
            valid_count += 1
            resolved.append(
                ResolvedSelectedOption(
                    group_id=group_id,
                    option_id=option.id,
                    product_id=option_product.id,
                    quantity=option.quantity,
                )
            )
        if valid_count < group.min_selections:
            violations.append(
                SelectionViolation(
                    SelectionViolationCode.TOO_FEW_SELECTIONS, group_id=group.id
                )
            )
        if valid_count > group.max_selections:
            violations.append(
                SelectionViolation(
                    SelectionViolationCode.TOO_MANY_SELECTIONS, group_id=group.id
                )
            )

    for group in groups:
        if group.status != 'ACTIVE' or group.min_selections == 0:
            continue
        if group.id not in selections_by_group:
            violations.append(
                SelectionViolation(
                    SelectionViolationCode.REQUIRED_GROUP_MISSING, group_id=group.id
                )
            )

    violations.sort(
        key=lambda item: (
            item.group_id or 0,
            item.option_id or 0,
            item.product_id or 0,
            item.code.value,
        )
    )
    resolved.sort(key=lambda item: (item.group_id, item.option_id))
    return SelectionValidationResult(
        is_valid=not violations,
        fixed_components=tuple(fixed),
        selected_options=tuple(resolved),
        violations=tuple(violations),
    )
