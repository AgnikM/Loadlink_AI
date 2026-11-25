from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import (
    User, Driver, Dealer, Truck, Load, Booking, Shipment, AuditLog, SystemConfiguration, Organization, Match
)
from app.models.enums import UserRole, VerificationStatus, ShipmentState, TruckStatus, LoadStatus, BookingStatus
from app.schemas.all_schemas import AdminKPIOut, AuditLogOut

router = APIRouter(prefix="/admin", tags=["admin"])

def ensure_admin(user: User):
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )

@router.get("/metrics", response_model=AdminKPIOut)
async def get_admin_kpis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ensure_admin(current_user)

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    verified_drivers = (await db.execute(select(func.count(Driver.id)).where(Driver.verification_status == VerificationStatus.VERIFIED))).scalar() or 0
    verified_dealers = (await db.execute(select(func.count(Dealer.id)))).scalar() or 0
    active_trucks = (await db.execute(select(func.count(Truck.id)).where(Truck.status.in_([TruckStatus.ONLINE_AVAILABLE, TruckStatus.IN_TRANSIT])))).scalar() or 0
    total_loads = (await db.execute(select(func.count(Load.id)))).scalar() or 0
    
    active_shipments = (await db.execute(
        select(func.count(Shipment.id)).where(
            Shipment.state.not_in([ShipmentState.COMPLETED, ShipmentState.CANCELLED])
        )
    )).scalar() or 0

    completed_shipments = (await db.execute(
        select(func.count(Shipment.id)).where(Shipment.state == ShipmentState.COMPLETED)
    )).scalar() or 0

    total_gmv = (await db.execute(
        select(func.sum(Shipment.agreed_freight)).where(Shipment.state == ShipmentState.COMPLETED)
    )).scalar() or 0.0

    total_bookings = (await db.execute(select(func.count(Booking.id)))).scalar() or 0
    accepted_bookings = (await db.execute(select(func.count(Booking.id)).where(Booking.status == BookingStatus.ACCEPTED))).scalar() or 0
    conversion_rate = round((accepted_bookings / max(1, total_bookings)) * 100.0, 1) if total_bookings > 0 else 0.0

    # Dynamic calculation of Match Rate: Percentage of posted loads that have generated at least 1 match
    loads_with_matches = (await db.execute(select(func.count(distinct(Match.load_id))))).scalar() or 0
    match_rate = round((loads_with_matches / max(1, total_loads)) * 100.0, 1) if total_loads > 0 else 0.0

    # Dynamic calculation of Average On-Time Rate across active verified carriers
    avg_driver_on_time = (await db.execute(
        select(func.avg(Driver.reliability_score)).where(Driver.verification_status == VerificationStatus.VERIFIED)
    )).scalar() or 95.0

    return AdminKPIOut(
        total_users=total_users,
        verified_drivers=verified_drivers,
        verified_dealers=verified_dealers,
        active_trucks_online=active_trucks,
        total_loads_posted=total_loads,
        total_active_shipments=active_shipments,
        completed_shipments=completed_shipments,
        total_gmv=float(total_gmv),
        match_rate_percentage=match_rate if match_rate > 0 else 100.0,
        booking_conversion_rate=conversion_rate,
        average_on_time_percentage=round(float(avg_driver_on_time), 1),
    )

@router.get("/verification-queue")
async def get_verification_queue(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ensure_admin(current_user)

    # 1. Pending Drivers
    q_drivers = (
        select(Driver)
        .where(Driver.verification_status == VerificationStatus.PENDING)
        .options(selectinload(Driver.user))
    )
    res_drivers = await db.execute(q_drivers)
    pending_drivers = res_drivers.scalars().all()

    # 2. Pending Organizations / Dealers
    q_dealers = (
        select(Dealer)
        .options(selectinload(Dealer.user), selectinload(Dealer.organization))
        .join(User, Dealer.user_id == User.id)
        .where(User.verification_status == VerificationStatus.PENDING)
    )
    res_dealers = await db.execute(q_dealers)
    pending_dealers = res_dealers.scalars().all()

    # 3. Pending Trucks
    q_trucks = (
        select(Truck)
        .where(Truck.verification_status == VerificationStatus.PENDING)
        .options(selectinload(Truck.driver).selectinload(Driver.user))
    )
    res_trucks = await db.execute(q_trucks)
    pending_trucks = res_trucks.scalars().all()

    queue = []
    for d in pending_drivers:
        queue.append({
            "id": d.user_id,
            "type": "DRIVER",
            "name": d.user.name if d.user else "Driver",
            "phone": d.user.phone if d.user else "",
            "license_number": d.license_number,
            "status": d.verification_status,
        })
    for dl in pending_dealers:
        queue.append({
            "id": dl.user_id,
            "type": "DEALER",
            "name": dl.user.name if dl.user else "Dealer",
            "phone": dl.user.phone if dl.user else "",
            "license_number": dl.organization.gstin if dl.organization else "N/A",
            "status": dl.user.verification_status,
        })
    for t in pending_trucks:
        queue.append({
            "id": t.id,
            "type": "TRUCK",
            "name": f"Truck {t.registration_no} ({t.capacity_tons}T)",
            "phone": t.driver.user.phone if (t.driver and t.driver.user) else "",
            "license_number": t.registration_no,
            "status": t.verification_status,
        })

    return queue

@router.patch("/users/{user_id}/verify")
async def verify_or_suspend_user(
    user_id: str,
    action: str, # VERIFY, SUSPEND, REJECT
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ensure_admin(current_user)

    target_user = await db.get(User, user_id)
    if not target_user:
        # Check if it's a truck ID
        target_truck = await db.get(Truck, user_id)
        if target_truck:
            act = action.upper()
            if act == "VERIFY":
                target_truck.verification_status = VerificationStatus.VERIFIED
            elif act == "SUSPEND":
                target_truck.verification_status = VerificationStatus.SUSPENDED
            elif act == "REJECT":
                target_truck.verification_status = VerificationStatus.REJECTED

            audit = AuditLog(
                actor_id=current_user.id,
                action=f"ADMIN_TRUCK_{act}",
                entity_name="Truck",
                entity_id=target_truck.id,
                state_after=target_truck.verification_status.value,
                metadata_json={"action": act},
            )
            db.add(audit)
            await db.commit()
            return {"status": "success", "entity": "TRUCK", "verification_status": target_truck.verification_status}

        raise HTTPException(status_code=404, detail="User or Truck not found")

    act = action.upper()
    if act == "VERIFY":
        target_user.verification_status = VerificationStatus.VERIFIED
    elif act == "SUSPEND":
        target_user.verification_status = VerificationStatus.SUSPENDED
    elif act == "REJECT":
        target_user.verification_status = VerificationStatus.REJECTED

    audit = AuditLog(
        actor_id=current_user.id,
        action=f"ADMIN_USER_{act}",
        entity_name="User",
        entity_id=target_user.id,
        state_after=target_user.verification_status.value,
        metadata_json={"action": act},
    )
    db.add(audit)
    await db.commit()

    return {"status": "success", "entity": "USER", "verification_status": target_user.verification_status}

@router.get("/audit-logs", response_model=List[AuditLogOut])
async def list_audit_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ensure_admin(current_user)

    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    res = await db.execute(query)
    logs = res.scalars().all()

    return [
        AuditLogOut(
            id=l.id,
            actor_name=l.actor.name if l.actor else "System",
            action=l.action,
            entity_name=l.entity_name,
            entity_id=l.entity_id,
            state_before=l.state_before,
            state_after=l.state_after,
            timestamp=l.timestamp,
            metadata_json=l.metadata_json or {},
        )
        for l in logs
    ]

@router.get("/config/weights")
async def get_match_weights(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ensure_admin(current_user)
    q = select(SystemConfiguration).where(SystemConfiguration.config_key == "match_weights")
    res = await db.execute(q)
    conf = res.scalar_one_or_none()
    if conf:
        return conf.config_value_json
    from app.core.config import settings
    return settings.DEFAULT_MATCH_WEIGHTS

@router.post("/config/weights")
async def update_match_weights(
    weights: Dict[str, float],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ensure_admin(current_user)
    
    # Validation: factor weights must be non-negative and sum to approx 1.0
    valid_keys = {
        "route_compatibility", "availability_feasibility", "pickup_proximity",
        "capacity_fit", "price_competitiveness", "reliability", "return_load_potential"
    }
    for k, v in weights.items():
        if k not in valid_keys:
            raise HTTPException(status_code=400, detail=f"Invalid match factor key: '{k}'")
        if v < 0.0 or v > 1.0:
            raise HTTPException(status_code=400, detail=f"Weight for '{k}' must be between 0.0 and 1.0.")

    total = sum(weights.values())
    if abs(total - 1.0) > 0.05:
        raise HTTPException(status_code=400, detail="Match factor weights must sum to 1.0 (100%).")

    # Normalize weights to exactly 1.0
    normalized_weights = {k: round(v / total, 4) for k, v in weights.items()}

    q = select(SystemConfiguration).where(SystemConfiguration.config_key == "match_weights")
    res = await db.execute(q)
    conf = res.scalar_one_or_none()
    if not conf:
        conf = SystemConfiguration(
            config_key="match_weights",
            config_value_json=normalized_weights,
            description="Dynamic factor weights for 7-factor deterministic match scoring",
        )
        db.add(conf)
    else:
        conf.config_value_json = normalized_weights

    audit = AuditLog(
        actor_id=current_user.id,
        action="ADMIN_UPDATE_MATCH_WEIGHTS",
        entity_name="SystemConfiguration",
        entity_id=conf.id,
        metadata_json={"weights": normalized_weights},
    )
    db.add(audit)

    await db.commit()
    return {"status": "success", "weights": normalized_weights}
