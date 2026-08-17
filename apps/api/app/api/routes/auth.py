from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_authenticated_context, get_db
from app.core.security import create_access_token, verify_password
from app.models import Tenant, TenantMembership, User


router = APIRouter(prefix='/auth', tags=['auth'])
_DUMMY_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$uU8CX0/5qQg0XcGXgJzYVw$Zvmh0SIePCpIIxBUPuo7M/AADFTBbeKylDyRmziVBk4'


def normalize_email(email: str) -> str:
    return email.strip().casefold()


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    tenant_id: int | None = Field(default=None, gt=0)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        if '@' not in normalized or normalized.startswith('@') or normalized.endswith('@'):
            raise ValueError('A valid email is required')
        return normalized


class LoginUserResponse(BaseModel):
    id: int
    email: str
    display_name: str


class LoginTenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    membership_id: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    user: LoginUserResponse
    tenant: LoginTenantResponse


class CurrentUserResponse(BaseModel):
    user_id: int
    email: str
    display_name: str
    tenant_id: int
    membership_id: int
    roles: list[str]
    permissions: list[str]


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid authentication credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )


@router.post('/login', response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    user_result = await db.execute(select(User).where(User.email == payload.email))
    user = user_result.scalar_one_or_none()
    password_valid = verify_password(
        payload.password,
        user.password_hash if user is not None else _DUMMY_PASSWORD_HASH,
    )
    if user is None or not password_valid or user.status != 'ACTIVE':
        raise _invalid_credentials()

    membership_result = await db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(
            TenantMembership.user_id == user.id,
            TenantMembership.status == 'ACTIVE',
            Tenant.status == 'ACTIVE',
        )
        .order_by(TenantMembership.id)
    )
    memberships = membership_result.all()
    if payload.tenant_id is not None:
        selected = next(
            (row for row in memberships if row.TenantMembership.tenant_id == payload.tenant_id),
            None,
        )
        if selected is None:
            raise _invalid_credentials()
    elif len(memberships) == 1:
        selected = memberships[0]
    elif len(memberships) > 1:
        raise HTTPException(status_code=400, detail='Tenant selection is required')
    else:
        raise _invalid_credentials()

    membership, tenant = selected
    settings = request.app.state.settings
    access_token = create_access_token(
        settings=settings,
        user_id=user.id,
        tenant_id=tenant.id,
        membership_id=membership.id,
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.auth_access_token_ttl_minutes * 60,
        user=LoginUserResponse(id=user.id, email=user.email, display_name=user.display_name),
        tenant=LoginTenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            membership_id=membership.id,
        ),
    )


@router.get('/me', response_model=CurrentUserResponse)
async def me(
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=context.user_id,
        email=context.email,
        display_name=context.display_name,
        tenant_id=context.tenant_id,
        membership_id=context.membership_id,
        roles=list(context.roles),
        permissions=sorted(context.permissions),
    )
