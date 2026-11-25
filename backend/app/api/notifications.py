from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("")
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    res = await db.execute(query)
    notifs = res.scalars().all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "payload": n.payload,
            "read_at": n.read_at,
            "created_at": n.created_at,
        }
        for n in notifs
    ]

@router.patch("/{notif_id}/read")
async def mark_as_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(Notification.id == notif_id, Notification.user_id == current_user.id)
        .values(read_at=now)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "success"}
