from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_authenticated_context, get_db
from app.core.security import create_access_token, verify_password
from app.identity.usernames import normalize_username
from app.identity.auth_sessions import (
    ActiveStaffSessionConflict,
    close_staff_auth_session,
    create_staff_auth_session,
)
from app.models import Tenant, TenantMembership, User


router = APIRouter(prefix='/auth', tags=['auth'])
_DUMMY_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$uU8CX0/5qQg0XcGXgJzYVw$Zvmh0SIePCpIIxBUPuo7M/AADFTBbeKylDyRmziVBk4'


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('username')
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)


class LoginUserResponse(BaseModel):
    id: int
    username: str
    email: str | None
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
    username: str
    email: str | None
    display_name: str
    tenant_id: int
    membership_id: int
    authorized_location_ids: list[int]
    roles: list[str]
    permissions: list[str]
    location_authorities: list['LocationAuthorityResponse']


class LocationAuthorityResponse(BaseModel):
    location_id: int
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
    user_result = await db.execute(select(User).where(User.username == payload.username))
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
    if len(memberships) == 1:
        selected = memberships[0]
    elif len(memberships) > 1:
        raise HTTPException(status_code=409, detail='Multiple active memberships')
    else:
        raise _invalid_credentials()

    membership, tenant = selected
    try:
        auth_session = await create_staff_auth_session(
            db,
            user_id=user.id,
            tenant_id=tenant.id,
            membership_id=membership.id,
        )
    except ActiveStaffSessionConflict as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                'code': 'staff_already_logged_in',
                'message': 'Staff already has an active session',
            },
        ) from exc
    except ValueError as exc:
        await db.rollback()
        raise _invalid_credentials() from exc
    settings = request.app.state.settings
    access_token = create_access_token(
        settings=settings,
        user_id=user.id,
        tenant_id=tenant.id,
        membership_id=membership.id,
        session_id=auth_session.session_id,
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.auth_access_token_ttl_minutes * 60,
        user=LoginUserResponse(
            id=user.id, username=user.username, email=user.email,
            display_name=user.display_name,
        ),
        tenant=LoginTenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            membership_id=membership.id,
        ),
    )


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    del context
    await close_staff_auth_session(
        db, session_id=request.state.auth_session_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/me', response_model=CurrentUserResponse)
async def me(
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=context.user_id,
        username=context.username,
        email=context.email,
        display_name=context.display_name,
        tenant_id=context.tenant_id,
        membership_id=context.membership_id,
        authorized_location_ids=list(context.authorized_location_ids),
        roles=list(context.roles),
        permissions=sorted(context.permissions),
        location_authorities=[
            LocationAuthorityResponse(
                location_id=value.location_id,
                roles=list(value.roles), permissions=sorted(value.permissions),
            )
            for value in context.location_authorities
        ],
    )
