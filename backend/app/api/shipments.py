from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import (
    Shipment, Load, Truck, Driver, Dealer, User, POD, TruckLocation
)
from app.models.enums import UserRole, ShipmentState
from app.schemas.all_schemas import (
    ShipmentOut, StateTransitionRequest, ReturnLoadOpportunity
)
from app.services.state_machine import state_machine
from app.services.return_load_service import return_load_service

router = APIRouter(prefix="/shipments", tags=["shipments"])

def serialize_shipment(s: Shipment) -> ShipmentOut:
    now = datetime.now(timezone.utc)
    is_stale = False
    if s.truck and s.truck.last_location_time:
        loc_time = s.truck.last_location_time.replace(tzinfo=timezone.utc) if s.truck.last_location_time.tzinfo is None else s.truck.last_location_time
        if (now - loc_time).total_seconds() > 900:  # 15 minutes stale threshold
            is_stale = True

    return ShipmentOut(
        id=s.id,
        booking_id=s.booking_id,
        load_id=s.load_id,
        truck_id=s.truck_id,
        truck_registration_no=s.truck.registration_no if s.truck else None,
        truck_type=s.truck.truck_type if s.truck else None,
        driver_id=s.driver_id,
        driver_name=s.driver.user.name if (s.driver and s.driver.user) else None,
        driver_phone=s.driver.user.phone if (s.driver and s.driver.user) else None,
        dealer_id=s.dealer_id,
        dealer_name=s.dealer.user.name if (s.dealer and s.dealer.user) else None,
        state=s.state,
        origin_name=s.load.origin_name if s.load else "Origin",
        origin_lat=s.load.origin_lat if s.load else 22.5448,
        origin_lon=s.load.origin_lon if s.load else 88.3186,
        destination_name=s.load.destination_name if s.load else "Destination",
        destination_lat=s.load.destination_lat if s.load else 23.5204,
        destination_lon=s.load.destination_lon if s.load else 87.3119,
        cargo_type=s.load.cargo_type if s.load else "Industrial",
        cargo_weight_tons=s.load.cargo_weight_tons if s.load else 15.0,
        agreed_freight=s.agreed_freight,
        distance_km=s.distance_km,
        pickup_eta=s.pickup_eta,
        delivery_eta=s.delivery_eta,
        actual_pickup_time=s.actual_pickup_time,
        actual_delivery_time=s.actual_delivery_time,
        current_lat=s.truck.current_lat if s.truck else None,
        current_lon=s.truck.current_lon if s.truck else None,
        last_location_time=s.truck.last_location_time if s.truck else None,
        is_location_stale=is_stale,
        created_at=s.created_at,
        updated_at=s.updated_at,
        has_pod=s.pod is not None,
        pod_verification_status=s.pod.verification_status if s.pod else None,
    )

@router.get("", response_model=List[ShipmentOut])
async def list_shipments(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Shipment)
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver).selectinload(Driver.user),
            selectinload(Shipment.dealer).selectinload(Dealer.user),
            selectinload(Shipment.pod),
        )
        .order_by(Shipment.created_at.desc())
    )

    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        query = query.where(Shipment.dealer_id == current_user.dealer_profile.id)
    elif current_user.role == UserRole.DRIVER and current_user.driver_profile:
        query = query.where(Shipment.driver_id == current_user.driver_profile.id)

    query = query.limit(limit).offset(offset)
    res = await db.execute(query)
    shipments = res.scalars().all()
    return [serialize_shipment(s) for s in shipments]

@router.get("/{shipment_id}", response_model=ShipmentOut)
async def get_shipment_detail(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver).selectinload(Driver.user),
            selectinload(Shipment.dealer).selectinload(Dealer.user),
            selectinload(Shipment.pod),
        )
    )
    res = await db.execute(query)
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Security & RBAC Isolation: Only owner dealer, assigned driver, or admin
    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if s.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot access another dealer's private shipment.",
            )
    elif current_user.role == UserRole.DRIVER and current_user.driver_profile:
        if s.driver_id != current_user.driver_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not the assigned driver for this shipment.",
            )

    return serialize_shipment(s)

@router.patch("/{shipment_id}/status", response_model=ShipmentOut)
async def transition_shipment_state(
    shipment_id: str,
    req: StateTransitionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver).selectinload(Driver.user),
            selectinload(Shipment.dealer).selectinload(Dealer.user),
            selectinload(Shipment.pod),
        )
    )
    res = await db.execute(query)
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    updated_shipment = await state_machine.transition(
        session=db,
        shipment=s,
        target_state=req.target_state,
        actor_user=current_user,
        idempotency_key=req.idempotency_key,
        note=req.note,
    )

    await db.commit()
    await db.refresh(updated_shipment)
    return serialize_shipment(updated_shipment)

@router.get("/{shipment_id}/return-loads", response_model=List[ReturnLoadOpportunity])
async def get_return_loads_for_shipment(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
        )
    )
    res = await db.execute(query)
    s = res.scalar_one_or_none()
    if not s or not s.load or not s.truck:
        raise HTTPException(status_code=404, detail="Shipment or truck not found")

    # Security check: only assigned driver or admin
    if current_user.role == UserRole.DRIVER and current_user.driver_profile:
        if s.driver_id != current_user.driver_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only assigned driver can view return load discovery.",
            )

    # Only show return loads when nearing or at destination
    allowed_states = [
        ShipmentState.IN_TRANSIT,
        ShipmentState.NEAR_DESTINATION,
        ShipmentState.DELIVERED,
        ShipmentState.POD_SUBMITTED,
        ShipmentState.COMPLETED,
    ]
    if s.state not in allowed_states:
        return []

    opps = await return_load_service.find_return_loads(
        session=db,
        delivery_lat=s.load.destination_lat,
        delivery_lon=s.load.destination_lon,
        truck_capacity_tons=s.truck.capacity_tons,
        truck_type=s.truck.truck_type,
    )
    return opps
