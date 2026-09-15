"""Canonical Product provisioning and scoped operator-key binding authority."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, Product, ProductCategory, ProductExternalMapping
from app.restaurant.catalog import category_provisioning


class ProductProvisioningError(ValueError):
    pass


class ProductScopeNotFoundError(ProductProvisioningError):
    pass


class ProductBindingConflictError(ProductProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class ProductProvisioningPlan:
    operation: str
    binding_namespace: str
    product_key: str
    category_id: int | None
    product_id: int | None


@dataclass(frozen=True, slots=True)
class ProductProvisioningResult:
    product: Product
    operation: str
    binding_namespace: str
    product_key: str


def onboarding_binding_namespace(*, contract_version: str, organization_id: int) -> str:
    value = f'ONBOARDING:{contract_version}:ORG:{organization_id}'
    if organization_id <= 0 or len(value) > 128:
        raise ProductProvisioningError('Invalid Product binding scope')
    return value


def _text(value: str, *, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ProductProvisioningError(f'{field} must contain between 1 and {maximum} characters')
    return normalized


def _description(value: str | None) -> str | None:
    if value is None:
        return None
    return _text(value, field='Product description', maximum=2000)


def _status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {'ACTIVE', 'INACTIVE'}:
        raise ProductProvisioningError('Unsupported Product status')
    return normalized


def _source(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {'PLATFORM', 'POS'}:
        raise ProductProvisioningError('Unsupported Product source')
    return normalized


def _binding(value: str, *, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ProductProvisioningError(f'Invalid {field}')
    return normalized


async def _organization(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
) -> Organization:
    value = await db.scalar(select(Organization).where(
        Organization.id == organization_id,
        Organization.tenant_id == tenant_id,
    ))
    if value is None:
        raise ProductScopeNotFoundError('Organization not found')
    return value


async def _category(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    category_id: int | None = None, category_name: str | None = None,
) -> ProductCategory | None:
    if category_id is None and category_name is None:
        return None
    statement = select(ProductCategory).where(
        ProductCategory.tenant_id == tenant_id,
        ProductCategory.organization_id == organization_id,
    )
    if category_id is not None:
        statement = statement.where(ProductCategory.id == category_id)
    if category_name is not None:
        statement = statement.where(ProductCategory.name == category_name.strip())
    value = await db.scalar(statement)
    if value is None:
        raise ProductScopeNotFoundError('Product Category not found')
    return value


async def create_product(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    category_id: int | None, name: str, description: str | None,
    status: str = 'ACTIVE', source: str = 'PLATFORM', commit: bool = True,
) -> Product:
    await _organization(db, tenant_id=tenant_id, organization_id=organization_id)
    category = await _category(
        db, tenant_id=tenant_id, organization_id=organization_id,
        category_id=category_id,
    )
    product = Product(
        tenant_id=tenant_id, organization_id=organization_id,
        category_id=None if category is None else category.id,
        name=_text(name, field='Product name', maximum=200),
        description=_description(description), status=_status(status),
        source=_source(source),
    )
    db.add(product)
    if commit:
        await db.commit()
        await db.refresh(product)
    else:
        await db.flush()
    return product


async def update_product(
    db: AsyncSession, *, tenant_id: int, product_id: int,
    changes: dict[str, object], commit: bool = True,
) -> Product:
    allowed = {'category_id', 'name', 'description', 'status'}
    if not changes or not set(changes) <= allowed:
        raise ProductProvisioningError('Invalid Product update fields')
    product = await db.scalar(select(Product).where(
        Product.id == product_id, Product.tenant_id == tenant_id,
    ).with_for_update())
    if product is None:
        raise ProductScopeNotFoundError('Product not found')
    if 'category_id' in changes:
        category_id = changes['category_id']
        if category_id is not None and not isinstance(category_id, int):
            raise ProductProvisioningError('Invalid Product Category identifier')
        category = await _category(
            db, tenant_id=tenant_id, organization_id=product.organization_id,
            category_id=category_id,
        )
        product.category_id = None if category is None else category.id
    if 'name' in changes:
        if not isinstance(changes['name'], str):
            raise ProductProvisioningError('Invalid Product name')
        product.name = _text(changes['name'], field='Product name', maximum=200)
    if 'description' in changes:
        value = changes['description']
        if value is not None and not isinstance(value, str):
            raise ProductProvisioningError('Invalid Product description')
        product.description = _description(value)
    if 'status' in changes:
        if not isinstance(changes['status'], str):
            raise ProductProvisioningError('Invalid Product status')
        product.status = _status(changes['status'])
    if commit:
        await db.commit()
        await db.refresh(product)
    else:
        await db.flush()
    return product


async def _mapped_product(
    db: AsyncSession, *, tenant_id: int, binding_namespace: str,
    product_key: str, for_update: bool = False,
) -> Product | None:
    statement = select(Product).join(
        ProductExternalMapping,
        (ProductExternalMapping.product_id == Product.id)
        & (ProductExternalMapping.tenant_id == Product.tenant_id),
    ).where(
        ProductExternalMapping.tenant_id == tenant_id,
        ProductExternalMapping.connector_key == binding_namespace,
        ProductExternalMapping.external_product_id == product_key,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _verify_mapping(product: Product, *, organization_id: int) -> None:
    if product.organization_id != organization_id or product.source != 'PLATFORM':
        raise ProductBindingConflictError(
            'Product binding belongs to a different canonical Product scope'
        )


def _operation(
    product: Product, *, category_id: int | None, name: str,
    description: str | None, status: str,
) -> str:
    current = (product.category_id, product.name, product.description, product.status)
    requested = (category_id, name, description, status)
    return 'UNCHANGED' if current == requested else 'UPDATE'


async def plan_product(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, product_key: str, category_key: str | None,
    name: str, description: str | None, status: str,
    allow_unresolved_category: bool = False,
) -> ProductProvisioningPlan:
    await _organization(db, tenant_id=tenant_id, organization_id=organization_id)
    namespace = _binding(binding_namespace, field='Product binding namespace', maximum=128)
    key = _binding(product_key, field='Product operator key', maximum=200)
    category = None
    unresolved_category = False
    if category_key is not None:
        try:
            category = await category_provisioning.resolve_category_binding(
                db, tenant_id=tenant_id, organization_id=organization_id,
                binding_namespace=namespace, category_key=category_key,
            )
        except category_provisioning.CategoryProvisioningError as exc:
            if not allow_unresolved_category:
                raise ProductScopeNotFoundError(str(exc)) from exc
            unresolved_category = True
    normalized_name = _text(name, field='Product name', maximum=200)
    normalized_description = _description(description)
    normalized_status = _status(status)
    product = await _mapped_product(
        db, tenant_id=tenant_id, binding_namespace=namespace, product_key=key,
    )
    if product is None:
        operation, product_id = 'CREATE', None
    else:
        _verify_mapping(product, organization_id=organization_id)
        operation = _operation(
            product, category_id=None if category is None else category.id,
            name=normalized_name, description=normalized_description,
            status=normalized_status,
        )
        if unresolved_category:
            operation = 'UPDATE'
        product_id = product.id
    return ProductProvisioningPlan(
        operation, namespace, key, None if category is None else category.id, product_id,
    )


async def provision_product(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, product_key: str, category_key: str | None,
    name: str, description: str | None, status: str,
) -> ProductProvisioningResult:
    plan = await plan_product(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, product_key=product_key,
        category_key=category_key, name=name, description=description, status=status,
    )
    if plan.product_id is not None:
        product = await db.scalar(select(Product).where(
            Product.id == plan.product_id, Product.tenant_id == tenant_id,
        ).with_for_update())
        if product is None:
            raise ProductBindingConflictError('Bound canonical Product no longer exists')
        _verify_mapping(product, organization_id=organization_id)
        operation = _operation(
            product, category_id=plan.category_id, name=name.strip(),
            description=None if description is None else description.strip(),
            status=status.strip().upper(),
        )
        if operation == 'UPDATE':
            await update_product(
                db, tenant_id=tenant_id, product_id=product.id,
                changes={
                    'category_id': plan.category_id, 'name': name,
                    'description': description, 'status': status,
                }, commit=False,
            )
            await db.commit()
            await db.refresh(product)
        return ProductProvisioningResult(product, operation, plan.binding_namespace, plan.product_key)

    product = await create_product(
        db, tenant_id=tenant_id, organization_id=organization_id,
        category_id=plan.category_id, name=name, description=description,
        status=status, source='PLATFORM', commit=False,
    )
    db.add(ProductExternalMapping(
        tenant_id=tenant_id, product_id=product.id,
        connector_key=plan.binding_namespace, external_product_id=plan.product_key,
    ))
    try:
        await db.commit()
        await db.refresh(product)
        return ProductProvisioningResult(product, 'CREATE', plan.binding_namespace, plan.product_key)
    except IntegrityError:
        await db.rollback()
        winner = await _mapped_product(
            db, tenant_id=tenant_id, binding_namespace=plan.binding_namespace,
            product_key=plan.product_key, for_update=True,
        )
        if winner is None:
            raise
        _verify_mapping(winner, organization_id=organization_id)
        operation = _operation(
            winner, category_id=plan.category_id, name=name.strip(),
            description=None if description is None else description.strip(),
            status=status.strip().upper(),
        )
        if operation == 'UPDATE':
            winner = await update_product(
                db, tenant_id=tenant_id, product_id=winner.id,
                changes={
                    'category_id': plan.category_id, 'name': name,
                    'description': description, 'status': status,
                },
            )
        return ProductProvisioningResult(winner, operation, plan.binding_namespace, plan.product_key)


async def resolve_product_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, product_key: str,
) -> Product:
    namespace = _binding(binding_namespace, field='Product binding namespace', maximum=128)
    key = _binding(product_key, field='Product operator key', maximum=200)
    product = await _mapped_product(
        db, tenant_id=tenant_id, binding_namespace=namespace, product_key=key,
    )
    if product is None:
        raise ProductScopeNotFoundError('Product binding not found')
    _verify_mapping(product, organization_id=organization_id)
    return product
