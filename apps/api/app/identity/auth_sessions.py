from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StaffAuthSession, User


class ActiveStaffSessionConflict(Exception):
    pass


async def create_staff_auth_session(
    db: AsyncSession,
    *,
    user_id: int,
    tenant_id: int,
    membership_id: int,
) -> StaffAuthSession:
    locked_user = await db.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if locked_user is None or locked_user.status != 'ACTIVE':
        raise ValueError('Staff identity is not active')

    active_session = await db.scalar(
        select(StaffAuthSession.id)
        .where(
            StaffAuthSession.user_id == user_id,
            StaffAuthSession.status == 'ACTIVE',
            StaffAuthSession.active_slot == 1,
        )
        .with_for_update()
    )
    if active_session is not None:
        raise ActiveStaffSessionConflict

    session = StaffAuthSession(
        session_id=str(uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        membership_id=membership_id,
        status='ACTIVE',
        active_slot=1,
    )
    db.add(session)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if 'uq_staff_auth_sessions_user_active' in str(exc):
            raise ActiveStaffSessionConflict from exc
        raise
    return session


async def close_staff_auth_session(
    db: AsyncSession,
    *,
    session_id: str,
) -> None:
    await db.execute(
        update(StaffAuthSession)
        .where(
            StaffAuthSession.session_id == session_id,
            StaffAuthSession.status == 'ACTIVE',
            StaffAuthSession.active_slot == 1,
        )
        .values(
            status='CLOSED',
            active_slot=None,
            closed_at=func.current_timestamp(),
        )
    )
    await db.commit()
