from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.identity import invitations


router = APIRouter(prefix='/identity/invitations', tags=['identity-invitations'])


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return invitations.normalize_email(value)


class InvitationCreateResponse(BaseModel):
    invitation_id: str
    email: str
    display_name: str
    expires_at: datetime
    acceptance_token: str


class InvitationAcceptRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    acceptance_token: SecretStr
    password: SecretStr


class ActivatedUserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    status: str


class InvitationRevocationResponse(BaseModel):
    invitation_id: str
    status: str


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post('', response_model=InvitationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: InvitationCreateRequest,
    request: Request,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('user.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationCreateResponse:
    try:
        result = await invitations.invite_identity(
            db, settings=request.app.state.settings,
            tenant_id=context.tenant_id,
            actor_membership_id=context.membership_id,
            email=payload.email, display_name=payload.display_name,
        )
    except invitations.IdentityInvitationError as exc:
        raise _conflict(exc) from exc
    value = result.invitation
    return InvitationCreateResponse(
        invitation_id=value.invitation_id, email=value.email,
        display_name=value.display_name, expires_at=value.expires_at,
        acceptance_token=result.acceptance_token,
    )


@router.post('/accept', response_model=ActivatedUserResponse)
async def accept_invitation(
    payload: InvitationAcceptRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActivatedUserResponse:
    try:
        result = await invitations.accept_invitation(
            db, settings=request.app.state.settings,
            acceptance_token=payload.acceptance_token.get_secret_value(),
            user_selected_password=payload.password.get_secret_value(),
        )
    except invitations.InvalidIdentityInvitationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except invitations.IdentityInvitationError as exc:
        raise _conflict(exc) from exc
    return ActivatedUserResponse.model_validate(
        result.user, from_attributes=True,
    )


@router.post(
    '/{invitation_id}/revoke', response_model=InvitationRevocationResponse,
)
async def revoke_invitation(
    invitation_id: Annotated[str, Path(min_length=36, max_length=36)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('user.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationRevocationResponse:
    try:
        result = await invitations.revoke_invitation(
            db, tenant_id=context.tenant_id,
            actor_membership_id=context.membership_id,
            invitation_id=invitation_id,
        )
    except invitations.IdentityInvitationError as exc:
        raise _conflict(exc) from exc
    return InvitationRevocationResponse(
        invitation_id=result.invitation.invitation_id,
        status='REVOKED',
    )
