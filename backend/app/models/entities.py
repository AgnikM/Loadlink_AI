import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import (
    UserRole, VerificationStatus, TruckType, TruckStatus,
    LoadStatus, BookingStatus, ShipmentState, PODStatus,
    FleetOwnershipType, AgreementStatus,
    CargoCategory, FragilityLevel, HazardClass,
    CustodyEventType, CargoCondition, DeliveryType,
    InsuranceAssessmentResult, InsuranceVerificationStatus,
    DirectPaymentStatus, PaymentMethod,
    FeeType, InvoiceStatus,
    DisputeCategory, DisputeStatus, GrievanceStatus,
    SOSStatus, SOSCategory, NetworkStatus,
    BreakdownIssueType, BreakdownStatus, ReplacementStatus
)

def utcnow():
    return datetime.now(timezone.utc)

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    is_demo = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    dealer_profile = relationship("Dealer", back_populates="user", uselist=False, cascade="all, delete-orphan")
    driver_profile = relationship("Driver", back_populates="user", uselist=False, cascade="all, delete-orphan")
    transporter_profile = relationship("Transporter", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="actor")

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    business_type = Column(String(100), default="Manufacturing / Trading")
    org_type = Column(String(50), default="DEALER_SHIPPER") # DEALER_SHIPPER, EXTERNAL_TRANSPORTER, LOADLINK_FLEET
    gstin = Column(String(50), nullable=True)
    operating_corridor = Column(String(255), default="Kolkata ↔ Durgapur ↔ Asansol")
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.VERIFIED)
    is_demo = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utcnow)

    dealers = relationship("Dealer", back_populates="organization")
    transporters = relationship("Transporter", back_populates="organization")
    trucks = relationship("Truck", back_populates="organization")
    drivers = relationship("Driver", back_populates="organization")

class Transporter(Base):
    __tablename__ = "transporters"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    fleet_size = Column(Integer, default=0)
    trust_score = Column(Float, default=95.0)
    is_demo = Column(Boolean, default=False, index=True)

    user = relationship("User", back_populates="transporter_profile")
    organization = relationship("Organization", back_populates="transporters")

class Dealer(Base):
    __tablename__ = "dealers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    trust_score = Column(Float, default=95.0)
    total_loads_posted = Column(Integer, default=0)
    total_completed_loads = Column(Integer, default=0)
    cancellations_count = Column(Integer, default=0)
    is_demo = Column(Boolean, default=False, index=True)

    user = relationship("User", back_populates="dealer_profile")
    organization = relationship("Organization", back_populates="dealers")
    loads = relationship("Load", back_populates="dealer")
    bookings = relationship("Booking", back_populates="dealer")
    shipments = relationship("Shipment", back_populates="dealer")

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    license_number = Column(String(50), nullable=False)
    license_expiry = Column(DateTime, nullable=True)
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.VERIFIED)
    reliability_score = Column(Float, default=94.0)
    total_trips = Column(Integer, default=0)
    on_time_trips = Column(Integer, default=0)
    cancellations_count = Column(Integer, default=0)
    emergency_contact_name = Column(String(255), default="Paramjeet Yadav (Brother)")
    emergency_contact_phone = Column(String(50), default="+919830099881")
    is_demo = Column(Boolean, default=False, index=True)

    user = relationship("User", back_populates="driver_profile")
    organization = relationship("Organization", back_populates="drivers")
    trucks = relationship("Truck", back_populates="driver")
    assignments = relationship("VehicleAssignment", back_populates="driver", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="driver")
    shipments = relationship("Shipment", back_populates="driver")
    inspections = relationship("PreTripInspection", back_populates="driver", cascade="all, delete-orphan")
    breakdowns = relationship("VehicleBreakdown", back_populates="driver", cascade="all, delete-orphan")
    sos_events = relationship("SOSEvent", back_populates="driver", cascade="all, delete-orphan")

class Truck(Base):
    __tablename__ = "trucks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    ownership_type = Column(SQLEnum(FleetOwnershipType), default=FleetOwnershipType.EXTERNAL_TRANSPORTER)
    registration_no = Column(String(50), unique=True, index=True, nullable=False)
    truck_type = Column(SQLEnum(TruckType), default=TruckType.OPEN_BODY)
    capacity_tons = Column(Float, nullable=False)
    legal_payload_tons = Column(Float, nullable=True)
    quoted_freight_inr = Column(Float, nullable=True)
    status = Column(SQLEnum(TruckStatus), default=TruckStatus.ONLINE_AVAILABLE)
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.VERIFIED)
    is_demo = Column(Boolean, default=False, index=True)
    
    current_lat = Column(Float, nullable=True)
    current_lon = Column(Float, nullable=True)
    current_location_name = Column(String(255), nullable=True)
    last_location_time = Column(DateTime, nullable=True)

    driver = relationship("Driver", back_populates="trucks")
    organization = relationship("Organization", back_populates="trucks")
    assignments = relationship("VehicleAssignment", back_populates="truck", cascade="all, delete-orphan")
    locations = relationship("TruckLocation", back_populates="truck", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="truck")
    bookings = relationship("Booking", back_populates="truck")
    shipments = relationship("Shipment", back_populates="truck")
    agreements = relationship("FreightAgreement", back_populates="truck")
    inspections = relationship("PreTripInspection", back_populates="truck", cascade="all, delete-orphan")
    breakdowns = relationship("VehicleBreakdown", back_populates="truck", cascade="all, delete-orphan")
    sos_events = relationship("SOSEvent", back_populates="truck", cascade="all, delete-orphan")

class VehicleAssignment(Base):
    __tablename__ = "vehicle_assignments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False, index=True)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False, index=True)
    assigned_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    assigned_at = Column(DateTime, default=utcnow)
    unassigned_at = Column(DateTime, nullable=True)
    assignment_notes = Column(Text, nullable=True)

    truck = relationship("Truck", back_populates="assignments")
    driver = relationship("Driver", back_populates="assignments")
    assigned_by = relationship("User")

class Load(Base):
    __tablename__ = "loads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False)
    
    origin_name = Column(String(255), nullable=False)
    origin_lat = Column(Float, nullable=False)
    origin_lon = Column(Float, nullable=False)
    
    destination_name = Column(String(255), nullable=False)
    destination_lat = Column(Float, nullable=False)
    destination_lon = Column(Float, nullable=False)
    
    cargo_type = Column(String(100), default="Industrial Goods")
    cargo_category = Column(SQLEnum(CargoCategory), default=CargoCategory.GENERAL_MERCHANDISE)
    cargo_description = Column(Text, nullable=True)
    cargo_weight_tons = Column(Float, nullable=False)
    declared_value_inr = Column(Float, default=100000.0)
    fragility = Column(SQLEnum(FragilityLevel), default=FragilityLevel.LOW)
    hazard_classification = Column(SQLEnum(HazardClass), default=HazardClass.NONE)
    handling_instructions = Column(Text, nullable=True)
    supporting_documents = Column(JSON, default=list)
    required_truck_type = Column(SQLEnum(TruckType), nullable=True)
    min_capacity_tons = Column(Float, nullable=False)
    max_capacity_tons = Column(Float, nullable=False)
    
    pickup_window_start = Column(DateTime, nullable=False)
    pickup_window_end = Column(DateTime, nullable=False)
    target_budget = Column(Float, nullable=True)
    estimated_benchmark_price = Column(Float, nullable=True)
    cargo_notes = Column(Text, nullable=True)
    
    status = Column(SQLEnum(LoadStatus), default=LoadStatus.POSTED)
    is_demo = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    dealer = relationship("Dealer", back_populates="loads")
    matches = relationship("Match", back_populates="load", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="load")
    shipment = relationship("Shipment", back_populates="load", uselist=False)
    insurance = relationship("CargoInsurance", back_populates="load", uselist=False)

class Match(Base):
    __tablename__ = "matches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=False)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)
    
    total_score = Column(Float, nullable=False)
    route_compat_score = Column(Float, default=0.0)
    availability_score = Column(Float, default=0.0)
    proximity_score = Column(Float, default=0.0)
    capacity_score = Column(Float, default=0.0)
    price_score = Column(Float, default=0.0)
    reliability_score = Column(Float, default=0.0)
    return_potential_score = Column(Float, default=0.0)
    
    road_eta_km = Column(Float, default=0.0)
    road_eta_mins = Column(Integer, default=0)
    explanation_summary = Column(Text, nullable=False)
    factor_breakdown = Column(JSON, nullable=False)
    
    is_coming_near_you = Column(Boolean, default=False)
    estimated_arrival_at_pickup = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, default=utcnow)

    load = relationship("Load", back_populates="matches")
    truck = relationship("Truck", back_populates="matches")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=False)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False)
    
    offered_price = Column(Float, nullable=False)
    status = Column(SQLEnum(BookingStatus), default=BookingStatus.PENDING)
    rejection_reason = Column(String(255), nullable=True)
    is_demo = Column(Boolean, default=False, index=True)
    
    requested_at = Column(DateTime, default=utcnow)
    responded_at = Column(DateTime, nullable=True)

    load = relationship("Load", back_populates="bookings")
    truck = relationship("Truck", back_populates="bookings")
    driver = relationship("Driver", back_populates="bookings")
    dealer = relationship("Dealer", back_populates="bookings")
    shipment = relationship("Shipment", back_populates="booking", uselist=False)
    agreements = relationship("FreightAgreement", back_populates="booking", cascade="all, delete-orphan")
    state_history = relationship("BookingStateHistory", back_populates="booking", cascade="all, delete-orphan")
    direct_payments = relationship("DirectPayment", back_populates="booking", cascade="all, delete-orphan")
    platform_invoices = relationship("PlatformInvoice", back_populates="booking", cascade="all, delete-orphan")
    disputes = relationship("DisputeCase", back_populates="booking", cascade="all, delete-orphan")
    insurance = relationship("CargoInsurance", back_populates="booking", uselist=False)

class FreightAgreement(Base):
    __tablename__ = "freight_agreements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=False)
    
    # Counterparties
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False)
    dealer_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    transporter_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=True)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)

    version = Column(Integer, default=1, nullable=False)
    status = Column(SQLEnum(AgreementStatus), default=AgreementStatus.PENDING_ACCEPTANCE)

    # Commercial & Operational terms
    agreed_freight = Column(Float, nullable=False)
    additional_charges = Column(JSON, default=dict)
    cargo_details = Column(JSON, nullable=False)
    vehicle_details = Column(JSON, nullable=False)
    driver_details = Column(JSON, nullable=False)

    pickup_terms = Column(Text, nullable=False)
    delivery_terms = Column(Text, nullable=False)
    insurance_requirements = Column(Text, nullable=False)
    cancellation_terms = Column(Text, nullable=False)
    delay_detention_rules = Column(Text, nullable=False)
    claims_dispute_conditions = Column(Text, nullable=False)

    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    booking = relationship("Booking", back_populates="agreements")
    truck = relationship("Truck", back_populates="agreements")
    dealer = relationship("Dealer")
    driver = relationship("Driver")
    dealer_user = relationship("User", foreign_keys=[dealer_user_id])
    transporter_user = relationship("User", foreign_keys=[transporter_user_id])
    acceptances = relationship("AgreementAcceptance", back_populates="agreement", cascade="all, delete-orphan")

class AgreementAcceptance(Base):
    __tablename__ = "agreement_acceptances"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agreement_id = Column(String(36), ForeignKey("freight_agreements.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    party_role = Column(SQLEnum(UserRole), nullable=False)

    content_hash = Column(String(64), nullable=False)
    ip_address = Column(String(45), default="127.0.0.1")
    user_agent = Column(String(255), default="LoadLink Web Client")
    acceptance_method = Column(String(50), default="EXPLICIT_DIGITAL_CONFIRMATION")
    accepted_at = Column(DateTime, default=utcnow)

    agreement = relationship("FreightAgreement", back_populates="acceptances")
    user = relationship("User")
    organization = relationship("Organization")

class BookingStateHistory(Base):
    __tablename__ = "booking_state_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    from_status = Column(SQLEnum(BookingStatus), nullable=True)
    to_status = Column(SQLEnum(BookingStatus), nullable=False)
    changed_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reason = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=utcnow)

    booking = relationship("Booking", back_populates="state_history")
    changed_by = relationship("User")

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, unique=True)
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=False, unique=True)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False)
    
    state = Column(SQLEnum(ShipmentState), default=ShipmentState.CONFIRMED)
    idempotency_key = Column(String(64), nullable=True, index=True)
    
    pickup_eta = Column(DateTime, nullable=True)
    delivery_eta = Column(DateTime, nullable=True)
    actual_pickup_time = Column(DateTime, nullable=True)
    actual_delivery_time = Column(DateTime, nullable=True)
    
    distance_km = Column(Float, default=0.0)
    agreed_freight = Column(Float, nullable=False)
    is_demo = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    booking = relationship("Booking", back_populates="shipment")
    load = relationship("Load", back_populates="shipment")
    truck = relationship("Truck", back_populates="shipments")
    driver = relationship("Driver", back_populates="shipments")
    dealer = relationship("Dealer", back_populates="shipments")
    pod = relationship("POD", back_populates="shipment", uselist=False, cascade="all, delete-orphan")
    locations = relationship("TruckLocation", back_populates="shipment", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="shipment", cascade="all, delete-orphan")
    custody_events = relationship("CustodyEvent", back_populates="shipment", cascade="all, delete-orphan")
    insurance = relationship("CargoInsurance", back_populates="shipment", uselist=False)
    direct_payments = relationship("DirectPayment", back_populates="shipment")
    disputes = relationship("DisputeCase", back_populates="shipment")
    sos_events = relationship("SOSEvent", back_populates="shipment")
    breakdowns = relationship("VehicleBreakdown", back_populates="shipment")
    replacements = relationship("TruckReplacementWorkflow", back_populates="shipment")

class TruckLocation(Base):
    __tablename__ = "truck_locations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=True)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=0.0)
    heading = Column(Float, default=0.0)
    accuracy_meters = Column(Float, default=5.0)
    source = Column(String(50), default="GPS")
    sequence_number = Column(Integer, default=0)
    is_suspicious_jump = Column(Boolean, default=False)
    is_demo = Column(Boolean, default=False, index=True)
    
    recorded_at = Column(DateTime, default=utcnow)

    shipment = relationship("Shipment", back_populates="locations")
    truck = relationship("Truck", back_populates="locations")

class POD(Base):
    __tablename__ = "pods"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=False, unique=True)
    
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    receiver_name = Column(String(255), nullable=False)
    receiver_phone = Column(String(20), nullable=True)
    receiver_signature_notes = Column(Text, nullable=True)
    
    submitted_by_driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False)
    submitted_at = Column(DateTime, default=utcnow)
    
    verification_status = Column(SQLEnum(PODStatus), default=PODStatus.PENDING_REVIEW)
    verified_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(255), nullable=True)

    shipment = relationship("Shipment", back_populates="pod")

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=False)
    rater_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    rated_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    score = Column(Integer, nullable=False)  # 1-5
    tags = Column(JSON, default=list)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    shipment = relationship("Shipment", back_populates="ratings")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    payload = Column(JSON, default=dict)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_name = Column(String(100), nullable=False)
    entity_id = Column(String(36), nullable=False)
    state_before = Column(String(100), nullable=True)
    state_after = Column(String(100), nullable=True)
    metadata_json = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=utcnow)

    actor = relationship("User", back_populates="audit_logs")

class SystemConfiguration(Base):
    __tablename__ = "system_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    config_key = Column(String(100), unique=True, index=True, nullable=False)
    config_value_json = Column(JSON, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

# --- Master Prompt 2 Entities ---

class CustodyEvent(Base):
    __tablename__ = "custody_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)
    event_type = Column(SQLEnum(CustodyEventType), nullable=False)

    # Loading / Verification Fields
    seal_number = Column(String(100), nullable=True)
    seal_intact = Column(Boolean, default=True)
    cargo_condition = Column(SQLEnum(CargoCondition), default=CargoCondition.INTACT)
    recorded_weight_tons = Column(Float, nullable=True)
    recorded_quantity = Column(Float, nullable=True)
    weight_discrepancy_tons = Column(Float, default=0.0)
    quantity_discrepancy = Column(Float, default=0.0)
    photographs = Column(JSON, default=list)

    # Telematics & Location
    location_name = Column(String(255), nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lon = Column(Float, nullable=True)

    # Driver Handover
    driver_acknowledged = Column(Boolean, default=False)
    driver_acknowledgement_time = Column(DateTime, nullable=True)
    driver_notes = Column(Text, nullable=True)

    # Delivery & Receiver Acknowledgement
    receiver_name = Column(String(255), nullable=True)
    receiver_phone = Column(String(50), nullable=True)
    receiver_acknowledged = Column(Boolean, default=False)
    delivery_type = Column(SQLEnum(DeliveryType), default=DeliveryType.FULL_DELIVERY)
    delivery_otp = Column(String(10), nullable=True)
    otp_verified = Column(Boolean, default=False)

    # Incidents & Damage Reporting
    damage_reported = Column(Boolean, default=False)
    damage_description = Column(Text, nullable=True)
    supporting_evidence = Column(JSON, default=list)

    recorded_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    shipment = relationship("Shipment", back_populates="custody_events")
    booking = relationship("Booking")
    recorded_by = relationship("User")

class InsurancePolicyRule(Base):
    __tablename__ = "insurance_policy_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    version = Column(Integer, default=1, index=True)
    policy_name = Column(String(255), default="Standard Corridor Freight Insurance Policy")
    max_uninsured_value_inr = Column(Float, default=200000.0)
    hazardous_requires_insurance = Column(Boolean, default=True)
    fragile_high_requires_insurance = Column(Boolean, default=True)
    review_threshold_inr = Column(Float, default=2000000.0)
    is_active = Column(Boolean, default=True)
    approved_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    approved_by = relationship("User")

class CargoInsurance(Base):
    __tablename__ = "cargo_insurances"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=True, index=True)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=True, index=True)

    assessment_result = Column(SQLEnum(InsuranceAssessmentResult), default=InsuranceAssessmentResult.NOT_REQUIRED)
    assessment_reasons = Column(JSON, default=list)

    policy_number = Column(String(100), nullable=True)
    insurer_name = Column(String(255), nullable=True)
    policyholder_name = Column(String(255), nullable=True)
    insured_party = Column(String(255), nullable=True)
    coverage_amount_inr = Column(Float, default=0.0)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    exclusions = Column(Text, nullable=True)
    certificate_url = Column(String(500), nullable=True)

    verification_status = Column(SQLEnum(InsuranceVerificationStatus), default=InsuranceVerificationStatus.UNASSESSED)
    verified_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    exception_permitted = Column(Boolean, default=False)
    exception_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    shipment = relationship("Shipment", back_populates="insurance")
    booking = relationship("Booking", back_populates="insurance")
    load = relationship("Load", back_populates="insurance")
    verified_by = relationship("User")

class DirectPayment(Base):
    __tablename__ = "direct_payments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=True, index=True)

    payer_dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=True)
    payer_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    payee_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    agreed_freight_inr = Column(Float, nullable=False)
    amount_paid_inr = Column(Float, default=0.0)
    payment_status = Column(SQLEnum(DirectPaymentStatus), default=DirectPaymentStatus.PENDING)
    due_date = Column(DateTime, nullable=True)
    payment_method = Column(SQLEnum(PaymentMethod), default=PaymentMethod.NEFT)
    payment_reference = Column(String(100), nullable=True)
    payment_evidence_url = Column(String(500), nullable=True)

    dealer_reported_at = Column(DateTime, nullable=True)
    dealer_notes = Column(Text, nullable=True)
    transporter_acknowledged_at = Column(DateTime, nullable=True)
    transporter_notes = Column(Text, nullable=True)

    is_partial = Column(Boolean, default=False)
    remaining_balance_inr = Column(Float, default=0.0)
    dispute_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    booking = relationship("Booking", back_populates="direct_payments")
    shipment = relationship("Shipment", back_populates="direct_payments")
    payer_user = relationship("User", foreign_keys=[payer_user_id])
    payee_user = relationship("User", foreign_keys=[payee_user_id])

class PlatformInvoice(Base):
    __tablename__ = "platform_invoices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    billed_to_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    fee_type = Column(SQLEnum(FeeType), default=FeeType.FIXED_BOOKING_FEE)
    freight_benchmark_inr = Column(Float, default=0.0)
    base_fee_inr = Column(Float, nullable=False)
    gst_rate_percent = Column(Float, default=18.0)
    gst_amount_inr = Column(Float, nullable=False)
    total_payable_inr = Column(Float, nullable=False)

    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.ISSUED)
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_gateway_ref = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    booking = relationship("Booking", back_populates="platform_invoices")
    billed_to = relationship("User")

class DisputeCase(Base):
    __tablename__ = "dispute_cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_number = Column(String(50), unique=True, index=True, nullable=False)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=True, index=True)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)

    raised_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    respondent_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    category = Column(SQLEnum(DisputeCategory), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    disputed_amount_inr = Column(Float, nullable=True)
    status = Column(SQLEnum(DisputeStatus), default=DisputeStatus.OPEN)

    assigned_officer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolution_proposal = Column(Text, nullable=True)
    resolution_accepted_by_complainant = Column(Boolean, default=False)
    resolution_accepted_by_respondent = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)

    ai_classification = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    shipment = relationship("Shipment", back_populates="disputes")
    booking = relationship("Booking", back_populates="disputes")
    raised_by = relationship("User", foreign_keys=[raised_by_user_id])
    respondent = relationship("User", foreign_keys=[respondent_user_id])
    assigned_officer = relationship("User", foreign_keys=[assigned_officer_id])
    evidence = relationship("DisputeEvidence", back_populates="dispute", cascade="all, delete-orphan")
    messages = relationship("DisputeMessage", back_populates="dispute", cascade="all, delete-orphan")

class DisputeEvidence(Base):
    __tablename__ = "dispute_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dispute_id = Column(String(36), ForeignKey("dispute_cases.id"), nullable=False, index=True)
    uploaded_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    evidence_type = Column(String(100), default="PHOTO_DAMAGE")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    dispute = relationship("DisputeCase", back_populates="evidence")
    uploaded_by = relationship("User")

class DisputeMessage(Base):
    __tablename__ = "dispute_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dispute_id = Column(String(36), ForeignKey("dispute_cases.id"), nullable=False, index=True)
    sender_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    message = Column(Text, nullable=False)
    is_officer_internal_note = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    dispute = relationship("DisputeCase", back_populates="messages")
    sender = relationship("User")

class Grievance(Base):
    __tablename__ = "grievances"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ticket_number = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    category = Column(String(100), default="GENERAL_SERVICE")
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    assigned_officer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    status = Column(SQLEnum(GrievanceStatus), default=GrievanceStatus.SUBMITTED)

    acknowledged_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])
    assigned_officer = relationship("User", foreign_keys=[assigned_officer_id])

# --- Master Prompt 3: SOS, Breakdown, Inspection & Replacement Models ---

class SOSEvent(Base):
    __tablename__ = "sos_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(64), unique=True, index=True, nullable=False)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False, index=True)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False, index=True)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=True, index=True)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_meters = Column(Float, default=5.0)
    incident_category = Column(SQLEnum(SOSCategory), default=SOSCategory.ACCIDENT)
    network_status = Column(SQLEnum(NetworkStatus), default=NetworkStatus.ONLINE)
    device_timestamp = Column(DateTime, nullable=False)
    server_timestamp = Column(DateTime, default=utcnow)
    status = Column(SQLEnum(SOSStatus), default=SOSStatus.TRIGGERED, index=True)

    # Notification & Response Tracking
    control_room_notified = Column(Boolean, default=False)
    control_room_notified_at = Column(DateTime, nullable=True)
    dealer_notified = Column(Boolean, default=False)
    dealer_notified_at = Column(DateTime, nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    emergency_contact_notified = Column(Boolean, default=False)
    emergency_contact_notified_at = Column(DateTime, nullable=True)

    assigned_responder_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    assigned_responder_notes = Column(Text, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    audio_or_media_url = Column(String(500), nullable=True)

    driver = relationship("Driver", back_populates="sos_events")
    truck = relationship("Truck", back_populates="sos_events")
    shipment = relationship("Shipment", back_populates="sos_events")
    booking = relationship("Booking")
    assigned_responder = relationship("User", foreign_keys=[assigned_responder_id])

class VehicleBreakdown(Base):
    __tablename__ = "vehicle_breakdowns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False, index=True)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False, index=True)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=True, index=True)

    issue_type = Column(SQLEnum(BreakdownIssueType), nullable=False)
    description = Column(Text, nullable=False)
    photo_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    device_timestamp = Column(DateTime, nullable=False)
    reported_at = Column(DateTime, default=utcnow)
    status = Column(SQLEnum(BreakdownStatus), default=BreakdownStatus.REPORTED, index=True)

    assigned_mechanic_or_service = Column(String(255), nullable=True)
    estimated_repair_hours = Column(Float, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    truck = relationship("Truck", back_populates="breakdowns")
    driver = relationship("Driver", back_populates="breakdowns")
    shipment = relationship("Shipment", back_populates="breakdowns")
    replacements = relationship("TruckReplacementWorkflow", back_populates="breakdown")

class PreTripInspection(Base):
    __tablename__ = "pre_trip_inspections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False, index=True)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False, index=True)
    inspected_at = Column(DateTime, default=utcnow)

    # 11-Point Pre-Trip Safety Checklist
    tyres_ok = Column(Boolean, default=True)
    brakes_ok = Column(Boolean, default=True)
    lights_ok = Column(Boolean, default=True)
    indicators_ok = Column(Boolean, default=True)
    mirrors_ok = Column(Boolean, default=True)
    steering_ok = Column(Boolean, default=True)
    engine_indicators_ok = Column(Boolean, default=True)
    oil_level_ok = Column(Boolean, default=True)
    coolant_level_ok = Column(Boolean, default=True)
    documents_valid = Column(Boolean, default=True)
    cargo_securing_equipment_ok = Column(Boolean, default=True)

    critical_defect_found = Column(Boolean, default=False)
    defect_description = Column(Text, nullable=True)
    inspection_evidence_photos = Column(JSON, default=list)

    safety_hold_triggered = Column(Boolean, default=False)
    safety_hold_cleared_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    safety_hold_cleared_at = Column(DateTime, nullable=True)
    repair_evidence_url = Column(String(500), nullable=True)
    clearance_notes = Column(Text, nullable=True)

    truck = relationship("Truck", back_populates="inspections")
    driver = relationship("Driver", back_populates="inspections")
    cleared_by = relationship("User", foreign_keys=[safety_hold_cleared_by_id])

class TruckReplacementWorkflow(Base):
    __tablename__ = "truck_replacement_workflows"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)
    original_truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)
    original_driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False)
    replacement_truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=True)
    replacement_driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=True)
    breakdown_id = Column(String(36), ForeignKey("vehicle_breakdowns.id"), nullable=True)

    reason = Column(Text, nullable=False)
    transporter_approved = Column(Boolean, default=False)
    transporter_approved_at = Column(DateTime, nullable=True)
    dealer_approved = Column(Boolean, default=False)
    dealer_approved_at = Column(DateTime, nullable=True)

    custody_transfer_verified = Column(Boolean, default=False)
    transfer_cargo_condition = Column(SQLEnum(CargoCondition), default=CargoCondition.INTACT)
    new_seal_number = Column(String(100), nullable=True)
    transfer_photos = Column(JSON, default=list)
    driver_acknowledgement = Column(Boolean, default=False)

    status = Column(SQLEnum(ReplacementStatus), default=ReplacementStatus.INITIATED, index=True)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

    shipment = relationship("Shipment", back_populates="replacements")
    original_truck = relationship("Truck", foreign_keys=[original_truck_id])
    original_driver = relationship("Driver", foreign_keys=[original_driver_id])
    replacement_truck = relationship("Truck", foreign_keys=[replacement_truck_id])
    replacement_driver = relationship("Driver", foreign_keys=[replacement_driver_id])
    breakdown = relationship("VehicleBreakdown", back_populates="replacements")

