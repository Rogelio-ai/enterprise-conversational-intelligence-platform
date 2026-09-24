from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_authenticated_context, get_db
from app.identity import access_provisioning


router = APIRouter(prefix='/identity/access-provisioning', tags=['identity-access'])


class LocationGrantRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    organization_id: int = Field(gt=0)
    location_id: int = Field(gt=0)


class AccessProvisioningRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    user_id: int = Field(gt=0)
    role_name: str = Field(min_length=1, max_length=100)
    locations: list[LocationGrantRequest] = Field(min_length=1, max_length=100)


class StaffAccountProvisioningRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    role_name: str = Field(min_length=1, max_length=100)
    locations: list[LocationGrantRequest] = Field(min_length=1, max_length=100)


class LocationGrantResponse(BaseModel):
    organization_id: int
    location_id: int
    operation: str


class AccessProvisioningResponse(BaseModel):
    user_id: int
    membership_id: int
    membership_operation: str
    role_id: int
    role_name: str
    role_operation: str
    location_grants: list[LocationGrantResponse]


@router.post('', response_model=AccessProvisioningResponse)
async def provision_identity_access(
    payload: AccessProvisioningRequest,
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessProvisioningResponse:
    try:
        result = await access_provisioning.provision_access(
            db,
            tenant_id=context.tenant_id,
            actor_membership_id=context.membership_id,
            user_id=payload.user_id,
            role_name=payload.role_name,
            locations=tuple(
                access_provisioning.LocationGrantCandidate(
                    organization_id=value.organization_id,
                    location_id=value.location_id,
                )
                for value in payload.locations
            ),
        )
    except access_provisioning.AccessProvisioningAuthorizationError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except access_provisioning.AccessProvisioningError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AccessProvisioningResponse(
        user_id=result.membership.user_id,
        membership_id=result.membership.id,
        membership_operation=result.membership_operation,
        role_id=result.role.id,
        role_name=result.role.name,
        role_operation=result.role_operation,
        location_grants=[
            LocationGrantResponse(
                organization_id=value.organization_id,
                location_id=value.location_id,
                operation=value.operation,
            )
            for value in result.location_grants
        ],
    )


@router.post('/staff', response_model=AccessProvisioningResponse)
async def provision_staff_account(
    payload: StaffAccountProvisioningRequest,
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessProvisioningResponse:
    locations = tuple(
        access_provisioning.LocationGrantCandidate(
            organization_id=value.organization_id, location_id=value.location_id,
        )
        for value in payload.locations
    )
    try:
        result = await access_provisioning.provision_staff_account(
            db, tenant_id=context.tenant_id,
            actor_membership_id=context.membership_id,
            username=payload.username, password=payload.password,
            display_name=payload.display_name, email=payload.email,
            password_minimum_length=request.app.state.settings.password_min_length,
            role_name=payload.role_name, locations=locations,
        )
    except access_provisioning.AccessProvisioningAuthorizationError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except access_provisioning.AccessProvisioningError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AccessProvisioningResponse(
        user_id=result.membership.user_id,
        membership_id=result.membership.id,
        membership_operation=result.membership_operation,
        role_id=result.role.id, role_name=result.role.name,
        role_operation=result.role_operation,
        location_grants=[LocationGrantResponse(
            organization_id=value.organization_id,
            location_id=value.location_id, operation=value.operation,
        ) for value in result.location_grants],
    )
