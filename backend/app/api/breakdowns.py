import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import VehicleBreakdown, Truck, Driver, User, Shipment
from app.models.enums import BreakdownStatus, TruckStatus, UserRole
from app.schemas.all_schemas import (
    BreakdownReportIn, BreakdownAssignSupportIn, BreakdownResolveIn, VehicleBreakdownOut
)

router = APIRouter(prefix="/breakdowns", tags=["breakdowns"])

def _serialize_breakdown(b: VehicleBreakdown) -> VehicleBreakdownOut:
    truck_reg = b.truck.registration_no if b.truck else None
    driver_name = b.driver.user.name if b.driver and b.driver.user else None

    return VehicleBreakdownOut(
        id=b.id,
        truck_id=b.truck_id,
        truck_registration_no=truck_reg,
        driver_id=b.driver_id,
        driver_name=driver_name,
        shipment_id=b.shipment_id,
        issue_type=b.issue_type,
        description=b.description,
        photo_url=b.photo_url,
        video_url=b.video_url,
        latitude=b.latitude,
        longitude=b.longitude,
        device_timestamp=b.device_timestamp,
        reported_at=b.reported_at,
        status=b.status,
        assigned_mechanic_or_service=b.assigned_mechanic_or_service,
        estimated_repair_hours=b.estimated_repair_hours,
        resolution_notes=b.resolution_notes,
        resolved_at=b.resolved_at,
    )

@router.post("/report", response_model=VehicleBreakdownOut)
async def report_breakdown(
    payload: BreakdownReportIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Driver or authorized operator reports breakdown
    driver = current_user.driver_profile
    if not driver:
        q_d = select(Driver).where(Driver.user_id == current_user.id)
        driver = (await db.execute(q_d)).scalar_one_or_none()

    truck = await db.get(Truck, payload.truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    # Mark truck as MAINTENANCE
    truck.status = TruckStatus.MAINTENANCE
    if payload.latitude and payload.longitude:
        truck.current_lat = payload.latitude
        truck.current_lon = payload.longitude
        truck.last_location_time = datetime.now(timezone.utc)

    breakdown = VehicleBreakdown(
        id=str(uuid.uuid4()),
        truck_id=payload.truck_id,
        driver_id=driver.id if driver else (truck.driver_id or "unassigned"),
        shipment_id=payload.shipment_id,
        issue_type=payload.issue_type,
        description=payload.description,
        photo_url=payload.photo_url,
        video_url=payload.video_url,
        latitude=payload.latitude,
        longitude=payload.longitude,
        device_timestamp=payload.device_timestamp,
        reported_at=datetime.now(timezone.utc),
        status=BreakdownStatus.REPORTED,
    )
    db.add(breakdown)
    await db.commit()
    await db.refresh(breakdown)

    q = (
        select(VehicleBreakdown)
        .where(VehicleBreakdown.id == breakdown.id)
        .options(
            selectinload(VehicleBreakdown.truck),
            selectinload(VehicleBreakdown.driver).selectinload(Driver.user),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_breakdown(reloaded)

@router.get("", response_model=List[VehicleBreakdownOut])
async def list_breakdowns(
    truck_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(VehicleBreakdown)
        .options(
            selectinload(VehicleBreakdown.truck),
            selectinload(VehicleBreakdown.driver).selectinload(Driver.user),
        )
        .order_by(desc(VehicleBreakdown.reported_at))
    )
    if truck_id:
        q = q.where(VehicleBreakdown.truck_id == truck_id)

    breakdowns = (await db.execute(q)).scalars().all()
    return [_serialize_breakdown(b) for b in breakdowns]

@router.get("/{breakdown_id}", response_model=VehicleBreakdownOut)
async def get_breakdown(
    breakdown_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(VehicleBreakdown)
        .where(VehicleBreakdown.id == breakdown_id)
        .options(
            selectinload(VehicleBreakdown.truck),
            selectinload(VehicleBreakdown.driver).selectinload(Driver.user),
        )
    )
    b = (await db.execute(q)).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Breakdown record not found")
    return _serialize_breakdown(b)

@router.post("/{breakdown_id}/assign-support", response_model=VehicleBreakdownOut)
async def assign_breakdown_support(
    breakdown_id: str,
    payload: BreakdownAssignSupportIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed_roles = [UserRole.FLEET_MANAGER, UserRole.CONTROL_ROOM, UserRole.ADMIN, UserRole.TRANSPORTER]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Fleet Managers, Control Room, or Transporters can dispatch support.",
        )

    b = await db.get(VehicleBreakdown, breakdown_id)
    if not b:
        raise HTTPException(status_code=404, detail="Breakdown record not found")

    b.assigned_mechanic_or_service = payload.assigned_mechanic_or_service
    b.estimated_repair_hours = payload.estimated_repair_hours
    b.status = BreakdownStatus.SUPPORT_ASSIGNED
    if payload.notes:
        b.resolution_notes = payload.notes

    await db.commit()

    q = (
        select(VehicleBreakdown)
        .where(VehicleBreakdown.id == breakdown_id)
        .options(
            selectinload(VehicleBreakdown.truck),
            selectinload(VehicleBreakdown.driver).selectinload(Driver.user),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_breakdown(reloaded)

@router.post("/{breakdown_id}/resolve", response_model=VehicleBreakdownOut)
async def resolve_breakdown(
    breakdown_id: str,
    payload: BreakdownResolveIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    b = await db.get(VehicleBreakdown, breakdown_id)
    if not b:
        raise HTTPException(status_code=404, detail="Breakdown record not found")

    truck = await db.get(Truck, b.truck_id)
    now = datetime.now(timezone.utc)
    b.resolved_at = now
    b.resolution_notes = payload.resolution_notes

    if payload.repaired_pending_inspection:
        b.status = BreakdownStatus.REPAIRED_PENDING_INSPECTION
        if truck:
            truck.status = TruckStatus.SAFETY_HOLD
    else:
        b.status = BreakdownStatus.RESOLVED
        if truck and truck.status in [TruckStatus.MAINTENANCE, TruckStatus.SAFETY_HOLD]:
            truck.status = TruckStatus.ONLINE_AVAILABLE

    await db.commit()

    q = (
        select(VehicleBreakdown)
        .where(VehicleBreakdown.id == breakdown_id)
        .options(
            selectinload(VehicleBreakdown.truck),
            selectinload(VehicleBreakdown.driver).selectinload(Driver.user),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_breakdown(reloaded)
