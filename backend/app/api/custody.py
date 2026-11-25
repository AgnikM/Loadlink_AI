import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import Shipment, CustodyEvent, User, Booking
from app.models.enums import UserRole, CustodyEventType, ShipmentState
from app.schemas.all_schemas import (
    LoadingHandoverCreate, TransitIncidentCreate, DeliveryHandoverCreate,
    CustodyEventOut
)
from app.services.custody_service import CustodyService

router = APIRouter(prefix="/custody", tags=["cargo-custody"])

def _check_shipment_actor_authorization(
    shipment: Shipment,
    current_user: User,
    action: str = "loading",
) -> None:
    """
    Enforces shipment-specific authorization for cargo custody transitions.
    Only authorized assigned drivers, fleet transporters, and shipment dealers
    may perform custody and incident actions (PRD Sec 14, FR-14).
    Cross-user and cross-shipment attempts are strictly rejected with HTTP 403.
    """
    # 1. Platform Operations & Admin
    if current_user.role in [UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.CONTROL_ROOM]:
        return

    # 2. Check if user is the assigned driver
    is_assigned_driver = (
        current_user.role == UserRole.DRIVER
        and current_user.driver_profile is not None
        and shipment.driver_id == current_user.driver_profile.id
    )

    # 3. Check if user is the transporter of the assigned truck
    is_assigned_transporter = (
        current_user.role == UserRole.TRANSPORTER
        and current_user.transporter_profile is not None
        and shipment.truck is not None
        and (
            (shipment.truck.transporter_id is not None and shipment.truck.transporter_id == current_user.transporter_profile.id)
            or (shipment.truck.organization_id is not None and shipment.truck.organization_id == current_user.transporter_profile.organization_id)
        )
    )

    # 4. Check if user is the dealer who owns this shipment
    is_shipment_dealer = (
        current_user.role == UserRole.DEALER
        and current_user.dealer_profile is not None
        and shipment.dealer_id == current_user.dealer_profile.id
    )

    if action == "loading":
        if is_assigned_driver or is_assigned_transporter or is_shipment_dealer:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only the assigned driver, transporter, or shipment dealer can record loading custody.",
        )
    elif action == "incident":
        if is_assigned_driver or is_assigned_transporter or is_shipment_dealer:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only the assigned driver, transporter, or shipment dealer can report transit incidents.",
        )
    elif action == "delivery":
        if is_assigned_driver or is_assigned_transporter or is_shipment_dealer:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only the assigned driver, transporter, or shipment dealer can record delivery handover.",
        )
    elif action == "events":
        if current_user.role in [UserRole.DISPUTE_OFFICER, UserRole.COMPLIANCE_OFFICER]:
            return
        if is_assigned_driver or is_assigned_transporter or is_shipment_dealer:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to view custody events for this shipment.",
        )

def _build_custody_out(event: CustodyEvent) -> CustodyEventOut:
    return CustodyEventOut(
        id=event.id,
        shipment_id=event.shipment_id,
        booking_id=event.booking_id,
        event_type=event.event_type,
        seal_number=event.seal_number,
        seal_intact=event.seal_intact,
        cargo_condition=event.cargo_condition,
        recorded_weight_tons=event.recorded_weight_tons,
        recorded_quantity=event.recorded_quantity,
        weight_discrepancy_tons=event.weight_discrepancy_tons,
        quantity_discrepancy=event.quantity_discrepancy,
        photographs=event.photographs or [],
        location_name=event.location_name,
        location_lat=event.location_lat,
        location_lon=event.location_lon,
        driver_acknowledged=event.driver_acknowledged,
        driver_acknowledgement_time=event.driver_acknowledgement_time,
        driver_notes=event.driver_notes,
        receiver_name=event.receiver_name,
        receiver_phone=event.receiver_phone,
        receiver_acknowledged=event.receiver_acknowledged,
        delivery_type=event.delivery_type,
        delivery_otp=event.delivery_otp,
        otp_verified=event.otp_verified,
        damage_reported=event.damage_reported,
        damage_description=event.damage_description,
        supporting_evidence=event.supporting_evidence or [],
        recorded_by_user_id=event.recorded_by_user_id,
        recorded_by_name=event.recorded_by.name if event.recorded_by else None,
        created_at=event.created_at,
    )

@router.post("/shipments/{shipment_id}/loading", response_model=CustodyEventOut)
async def record_loading_handover(
    shipment_id: str,
    req: LoadingHandoverCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Shipment)
        .where((Shipment.id == shipment_id) | (Shipment.booking_id == shipment_id))
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver),
            selectinload(Shipment.dealer),
        )
    )
    shipment = (await db.execute(q)).scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    _check_shipment_actor_authorization(shipment, current_user, action="loading")

    event = await CustodyService.record_loading_handover(shipment, current_user, req.model_dump(), db)
    return _build_custody_out(event)

@router.post("/shipments/{shipment_id}/incident", response_model=CustodyEventOut)
async def record_transit_incident(
    shipment_id: str,
    req: TransitIncidentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Shipment)
        .where((Shipment.id == shipment_id) | (Shipment.booking_id == shipment_id))
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver),
            selectinload(Shipment.dealer),
        )
    )
    shipment = (await db.execute(q)).scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    _check_shipment_actor_authorization(shipment, current_user, action="incident")

    event = await CustodyService.record_transit_incident(shipment, current_user, req.model_dump(), db)
    return _build_custody_out(event)

@router.post("/shipments/{shipment_id}/delivery", response_model=CustodyEventOut)
async def record_delivery_handover(
    shipment_id: str,
    req: DeliveryHandoverCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Shipment)
        .where((Shipment.id == shipment_id) | (Shipment.booking_id == shipment_id))
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver),
            selectinload(Shipment.dealer),
        )
    )
    shipment = (await db.execute(q)).scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    _check_shipment_actor_authorization(shipment, current_user, action="delivery")

    event, pod = await CustodyService.record_delivery_handover(shipment, current_user, req.model_dump(), db)
    return _build_custody_out(event)

@router.get("/shipments/{shipment_id}/events", response_model=List[CustodyEventOut])
async def list_custody_events(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q_ship = (
        select(Shipment)
        .where((Shipment.id == shipment_id) | (Shipment.booking_id == shipment_id))
        .options(
            selectinload(Shipment.truck),
            selectinload(Shipment.driver),
            selectinload(Shipment.dealer),
        )
    )
    shipment = (await db.execute(q_ship)).scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    _check_shipment_actor_authorization(shipment, current_user, action="events")

    q = (
        select(CustodyEvent)
        .where((CustodyEvent.shipment_id == shipment.id) | (CustodyEvent.booking_id == shipment.booking_id))
        .options(selectinload(CustodyEvent.recorded_by))
        .order_by(CustodyEvent.created_at.desc())
    )
    res = await db.execute(q)
    events = res.scalars().all()
    return [_build_custody_out(e) for e in events]
