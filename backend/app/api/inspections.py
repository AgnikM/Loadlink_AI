import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import PreTripInspection, Truck, Driver, User
from app.models.enums import TruckStatus, UserRole
from app.schemas.all_schemas import (
    PreTripInspectionIn, SafetyHoldClearIn, PreTripInspectionOut
)

router = APIRouter(prefix="/inspections", tags=["inspections"])

def _serialize_inspection(i: PreTripInspection) -> PreTripInspectionOut:
    truck_reg = i.truck.registration_no if i.truck else None
    driver_name = i.driver.user.name if i.driver and i.driver.user else None
    cleared_name = i.cleared_by.name if i.cleared_by else None

    return PreTripInspectionOut(
        id=i.id,
        truck_id=i.truck_id,
        truck_registration_no=truck_reg,
        driver_id=i.driver_id,
        driver_name=driver_name,
        inspected_at=i.inspected_at,
        tyres_ok=i.tyres_ok,
        brakes_ok=i.brakes_ok,
        lights_ok=i.lights_ok,
        indicators_ok=i.indicators_ok,
        mirrors_ok=i.mirrors_ok,
        steering_ok=i.steering_ok,
        engine_indicators_ok=i.engine_indicators_ok,
        oil_level_ok=i.oil_level_ok,
        coolant_level_ok=i.coolant_level_ok,
        documents_valid=i.documents_valid,
        cargo_securing_equipment_ok=i.cargo_securing_equipment_ok,
        critical_defect_found=i.critical_defect_found,
        defect_description=i.defect_description,
        inspection_evidence_photos=i.inspection_evidence_photos or [],
        safety_hold_triggered=i.safety_hold_triggered,
        safety_hold_cleared_by_name=cleared_name,
        safety_hold_cleared_at=i.safety_hold_cleared_at,
        repair_evidence_url=i.repair_evidence_url,
        clearance_notes=i.clearance_notes,
    )

@router.post("/pre-trip", response_model=PreTripInspectionOut)
async def submit_pre_trip_inspection(
    payload: PreTripInspectionIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    driver = current_user.driver_profile
    if not driver:
        q_d = select(Driver).where(Driver.user_id == current_user.id)
        driver = (await db.execute(q_d)).scalar_one_or_none()

    truck = await db.get(Truck, payload.truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    # Critical safety checks: Brakes, Tyres, Steering, or Cargo Securing
    critical_defect = (
        (not payload.brakes_ok) or
        (not payload.tyres_ok) or
        (not payload.steering_ok) or
        (not payload.cargo_securing_equipment_ok)
    )

    safety_hold = False
    if critical_defect:
        safety_hold = True
        truck.status = TruckStatus.SAFETY_HOLD

    insp = PreTripInspection(
        id=str(uuid.uuid4()),
        truck_id=payload.truck_id,
        driver_id=driver.id if driver else (truck.driver_id or "unassigned"),
        inspected_at=datetime.now(timezone.utc),
        tyres_ok=payload.tyres_ok,
        brakes_ok=payload.brakes_ok,
        lights_ok=payload.lights_ok,
        indicators_ok=payload.indicators_ok,
        mirrors_ok=payload.mirrors_ok,
        steering_ok=payload.steering_ok,
        engine_indicators_ok=payload.engine_indicators_ok,
        oil_level_ok=payload.oil_level_ok,
        coolant_level_ok=payload.coolant_level_ok,
        documents_valid=payload.documents_valid,
        cargo_securing_equipment_ok=payload.cargo_securing_equipment_ok,
        critical_defect_found=critical_defect,
        defect_description=payload.defect_description,
        inspection_evidence_photos=payload.inspection_evidence_photos,
        safety_hold_triggered=safety_hold,
    )
    db.add(insp)
    await db.commit()
    await db.refresh(insp)

    q = (
        select(PreTripInspection)
        .where(PreTripInspection.id == insp.id)
        .options(
            selectinload(PreTripInspection.truck),
            selectinload(PreTripInspection.driver).selectinload(Driver.user),
            selectinload(PreTripInspection.cleared_by),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_inspection(reloaded)

@router.get("/truck/{truck_id}", response_model=List[PreTripInspectionOut])
async def list_truck_inspections(
    truck_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(PreTripInspection)
        .where(PreTripInspection.truck_id == truck_id)
        .options(
            selectinload(PreTripInspection.truck),
            selectinload(PreTripInspection.driver).selectinload(Driver.user),
            selectinload(PreTripInspection.cleared_by),
        )
        .order_by(desc(PreTripInspection.inspected_at))
    )
    inspections = (await db.execute(q)).scalars().all()
    return [_serialize_inspection(i) for i in inspections]

@router.post("/{inspection_id}/clear-safety-hold", response_model=PreTripInspectionOut)
async def clear_safety_hold(
    inspection_id: str,
    payload: SafetyHoldClearIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Rule E: Only authorized fleet managers or inspectors/admin can clear a safety hold
    allowed_roles = [UserRole.FLEET_MANAGER, UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only authorized Fleet Managers or Compliance Officers can clear a safety hold.",
        )

    insp = await db.get(PreTripInspection, inspection_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection record not found")

    if not insp.safety_hold_triggered:
        raise HTTPException(status_code=400, detail="This inspection did not trigger a safety hold.")

    now = datetime.now(timezone.utc)
    insp.safety_hold_cleared_by_id = current_user.id
    insp.safety_hold_cleared_at = now
    insp.repair_evidence_url = payload.repair_evidence_url
    insp.clearance_notes = payload.clearance_notes

    # Release truck from SAFETY_HOLD
    truck = await db.get(Truck, insp.truck_id)
    if truck and truck.status == TruckStatus.SAFETY_HOLD:
        truck.status = TruckStatus.ONLINE_AVAILABLE

    await db.commit()

    q = (
        select(PreTripInspection)
        .where(PreTripInspection.id == inspection_id)
        .options(
            selectinload(PreTripInspection.truck),
            selectinload(PreTripInspection.driver).selectinload(Driver.user),
            selectinload(PreTripInspection.cleared_by),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_inspection(reloaded)
