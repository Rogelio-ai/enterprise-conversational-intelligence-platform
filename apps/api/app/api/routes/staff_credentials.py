from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.identity import credential_administration


router = APIRouter(prefix='/identity/staff', tags=['identity-access'])


class ChangeStaffPasswordRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    new_password: SecretStr = Field(min_length=1, max_length=128)


class ChangeStaffPasswordResponse(BaseModel):
    target_membership_id: int
    status: Literal['CHANGED'] = 'CHANGED'
    sessions_revoked: int


@router.put(
    '/{target_membership_id}/password',
    response_model=ChangeStaffPasswordResponse,
)
async def change_staff_password(
    target_membership_id: Annotated[int, Path(gt=0)],
    payload: ChangeStaffPasswordRequest,
    request: Request,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_permission(credential_administration.PERMISSION)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChangeStaffPasswordResponse:
    try:
        result = await credential_administration.change_staff_password(
            db,
            tenant_id=context.tenant_id,
            actor_membership_id=context.membership_id,
            target_membership_id=target_membership_id,
            new_password=payload.new_password.get_secret_value(),
            password_minimum_length=request.app.state.settings.password_min_length,
            correlation_id=get_correlation_id(),
        )
    except credential_administration.StaffCredentialAuthorizationError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except credential_administration.StaffCredentialTargetNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except credential_administration.StaffCredentialPasswordPolicyError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except credential_administration.StaffCredentialTargetInvalidError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return ChangeStaffPasswordResponse(
        target_membership_id=result.target_membership_id,
        sessions_revoked=result.sessions_revoked,
    )
