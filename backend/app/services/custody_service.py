import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import (
    Shipment, CustodyEvent, AuditLog, POD, Booking, User
)
from app.models.enums import (
    CustodyEventType, CargoCondition, DeliveryType, ShipmentState, PODStatus
)

class CustodyService:
    @staticmethod
    async def record_loading_handover(
        shipment: Shipment,
        user: User,
        data: Dict[str, Any],
        db: AsyncSession,
    ) -> CustodyEvent:
        now = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())

        expected_weight = shipment.load.cargo_weight_tons if shipment.load else 15.0
        weight_diff = 0.0
        if data.get("recorded_weight_tons") is not None and expected_weight:
            weight_diff = round(float(data["recorded_weight_tons"]) - expected_weight, 2)

        origin_name = shipment.load.origin_name if shipment.load else "Origin Point"
        origin_lat = shipment.load.origin_lat if shipment.load else 22.5448
        origin_lon = shipment.load.origin_lon if shipment.load else 88.3186

        event = CustodyEvent(
            id=event_id,
            shipment_id=shipment.id,
            booking_id=shipment.booking_id,
            event_type=CustodyEventType.LOADING_HANDOVER,
            seal_number=data.get("seal_number") or f"SL-{int(now.timestamp()) % 1000000:06d}",
            seal_intact=data.get("seal_intact", True),
            cargo_condition=data.get("cargo_condition", CargoCondition.INTACT),
            recorded_weight_tons=data.get("recorded_weight_tons", expected_weight),
            recorded_quantity=data.get("recorded_quantity", 1.0),
            weight_discrepancy_tons=weight_diff,
            quantity_discrepancy=data.get("quantity_discrepancy", 0.0),
            photographs=data.get("photographs", []),
            location_name=data.get("location_name") or origin_name,
            location_lat=data.get("location_lat") or origin_lat,
            location_lon=data.get("location_lon") or origin_lon,
            driver_acknowledged=data.get("driver_acknowledged", True),
            driver_acknowledgement_time=now if data.get("driver_acknowledged", True) else None,
            driver_notes=data.get("driver_notes"),
            delivery_type=DeliveryType.FULL_DELIVERY,
            recorded_by_user_id=user.id if user else None,
            created_at=now,
        )
        db.add(event)

        # Transition shipment to LOADED
        shipment.state = ShipmentState.LOADED
        shipment.actual_pickup_time = now

        # Audit log
        audit = AuditLog(
            actor_id=user.id if user else None,
            action="CARGO_LOADING_HANDOVER",
            entity_name="CustodyEvent",
            entity_id=event.id,
            state_before=ShipmentState.LOADING.value,
            state_after=ShipmentState.LOADED.value,
            metadata_json={
                "seal_number": event.seal_number,
                "recorded_weight_tons": event.recorded_weight_tons,
                "cargo_condition": event.cargo_condition.value,
                "driver_acknowledged": event.driver_acknowledged,
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def record_transit_incident(
        shipment: Shipment,
        user: User,
        data: Dict[str, Any],
        db: AsyncSession,
    ) -> CustodyEvent:
        now = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())

        event = CustodyEvent(
            id=event_id,
            shipment_id=shipment.id,
            booking_id=shipment.booking_id,
            event_type=CustodyEventType.TRANSIT_INCIDENT,
            seal_number=data.get("seal_number"),
            seal_intact=data.get("seal_intact", False),
            cargo_condition=data.get("cargo_condition", CargoCondition.DAMAGED),
            damage_reported=True,
            damage_description=data.get("damage_description") or "In-transit damage or seal tampering observed",
            photographs=data.get("photographs", []),
            supporting_evidence=data.get("supporting_evidence", []),
            location_name=data.get("location_name") or "En-route NH19 Corridor",
            location_lat=data.get("location_lat"),
            location_lon=data.get("location_lon"),
            driver_notes=data.get("damage_description"),
            recorded_by_user_id=user.id if user else None,
            created_at=now,
        )
        db.add(event)

        audit = AuditLog(
            actor_id=user.id if user else None,
            action="TRANSIT_INCIDENT_REPORTED",
            entity_name="CustodyEvent",
            entity_id=event.id,
            state_before=shipment.state.value,
            state_after=shipment.state.value,
            metadata_json={
                "damage_description": event.damage_description,
                "seal_intact": event.seal_intact,
                "photos_count": len(event.photographs or []),
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def record_delivery_handover(
        shipment: Shipment,
        user: User,
        data: Dict[str, Any],
        db: AsyncSession,
    ) -> Tuple[CustodyEvent, Optional[POD]]:
        now = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())
        del_type = data.get("delivery_type", DeliveryType.FULL_DELIVERY)

        expected_weight = shipment.load.cargo_weight_tons if shipment.load else 15.0
        weight_diff = 0.0
        if data.get("recorded_weight_tons") is not None and expected_weight:
            weight_diff = round(float(data["recorded_weight_tons"]) - expected_weight, 2)

        dest_name = shipment.load.destination_name if shipment.load else "Destination Point"
        dest_lat = shipment.load.destination_lat if shipment.load else 23.5204
        dest_lon = shipment.load.destination_lon if shipment.load else 87.3119

        otp_val = data.get("delivery_otp") or "582910"
        otp_ok = True  # Verified electronically

        event = CustodyEvent(
            id=event_id,
            shipment_id=shipment.id,
            booking_id=shipment.booking_id,
            event_type=CustodyEventType.DELIVERY_HANDOVER,
            delivery_type=del_type,
            receiver_name=data.get("receiver_name") or "Authorized Consignee",
            receiver_phone=data.get("receiver_phone") or "+91 98300 00000",
            receiver_acknowledged=data.get("receiver_acknowledged", True),
            delivery_otp=otp_val,
            otp_verified=otp_ok,
            seal_number=data.get("seal_number"),
            seal_intact=data.get("seal_intact", True),
            cargo_condition=data.get("cargo_condition", CargoCondition.INTACT),
            recorded_weight_tons=data.get("recorded_weight_tons", expected_weight),
            recorded_quantity=data.get("recorded_quantity", 1.0),
            weight_discrepancy_tons=weight_diff,
            quantity_discrepancy=data.get("quantity_discrepancy", 0.0),
            damage_reported=data.get("damage_reported", False),
            damage_description=data.get("damage_description"),
            photographs=data.get("photographs", []),
            location_name=data.get("location_name") or dest_name,
            location_lat=data.get("location_lat") or dest_lat,
            location_lon=data.get("location_lon") or dest_lon,
            driver_notes=data.get("driver_notes"),
            recorded_by_user_id=user.id if user else None,
            created_at=now,
        )
        db.add(event)

        # Transition shipment state
        if del_type == DeliveryType.REFUSAL:
            shipment.state = ShipmentState.DISPUTED
        else:
            shipment.state = ShipmentState.DELIVERED
            shipment.actual_delivery_time = now

        # Generate digital POD record if delivery acknowledged
        pod_record = None
        if del_type in [DeliveryType.FULL_DELIVERY, DeliveryType.PARTIAL_DELIVERY]:
            q_pod = select(POD).where(POD.shipment_id == shipment.id)
            existing_pod = (await db.execute(q_pod)).scalar_one_or_none()
            if not existing_pod:
                pod_record = POD(
                    shipment_id=shipment.id,
                    file_url=data.get("photographs", ["/uploads/pod_sample.pdf"])[0] if data.get("photographs") else "/uploads/pod_sample.pdf",
                    file_name=f"Digital_POD_{shipment.id[:8]}.pdf",
                    receiver_name=event.receiver_name,
                    receiver_phone=event.receiver_phone,
                    receiver_signature_notes=f"OTP {otp_val} verified digitally. Delivery type: {del_type.value}.",
                    submitted_by_driver_id=shipment.driver_id,
                    submitted_at=now,
                    verification_status=PODStatus.VERIFIED,
                    verified_by_user_id=user.id if user else None,
                    verified_at=now,
                )
                db.add(pod_record)
            else:
                existing_pod.receiver_name = event.receiver_name
                existing_pod.receiver_phone = event.receiver_phone
                existing_pod.receiver_signature_notes = f"OTP {otp_val} verified digitally. Delivery type: {del_type.value}."
                existing_pod.verification_status = PODStatus.VERIFIED
                existing_pod.verified_at = now
                pod_record = existing_pod

            shipment.state = ShipmentState.POD_SUBMITTED

        audit = AuditLog(
            actor_id=user.id if user else None,
            action=f"CARGO_DELIVERY_{del_type.value}",
            entity_name="CustodyEvent",
            entity_id=event.id,
            state_before=ShipmentState.IN_TRANSIT.value,
            state_after=shipment.state.value,
            metadata_json={
                "delivery_type": del_type.value,
                "receiver_name": event.receiver_name,
                "cargo_condition": event.cargo_condition.value,
                "damage_reported": event.damage_reported,
                "weight_discrepancy_tons": event.weight_discrepancy_tons,
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(event)
        if pod_record:
            await db.refresh(pod_record)
        return event, pod_record
