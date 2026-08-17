from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthenticatedContext, require_permission


router = APIRouter(prefix='/tenants', tags=['tenants'])


class CurrentTenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    status: str


@router.get('/current', response_model=CurrentTenantResponse)
async def current_tenant(
    context: Annotated[AuthenticatedContext, Depends(require_permission('tenant.read'))],
) -> CurrentTenantResponse:
    return CurrentTenantResponse(
        id=context.tenant_id,
        name=context.tenant_name,
        slug=context.tenant_slug,
        status='ACTIVE',
    )
