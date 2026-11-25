import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user, get_current_user_optional
from app.models.entities import Truck, Driver, User, TruckLocation, VehicleAssignment, Organization, AuditLog
from app.models.enums import UserRole, TruckStatus, VerificationStatus, FleetOwnershipType
from app.schemas.all_schemas import (
    TruckCreate, TruckAvailabilityUpdate, TruckLocationUpdate, TruckOut,
    VehicleAssignmentCreate, VehicleAssignmentOut
)

router = APIRouter(prefix="/trucks", tags=["trucks"])

@router.post("", response_model=TruckOut)
async def create_truck(
    req: TruckCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    driver_id = req.driver_id
    driver_user = None
    org_id = req.organization_id
    ownership_type = req.ownership_type or FleetOwnershipType.EXTERNAL_TRANSPORTER

    if current_user:
        if current_user.role == UserRole.DRIVER and current_user.driver_profile:
            driver_id = current_user.driver_profile.id
            driver_user = current_user
            if current_user.driver_profile.organization_id:
                org_id = current_user.driver_profile.organization_id
        elif current_user.role == UserRole.TRANSPORTER and current_user.transporter_profile:
            org_id = current_user.transporter_profile.organization_id
            ownership_type = FleetOwnershipType.EXTERNAL_TRANSPORTER
        elif current_user.role == UserRole.FLEET_MANAGER:
            ownership_type = FleetOwnershipType.LOADLINK_OWNED
            if current_user.transporter_profile:
                org_id = current_user.transporter_profile.organization_id

    if not driver_id and not org_id:
        # Fallback to demo driver or first available driver in database if none supplied
        q_driver = select(Driver).options(selectinload(Driver.user))
        res_driver = await db.execute(q_driver)
        driver_obj = res_driver.scalars().first()
        if driver_obj:
            driver_id = driver_obj.id
            driver_user = driver_obj.user

    reg_no = req.registration_no or f"WB-19-{int(datetime.now().timestamp()) % 10000:04d}"

    # Check unique registration
    res = await db.execute(
        select(Truck)
        .where(Truck.registration_no == reg_no)
        .options(selectinload(Truck.driver).selectinload(Driver.user), selectinload(Truck.organization))
    )
    existing = res.scalar_one_or_none()
    if existing:
        return _build_truck_out(existing)

    truck = Truck(
        driver_id=driver_id,
        organization_id=org_id,
        ownership_type=ownership_type,
        registration_no=reg_no,
        truck_type=req.truck_type,
        capacity_tons=req.capacity_tons or 16.0,
        status=TruckStatus.ONLINE_AVAILABLE,
        verification_status=VerificationStatus.VERIFIED,
        current_lat=req.current_lat or 22.5448,
        current_lon=req.current_lon or 88.3186,
        current_location_name=req.current_location_name or "Kolkata Port / Docks",
        last_location_time=datetime.now(timezone.utc),
    )
    db.add(truck)
    await db.flush()

    # Record initial vehicle assignment if driver is assigned
    if driver_id:
        assignment = VehicleAssignment(
            truck_id=truck.id,
            driver_id=driver_id,
            assigned_by_user_id=current_user.id if current_user else None,
            is_active=True,
            assignment_notes="Initial truck registration assignment",
        )
        db.add(assignment)

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id if current_user else None,
        action="REGISTER_TRUCK",
        entity_name="Truck",
        entity_id=truck.id,
        state_after=truck.status.value,
        metadata_json={
            "registration_no": truck.registration_no,
            "ownership_type": ownership_type.value,
            "capacity_tons": truck.capacity_tons,
        },
    )
    db.add(audit)

    await db.commit()

    # Re-query with relations
    q_truck = (
        select(Truck)
        .where(Truck.id == truck.id)
        .options(selectinload(Truck.driver).selectinload(Driver.user), selectinload(Truck.organization))
    )
    truck_loaded = (await db.execute(q_truck)).scalar_one()
    return _build_truck_out(truck_loaded)

def _build_truck_out(t: Truck) -> TruckOut:
    return TruckOut(
        id=t.id,
        driver_id=t.driver_id,
        driver_name=t.driver.user.name if (t.driver and t.driver.user) else None,
        driver_phone=t.driver.user.phone if (t.driver and t.driver.user) else None,
        driver_reliability_score=t.driver.reliability_score if t.driver else None,
        ownership_type=t.ownership_type,
        organization_id=t.organization_id,
        organization_name=t.organization.name if t.organization else None,
        registration_no=t.registration_no,
        truck_type=t.truck_type,
        capacity_tons=t.capacity_tons,
        legal_payload_tons=t.legal_payload_tons,
        quoted_freight_inr=t.quoted_freight_inr,
        status=t.status,
        verification_status=t.verification_status,
        is_demo=bool(getattr(t, "is_demo", False)),
        current_lat=t.current_lat,
        current_lon=t.current_lon,
        current_location_name=t.current_location_name,
        last_location_time=t.last_location_time,
    )

@router.get("", response_model=List[TruckOut])
async def list_trucks(
    status_filter: Optional[TruckStatus] = None,
    ownership_type: Optional[FleetOwnershipType] = None,
    organization_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    query = select(Truck).options(
        selectinload(Truck.driver).selectinload(Driver.user),
        selectinload(Truck.organization),
    )

    if status_filter:
        query = query.where(Truck.status == status_filter)
    if ownership_type:
        query = query.where(Truck.ownership_type == ownership_type)
    if organization_id:
        query = query.where(Truck.organization_id == organization_id)

    # Scoping for Transporter / Fleet Manager if requested without explicit org filter
    if current_user and not organization_id:
        if current_user.role == UserRole.TRANSPORTER and current_user.transporter_profile and current_user.transporter_profile.organization_id:
            # Transporters see their fleet first
            pass
        elif current_user.role == UserRole.FLEET_MANAGER:
            # Fleet managers can see LoadLink owned fleet
            pass

    query = query.limit(limit).offset(offset)
    res = await db.execute(query)
    trucks = res.scalars().all()
    return [_build_truck_out(t) for t in trucks]

@router.get("/drivers")
async def list_drivers(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    query = select(Driver).options(selectinload(Driver.user))
    res = await db.execute(query)
    drivers = res.scalars().all()

    # Get active assignments
    q_assign = (
        select(VehicleAssignment)
        .where(VehicleAssignment.is_active == True)
        .options(selectinload(VehicleAssignment.truck))
    )
    res_assign = await db.execute(q_assign)
    active_assigns = {a.driver_id: a for a in res_assign.scalars().all()}

    out = []
    for d in drivers:
        active_a = active_assigns.get(d.id)
        out.append({
            "id": d.id,
            "user_id": d.user_id,
            "name": d.user.name if d.user else "Driver",
            "phone": d.user.phone if d.user else None,
            "email": d.user.email if d.user else None,
            "license_number": d.license_number,
            "reliability_score": d.reliability_score,
            "is_demo": bool(getattr(d, "is_demo", False)),
            "organization_id": d.organization_id,
            "is_assigned": active_a is not None,
            "active_truck_id": active_a.truck_id if active_a else None,
            "active_truck_reg": active_a.truck.registration_no if (active_a and active_a.truck) else None,
        })
    return out

@router.patch("/{truck_id}/availability", response_model=TruckOut)
async def update_truck_availability(
    truck_id: str,
    available: Optional[bool] = Query(None),
    req: Optional[TruckAvailabilityUpdate] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Truck)
        .where((Truck.id == truck_id) | (Truck.registration_no == truck_id))
        .options(
            selectinload(Truck.driver).selectinload(Driver.user),
            selectinload(Truck.organization),
        )
    )
    res = await db.execute(query)
    truck = res.scalar_one_or_none()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    # Authorize driver or transporter or fleet manager or admin
    if current_user:
        if current_user.role == UserRole.DRIVER:
            if current_user.driver_profile and truck.driver_id != current_user.driver_profile.id:
                raise HTTPException(status_code=403, detail="Not authorized to update this truck")
        elif current_user.role == UserRole.TRANSPORTER:
            if current_user.transporter_profile and truck.organization_id != current_user.transporter_profile.organization_id:
                raise HTTPException(status_code=403, detail="Not authorized to update a truck outside your transporter fleet")
        elif current_user.role == UserRole.FLEET_MANAGER:
            if truck.ownership_type != FleetOwnershipType.LOADLINK_OWNED and current_user.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Fleet Manager can only modify LoadLink owned fleet vehicles")

    before_state = truck.status.value

    if req and req.status:
        # If vehicle is placed in safety hold, verify authorization
        if req.status == TruckStatus.SAFETY_HOLD:
            if current_user and current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.CONTROL_ROOM]:
                raise HTTPException(status_code=403, detail="Only Compliance Officer, Control Room, or Admin can place vehicle on SAFETY_HOLD.")
        truck.status = req.status
    elif available is not None:
        truck.status = TruckStatus.ONLINE_AVAILABLE if available else TruckStatus.OFFLINE
    elif req and req.available is not None:
        truck.status = TruckStatus.ONLINE_AVAILABLE if req.available else TruckStatus.OFFLINE
    else:
        truck.status = TruckStatus.OFFLINE if truck.status in [TruckStatus.ONLINE_AVAILABLE, TruckStatus.AVAILABLE] else TruckStatus.ONLINE_AVAILABLE

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id if current_user else None,
        action="UPDATE_TRUCK_STATUS",
        entity_name="Truck",
        entity_id=truck.id,
        state_before=before_state,
        state_after=truck.status.value,
        metadata_json={"truck_reg": truck.registration_no},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(truck)
    return _build_truck_out(truck)

@router.post("/{truck_id}/assign", response_model=VehicleAssignmentOut)
async def assign_driver_to_truck(
    truck_id: str,
    req: VehicleAssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign driver to vehicle according to business rules:
    - Maintain driver-to-vehicle assignment history.
    - Prevent conflicting active assignments (at most 1 active assignment per truck, at most 1 per driver).
    """
    # 1. Fetch Truck
    q_truck = select(Truck).where((Truck.id == truck_id) | (Truck.registration_no == truck_id))
    truck = (await db.execute(q_truck)).scalar_one_or_none()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    # 1.5 Safety Hold & Transit Concurrency Guard
    if truck.status in [TruckStatus.IN_TRANSIT, TruckStatus.SAFETY_HOLD]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reassign vehicle: Truck is currently in state '{truck.status.value}'.",
        )

    # 2. Fetch Driver
    q_driver = select(Driver).where((Driver.id == req.driver_id) | (Driver.user_id == req.driver_id)).options(selectinload(Driver.user))
    driver = (await db.execute(q_driver)).scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # 3. Authorization check
    if current_user.role == UserRole.TRANSPORTER and current_user.transporter_profile:
        if truck.organization_id != current_user.transporter_profile.organization_id:
            raise HTTPException(status_code=403, detail="Cannot assign drivers to vehicles outside your transporter fleet")
    elif current_user.role == UserRole.FLEET_MANAGER:
        if truck.ownership_type != FleetOwnershipType.LOADLINK_OWNED and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Fleet Manager can only manage assignments for LoadLink owned vehicles")
    elif current_user.role not in [UserRole.ADMIN, UserRole.CONTROL_ROOM, UserRole.TRANSPORTER, UserRole.FLEET_MANAGER]:
        raise HTTPException(status_code=403, detail="Insufficient privileges to assign vehicle")

    # 3.5. Concurrency & Safety Hold Protection (Master Prompt 2.1 Task 5)
    if truck.status in [TruckStatus.IN_TRANSIT, TruckStatus.SAFETY_HOLD]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reassign vehicle: Truck is currently in state '{truck.status.value}'.",
        )

    from app.models.entities import Shipment
    from app.models.enums import ShipmentState

    q_truck_active = select(Shipment).where(
        Shipment.truck_id == truck.id,
        Shipment.state.in_([ShipmentState.DRIVER_EN_ROUTE, ShipmentState.ARRIVED_PICKUP, ShipmentState.IN_TRANSIT, ShipmentState.NEAR_DESTINATION])
    )
    if (await db.execute(q_truck_active)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reassign vehicle: Truck is actively engaged in an ongoing consignment.",
        )

    q_driver_active = select(Shipment).where(
        Shipment.driver_id == driver.id,
        Shipment.state.in_([ShipmentState.DRIVER_EN_ROUTE, ShipmentState.ARRIVED_PICKUP, ShipmentState.IN_TRANSIT, ShipmentState.NEAR_DESTINATION])
    )
    if (await db.execute(q_driver_active)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reassign driver: Driver is actively in transit with an ongoing consignment.",
        )

    now = datetime.now(timezone.utc)

    # 4. Resolve Conflicting Active Assignments
    # Deactivate existing active assignment on this truck
    q_curr_truck_assign = select(VehicleAssignment).where(
        VehicleAssignment.truck_id == truck.id,
        VehicleAssignment.is_active == True,
    )
    existing_truck_assigns = (await db.execute(q_curr_truck_assign)).scalars().all()
    for a in existing_truck_assigns:
        a.is_active = False
        a.unassigned_at = now

    # Deactivate existing active assignment for this driver on any other truck
    q_curr_driver_assign = select(VehicleAssignment).where(
        VehicleAssignment.driver_id == driver.id,
        VehicleAssignment.is_active == True,
    )
    existing_driver_assigns = (await db.execute(q_curr_driver_assign)).scalars().all()
    for a in existing_driver_assigns:
        a.is_active = False
        a.unassigned_at = now
        if a.truck_id != truck.id:
            q_other_truck = select(Truck).where(Truck.id == a.truck_id)
            other_truck = (await db.execute(q_other_truck)).scalar_one_or_none()
            if other_truck and other_truck.driver_id == driver.id:
                other_truck.driver_id = None

    # 5. Create new active assignment
    assign_id = str(uuid.uuid4())
    assignment = VehicleAssignment(
        id=assign_id,
        truck_id=truck.id,
        driver_id=driver.id,
        assigned_by_user_id=current_user.id,
        is_active=True,
        assigned_at=now,
        assignment_notes=req.assignment_notes or f"Assigned by {current_user.name}",
    )
    db.add(assignment)

    # 6. Update truck's active driver_id
    truck.driver_id = driver.id
    if truck.status == TruckStatus.OFFLINE:
        truck.status = TruckStatus.ONLINE_AVAILABLE

    # 7. Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        action="VEHICLE_ASSIGNMENT_CREATED",
        entity_name="VehicleAssignment",
        entity_id=assignment.id,
        state_after="ACTIVE",
        metadata_json={
            "truck_reg": truck.registration_no,
            "driver_name": driver.user.name if driver.user else "",
            "driver_license": driver.license_number,
        },
    )
    db.add(audit)

    await db.commit()
    await db.refresh(assignment)

    return VehicleAssignmentOut(
        id=assignment.id,
        truck_id=assignment.truck_id,
        truck_registration_no=truck.registration_no,
        driver_id=assignment.driver_id,
        driver_name=driver.user.name if driver.user else "Driver",
        driver_license=driver.license_number,
        driver_phone=driver.user.phone if driver.user else None,
        is_active=assignment.is_active,
        assigned_at=assignment.assigned_at,
        unassigned_at=assignment.unassigned_at,
        assignment_notes=assignment.assignment_notes,
        assigned_by_name=current_user.name,
    )

@router.post("/{truck_id}/unassign")
async def unassign_driver_from_truck(
    truck_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q_truck = select(Truck).where((Truck.id == truck_id) | (Truck.registration_no == truck_id))
    truck = (await db.execute(q_truck)).scalar_one_or_none()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    if truck.status in [TruckStatus.IN_TRANSIT, TruckStatus.SAFETY_HOLD]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot unassign vehicle: Truck is currently in status '{truck.status.value}'.",
        )

    from app.models.entities import Shipment
    from app.models.enums import ShipmentState
    q_truck_active = select(Shipment).where(
        Shipment.truck_id == truck.id,
        Shipment.state.in_([ShipmentState.DRIVER_EN_ROUTE, ShipmentState.ARRIVED_PICKUP, ShipmentState.IN_TRANSIT, ShipmentState.NEAR_DESTINATION])
    )
    if (await db.execute(q_truck_active)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot unassign vehicle: Truck is actively engaged in an ongoing consignment.",
        )

    now = datetime.now(timezone.utc)
    q_curr = select(VehicleAssignment).where(
        VehicleAssignment.truck_id == truck.id,
        VehicleAssignment.is_active == True,
    )
    active_assigns = (await db.execute(q_curr)).scalars().all()
    for a in active_assigns:
        a.is_active = False
        a.unassigned_at = now

    truck.driver_id = None
    audit = AuditLog(
        actor_id=current_user.id,
        action="VEHICLE_UNASSIGNED",
        entity_name="Truck",
        entity_id=truck.id,
        state_after="UNASSIGNED",
        metadata_json={"truck_reg": truck.registration_no},
    )
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": f"Truck {truck.registration_no} unassigned from driver"}

@router.get("/{truck_id}/assignments", response_model=List[VehicleAssignmentOut])
async def list_truck_assignment_history(
    truck_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q_truck = select(Truck).where((Truck.id == truck_id) | (Truck.registration_no == truck_id))
    truck = (await db.execute(q_truck)).scalar_one_or_none()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    query = (
        select(VehicleAssignment)
        .where(VehicleAssignment.truck_id == truck.id)
        .options(
            selectinload(VehicleAssignment.driver).selectinload(Driver.user),
            selectinload(VehicleAssignment.assigned_by),
        )
        .order_by(VehicleAssignment.assigned_at.desc())
    )
    res = await db.execute(query)
    assigns = res.scalars().all()

    return [
        VehicleAssignmentOut(
            id=a.id,
            truck_id=a.truck_id,
            truck_registration_no=truck.registration_no,
            driver_id=a.driver_id,
            driver_name=a.driver.user.name if (a.driver and a.driver.user) else None,
            driver_license=a.driver.license_number if a.driver else None,
            driver_phone=a.driver.user.phone if (a.driver and a.driver.user) else None,
            is_active=a.is_active,
            assigned_at=a.assigned_at,
            unassigned_at=a.unassigned_at,
            assignment_notes=a.assignment_notes,
            assigned_by_name=a.assigned_by.name if a.assigned_by else None,
        )
        for a in assigns
    ]

@router.patch("/{truck_id}/safety-hold", response_model=TruckOut)
async def toggle_safety_hold(
    truck_id: str,
    hold: bool = Query(True),
    reason: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.CONTROL_ROOM]:
        raise HTTPException(
            status_code=403,
            detail="Administrative, Compliance, or Control Room authorization required for SAFETY_HOLD.",
        )

    q = select(Truck).where((Truck.id == truck_id) | (Truck.registration_no == truck_id)).options(
        selectinload(Truck.driver).selectinload(Driver.user),
        selectinload(Truck.organization),
    )
    truck = (await db.execute(q)).scalar_one_or_none()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    before = truck.status.value
    truck.status = TruckStatus.SAFETY_HOLD if hold else TruckStatus.ONLINE_AVAILABLE

    audit = AuditLog(
        actor_id=current_user.id,
        action="TRUCK_SAFETY_HOLD_APPLIED" if hold else "TRUCK_SAFETY_HOLD_RELEASED",
        entity_name="Truck",
        entity_id=truck.id,
        state_before=before,
        state_after=truck.status.value,
        metadata_json={"reason": reason or "Compliance or mechanical safety inspection required"},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(truck)
    return _build_truck_out(truck)

@router.post("/{truck_id}/locations")
async def submit_truck_location(
    truck_id: str,
    req: TruckLocationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # GPS coordinate validation
    if not (-90 <= req.latitude <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90.")
    if not (-180 <= req.longitude <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180.")

    query = (
        select(Truck)
        .where(Truck.id == truck_id)
        .options(selectinload(Truck.driver).selectinload(Driver.user))
    )
    res = await db.execute(query)
    truck = res.scalar_one_or_none()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    if current_user.role == UserRole.DRIVER:
        if not current_user.driver_profile or truck.driver_id != current_user.driver_profile.id:
            raise HTTPException(status_code=403, detail="Not authorized to update location for this truck")

    now = datetime.now(timezone.utc)
    truck.current_lat = req.latitude
    truck.current_lon = req.longitude
    if req.location_name:
        truck.current_location_name = req.location_name
    truck.last_location_time = now

    loc_record = TruckLocation(
        truck_id=truck.id,
        latitude=req.latitude,
        longitude=req.longitude,
        speed_kmh=req.speed_kmh or 0.0,
        heading=req.heading or 0.0,
        accuracy_meters=req.accuracy_meters or 5.0,
        source=req.source or "GPS",
        recorded_at=now,
    )
    db.add(loc_record)
    await db.commit()

    return {"status": "success", "recorded_at": now}
