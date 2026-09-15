"""Canonical Product Category provisioning and scoped operator-key binding."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Organization,
    ProductCategory,
    ProductCategoryExternalMapping,
)
from app.restaurant.catalog import structure


_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_CATEGORY_NAME_CONSTRAINT = 'uq_product_categories_tenant_org_name'


class CategoryProvisioningError(ValueError):
    pass


class CategoryScopeNotFoundError(CategoryProvisioningError):
    pass


class CategoryConflictError(CategoryProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class CategoryProvisioningPlan:
    operation: str
    binding_namespace: str
    category_key: str
    parent_category_id: int | None
    category_id: int | None


@dataclass(frozen=True, slots=True)
class CategoryProvisioningResult:
    category: ProductCategory
    operation: str
    binding_namespace: str
    category_key: str


def onboarding_binding_namespace(*, contract_version: str, organization_id: int) -> str:
    value = f'ONBOARDING:{contract_version}:ORG:{organization_id}'
    if organization_id <= 0 or len(value) > 128:
        raise CategoryProvisioningError('Invalid Product Category binding scope')
    return value


def _text(value: str, *, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise CategoryProvisioningError(
            f'{field} must contain between 1 and {maximum} characters'
        )
    return normalized


def _status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {'ACTIVE', 'INACTIVE'}:
        raise CategoryProvisioningError('Unsupported Product Category status')
    return normalized


def _order(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CategoryProvisioningError('Invalid Product Category display order')
    return value


def _is_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == constraint_name


def _translate_integrity_error(exc: IntegrityError) -> None:
    if _is_constraint(exc, _CATEGORY_NAME_CONSTRAINT):
        raise CategoryConflictError(
            'Product Category name already exists in this Organization'
        ) from exc
    raise exc


async def _organization(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
) -> Organization:
    organization = await db.scalar(select(Organization).where(
        Organization.id == organization_id,
        Organization.tenant_id == tenant_id,
    ))
    if organization is None:
        raise CategoryScopeNotFoundError('Organization not found')
    return organization


async def create_category(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    parent_id: int | None, name: str, display_order: int = 0,
    status: str = 'ACTIVE', commit: bool = True,
) -> ProductCategory:
    await _organization(db, tenant_id=tenant_id, organization_id=organization_id)
    if parent_id is not None:
        try:
            await structure.validate_new_category_parent(
                db, tenant_id=tenant_id,
                organization_id=organization_id, parent_id=parent_id,
            )
        except structure.StructureNotFoundError as exc:
            raise CategoryScopeNotFoundError(str(exc)) from exc
    category = ProductCategory(
        tenant_id=tenant_id, organization_id=organization_id, parent_id=parent_id,
        name=_text(name, field='Product Category name', maximum=200),
        display_order=_order(display_order), status=_status(status),
    )
    db.add(category)
    try:
        if commit:
            await db.commit()
            await db.refresh(category)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if commit:
            _translate_integrity_error(exc)
        raise
    return category


async def update_category(
    db: AsyncSession, *, tenant_id: int, category_id: int,
    changes: dict[str, object], commit: bool = True,
) -> ProductCategory:
    allowed = {'parent_id', 'name', 'display_order', 'status'}
    if not changes or not set(changes) <= allowed:
        raise CategoryProvisioningError('Invalid Product Category update fields')
    updates = dict(changes)
    if 'parent_id' in updates:
        parent_id = updates.pop('parent_id')
        if parent_id is not None and not isinstance(parent_id, int):
            raise CategoryProvisioningError('Invalid parent Product Category identifier')
        try:
            category = await structure.set_category_parent(
                db, tenant_id=tenant_id,
                category_id=category_id, parent_id=parent_id,
            )
        except structure.StructureNotFoundError as exc:
            raise CategoryScopeNotFoundError(str(exc)) from exc
        except structure.StructureConflictError as exc:
            raise CategoryConflictError(str(exc)) from exc
    else:
        category = await db.scalar(select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.tenant_id == tenant_id,
        ).with_for_update())
        if category is None:
            raise CategoryScopeNotFoundError('Product Category not found')
    if 'name' in updates:
        if not isinstance(updates['name'], str):
            raise CategoryProvisioningError('Invalid Product Category name')
        category.name = _text(
            updates['name'], field='Product Category name', maximum=200
        )
    if 'display_order' in updates:
        category.display_order = _order(updates['display_order'])
    if 'status' in updates:
        if not isinstance(updates['status'], str):
            raise CategoryProvisioningError('Invalid Product Category status')
        category.status = _status(updates['status'])
    try:
        if commit:
            await db.commit()
            await db.refresh(category)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        _translate_integrity_error(exc)
    return category


async def _mapped_category(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, category_key: str, for_update: bool = False,
) -> ProductCategory | None:
    statement = select(ProductCategory).join(
        ProductCategoryExternalMapping,
        (ProductCategoryExternalMapping.category_id == ProductCategory.id)
        & (ProductCategoryExternalMapping.tenant_id == ProductCategory.tenant_id)
        & (
            ProductCategoryExternalMapping.organization_id
            == ProductCategory.organization_id
        ),
    ).where(
        ProductCategoryExternalMapping.tenant_id == tenant_id,
        ProductCategoryExternalMapping.organization_id == organization_id,
        ProductCategoryExternalMapping.connector_key == binding_namespace,
        ProductCategoryExternalMapping.external_category_id == category_key,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _operation(
    category: ProductCategory, *, parent_id: int | None, name: str,
    display_order: int, status: str,
) -> str:
    current = (category.parent_id, category.name, category.display_order, category.status)
    requested = (parent_id, name, display_order, status)
    return 'UNCHANGED' if current == requested else 'UPDATE'


async def resolve_category_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, category_key: str, for_update: bool = False,
) -> ProductCategory:
    namespace = _text(
        binding_namespace, field='Product Category binding namespace', maximum=128
    )
    key = _text(category_key, field='Product Category operator key', maximum=200)
    category = await _mapped_category(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=namespace, category_key=key, for_update=for_update,
    )
    if category is None:
        raise CategoryScopeNotFoundError('Product Category binding not found')
    return category


async def plan_category(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, category_key: str,
    parent_category_key: str | None, name: str, display_order: int, status: str,
    allow_unresolved_parent: bool = False,
) -> CategoryProvisioningPlan:
    await _organization(db, tenant_id=tenant_id, organization_id=organization_id)
    namespace = _text(
        binding_namespace, field='Product Category binding namespace', maximum=128
    )
    key = _text(category_key, field='Product Category operator key', maximum=200)
    normalized_name = _text(name, field='Product Category name', maximum=200)
    normalized_order = _order(display_order)
    normalized_status = _status(status)
    parent_id = None
    if parent_category_key is not None:
        try:
            parent_id = (await resolve_category_binding(
                db, tenant_id=tenant_id, organization_id=organization_id,
                binding_namespace=namespace, category_key=parent_category_key,
            )).id
        except CategoryScopeNotFoundError:
            if not allow_unresolved_parent:
                raise
    category = await _mapped_category(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=namespace, category_key=key,
    )
    operation = 'CREATE' if category is None else _operation(
        category, parent_id=parent_id, name=normalized_name,
        display_order=normalized_order, status=normalized_status,
    )
    if category is not None and parent_category_key is not None and parent_id is None:
        operation = 'UPDATE'
    return CategoryProvisioningPlan(
        operation, namespace, key, parent_id,
        None if category is None else category.id,
    )


async def provision_category(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, category_key: str,
    parent_category_key: str | None, name: str, display_order: int, status: str,
) -> CategoryProvisioningResult:
    plan = await plan_category(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, category_key=category_key,
        parent_category_key=parent_category_key, name=name,
        display_order=display_order, status=status,
    )
    changes = {
        'parent_id': plan.parent_category_id, 'name': name,
        'display_order': display_order, 'status': status,
    }
    if plan.category_id is not None:
        category = await resolve_category_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=plan.binding_namespace,
            category_key=plan.category_key, for_update=True,
        )
        operation = _operation(
            category, parent_id=plan.parent_category_id, name=name.strip(),
            display_order=display_order, status=status.strip().upper(),
        )
        if operation == 'UPDATE':
            category = await update_category(
                db, tenant_id=tenant_id, category_id=category.id, changes=changes,
            )
        return CategoryProvisioningResult(
            category, operation, plan.binding_namespace, plan.category_key
        )

    try:
        category = await create_category(
            db, tenant_id=tenant_id, organization_id=organization_id,
            parent_id=plan.parent_category_id, name=name,
            display_order=display_order, status=status, commit=False,
        )
        db.add(ProductCategoryExternalMapping(
            tenant_id=tenant_id, organization_id=organization_id,
            category_id=category.id, connector_key=plan.binding_namespace,
            external_category_id=plan.category_key,
        ))
        await db.commit()
        await db.refresh(category)
        return CategoryProvisioningResult(
            category, 'CREATE', plan.binding_namespace, plan.category_key
        )
    except IntegrityError as exc:
        await db.rollback()
        winner = await _mapped_category(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=plan.binding_namespace,
            category_key=plan.category_key, for_update=True,
        )
        if winner is None:
            _translate_integrity_error(exc)
        operation = _operation(
            winner, parent_id=plan.parent_category_id, name=name.strip(),
            display_order=display_order, status=status.strip().upper(),
        )
        if operation == 'UPDATE':
            winner = await update_category(
                db, tenant_id=tenant_id, category_id=winner.id, changes=changes,
            )
        return CategoryProvisioningResult(
            winner, operation, plan.binding_namespace, plan.category_key
        )
