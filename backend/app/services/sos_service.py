import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import SOSEvent, User, Driver, Truck, Shipment, Notification, Dealer
from app.models.enums import SOSStatus, SOSCategory, NetworkStatus, UserRole
from app.schemas.all_schemas import SOSTriggerIn, SOSActionIn

class SOSService:
    @staticmethod
    async def trigger_sos(
        db: AsyncSession,
        driver_user: User,
        payload: SOSTriggerIn,
    ) -> SOSEvent:
        # 1. Idempotency & Duplicate Prevention
        q_existing = (
            select(SOSEvent)
            .where(SOSEvent.event_id == payload.event_id)
            .options(
                selectinload(SOSEvent.driver).selectinload(Driver.user),
                selectinload(SOSEvent.truck),
                selectinload(SOSEvent.shipment),
            )
        )
        existing = (await db.execute(q_existing)).scalar_one_or_none()
        if existing:
            # Already persisted; return without duplicate creation
            return existing

        # 2. Resolve Driver profile & Truck
        driver = driver_user.driver_profile
        if not driver:
            q_d = select(Driver).where(Driver.user_id == driver_user.id)
            driver = (await db.execute(q_d)).scalar_one_or_none()

        truck_id = payload.truck_id
        q_truck = select(Truck).where(Truck.id == truck_id)
        truck = (await db.execute(q_truck)).scalar_one_or_none()

        # Resolve emergency contact from payload or driver profile
        emergency_name = payload.emergency_contact_name or (driver.emergency_contact_name if driver else "Emergency Contact")
        emergency_phone = payload.emergency_contact_phone or (driver.emergency_contact_phone if driver else "+919830099881")

        # 3. Persist SOS Event immediately (Persistence First Principle)
        now = datetime.now(timezone.utc)
        sos = SOSEvent(
            id=str(uuid.uuid4()),
            event_id=payload.event_id,
            driver_id=driver.id if driver else driver_user.id,
            truck_id=truck_id,
            shipment_id=payload.shipment_id,
            booking_id=payload.booking_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
            incident_category=payload.incident_category,
            network_status=payload.network_status,
            device_timestamp=payload.device_timestamp,
            server_timestamp=now,
            status=SOSStatus.TRIGGERED,
            emergency_contact_name=emergency_name,
            emergency_contact_phone=emergency_phone,
            audio_or_media_url=payload.audio_or_media_url,
        )
        db.add(sos)
        await db.commit()
        await db.refresh(sos)

        # 4. Asynchronous / Background Notification Fan-Out
        await SOSService._dispatch_notifications(db, sos, driver_user, truck)
        return sos

    @staticmethod
    async def _dispatch_notifications(
        db: AsyncSession,
        sos: SOSEvent,
        driver_user: User,
        truck: Optional[Truck],
    ):
        now = datetime.now(timezone.utc)
        reg_no = truck.registration_no if truck else "Vehicle"

        # 1. LoadLink Control Room Notification
        q_ctrl = select(User).where(User.role.in_([UserRole.CONTROL_ROOM, UserRole.ADMIN]))
        ctrl_users = (await db.execute(q_ctrl)).scalars().all()
        for u in ctrl_users:
            notif = Notification(
                user_id=u.id,
                type="SOS_ALERT",
                title=f"🚨 CRITICAL SOS: {reg_no} ({sos.incident_category.value})",
                payload={
                    "sos_id": sos.id,
                    "event_id": sos.event_id,
                    "truck_id": sos.truck_id,
                    "driver_name": driver_user.name,
                    "driver_phone": driver_user.phone,
                    "latitude": sos.latitude,
                    "longitude": sos.longitude,
                    "category": sos.incident_category.value,
                    "device_timestamp": sos.device_timestamp.isoformat(),
                },
            )
            db.add(notif)
        sos.control_room_notified = True
        sos.control_room_notified_at = now

        # 2. Associated Dealer / Shipper Notification (if on active shipment)
        if sos.shipment_id:
            q_ship = (
                select(Shipment)
                .where(Shipment.id == sos.shipment_id)
                .options(selectinload(Shipment.dealer).selectinload(Dealer.user))
            )
            ship = (await db.execute(q_ship)).scalar_one_or_none()
            if ship and ship.dealer and ship.dealer.user_id:
                dealer_notif = Notification(
                    user_id=ship.dealer.user_id,
                    type="SOS_SHIPMENT_EMERGENCY",
                    title=f"⚠️ Highway Emergency on Shipment #{ship.id[:8]}",
                    payload={
                        "sos_id": sos.id,
                        "shipment_id": ship.id,
                        "truck_registration": reg_no,
                        "category": sos.incident_category.value,
                        "latitude": sos.latitude,
                        "longitude": sos.longitude,
                    },
                )
                db.add(dealer_notif)
                sos.dealer_notified = True
                sos.dealer_notified_at = now

        # 3. Driver's Registered Emergency Contact Notification (Mock SMS Gateway)
        if sos.emergency_contact_phone:
            # Simulated SMS delivery via telecom gateway
            sos.emergency_contact_notified = True
            sos.emergency_contact_notified_at = now

        # Once notifications are dispatched, state advances to NOTIFICATION_PENDING / ACKNOWLEDGED
        if sos.status == SOSStatus.TRIGGERED:
            sos.status = SOSStatus.NOTIFICATION_PENDING

        await db.commit()
        await db.refresh(sos)

    @staticmethod
    async def acknowledge_sos(
        db: AsyncSession,
        sos_id: str,
        responder_user: User,
        notes: Optional[str] = None,
    ) -> SOSEvent:
        sos = await db.get(SOSEvent, sos_id)
        if not sos:
            raise ValueError("SOS Event not found")

        now = datetime.now(timezone.utc)
        sos.status = SOSStatus.ACKNOWLEDGED
        sos.acknowledged_at = now
        sos.assigned_responder_id = responder_user.id
        if notes:
            sos.assigned_responder_notes = notes

        await db.commit()
        await db.refresh(sos)
        return sos

    @staticmethod
    async def update_response(
        db: AsyncSession,
        sos_id: str,
        responder_user: User,
        action_type: str,
        notes: str,
    ) -> SOSEvent:
        sos = await db.get(SOSEvent, sos_id)
        if not sos:
            raise ValueError("SOS Event not found")

        sos.status = SOSStatus.RESPONDING
        existing_notes = sos.assigned_responder_notes or ""
        sos.assigned_responder_notes = f"{existing_notes}\n[{action_type}] {notes}".strip()
        sos.assigned_responder_id = responder_user.id

        await db.commit()
        await db.refresh(sos)
        return sos

    @staticmethod
    async def resolve_sos(
        db: AsyncSession,
        sos_id: str,
        resolver_user: User,
        resolution_notes: str,
        is_false_alarm: bool = False,
    ) -> SOSEvent:
        sos = await db.get(SOSEvent, sos_id)
        if not sos:
            raise ValueError("SOS Event not found")

        now = datetime.now(timezone.utc)
        sos.status = SOSStatus.FALSE_ALARM if is_false_alarm else SOSStatus.RESOLVED
        sos.resolved_at = now
        sos.resolution_notes = resolution_notes
        if not sos.assigned_responder_id:
            sos.assigned_responder_id = resolver_user.id

        await db.commit()
        await db.refresh(sos)
        return sos

sos_service = SOSService()
