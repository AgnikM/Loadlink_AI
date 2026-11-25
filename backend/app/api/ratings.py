from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import Rating, Shipment, User, Driver, Dealer
from app.models.enums import UserRole, ShipmentState
from app.schemas.all_schemas import RatingCreate, RatingOut
from app.services.trust_service import trust_service

router = APIRouter(prefix="/ratings", tags=["ratings"])

@router.post("", response_model=RatingOut)
async def submit_rating(
    req: RatingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch shipment
    q = (
        select(Shipment)
        .where(Shipment.id == req.shipment_id)
        .options(
            selectinload(Shipment.dealer).selectinload(Dealer.user),
            selectinload(Shipment.driver).selectinload(Driver.user),
        )
    )
    res = await db.execute(q)
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    if s.state not in [ShipmentState.COMPLETED, ShipmentState.DELIVERED, ShipmentState.POD_SUBMITTED]:
        raise HTTPException(status_code=400, detail="Cannot rate until shipment is delivered or completed.")

    # Duplicate rating check: Check if current user already rated this shipment
    q_existing = select(Rating).where(
        Rating.shipment_id == s.id,
        Rating.rater_user_id == current_user.id
    )
    res_existing = await db.execute(q_existing)
    if res_existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already submitted a rating for this shipment.",
        )

    # Determine rated counterparty
    if current_user.role == UserRole.DEALER:
        if not s.dealer or s.dealer.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to rate for this shipment")
        rated_user_id = s.driver.user_id if s.driver else current_user.id
    elif current_user.role == UserRole.DRIVER:
        if not s.driver or s.driver.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to rate for this shipment")
        rated_user_id = s.dealer.user_id if s.dealer else current_user.id
    else:
        # Admin
        rated_user_id = s.driver.user_id if s.driver else current_user.id

    rating = Rating(
        shipment_id=s.id,
        rater_user_id=current_user.id,
        rated_user_id=rated_user_id,
        score=req.score,
        tags=req.tags,
        comment=req.comment,
    )
    db.add(rating)
    await db.flush()

    # Recalculate trust scores dynamically with empirical events
    if s.driver:
        await trust_service.recalculate_driver_reliability(db, s.driver_id)
    if s.dealer:
        await trust_service.recalculate_dealer_trust(db, s.dealer_id)

    await db.commit()
    await db.refresh(rating)

    return RatingOut(
        id=rating.id,
        shipment_id=rating.shipment_id,
        rater_name=current_user.name,
        score=rating.score,
        tags=rating.tags or [],
        comment=rating.comment,
        created_at=rating.created_at,
    )
