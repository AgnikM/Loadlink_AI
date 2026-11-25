import hashlib
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user, get_current_user_optional
from app.models.entities import (
    Booking, Load, Truck, Driver, Dealer, Shipment, User, AuditLog, Notification,
    FreightAgreement, AgreementAcceptance, BookingStateHistory, Organization
)
from app.models.enums import (
    UserRole, BookingStatus, ShipmentState, TruckStatus, LoadStatus,
    VerificationStatus, AgreementStatus, FleetOwnershipType
)
from app.schemas.all_schemas import (
    BookingCreate, BookingAction, BookingStatusUpdate, BookingOut,
    FreightAgreementCreate, FreightAgreementUpdate, FreightAgreementOut,
    AgreementAcceptanceCreate, AgreementAcceptanceOut, BookingStateHistoryOut
)
from app.services.routing_service import routing_service

router = APIRouter(prefix="/bookings", tags=["bookings"])

def generate_agreement_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def perform_pre_dispatch_checks(truck: Truck, driver: Optional[Driver], cargo_weight_tons: Optional[float] = None):
    """
    Mandatory pre-dispatch checks (PRD & Master Prompt 1 & 2 Requirements):
    - Vehicle operational state must not be MAINTENANCE or SAFETY_HOLD
    - Vehicle verification status must be VERIFIED
    - Driver verification status must be VERIFIED
    - Cargo weight must not exceed legal vehicle payload capacity
    """
    if cargo_weight_tons is not None and cargo_weight_tons > truck.capacity_tons:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cargo weight validation failed: Consignment weight ({cargo_weight_tons}T) exceeds vehicle payload capacity ({truck.capacity_tons}T).",
        )
    if truck.status in [TruckStatus.MAINTENANCE, TruckStatus.SAFETY_HOLD]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pre-dispatch check failed: Vehicle {truck.registration_no} is currently in '{truck.status.value}' state. Cannot confirm booking.",
        )
    if truck.verification_status != VerificationStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pre-dispatch check failed: Vehicle {truck.registration_no} documentation is not verified.",
        )
    if driver and driver.verification_status != VerificationStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pre-dispatch check failed: Driver {driver.license_number} credentials are not verified.",
        )

def _build_booking_out(b: Booking, shipment_id: Optional[str] = None) -> BookingOut:
    ag_id = None
    ag_status = None
    is_ag_accepted = False
    if b.agreements:
        latest = sorted(b.agreements, key=lambda a: a.version, reverse=True)[0]
        ag_id = latest.id
        ag_status = latest.status
        is_ag_accepted = (latest.status == AgreementStatus.MUTUALLY_ACCEPTED)

    return BookingOut(
        id=b.id,
        load_id=b.load_id,
        truck_id=b.truck_id,
        truck_registration_no=b.truck.registration_no if b.truck else "",
        driver_id=b.driver_id,
        driver_name=b.driver.user.name if (b.driver and b.driver.user) else "",
        dealer_id=b.dealer_id,
        dealer_name=b.dealer.user.name if (b.dealer and b.dealer.user) else "",
        origin_name=b.load.origin_name if b.load else "",
        destination_name=b.load.destination_name if b.load else "",
        cargo_weight_tons=b.load.cargo_weight_tons if b.load else 0.0,
        offered_price=b.offered_price,
        status=b.status,
        rejection_reason=b.rejection_reason,
        requested_at=b.requested_at,
        responded_at=b.responded_at,
        shipment_id=shipment_id or (b.shipment.id if b.shipment else None),
        agreement_id=ag_id,
        agreement_status=ag_status,
        is_agreement_accepted=is_ag_accepted,
    )

def _is_role_match(role_val, target_roles):
    val_str = role_val.value if hasattr(role_val, "value") else str(role_val)
    target_strs = [r.value if hasattr(r, "value") else str(r) for r in target_roles]
    return val_str in target_strs

def _build_agreement_out(ag: FreightAgreement) -> FreightAgreementOut:
    dealer_accepted = any(
        _is_role_match(a.party_role, [UserRole.DEALER]) and a.version == ag.version
        for a in ag.acceptances
    )
    transporter_accepted = any(
        _is_role_match(a.party_role, [UserRole.DRIVER, UserRole.TRANSPORTER, UserRole.FLEET_MANAGER]) and a.version == ag.version
        for a in ag.acceptances
    )
    mutually_accepted = (ag.status in [AgreementStatus.MUTUALLY_ACCEPTED, "MUTUALLY_ACCEPTED"]) or (dealer_accepted and transporter_accepted)

    return FreightAgreementOut(
        id=ag.id,
        booking_id=ag.booking_id,
        load_id=ag.load_id,
        dealer_id=ag.dealer_id,
        dealer_name=ag.dealer.user.name if (ag.dealer and ag.dealer.user) else None,
        dealer_user_id=ag.dealer_user_id,
        transporter_user_id=ag.transporter_user_id,
        transporter_name=ag.transporter_user.name if ag.transporter_user else "Carrier Transporter",
        driver_id=ag.driver_id,
        driver_name=ag.driver.user.name if (ag.driver and ag.driver.user) else None,
        truck_id=ag.truck_id,
        truck_registration_no=ag.truck.registration_no if ag.truck else None,
        version=ag.version,
        status=ag.status,
        agreed_freight=ag.agreed_freight,
        additional_charges=ag.additional_charges or {},
        cargo_details=ag.cargo_details or {},
        vehicle_details=ag.vehicle_details or {},
        driver_details=ag.driver_details or {},
        pickup_terms=ag.pickup_terms,
        delivery_terms=ag.delivery_terms,
        insurance_requirements=ag.insurance_requirements,
        cancellation_terms=ag.cancellation_terms,
        delay_detention_rules=ag.delay_detention_rules,
        claims_dispute_conditions=ag.claims_dispute_conditions,
        content_hash=ag.content_hash,
        created_at=ag.created_at,
        updated_at=ag.updated_at,
        acceptances=[
            AgreementAcceptanceOut(
                id=a.id,
                agreement_id=a.agreement_id,
                version=a.version,
                party_role=a.party_role,
                user_id=a.user_id,
                user_name=a.user.name if a.user else None,
                organization_name=a.organization.name if a.organization else None,
                content_hash=a.content_hash,
                accepted_at=a.accepted_at,
                acceptance_method=a.acceptance_method,
            )
            for a in ag.acceptances
        ],
        is_accepted_by_dealer=dealer_accepted,
        is_accepted_by_transporter=transporter_accepted,
        is_mutually_accepted=mutually_accepted,
    )

@router.post("", response_model=BookingOut)
async def create_booking(
    req: BookingCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    dealer_id = None
    dealer_user_id = None
    dealer_org_id = None
    dealer_name = "Bengal Steel"

    if current_user and current_user.role == UserRole.DEALER and current_user.dealer_profile:
        dealer_id = current_user.dealer_profile.id
        dealer_user_id = current_user.id
        dealer_org_id = current_user.dealer_profile.organization_id
        dealer_name = current_user.name
    else:
        # Fallback to demo dealer
        q_dealer = select(Dealer).options(selectinload(Dealer.user))
        res_dealer = await db.execute(q_dealer)
        d_obj = res_dealer.scalars().first()
        if d_obj:
            dealer_id = d_obj.id
            dealer_user_id = d_obj.user_id
            dealer_org_id = d_obj.organization_id
            dealer_name = d_obj.user.name if d_obj.user else "Bengal Steel"
        else:
            raise HTTPException(status_code=400, detail="No registered dealer found.")

    # 1. Fetch load & truck
    q_load = select(Load).where(Load.id == req.load_id)
    res_load = await db.execute(q_load)
    load = res_load.scalar_one_or_none()
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")

    q_truck = (
        select(Truck)
        .where((Truck.id == req.truck_id) | (Truck.registration_no == req.truck_id))
        .options(
            selectinload(Truck.driver).selectinload(Driver.user),
            selectinload(Truck.organization),
        )
    )
    res_truck = await db.execute(q_truck)
    truck = res_truck.scalar_one_or_none()
    if not truck or not truck.driver:
        raise HTTPException(status_code=404, detail="Truck or associated driver not found")

    # Run pre-dispatch checks (including legal vehicle payload capacity validation)
    perform_pre_dispatch_checks(truck, truck.driver, cargo_weight_tons=load.cargo_weight_tons)

    booking_id = str(uuid.uuid4())
    offered_price = req.offered_price or req.agreed_freight_inr or 18000.0

    booking = Booking(
        id=booking_id,
        load_id=load.id,
        truck_id=truck.id,
        driver_id=truck.driver_id,
        dealer_id=dealer_id,
        offered_price=offered_price,
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    load.status = LoadStatus.BOOKING_REQUESTED
    await db.flush()

    # 2. Automatically generate the Direct Freight Agreement (Version 1) between Dealer and Transporter
    transporter_user_id = truck.driver.user_id if (truck.driver and truck.driver.user_id) else dealer_user_id
    transporter_org_id = truck.organization_id or (truck.driver.organization_id if truck.driver else None)

    commercial_terms = {
        "booking_id": booking.id,
        "load_id": load.id,
        "agreed_freight_inr": offered_price,
        "pickup_origin": load.origin_name,
        "delivery_destination": load.destination_name,
        "cargo": {
            "type": load.cargo_type,
            "weight_tons": load.cargo_weight_tons,
            "notes": load.cargo_notes or "",
        },
        "vehicle": {
            "registration_no": truck.registration_no,
            "truck_type": truck.truck_type.value,
            "capacity_tons": truck.capacity_tons,
        },
        "driver": {
            "name": truck.driver.user.name if (truck.driver and truck.driver.user) else "Commercial Carrier",
            "license_number": truck.driver.license_number if truck.driver else "",
        },
        "additional_charges": {
            "detention_rate_per_hour_inr": 350.0,
            "free_loading_hours": 3,
            "dry_run_penalty_inr": 1500.0,
        },
        "cancellation_terms": "Cancellation permitted prior to vehicle departure without penalty. Post-arrival cancellation subject to standard dry-run compensation (₹1,500).",
        "insurance_requirements": "Cargo transit risk underwritten under statutory Carriage by Road Rules, 2007.",
        "claims_dispute_conditions": "Consignment inspection required at offload. Immediate endorsement on POD. Jurisdiction: Kolkata Courts.",
    }
    content_hash = generate_agreement_hash(commercial_terms)

    agreement = FreightAgreement(
        booking_id=booking.id,
        load_id=load.id,
        dealer_id=dealer_id,
        dealer_user_id=dealer_user_id,
        transporter_user_id=transporter_user_id,
        driver_id=truck.driver_id,
        truck_id=truck.id,
        version=1,
        status=AgreementStatus.PENDING_ACCEPTANCE,
        agreed_freight=offered_price,
        additional_charges=commercial_terms["additional_charges"],
        cargo_details=commercial_terms["cargo"],
        vehicle_details=commercial_terms["vehicle"],
        driver_details=commercial_terms["driver"],
        pickup_terms=f"Vehicle shall report at {load.origin_name} within specified pickup window.",
        delivery_terms=f"Direct transit to {load.destination_name}. Consignee physical inspection and signed digital POD mandatory.",
        insurance_requirements=commercial_terms["insurance_requirements"],
        cancellation_terms=commercial_terms["cancellation_terms"],
        delay_detention_rules="Free window 3 hours. ₹350/hr detention fee applicable thereafter.",
        claims_dispute_conditions=commercial_terms["claims_dispute_conditions"],
        content_hash=content_hash,
    )
    db.add(agreement)
    await db.flush()

    # Record dealer's offer initiation acceptance
    dealer_acceptance = AgreementAcceptance(
        agreement_id=agreement.id,
        version=1,
        user_id=dealer_user_id,
        organization_id=dealer_org_id,
        party_role=UserRole.DEALER,
        content_hash=content_hash,
        acceptance_method="OFFER_INITIATION_DIGITAL_CONFIRMATION",
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(dealer_acceptance)

    # Record state-transition history
    state_hist = BookingStateHistory(
        booking_id=booking.id,
        from_status=None,
        to_status=BookingStatus.PENDING,
        changed_by_user_id=dealer_user_id,
        reason="Direct freight agreement v1 initiated with booking request",
    )
    db.add(state_hist)

    # Notification for driver
    if truck.driver and truck.driver.user_id:
        notif = Notification(
            user_id=truck.driver.user_id,
            type="BOOKING_REQUEST_RECEIVED",
            title="New Direct Freight Agreement & Booking Request",
            payload={
                "booking_id": booking.id,
                "agreement_id": agreement.id,
                "origin": load.origin_name,
                "destination": load.destination_name,
                "offered_price": offered_price,
                "cargo_weight_tons": load.cargo_weight_tons,
            }
        )
        db.add(notif)

    await db.commit()
    await db.refresh(booking)

    # Re-query booking with agreements
    q_b = (
        select(Booking)
        .where(Booking.id == booking.id)
        .options(
            selectinload(Booking.load),
            selectinload(Booking.truck),
            selectinload(Booking.driver).selectinload(Driver.user),
            selectinload(Booking.dealer).selectinload(Dealer.user),
            selectinload(Booking.agreements).selectinload(FreightAgreement.acceptances),
            selectinload(Booking.shipment),
        )
    )
    b_loaded = (await db.execute(q_b)).scalar_one()
    return _build_booking_out(b_loaded)

@router.patch("/{booking_id}/status", response_model=BookingOut)
async def update_booking_status(
    booking_id: str,
    req: BookingStatusUpdate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.load),
            selectinload(Booking.truck),
            selectinload(Booking.driver).selectinload(Driver.user),
            selectinload(Booking.dealer).selectinload(Dealer.user),
            selectinload(Booking.shipment),
            selectinload(Booking.agreements).selectinload(FreightAgreement.acceptances),
        )
    )
    res = await db.execute(query)
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking request not found")

    target_status = req.status.upper()
    now = datetime.now(timezone.utc)
    booking.responded_at = now
    created_shipment_id = None
    prev_status = booking.status

    if target_status == "ACCEPTED":
        # Pre-dispatch checks
        perform_pre_dispatch_checks(booking.truck, booking.driver)

        # Direct agreement mutual acceptance check
        latest_ag = sorted(booking.agreements, key=lambda a: a.version, reverse=True)[0] if booking.agreements else None
        if latest_ag:
            dealer_acc = any(a.party_role == UserRole.DEALER and a.version == latest_ag.version for a in latest_ag.acceptances)
            carrier_acc = any(a.party_role in [UserRole.DRIVER, UserRole.TRANSPORTER, UserRole.FLEET_MANAGER] and a.version == latest_ag.version for a in latest_ag.acceptances)
            if not carrier_acc:
                # Driver accepted via this status update
                carrier_acc_record = AgreementAcceptance(
                    agreement_id=latest_ag.id,
                    version=latest_ag.version,
                    user_id=current_user.id if current_user else booking.driver.user_id,
                    party_role=current_user.role if current_user else UserRole.DRIVER,
                    content_hash=latest_ag.content_hash,
                    acceptance_method="STATUS_UPDATE_DIGITAL_CONFIRMATION",
                    accepted_at=now,
                )
                db.add(carrier_acc_record)
                carrier_acc = True

            if dealer_acc and carrier_acc:
                latest_ag.status = AgreementStatus.MUTUALLY_ACCEPTED

        booking.status = BookingStatus.ACCEPTED
        if booking.truck:
            booking.truck.status = TruckStatus.ASSIGNED
        if booking.load:
            booking.load.status = LoadStatus.CONFIRMED

        # Check if shipment already exists
        if not booking.shipment:
            route_info = await routing_service.get_route(
                booking.load.origin_lat, booking.load.origin_lon,
                booking.load.destination_lat, booking.load.destination_lon
            )
            dist_km = route_info["distance_km"]
            mins_duration = route_info["duration_minutes"]

            pickup_eta = booking.load.pickup_window_start
            delivery_eta = datetime.fromtimestamp(pickup_eta.timestamp() + mins_duration * 60, tz=timezone.utc)

            shipment = Shipment(
                booking_id=booking.id,
                load_id=booking.load_id,
                truck_id=booking.truck_id,
                driver_id=booking.driver_id,
                dealer_id=booking.dealer_id,
                state=ShipmentState.CONFIRMED,
                distance_km=dist_km,
                agreed_freight=booking.offered_price,
                pickup_eta=pickup_eta,
                delivery_eta=delivery_eta,
            )
            db.add(shipment)
            await db.flush()
            created_shipment_id = shipment.id
    elif target_status == "IN_TRANSIT":
        if booking.shipment:
            booking.shipment.state = ShipmentState.IN_TRANSIT
        if booking.truck:
            booking.truck.status = TruckStatus.IN_TRANSIT
        if booking.load:
            booking.load.status = LoadStatus.IN_PROGRESS
    elif target_status == "DELIVERED":
        if booking.shipment:
            booking.shipment.state = ShipmentState.DELIVERED
        if booking.truck:
            booking.truck.status = TruckStatus.ONLINE_AVAILABLE
        if booking.load:
            booking.load.status = LoadStatus.COMPLETED
    elif target_status == "REJECTED":
        booking.status = BookingStatus.REJECTED
        if booking.load:
            booking.load.status = LoadStatus.POSTED
    elif target_status == "CANCELLED":
        booking.status = BookingStatus.CANCELLED
        if booking.load:
            booking.load.status = LoadStatus.POSTED

    # Record state transition history
    hist = BookingStateHistory(
        booking_id=booking.id,
        from_status=prev_status,
        to_status=booking.status,
        changed_by_user_id=current_user.id if current_user else None,
        reason=f"Status update to {target_status}",
    )
    db.add(hist)

    await db.commit()
    await db.refresh(booking)
    return _build_booking_out(booking, created_shipment_id)

@router.patch("/{booking_id}", response_model=BookingOut)
@router.post("/{booking_id}/respond", response_model=BookingOut)
async def respond_to_booking(
    booking_id: str,
    req: BookingAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.load),
            selectinload(Booking.truck),
            selectinload(Booking.driver).selectinload(Driver.user),
            selectinload(Booking.dealer).selectinload(Dealer.user),
            selectinload(Booking.shipment),
            selectinload(Booking.agreements).selectinload(FreightAgreement.acceptances),
        )
    )
    res = await db.execute(query)
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking request not found")

    if booking.status not in [BookingStatus.PENDING, BookingStatus.AGREEMENT_PENDING]:
        raise HTTPException(status_code=400, detail=f"Booking is already in '{booking.status.value}' state.")

    now = datetime.now(timezone.utc)
    booking.responded_at = now
    action = req.action.upper()
    created_shipment_id = None
    prev_status = booking.status

    if action == "ACCEPT":
        # 1. Ensure only the assigned driver, transporter, or admin can accept
        if current_user.role == UserRole.DRIVER:
            if not current_user.driver_profile or booking.driver_id != current_user.driver_profile.id:
                raise HTTPException(status_code=403, detail="Only assigned driver can accept this booking")
        elif current_user.role == UserRole.TRANSPORTER:
            if not current_user.transporter_profile or booking.truck.organization_id != current_user.transporter_profile.organization_id:
                raise HTTPException(status_code=403, detail="Only carrier transporter managing this vehicle can accept this booking")
        elif current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only assigned driver, transporter, or admin can accept this booking")

        # 2. Mandatory pre-dispatch checks
        perform_pre_dispatch_checks(booking.truck, booking.driver)

        # 3. Direct Freight Agreement Acceptance
        latest_ag = sorted(booking.agreements, key=lambda a: a.version, reverse=True)[0] if booking.agreements else None
        if not latest_ag:
            raise HTTPException(status_code=400, detail="No freight agreement found for this booking.")

        # Check if driver/transporter already accepted this version; if not, record digital acceptance
        driver_org_id = current_user.driver_profile.organization_id if (current_user.driver_profile and current_user.driver_profile.organization_id) else None
        if current_user.transporter_profile:
            driver_org_id = current_user.transporter_profile.organization_id

        has_carrier_accepted = any(
            a.party_role in [UserRole.DRIVER, UserRole.TRANSPORTER, UserRole.FLEET_MANAGER] and a.version == latest_ag.version
            for a in latest_ag.acceptances
        )
        if not has_carrier_accepted:
            acceptance = AgreementAcceptance(
                agreement_id=latest_ag.id,
                version=latest_ag.version,
                user_id=current_user.id,
                organization_id=driver_org_id,
                party_role=current_user.role,
                content_hash=latest_ag.content_hash,
                acceptance_method="EXPLICIT_DIGITAL_CONFIRMATION",
                accepted_at=now,
            )
            db.add(acceptance)
            await db.flush()

        # Check mutual acceptance
        has_dealer_accepted = any(
            a.party_role == UserRole.DEALER and a.version == latest_ag.version
            for a in latest_ag.acceptances
        )
        if not has_dealer_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Freight agreement version {latest_ag.version} requires shipper/dealer digital acceptance before confirmation.",
            )

        latest_ag.status = AgreementStatus.MUTUALLY_ACCEPTED

        booking.status = BookingStatus.ACCEPTED
        booking.truck.status = TruckStatus.ASSIGNED
        booking.load.status = LoadStatus.CONFIRMED

        # Cancel other pending bookings for the same load or truck to protect concurrency
        q_other_pending = select(Booking).where(
            Booking.id != booking.id,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.AGREEMENT_PENDING]),
            ((Booking.load_id == booking.load_id) | (Booking.truck_id == booking.truck_id))
        )
        res_other = await db.execute(q_other_pending)
        for ob in res_other.scalars().all():
            ob.status = BookingStatus.CANCELLED
            ob.rejection_reason = "Auto-cancelled: load or truck confirmed with another booking."

        # Calculate estimated distance and pickup/delivery ETAs
        route_info = await routing_service.get_route(
            booking.load.origin_lat, booking.load.origin_lon,
            booking.load.destination_lat, booking.load.destination_lon
        )
        dist_km = route_info["distance_km"]
        mins_duration = route_info["duration_minutes"]

        pickup_eta = booking.load.pickup_window_start
        delivery_eta = datetime.fromtimestamp(pickup_eta.timestamp() + mins_duration * 60, tz=timezone.utc)

        # Instantiate Shipment with initial state CONFIRMED
        shipment = Shipment(
            booking_id=booking.id,
            load_id=booking.load_id,
            truck_id=booking.truck_id,
            driver_id=booking.driver_id,
            dealer_id=booking.dealer_id,
            state=ShipmentState.CONFIRMED,
            distance_km=dist_km,
            agreed_freight=booking.offered_price,
            pickup_eta=pickup_eta,
            delivery_eta=delivery_eta,
        )
        db.add(shipment)
        await db.flush()
        created_shipment_id = shipment.id

        # Notify dealer
        notif = Notification(
            user_id=booking.dealer.user_id,
            type="BOOKING_ACCEPTED",
            title="Agreement Mutually Signed & Booking Accepted!",
            payload={"shipment_id": shipment.id, "truck_reg": booking.truck.registration_no, "agreement_id": latest_ag.id}
        )
        db.add(notif)

    elif action == "REJECT":
        if current_user.role == UserRole.DRIVER:
            if not current_user.driver_profile or booking.driver_id != current_user.driver_profile.id:
                raise HTTPException(status_code=403, detail="Only assigned driver can reject this booking")
        elif current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only assigned driver or admin can reject this booking")

        booking.status = BookingStatus.REJECTED
        booking.rejection_reason = req.rejection_reason or "Driver unavailable"
        booking.load.status = LoadStatus.POSTED

    elif action == "CANCEL":
        if current_user.role == UserRole.DEALER:
            if not current_user.dealer_profile or booking.dealer_id != current_user.dealer_profile.id:
                raise HTTPException(status_code=403, detail="Only the load owner dealer can cancel this booking")
        elif current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only owner dealer or admin can cancel this booking")

        booking.status = BookingStatus.CANCELLED
        booking.rejection_reason = req.rejection_reason or "Cancelled by user"
        booking.load.status = LoadStatus.POSTED

    # Record state-transition history
    hist = BookingStateHistory(
        booking_id=booking.id,
        from_status=prev_status,
        to_status=booking.status,
        changed_by_user_id=current_user.id,
        reason=req.rejection_reason or f"Action {action} performed",
    )
    db.add(hist)

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        action=f"BOOKING_{action}",
        entity_name="Booking",
        entity_id=booking.id,
        state_after=booking.status.value,
        metadata_json={"rejection_reason": booking.rejection_reason},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(booking)
    return _build_booking_out(booking, created_shipment_id)

@router.get("/{booking_id}/agreement", response_model=FreightAgreementOut)
async def get_booking_agreement(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(FreightAgreement)
        .where(FreightAgreement.booking_id == booking_id)
        .options(
            selectinload(FreightAgreement.dealer).selectinload(Dealer.user),
            selectinload(FreightAgreement.driver).selectinload(Driver.user),
            selectinload(FreightAgreement.truck),
            selectinload(FreightAgreement.transporter_user),
            selectinload(FreightAgreement.acceptances).selectinload(AgreementAcceptance.user),
            selectinload(FreightAgreement.acceptances).selectinload(AgreementAcceptance.organization),
        )
        .execution_options(populate_existing=True)
        .order_by(FreightAgreement.version.desc())
    )
    res = await db.execute(query)
    ag = res.scalars().first()
    if not ag:
        raise HTTPException(status_code=404, detail="Freight agreement not found for this booking")
    return _build_agreement_out(ag)

@router.post("/{booking_id}/agreement/accept", response_model=FreightAgreementOut)
async def accept_booking_agreement(
    booking_id: str,
    req: AgreementAcceptanceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Explicit direct agreement digital acceptance by counterparty:
    - Records user, organization, agreement version, acceptance timestamp, content hash
    - When both Shipper and Transporter accept the same version, status becomes MUTUALLY_ACCEPTED.
    """
    query = (
        select(FreightAgreement)
        .where(FreightAgreement.booking_id == booking_id)
        .options(
            selectinload(FreightAgreement.dealer).selectinload(Dealer.user),
            selectinload(FreightAgreement.driver).selectinload(Driver.user),
            selectinload(FreightAgreement.truck),
            selectinload(FreightAgreement.transporter_user),
            selectinload(FreightAgreement.acceptances).selectinload(AgreementAcceptance.user),
            selectinload(FreightAgreement.acceptances).selectinload(AgreementAcceptance.organization),
        )
        .execution_options(populate_existing=True)
        .order_by(FreightAgreement.version.desc())
    )
    res = await db.execute(query)
    ag = res.scalars().first()
    if not ag:
        raise HTTPException(status_code=404, detail="Freight agreement not found for this booking")

    # Authorize counterparty
    driver_profile = None
    if current_user.role == UserRole.DRIVER:
        q_d = select(Driver).where(Driver.user_id == current_user.id)
        driver_profile = (await db.execute(q_d)).scalar_one_or_none()

    dealer_profile = None
    if current_user.role == UserRole.DEALER:
        q_dl = select(Dealer).where(Dealer.user_id == current_user.id)
        dealer_profile = (await db.execute(q_dl)).scalar_one_or_none()

    transporter_profile = None
    if current_user.role == UserRole.TRANSPORTER:
        q_tr = select(Transporter).where(Transporter.user_id == current_user.id)
        transporter_profile = (await db.execute(q_tr)).scalar_one_or_none()

    is_dealer = (current_user.role == UserRole.DEALER and dealer_profile and ag.dealer_id == dealer_profile.id)
    is_carrier = (current_user.role == UserRole.DRIVER and driver_profile and ag.driver_id == driver_profile.id) or \
                 (current_user.role == UserRole.TRANSPORTER and transporter_profile and ag.truck and ag.truck.organization_id == transporter_profile.organization_id)
    is_admin = (current_user.role == UserRole.ADMIN)

    if not (is_dealer or is_carrier or is_admin):
        raise HTTPException(status_code=403, detail="Only authorized counterparty (Dealer, Driver, Transporter) can accept this agreement")

    # Check already accepted
    already_accepted = any(
        a.user_id == current_user.id and a.version == ag.version
        for a in ag.acceptances
    )
    if already_accepted:
        return _build_agreement_out(ag)

    now = datetime.now(timezone.utc)
    org_id = None
    if dealer_profile:
        org_id = dealer_profile.organization_id
    elif transporter_profile:
        org_id = transporter_profile.organization_id
    elif driver_profile:
        org_id = driver_profile.organization_id

    acceptance = AgreementAcceptance(
        agreement_id=ag.id,
        version=ag.version,
        user_id=current_user.id,
        organization_id=org_id,
        party_role=current_user.role,
        content_hash=ag.content_hash,
        acceptance_method=req.acceptance_method or "EXPLICIT_DIGITAL_CONFIRMATION",
        accepted_at=now,
    )
    db.add(acceptance)
    if hasattr(ag, "acceptances") and ag.acceptances is not None:
        ag.acceptances.append(acceptance)
    await db.flush()

    # Check mutual acceptance
    q_recheck = (
        select(AgreementAcceptance)
        .where(AgreementAcceptance.agreement_id == ag.id, AgreementAcceptance.version == ag.version)
    )
    acceptances_all = (await db.execute(q_recheck)).scalars().all()
    dealer_done = any(_is_role_match(a.party_role, [UserRole.DEALER]) for a in acceptances_all)
    carrier_done = any(_is_role_match(a.party_role, [UserRole.DRIVER, UserRole.TRANSPORTER, UserRole.FLEET_MANAGER]) for a in acceptances_all)

    if dealer_done and carrier_done:
        ag.status = AgreementStatus.MUTUALLY_ACCEPTED

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        action=f"AGREEMENT_ACCEPTED_V{ag.version}",
        entity_name="FreightAgreement",
        entity_id=ag.id,
        state_after=ag.status.value,
        metadata_json={"version": ag.version, "hash": ag.content_hash, "role": current_user.role.value},
    )
    db.add(audit)

    await db.commit()
    return await get_booking_agreement(booking_id, current_user, db)

@router.patch("/{booking_id}/agreement", response_model=FreightAgreementOut)
async def update_booking_agreement(
    booking_id: str,
    req: FreightAgreementUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Terms amendment creates a new agreement version:
    - Increments version number
    - Re-hashes terms
    - Resets status to PENDING_ACCEPTANCE requiring renewed acceptance from counterparties
    """
    query = (
        select(FreightAgreement)
        .where(FreightAgreement.booking_id == booking_id)
        .options(
            selectinload(FreightAgreement.dealer).selectinload(Dealer.user),
            selectinload(FreightAgreement.driver).selectinload(Driver.user),
            selectinload(FreightAgreement.truck),
            selectinload(FreightAgreement.transporter_user),
            selectinload(FreightAgreement.acceptances),
            selectinload(FreightAgreement.booking),
        )
        .order_by(FreightAgreement.version.desc())
    )
    res = await db.execute(query)
    curr_ag = res.scalars().first()
    if not curr_ag:
        raise HTTPException(status_code=404, detail="Freight agreement not found")

    new_version = curr_ag.version + 1
    new_freight = req.agreed_freight or curr_ag.agreed_freight

    # Compile new canonical data
    updated_terms = {
        "booking_id": booking_id,
        "load_id": curr_ag.load_id,
        "version": new_version,
        "agreed_freight_inr": new_freight,
        "additional_charges": req.additional_charges or curr_ag.additional_charges,
        "cargo": curr_ag.cargo_details,
        "vehicle": curr_ag.vehicle_details,
        "driver": curr_ag.driver_details,
        "pickup_terms": req.pickup_terms or curr_ag.pickup_terms,
        "delivery_terms": req.delivery_terms or curr_ag.delivery_terms,
        "insurance_requirements": req.insurance_requirements or curr_ag.insurance_requirements,
        "cancellation_terms": req.cancellation_terms or curr_ag.cancellation_terms,
        "delay_detention_rules": req.delay_detention_rules or curr_ag.delay_detention_rules,
        "claims_dispute_conditions": req.claims_dispute_conditions or curr_ag.claims_dispute_conditions,
    }
    new_hash = generate_agreement_hash(updated_terms)

    # Mark old agreement superseded
    curr_ag.status = AgreementStatus.SUPERSEDED

    new_ag = FreightAgreement(
        booking_id=booking_id,
        load_id=curr_ag.load_id,
        dealer_id=curr_ag.dealer_id,
        dealer_user_id=curr_ag.dealer_user_id,
        transporter_user_id=curr_ag.transporter_user_id,
        driver_id=curr_ag.driver_id,
        truck_id=curr_ag.truck_id,
        version=new_version,
        status=AgreementStatus.PENDING_ACCEPTANCE,
        agreed_freight=new_freight,
        additional_charges=updated_terms["additional_charges"],
        cargo_details=curr_ag.cargo_details,
        vehicle_details=curr_ag.vehicle_details,
        driver_details=curr_ag.driver_details,
        pickup_terms=updated_terms["pickup_terms"],
        delivery_terms=updated_terms["delivery_terms"],
        insurance_requirements=updated_terms["insurance_requirements"],
        cancellation_terms=updated_terms["cancellation_terms"],
        delay_detention_rules=updated_terms["delay_detention_rules"],
        claims_dispute_conditions=updated_terms["claims_dispute_conditions"],
        content_hash=new_hash,
    )
    db.add(new_ag)
    await db.flush()

    # Automatically record proposing party's acceptance on new version
    org_id = current_user.dealer_profile.organization_id if current_user.dealer_profile else (
        current_user.transporter_profile.organization_id if current_user.transporter_profile else None
    )
    acceptance = AgreementAcceptance(
        agreement_id=new_ag.id,
        version=new_version,
        user_id=current_user.id,
        organization_id=org_id,
        party_role=current_user.role,
        content_hash=new_hash,
        acceptance_method="TERMS_AMENDMENT_DIGITAL_INITIATION",
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(acceptance)

    # Update booking status to AGREEMENT_PENDING and price
    if curr_ag.booking:
        curr_ag.booking.offered_price = new_freight
        curr_ag.booking.status = BookingStatus.AGREEMENT_PENDING

    # History
    hist = BookingStateHistory(
        booking_id=booking_id,
        from_status=curr_ag.booking.status if curr_ag.booking else BookingStatus.PENDING,
        to_status=BookingStatus.AGREEMENT_PENDING,
        changed_by_user_id=current_user.id,
        reason=f"Terms amended to version {new_version}. Counterparty renewed acceptance required.",
    )
    db.add(hist)

    await db.commit()
    return await get_booking_agreement(booking_id, current_user, db)

@router.get("/{booking_id}/history", response_model=List[BookingStateHistoryOut])
async def get_booking_history(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(BookingStateHistory)
        .where(BookingStateHistory.booking_id == booking_id)
        .options(selectinload(BookingStateHistory.changed_by))
        .order_by(BookingStateHistory.timestamp.asc())
    )
    res = await db.execute(query)
    entries = res.scalars().all()
    return [
        BookingStateHistoryOut(
            id=e.id,
            booking_id=e.booking_id,
            from_status=e.from_status,
            to_status=e.to_status,
            changed_by_name=e.changed_by.name if e.changed_by else "System",
            reason=e.reason,
            timestamp=e.timestamp,
        )
        for e in entries
    ]

@router.get("", response_model=List[BookingOut])
async def list_bookings(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Booking)
        .options(
            selectinload(Booking.load),
            selectinload(Booking.truck),
            selectinload(Booking.driver).selectinload(Driver.user),
            selectinload(Booking.dealer).selectinload(Dealer.user),
            selectinload(Booking.agreements).selectinload(FreightAgreement.acceptances),
            selectinload(Booking.shipment),
        )
        .order_by(Booking.requested_at.desc())
    )

    if current_user and current_user.role == UserRole.DEALER and current_user.dealer_profile:
        query = query.where(Booking.dealer_id == current_user.dealer_profile.id)
    elif current_user and current_user.role == UserRole.DRIVER and current_user.driver_profile:
        query = query.where(Booking.driver_id == current_user.driver_profile.id)

    query = query.limit(limit).offset(offset)
    res = await db.execute(query)
    bookings = res.scalars().all()
    return [_build_booking_out(b) for b in bookings]
