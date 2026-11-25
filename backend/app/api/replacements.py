import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import (
    TruckReplacementWorkflow, Shipment, Truck, Driver, User, CustodyEvent, VehicleBreakdown
)
from app.models.enums import (
    ReplacementStatus, TruckStatus, ShipmentState, CustodyEventType, CargoCondition, UserRole
)
from app.schemas.all_schemas import (
    ReplacementInitiateIn, ReplacementApprovalIn, ReplacementCustodyTransferIn,
    TruckReplacementOut, TruckOut
)

router = APIRouter(prefix="/replacements", tags=["replacements"])

def _serialize_replacement(r: TruckReplacementWorkflow) -> TruckReplacementOut:
    orig_truck_reg = r.original_truck.registration_no if r.original_truck else None
    orig_driver_name = r.original_driver.user.name if r.original_driver and r.original_driver.user else None
    repl_truck_reg = r.replacement_truck.registration_no if r.replacement_truck else None
    repl_driver_name = r.replacement_driver.user.name if r.replacement_driver and r.replacement_driver.user else None

    return TruckReplacementOut(
        id=r.id,
        shipment_id=r.shipment_id,
        original_truck_id=r.original_truck_id,
        original_truck_reg=orig_truck_reg,
        original_driver_name=orig_driver_name,
        replacement_truck_id=r.replacement_truck_id,
        replacement_truck_reg=repl_truck_reg,
        replacement_driver_name=repl_driver_name,
        breakdown_id=r.breakdown_id,
        reason=r.reason,
        transporter_approved=r.transporter_approved,
        transporter_approved_at=r.transporter_approved_at,
        dealer_approved=r.dealer_approved,
        dealer_approved_at=r.dealer_approved_at,
        custody_transfer_verified=r.custody_transfer_verified,
        transfer_cargo_condition=r.transfer_cargo_condition,
        new_seal_number=r.new_seal_number,
        transfer_photos=r.transfer_photos or [],
        driver_acknowledgement=r.driver_acknowledgement,
        status=r.status,
        created_at=r.created_at,
        completed_at=r.completed_at,
    )

@router.get("/eligible-trucks", response_model=List[TruckOut])
async def get_eligible_replacement_trucks(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    shipment = await db.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Load shipment load requirements
    q_load = select(Shipment).where(Shipment.id == shipment_id).options(selectinload(Shipment.load))
    ship = (await db.execute(q_load)).scalar_one()
    min_capacity = ship.load.cargo_weight_tons if (ship.load and ship.load.cargo_weight_tons) else 10.0

    # Find trucks that are ONLINE_AVAILABLE with capacity >= min_capacity and has an assigned driver
    q_trucks = (
        select(Truck)
        .where(
            Truck.status.in_([TruckStatus.ONLINE_AVAILABLE, TruckStatus.AVAILABLE]),
            Truck.capacity_tons >= min_capacity,
            Truck.id != shipment.truck_id,
            Truck.driver_id.isnot(None),
        )
        .options(selectinload(Truck.driver).selectinload(Driver.user))
    )
    eligible = (await db.execute(q_trucks)).scalars().all()
    
    # Format as TruckOut
    res = []
    for t in eligible:
        driver_name = t.driver.user.name if (t.driver and t.driver.user) else None
        driver_phone = t.driver.user.phone if (t.driver and t.driver.user) else None
        res.append(
            TruckOut(
                id=t.id,
                driver_id=t.driver_id,
                driver_name=driver_name,
                driver_phone=driver_phone,
                driver_reliability_score=t.driver.reliability_score if t.driver else 95.0,
                registration_no=t.registration_no,
                truck_type=t.truck_type,
                capacity_tons=t.capacity_tons,
                status=t.status,
                verification_status=t.verification_status,
                current_lat=t.current_lat,
                current_lon=t.current_lon,
                current_location_name=t.current_location_name,
                last_location_time=t.last_location_time,
            )
        )
    return res

@router.post("/initiate", response_model=TruckReplacementOut)
async def initiate_truck_replacement(
    payload: ReplacementInitiateIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q_ship = (
        select(Shipment)
        .where(Shipment.id == payload.shipment_id)
        .options(selectinload(Shipment.truck), selectinload(Shipment.driver))
    )
    ship = (await db.execute(q_ship)).scalar_one_or_none()
    if not ship:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Mark broken truck as SAFETY_HOLD / MAINTENANCE
    orig_truck = ship.truck
    if orig_truck:
        orig_truck.status = TruckStatus.SAFETY_HOLD

    workflow = TruckReplacementWorkflow(
        id=str(uuid.uuid4()),
        shipment_id=payload.shipment_id,
        original_truck_id=ship.truck_id,
        original_driver_id=ship.driver_id,
        replacement_truck_id=payload.replacement_truck_id,
        replacement_driver_id=payload.replacement_driver_id,
        breakdown_id=payload.breakdown_id,
        reason=payload.reason,
        status=ReplacementStatus.PENDING_APPROVALS,
        created_at=datetime.now(timezone.utc),
    )
    db.add(workflow)
    await db.commit()

    q = (
        select(TruckReplacementWorkflow)
        .where(TruckReplacementWorkflow.id == workflow.id)
        .options(
            selectinload(TruckReplacementWorkflow.original_truck),
            selectinload(TruckReplacementWorkflow.original_driver).selectinload(Driver.user),
            selectinload(TruckReplacementWorkflow.replacement_truck),
            selectinload(TruckReplacementWorkflow.replacement_driver).selectinload(Driver.user),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_replacement(reloaded)

@router.post("/{replacement_id}/approve", response_model=TruckReplacementOut)
async def approve_replacement(
    replacement_id: str,
    payload: ReplacementApprovalIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    w = await db.get(TruckReplacementWorkflow, replacement_id)
    if not w:
        raise HTTPException(status_code=404, detail="Replacement workflow not found")

    now = datetime.now(timezone.utc)
    role = payload.approver_role.upper()
    if role in ["DEALER", "SHIPPER"] or current_user.role == UserRole.DEALER:
        w.dealer_approved = payload.approved
        w.dealer_approved_at = now
    elif role in ["TRANSPORTER", "FLEET_MANAGER"] or current_user.role in [UserRole.TRANSPORTER, UserRole.FLEET_MANAGER, UserRole.ADMIN]:
        w.transporter_approved = payload.approved
        w.transporter_approved_at = now
    else:
        # Control room / Admin can approve for both
        w.dealer_approved = True
        w.dealer_approved_at = now
        w.transporter_approved = True
        w.transporter_approved_at = now

    if w.dealer_approved and w.transporter_approved:
        w.status = ReplacementStatus.APPROVED

    await db.commit()

    q = (
        select(TruckReplacementWorkflow)
        .where(TruckReplacementWorkflow.id == replacement_id)
        .options(
            selectinload(TruckReplacementWorkflow.original_truck),
            selectinload(TruckReplacementWorkflow.original_driver).selectinload(Driver.user),
            selectinload(TruckReplacementWorkflow.replacement_truck),
            selectinload(TruckReplacementWorkflow.replacement_driver).selectinload(Driver.user),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_replacement(reloaded)

@router.post("/{replacement_id}/record-custody-transfer", response_model=TruckReplacementOut)
async def record_custody_transfer(
    replacement_id: str,
    payload: ReplacementCustodyTransferIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    w = await db.get(TruckReplacementWorkflow, replacement_id)
    if not w:
        raise HTTPException(status_code=404, detail="Replacement workflow not found")

    # Strict rule: "Do not silently transfer cargo to another truck without custody records."
    now = datetime.now(timezone.utc)
    w.custody_transfer_verified = True
    w.transfer_cargo_condition = payload.transfer_cargo_condition
    w.new_seal_number = payload.new_seal_number
    w.transfer_photos = payload.transfer_photos
    w.driver_acknowledgement = payload.driver_acknowledgement
    w.status = ReplacementStatus.CUSTODY_TRANSFERRED

    # Create auditable CustodyEvent
    custody_ev = CustodyEvent(
        id=str(uuid.uuid4()),
        shipment_id=w.shipment_id,
        event_type=CustodyEventType.TRANSIT_INCIDENT,
        seal_number=payload.new_seal_number,
        seal_intact=True,
        cargo_condition=payload.transfer_cargo_condition,
        photographs=payload.transfer_photos,
        location_name="Corridor Emergency Transfer Hub",
        driver_acknowledged=payload.driver_acknowledgement,
        driver_acknowledgement_time=now,
        driver_notes=f"Cargo transhipped from broken truck to replacement truck. New seal: {payload.new_seal_number}",
        recorded_by_user_id=current_user.id,
        created_at=now,
    )
    db.add(custody_ev)

    await db.commit()

    q = (
        select(TruckReplacementWorkflow)
        .where(TruckReplacementWorkflow.id == replacement_id)
        .options(
            selectinload(TruckReplacementWorkflow.original_truck),
            selectinload(TruckReplacementWorkflow.original_driver).selectinload(Driver.user),
            selectinload(TruckReplacementWorkflow.replacement_truck),
            selectinload(TruckReplacementWorkflow.replacement_driver).selectinload(Driver.user),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_replacement(reloaded)

@router.post("/{replacement_id}/complete", response_model=TruckReplacementOut)
async def complete_replacement(
    replacement_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    w = await db.get(TruckReplacementWorkflow, replacement_id)
    if not w:
        raise HTTPException(status_code=404, detail="Replacement workflow not found")

    if not w.custody_transfer_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete replacement: Custody transfer and seal verification must be recorded first.",
        )

    # Perform atomic reassignment of shipment to replacement truck and driver
    shipment = await db.get(Shipment, w.shipment_id)
    if shipment and w.replacement_truck_id and w.replacement_driver_id:
        shipment.truck_id = w.replacement_truck_id
        shipment.driver_id = w.replacement_driver_id

        # Update replacement truck status to IN_TRANSIT
        repl_truck = await db.get(Truck, w.replacement_truck_id)
        if repl_truck:
            repl_truck.status = TruckStatus.IN_TRANSIT

    now = datetime.now(timezone.utc)
    w.status = ReplacementStatus.COMPLETED
    w.completed_at = now

    await db.commit()

    q = (
        select(TruckReplacementWorkflow)
        .where(TruckReplacementWorkflow.id == replacement_id)
        .options(
            selectinload(TruckReplacementWorkflow.original_truck),
            selectinload(TruckReplacementWorkflow.original_driver).selectinload(Driver.user),
            selectinload(TruckReplacementWorkflow.replacement_truck),
            selectinload(TruckReplacementWorkflow.replacement_driver).selectinload(Driver.user),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_replacement(reloaded)
