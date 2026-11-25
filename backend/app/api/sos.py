from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import SOSEvent, User, Driver, Truck, Shipment
from app.models.enums import UserRole, SOSStatus
from app.schemas.all_schemas import SOSTriggerIn, SOSActionIn, SOSEventOut
from app.services.sos_service import sos_service

router = APIRouter(prefix="/sos", tags=["sos"])

def _serialize_sos(sos: SOSEvent) -> SOSEventOut:
    driver_name = sos.driver.user.name if sos.driver and sos.driver.user else None
    driver_phone = sos.driver.user.phone if sos.driver and sos.driver.user else None
    truck_reg = sos.truck.registration_no if sos.truck else None
    responder_name = sos.assigned_responder.name if sos.assigned_responder else None

    return SOSEventOut(
        id=sos.id,
        event_id=sos.event_id,
        driver_id=sos.driver_id,
        driver_name=driver_name,
        driver_phone=driver_phone,
        truck_id=sos.truck_id,
        truck_registration_no=truck_reg,
        shipment_id=sos.shipment_id,
        booking_id=sos.booking_id,
        latitude=sos.latitude,
        longitude=sos.longitude,
        accuracy_meters=sos.accuracy_meters,
        incident_category=sos.incident_category,
        network_status=sos.network_status,
        device_timestamp=sos.device_timestamp,
        server_timestamp=sos.server_timestamp,
        status=sos.status,
        control_room_notified=sos.control_room_notified,
        control_room_notified_at=sos.control_room_notified_at,
        dealer_notified=sos.dealer_notified,
        dealer_notified_at=sos.dealer_notified_at,
        emergency_contact_name=sos.emergency_contact_name,
        emergency_contact_phone=sos.emergency_contact_phone,
        emergency_contact_notified=sos.emergency_contact_notified,
        emergency_contact_notified_at=sos.emergency_contact_notified_at,
        assigned_responder_name=responder_name,
        assigned_responder_notes=sos.assigned_responder_notes,
        acknowledged_at=sos.acknowledged_at,
        resolved_at=sos.resolved_at,
        resolution_notes=sos.resolution_notes,
        audio_or_media_url=sos.audio_or_media_url,
    )

@router.post("/trigger", response_model=SOSEventOut)
async def trigger_sos(
    payload: SOSTriggerIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sos = await sos_service.trigger_sos(db, current_user, payload)
    
    # Reload with relationships
    q = (
        select(SOSEvent)
        .where(SOSEvent.id == sos.id)
        .options(
            selectinload(SOSEvent.driver).selectinload(Driver.user),
            selectinload(SOSEvent.truck),
            selectinload(SOSEvent.assigned_responder),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_sos(reloaded)

@router.get("/active", response_model=List[SOSEventOut])
async def get_active_sos_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Control Room, Admin, Fleet Manager or Compliance Officer can view active SOS list
    allowed_roles = [UserRole.CONTROL_ROOM, UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.COMPLIANCE_OFFICER]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Control room privileges required to view active emergencies.",
        )

    q = (
        select(SOSEvent)
        .where(SOSEvent.status.in_([
            SOSStatus.TRIGGERED,
            SOSStatus.NOTIFICATION_PENDING,
            SOSStatus.ACKNOWLEDGED,
            SOSStatus.RESPONDING,
        ]))
        .options(
            selectinload(SOSEvent.driver).selectinload(Driver.user),
            selectinload(SOSEvent.truck),
            selectinload(SOSEvent.assigned_responder),
        )
        .order_by(desc(SOSEvent.device_timestamp))
    )
    alerts = (await db.execute(q)).scalars().all()
    return [_serialize_sos(a) for a in alerts]

@router.get("/{sos_id}", response_model=SOSEventOut)
async def get_sos_detail(
    sos_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(SOSEvent)
        .where(SOSEvent.id == sos_id)
        .options(
            selectinload(SOSEvent.driver).selectinload(Driver.user),
            selectinload(SOSEvent.truck),
            selectinload(SOSEvent.assigned_responder),
        )
    )
    sos = (await db.execute(q)).scalar_one_or_none()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS Event not found")
    return _serialize_sos(sos)

@router.post("/{sos_id}/action", response_model=SOSEventOut)
async def handle_sos_action(
    sos_id: str,
    payload: SOSActionIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed_roles = [UserRole.CONTROL_ROOM, UserRole.ADMIN, UserRole.FLEET_MANAGER]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Control Room or Fleet Managers can act on SOS alerts.",
        )

    action = payload.action.upper()
    if action == "ACKNOWLEDGE":
        updated = await sos_service.acknowledge_sos(db, sos_id, current_user, payload.notes)
    elif action == "RESPOND":
        updated = await sos_service.update_response(db, sos_id, current_user, "RESPONDING", payload.notes or "Emergency response underway")
    elif action == "RESOLVE":
        updated = await sos_service.resolve_sos(db, sos_id, current_user, payload.notes or "Emergency resolved successfully", is_false_alarm=False)
    elif action == "FALSE_ALARM":
        updated = await sos_service.resolve_sos(db, sos_id, current_user, payload.notes or "Verified as False Alarm by driver/control room", is_false_alarm=True)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported SOS action: {payload.action}")

    q = (
        select(SOSEvent)
        .where(SOSEvent.id == updated.id)
        .options(
            selectinload(SOSEvent.driver).selectinload(Driver.user),
            selectinload(SOSEvent.truck),
            selectinload(SOSEvent.assigned_responder),
        )
    )
    reloaded = (await db.execute(q)).scalar_one()
    return _serialize_sos(reloaded)
