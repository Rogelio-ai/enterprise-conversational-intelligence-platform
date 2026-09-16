from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_authenticated_context, get_db
from app.onboarding.analyzer import analyze_xlsx
from app.onboarding.importer import ImportRejectedError, confirm_import, coverage, dataset_fingerprint


router = APIRouter(prefix='/onboarding/stage0', tags=['onboarding'])
XLSX_MEDIA_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


@router.get('/coverage')
async def import_coverage(
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
) -> dict:
    return {'groups': coverage()}


@router.post('/analyze')
async def analyze(
    content: Annotated[bytes, Body(media_type=XLSX_MEDIA_TYPE, max_length=10 * 1024 * 1024)],
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    filename: Annotated[str | None, Header(alias='X-Filename')] = None,
) -> dict:
    analysis = analyze_xlsx(content, filename=filename)
    return {'dataset_fingerprint': dataset_fingerprint(analysis), 'analysis': analysis.to_dict()}


@router.post('/confirm')
async def confirm(
    request: Request,
    response: Response,
    content: Annotated[bytes, Body(media_type=XLSX_MEDIA_TYPE, max_length=10 * 1024 * 1024)],
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: Annotated[int, Query(gt=0)],
    expected_fingerprint: Annotated[str, Header(alias='X-Dataset-Fingerprint', min_length=64, max_length=64)],
    explicit_confirmation: Annotated[Literal['true'], Header(alias='X-Confirm-Import')],
    filename: Annotated[str | None, Header(alias='X-Filename')] = None,
) -> dict:
    del explicit_confirmation
    analysis = analyze_xlsx(content, filename=filename)
    try:
        result = await confirm_import(
            db, analysis=analysis, expected_fingerprint=expected_fingerprint,
            tenant_id=context.tenant_id, tenant_slug=context.tenant_slug,
            membership_id=context.membership_id, location_id=location_id,
            authorized_location_ids=context.authorized_location_ids,
            permissions=context.permissions,
            settings=request.app.state.settings,
        )
    except ImportRejectedError as exc:
        code = status.HTTP_403_FORBIDDEN if exc.code in {
            'UNAUTHORIZED_SCOPE', 'INSUFFICIENT_PERMISSION'
        } else status.HTTP_409_CONFLICT
        if exc.code == 'INVALID_ANALYSIS':
            code = status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, {'code': exc.code, 'message': str(exc)}) from exc
    response.status_code = status.HTTP_200_OK if result['replay'] else status.HTTP_201_CREATED
    return result
