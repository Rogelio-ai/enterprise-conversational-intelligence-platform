"""Controlled, atomic provisioning of the minimum operational core."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.locations import (
    normalize_country_code,
    normalize_optional_email,
    validate_timezone,
)
from app.api.routes.organizations import normalize_code
from app.identity.access_provisioning import (
    AccessProvisioningError,
    LocationGrantCandidate,
    provision_staff_account_in_transaction,
)
from app.models import (
    Location,
    MembershipLocationGrant,
    MembershipLocationRole,
    MembershipRole,
    MinimalProvisioningRun,
    Organization,
    Permission,
    Role,
    RolePermission,
    Tenant,
    TenantMembership,
)
from app.organization_location import assign_headquarters_in_transaction


class MinimalProvisioningError(ValueError):
    pass


class MinimalProvisioningManifest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    manifest_version: int = Field(default=1, ge=1, le=1)
    operation_id: str = Field(min_length=1, max_length=128)
    tenant_id: int = Field(gt=0)
    actor_membership_id: int = Field(gt=0)
    organization_code: str = Field(min_length=1, max_length=64)
    organization_name: str = Field(min_length=1, max_length=200)
    location_code: str = Field(min_length=1, max_length=64)
    location_name: str = Field(min_length=1, max_length=200)
    location_timezone: str = Field(min_length=1, max_length=64)
    location_address_line1: str | None = Field(default=None, max_length=200)
    location_address_line2: str | None = Field(default=None, max_length=200)
    location_locality: str | None = Field(default=None, max_length=100)
    location_administrative_area: str | None = Field(default=None, max_length=100)
    location_postal_code: str | None = Field(default=None, max_length=32)
    location_country_code: str | None = Field(default=None, max_length=2)
    location_phone: str | None = Field(default=None, max_length=32)
    location_email: str | None = Field(default=None, max_length=320)
    staff_username: str = Field(min_length=1, max_length=64)
    staff_display_name: str = Field(min_length=1, max_length=200)
    staff_email: str | None = Field(default=None, max_length=320)
    role_name: str = Field(min_length=1, max_length=100)

    @field_validator('organization_code', 'location_code')
    @classmethod
    def validate_code(cls, value: str) -> str:
        return normalize_code(value)

    @field_validator('location_timezone')
    @classmethod
    def validate_location_timezone(cls, value: str) -> str:
        return validate_timezone(value)

    @field_validator('location_country_code')
    @classmethod
    def validate_location_country(cls, value: str | None) -> str | None:
        return normalize_country_code(value)

    @field_validator('location_email', 'staff_email')
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_optional_email(value)

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode='json'),
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class MinimalProvisioningResult:
    organization_id: int
    location_id: int
    staff_user_id: int
    replayed: bool


async def _authorize_actor(
    db: AsyncSession, *, tenant_id: int, actor_membership_id: int,
) -> tuple[int, ...]:
    actor = await db.scalar(
        select(TenantMembership)
        .where(
            TenantMembership.id == actor_membership_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == 'ACTIVE',
        )
        .with_for_update()
    )
    if actor is None:
        raise MinimalProvisioningError('Provisioning actor is not an active Tenant member')
    role_ids = tuple((await db.scalars(
        select(MembershipRole.role_id)
        .where(
            MembershipRole.tenant_id == tenant_id,
            MembershipRole.membership_id == actor_membership_id,
        )
        .order_by(MembershipRole.role_id)
        .with_for_update()
    )).all())
    permissions = frozenset((await db.scalars(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .where(
            Role.id.in_(role_ids),
            Role.tenant_id == tenant_id,
            Role.status == 'ACTIVE',
        )
    )).all())
    required = {'organization.manage', 'location.manage', 'user.manage', 'role.manage'}
    if not required <= permissions:
        raise MinimalProvisioningError('Provisioning actor lacks required permissions')
    return role_ids


async def provision_minimal_core(
    db: AsyncSession,
    *,
    manifest: MinimalProvisioningManifest,
    staff_password: str,
    password_minimum_length: int,
) -> MinimalProvisioningResult:
    """Provision core state with one caller-owned commit and exact replay."""
    fingerprint = manifest.fingerprint()
    try:
        tenant = await db.scalar(
            select(Tenant)
            .where(Tenant.id == manifest.tenant_id)
            .with_for_update()
        )
        if tenant is None or tenant.status != 'ACTIVE':
            raise MinimalProvisioningError('Provisioning Tenant is not active')

        existing_run = await db.scalar(
            select(MinimalProvisioningRun)
            .where(
                MinimalProvisioningRun.tenant_id == manifest.tenant_id,
                MinimalProvisioningRun.operation_id == manifest.operation_id,
            )
            .with_for_update()
        )
        if existing_run is not None:
            if existing_run.request_fingerprint != fingerprint:
                raise MinimalProvisioningError(
                    'Provisioning operation ID conflicts with different content'
                )
            replay_result = MinimalProvisioningResult(
                organization_id=existing_run.organization_id,
                location_id=existing_run.location_id,
                staff_user_id=existing_run.staff_user_id,
                replayed=True,
            )
            await db.rollback()
            return replay_result

        actor_role_ids = await _authorize_actor(
            db,
            tenant_id=manifest.tenant_id,
            actor_membership_id=manifest.actor_membership_id,
        )
        if await db.scalar(select(Organization.id).where(
            Organization.tenant_id == manifest.tenant_id,
            Organization.code == manifest.organization_code,
        ).with_for_update()) is not None:
            raise MinimalProvisioningError('Organization code already exists in this Tenant')

        organization = Organization(
            tenant_id=manifest.tenant_id,
            code=manifest.organization_code,
            name=manifest.organization_name,
            status='INACTIVE',
        )
        db.add(organization)
        await db.flush()
        location = Location(
            tenant_id=manifest.tenant_id,
            organization_id=organization.id,
            code=manifest.location_code,
            name=manifest.location_name,
            timezone=manifest.location_timezone,
            status='ACTIVE',
            address_line1=manifest.location_address_line1,
            address_line2=manifest.location_address_line2,
            locality=manifest.location_locality,
            administrative_area=manifest.location_administrative_area,
            postal_code=manifest.location_postal_code,
            country_code=manifest.location_country_code,
            phone=manifest.location_phone,
            email=manifest.location_email,
        )
        db.add(location)
        await db.flush()
        await assign_headquarters_in_transaction(
            db,
            organization=organization,
            location_id=location.id,
            actor_membership_id=manifest.actor_membership_id,
            operation_id=(
                'hq-' + hashlib.sha256(
                    f'{manifest.tenant_id}:{manifest.operation_id}'.encode('utf-8')
                ).hexdigest()
            ),
        )
        db.add(MembershipLocationGrant(
            tenant_id=manifest.tenant_id,
            membership_id=manifest.actor_membership_id,
            location_id=location.id,
        ))
        db.add_all([
            MembershipLocationRole(
                tenant_id=manifest.tenant_id,
                membership_id=manifest.actor_membership_id,
                location_id=location.id,
                role_id=role_id,
            )
            for role_id in actor_role_ids
        ])
        organization.status = 'ACTIVE'
        await db.flush()

        access = await provision_staff_account_in_transaction(
            db,
            tenant_id=manifest.tenant_id,
            actor_membership_id=manifest.actor_membership_id,
            username=manifest.staff_username,
            password=staff_password,
            display_name=manifest.staff_display_name,
            email=manifest.staff_email,
            password_minimum_length=password_minimum_length,
            role_name=manifest.role_name,
            locations=(LocationGrantCandidate(
                organization_id=organization.id,
                location_id=location.id,
            ),),
        )
        run = MinimalProvisioningRun(
            tenant_id=manifest.tenant_id,
            actor_membership_id=manifest.actor_membership_id,
            operation_id=manifest.operation_id,
            manifest_version=manifest.manifest_version,
            request_fingerprint=fingerprint,
            organization_id=organization.id,
            location_id=location.id,
            staff_user_id=access.membership.user_id,
        )
        db.add(run)
        await db.flush()
        result = MinimalProvisioningResult(
            organization_id=organization.id,
            location_id=location.id,
            staff_user_id=access.membership.user_id,
            replayed=False,
        )
        await db.commit()
        return result
    except (IntegrityError, AccessProvisioningError) as exc:
        await db.rollback()
        raise MinimalProvisioningError(
            'Minimal provisioning conflicted with existing or concurrent state'
        ) from exc
    except Exception:
        await db.rollback()
        raise
