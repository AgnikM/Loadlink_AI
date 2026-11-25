from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, model_validator, ConfigDict
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

# --- Auth & User Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: str
    name: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    phone: str
    password: str
    name: str
    role: UserRole
    # For Dealer / Transporter / Fleet Manager
    organization_name: Optional[str] = None
    organization_type: Optional[str] = "DEALER_SHIPPER"
    gstin: Optional[str] = None
    fleet_size: Optional[int] = 0
    # For Driver
    license_number: Optional[str] = None
    # Truck info if Driver or Transporter
    truck_registration_no: Optional[str] = None
    truck_type: Optional[TruckType] = None
    truck_capacity_tons: Optional[float] = None
    ownership_type: Optional[FleetOwnershipType] = FleetOwnershipType.EXTERNAL_TRANSPORTER
    initial_location_hub: Optional[str] = "Kolkata Port / Docks"

class UserOut(BaseModel):
    id: str
    email: str
    phone: str
    name: str
    role: UserRole
    verification_status: VerificationStatus
    created_at: datetime
    dealer_id: Optional[str] = None
    driver_id: Optional[str] = None
    transporter_id: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    truck_id: Optional[str] = None
    trust_or_reliability_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

# --- Load Schemas ---
class LoadCreate(BaseModel):
    origin_name: Optional[str] = None
    origin_lat: Optional[float] = None
    origin_lon: Optional[float] = None
    destination_name: Optional[str] = None
    destination_lat: Optional[float] = None
    destination_lon: Optional[float] = None
    cargo_type: str = "Industrial Freight"
    cargo_category: Optional[CargoCategory] = CargoCategory.GENERAL_MERCHANDISE
    cargo_description: Optional[str] = None
    cargo_weight_tons: Optional[float] = None
    declared_value_inr: Optional[float] = 100000.0
    fragility: Optional[FragilityLevel] = FragilityLevel.LOW
    hazard_classification: Optional[HazardClass] = HazardClass.NONE
    handling_instructions: Optional[str] = None
    supporting_documents: Optional[List[Dict[str, Any]]] = None
    required_truck_type: Optional[TruckType] = None
    min_capacity_tons: Optional[float] = None
    max_capacity_tons: Optional[float] = None
    pickup_window_start: Optional[datetime] = None
    pickup_window_end: Optional[datetime] = None
    target_budget: Optional[float] = None
    cargo_notes: Optional[str] = None

    # Aliases supported for frontend compatibility
    origin: Optional[str] = None
    destination: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lon: Optional[float] = None
    drop_lat: Optional[float] = None
    drop_lon: Optional[float] = None
    required_tonnes: Optional[float] = None
    vehicle_type: Optional[str] = None
    budget_inr: Optional[float] = None
    pickup_at: Optional[str] = None
    dealer_name: Optional[str] = None
    category: Optional[str] = None
    declared_value: Optional[float] = None
    description: Optional[str] = None
    hazard_class: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_load_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "category" in data and not data.get("cargo_category"):
                data["cargo_category"] = data["category"]
            if "declared_value" in data and data.get("declared_value_inr") is None:
                try: data["declared_value_inr"] = float(data["declared_value"])
                except Exception: pass
            if "description" in data and not data.get("cargo_description"):
                data["cargo_description"] = data["description"]
            if "hazard_class" in data and not data.get("hazard_classification"):
                data["hazard_classification"] = data["hazard_class"]
            if "origin" in data and not data.get("origin_name"):
                data["origin_name"] = data["origin"]
            if "destination" in data and not data.get("destination_name"):
                data["destination_name"] = data["destination"]
            if "pickup_lat" in data and data.get("origin_lat") is None:
                try: data["origin_lat"] = float(data["pickup_lat"])
                except Exception: pass
            if "pickup_lon" in data and data.get("origin_lon") is None:
                try: data["origin_lon"] = float(data["pickup_lon"])
                except Exception: pass
            if "drop_lat" in data and data.get("destination_lat") is None:
                try: data["destination_lat"] = float(data["drop_lat"])
                except Exception: pass
            if "drop_lon" in data and data.get("destination_lon") is None:
                try: data["destination_lon"] = float(data["drop_lon"])
                except Exception: pass
            if "required_tonnes" in data and data.get("cargo_weight_tons") is None:
                try: data["cargo_weight_tons"] = float(data["required_tonnes"])
                except Exception: pass
            if "budget_inr" in data and data.get("target_budget") is None:
                try: data["target_budget"] = float(data["budget_inr"])
                except Exception: pass
            if "vehicle_type" in data and data.get("required_truck_type") is None:
                vt = str(data["vehicle_type"]).upper()
                if "CONTAINER" in vt:
                    data["required_truck_type"] = TruckType.CLOSED_CONTAINER
                elif "TRAILER" in vt:
                    data["required_truck_type"] = TruckType.TRAILER
                elif "TIPPER" in vt:
                    data["required_truck_type"] = TruckType.TIPPER
                else:
                    data["required_truck_type"] = TruckType.OPEN_BODY
            if "pickup_at" in data and data.get("pickup_window_start") is None:
                try:
                    p_at = data["pickup_at"]
                    if isinstance(p_at, str):
                        data["pickup_window_start"] = datetime.fromisoformat(p_at.replace("Z", "+00:00"))
                except Exception:
                    data["pickup_window_start"] = datetime.now(timezone.utc) + timedelta(hours=2)
            if not data.get("pickup_window_start"):
                data["pickup_window_start"] = datetime.now(timezone.utc) + timedelta(hours=2)
            if not data.get("pickup_window_end"):
                p_start = data.get("pickup_window_start")
                if isinstance(p_start, str):
                    try: p_start = datetime.fromisoformat(p_start.replace("Z", "+00:00"))
                    except Exception: p_start = datetime.now(timezone.utc)
                data["pickup_window_end"] = p_start + timedelta(hours=18)
            if data.get("cargo_weight_tons") is not None:
                w = float(data["cargo_weight_tons"])
                if data.get("min_capacity_tons") is None:
                    data["min_capacity_tons"] = max(1.0, w - 2.0)
                if data.get("max_capacity_tons") is None:
                    data["max_capacity_tons"] = w + 10.0
            if not data.get("origin_name"):
                data["origin_name"] = "Kolkata Port / Docks"
            if not data.get("destination_name"):
                data["destination_name"] = "Durgapur Steel Complex"
            if data.get("origin_lat") is None:
                data["origin_lat"] = 22.5448
            if data.get("origin_lon") is None:
                data["origin_lon"] = 88.3186
            if data.get("destination_lat") is None:
                data["destination_lat"] = 23.5204
            if data.get("destination_lon") is None:
                data["destination_lon"] = 87.3119
            if data.get("cargo_weight_tons") is None:
                data["cargo_weight_tons"] = 15.0
                data["min_capacity_tons"] = 10.0
                data["max_capacity_tons"] = 20.0
        return data

class LoadOut(BaseModel):
    id: str
    dealer_id: str
    dealer_name: Optional[str] = None
    origin_name: str
    origin_lat: float
    origin_lon: float
    destination_name: str
    destination_lat: float
    destination_lon: float
    cargo_type: str
    cargo_category: Optional[CargoCategory] = CargoCategory.GENERAL_MERCHANDISE
    cargo_description: Optional[str] = None
    cargo_weight_tons: float
    declared_value_inr: Optional[float] = 100000.0
    fragility: Optional[FragilityLevel] = FragilityLevel.LOW
    hazard_classification: Optional[HazardClass] = HazardClass.NONE
    handling_instructions: Optional[str] = None
    supporting_documents: Optional[List[Dict[str, Any]]] = None
    required_truck_type: Optional[TruckType]
    min_capacity_tons: float
    max_capacity_tons: float
    pickup_window_start: datetime
    pickup_window_end: datetime
    target_budget: Optional[float]
    estimated_benchmark_price: Optional[float]
    cargo_notes: Optional[str]
    status: LoadStatus
    is_demo: bool = False
    created_at: datetime
    matches_count: Optional[int] = 0

    # Frontend compatibility fields
    origin: Optional[str] = None
    destination: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lon: Optional[float] = None
    drop_lat: Optional[float] = None
    drop_lon: Optional[float] = None
    required_tonnes: Optional[float] = None
    vehicle_type: Optional[str] = None
    budget_inr: Optional[float] = None
    pickup_at: Optional[str] = None

    @model_validator(mode="after")
    def populate_display_fields(self):
        self.origin = self.origin_name
        self.destination = self.destination_name
        self.pickup_lat = self.origin_lat
        self.pickup_lon = self.origin_lon
        self.drop_lat = self.destination_lat
        self.drop_lon = self.destination_lon
        self.required_tonnes = self.cargo_weight_tons
        vt_map = {
            TruckType.OPEN_BODY: "Open",
            TruckType.CLOSED_CONTAINER: "Container",
            TruckType.TRAILER: "Trailer",
            TruckType.TIPPER: "Tipper"
        }
        self.vehicle_type = vt_map.get(self.required_truck_type, "Open") if self.required_truck_type else "Open"
        self.budget_inr = self.target_budget or self.estimated_benchmark_price or 18000.0
        self.pickup_at = self.pickup_window_start.isoformat() if self.pickup_window_start else None
        return self

    model_config = ConfigDict(from_attributes=True)

# --- Truck Schemas ---
class TruckCreate(BaseModel):
    registration_no: Optional[str] = None
    truck_type: TruckType = TruckType.OPEN_BODY
    capacity_tons: Optional[float] = None
    ownership_type: Optional[FleetOwnershipType] = FleetOwnershipType.EXTERNAL_TRANSPORTER
    organization_id: Optional[str] = None
    driver_id: Optional[str] = None
    current_lat: Optional[float] = 22.5448
    current_lon: Optional[float] = 88.3186
    current_location_name: Optional[str] = "Kolkata Port / Docks"

    # Compatibility fields for frontend
    id: Optional[str] = None
    driver_name: Optional[str] = None
    phone: Optional[str] = None
    vehicle_type: Optional[str] = None
    capacity_tonnes: Optional[float] = None
    legal_payload_tonnes: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reliability_score: Optional[float] = 70.0
    quoted_freight_inr: Optional[float] = 19000.0

    @model_validator(mode="before")
    @classmethod
    def populate_truck_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "id" in data and not data.get("registration_no"):
                data["registration_no"] = str(data["id"]).strip().upper()
            if "capacity_tonnes" in data and data.get("capacity_tons") is None:
                try: data["capacity_tons"] = float(data["capacity_tonnes"])
                except Exception: pass
            if "legal_payload_tonnes" in data and data.get("capacity_tons") is None:
                try: data["capacity_tons"] = float(data["legal_payload_tonnes"])
                except Exception: pass
            if "latitude" in data and data.get("current_lat") is None:
                try: data["current_lat"] = float(data["latitude"])
                except Exception: pass
            if "longitude" in data and data.get("current_lon") is None:
                try: data["current_lon"] = float(data["longitude"])
                except Exception: pass
            if "vehicle_type" in data and data.get("truck_type") is None:
                vt = str(data["vehicle_type"]).upper()
                if "CONTAINER" in vt: data["truck_type"] = TruckType.CLOSED_CONTAINER
                elif "TRAILER" in vt: data["truck_type"] = TruckType.TRAILER
                elif "TIPPER" in vt: data["truck_type"] = TruckType.TIPPER
                else: data["truck_type"] = TruckType.OPEN_BODY
            if not data.get("registration_no"):
                import random
                data["registration_no"] = f"WB-{random.randint(10, 99)}-{random.randint(1000, 9999)}"
            if data.get("capacity_tons") is None:
                data["capacity_tons"] = 16.0
        return data

class TruckAvailabilityUpdate(BaseModel):
    status: Optional[TruckStatus] = None
    available: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def validate_availability(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "available" in data and data.get("status") is None:
                data["status"] = TruckStatus.ONLINE_AVAILABLE if data["available"] else TruckStatus.OFFLINE
        return data

class TruckLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = 0.0
    heading: Optional[float] = 0.0
    accuracy_meters: Optional[float] = 5.0
    source: Optional[str] = "GPS"
    location_name: Optional[str] = None

class TruckOut(BaseModel):
    id: str
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    driver_reliability_score: Optional[float] = None
    ownership_type: Optional[FleetOwnershipType] = FleetOwnershipType.EXTERNAL_TRANSPORTER
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    registration_no: str
    truck_type: TruckType
    capacity_tons: float
    legal_payload_tons: Optional[float] = None
    status: TruckStatus
    verification_status: VerificationStatus
    is_demo: bool = False
    current_lat: Optional[float]
    current_lon: Optional[float]
    current_location_name: Optional[str]
    last_location_time: Optional[datetime]

    # Frontend compatibility fields
    vehicle_type: Optional[str] = None
    capacity_tonnes: Optional[float] = None
    legal_payload_tonnes: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    destination_lat: Optional[float] = None
    destination_lon: Optional[float] = None
    available: Optional[bool] = None
    verified: Optional[bool] = None
    documents_valid: Optional[bool] = None
    reliability_score: Optional[float] = None
    quoted_freight_inr: Optional[float] = None

    @model_validator(mode="after")
    def populate_truck_display_fields(self):
        vt_map = {
            TruckType.OPEN_BODY: "Open",
            TruckType.CLOSED_CONTAINER: "Container",
            TruckType.TRAILER: "Trailer",
            TruckType.TIPPER: "Tipper"
        }
        self.vehicle_type = vt_map.get(self.truck_type, "Open")
        self.capacity_tonnes = self.capacity_tons
        self.legal_payload_tonnes = self.legal_payload_tons or self.capacity_tons
        self.latitude = self.current_lat if self.current_lat is not None else 22.5448
        self.longitude = self.current_lon if self.current_lon is not None else 88.3186
        self.available = (self.status in [TruckStatus.ONLINE_AVAILABLE, TruckStatus.AVAILABLE])
        self.verified = (self.verification_status == VerificationStatus.VERIFIED and not self.is_demo)
        self.documents_valid = (self.verification_status == VerificationStatus.VERIFIED and not self.is_demo)
        self.reliability_score = self.driver_reliability_score or 85.0
        self.quoted_freight_inr = self.quoted_freight_inr or 19000.0
        return self

    model_config = ConfigDict(from_attributes=True)

# --- Fleet Assignment Schemas ---
class VehicleAssignmentCreate(BaseModel):
    truck_id: Optional[str] = None
    driver_id: str
    assignment_notes: Optional[str] = None

class VehicleAssignmentOut(BaseModel):
    id: str
    truck_id: str
    truck_registration_no: Optional[str] = None
    driver_id: str
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    driver_phone: Optional[str] = None
    is_active: bool
    assigned_at: datetime
    unassigned_at: Optional[datetime] = None
    assignment_notes: Optional[str] = None
    assigned_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Match Schemas ---
class MatchScoreBreakdown(BaseModel):
    route_compatibility: float
    availability_feasibility: float
    pickup_proximity: float
    capacity_fit: float
    price_competitiveness: float
    reliability: float
    return_load_potential: float

class MatchOut(BaseModel):
    id: str
    load_id: str
    truck_id: str
    truck_registration_no: str
    truck_type: TruckType
    truck_capacity_tons: float
    driver_id: str
    driver_name: str
    driver_phone: str
    driver_reliability_score: float
    total_score: float
    factor_breakdown: Dict[str, float]
    road_eta_km: float
    road_eta_mins: int
    explanation_summary: str
    is_coming_near_you: bool
    estimated_arrival_at_pickup: Optional[datetime]
    truck_current_lat: Optional[float]
    truck_current_lon: Optional[float]
    truck_location_name: Optional[str]
    is_demo: Optional[bool] = False

# --- Booking Schemas ---
class BookingCreate(BaseModel):
    load_id: str
    truck_id: str
    offered_price: Optional[float] = None
    agreed_freight_inr: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def populate_booking_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "agreed_freight_inr" in data and data.get("offered_price") is None:
                try: data["offered_price"] = float(data["agreed_freight_inr"])
                except Exception: pass
            elif "offered_price" in data and data.get("agreed_freight_inr") is None:
                try: data["agreed_freight_inr"] = float(data["offered_price"])
                except Exception: pass
            if data.get("offered_price") is None:
                data["offered_price"] = 18000.0
                data["agreed_freight_inr"] = 18000.0
        return data

class BookingAction(BaseModel):
    action: str  # ACCEPT, REJECT, CANCEL
    rejection_reason: Optional[str] = None

class BookingStatusUpdate(BaseModel):
    status: str  # ACCEPTED, IN_TRANSIT, DELIVERED, REJECTED, CANCELLED

class BookingOut(BaseModel):
    id: str
    load_id: str
    truck_id: str
    truck_registration_no: Optional[str] = None
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    dealer_id: str
    dealer_name: Optional[str] = None
    origin_name: Optional[str] = None
    destination_name: Optional[str] = None
    cargo_weight_tons: Optional[float] = None
    offered_price: float
    status: BookingStatus
    rejection_reason: Optional[str] = None
    requested_at: datetime
    responded_at: Optional[datetime]
    shipment_id: Optional[str] = None

    # Agreement integration
    agreement_id: Optional[str] = None
    agreement_status: Optional[AgreementStatus] = None
    is_agreement_accepted: bool = False

    # Frontend compatibility
    agreed_freight_inr: Optional[float] = None

    @model_validator(mode="after")
    def populate_booking_display_fields(self):
        self.agreed_freight_inr = self.offered_price
        return self

    model_config = ConfigDict(from_attributes=True)

# --- Direct Freight Agreement Schemas ---
class FreightAgreementCreate(BaseModel):
    booking_id: str
    agreed_freight: Optional[float] = None
    additional_charges: Optional[Dict[str, Any]] = None
    pickup_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    insurance_requirements: Optional[str] = None
    cancellation_terms: Optional[str] = None
    delay_detention_rules: Optional[str] = None
    claims_dispute_conditions: Optional[str] = None

class FreightAgreementUpdate(BaseModel):
    agreed_freight: Optional[float] = None
    additional_charges: Optional[Dict[str, Any]] = None
    pickup_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    insurance_requirements: Optional[str] = None
    cancellation_terms: Optional[str] = None
    delay_detention_rules: Optional[str] = None
    claims_dispute_conditions: Optional[str] = None

class AgreementAcceptanceCreate(BaseModel):
    acceptance_method: Optional[str] = "EXPLICIT_DIGITAL_CONFIRMATION"

class AgreementAcceptanceOut(BaseModel):
    id: str
    agreement_id: str
    version: int
    party_role: UserRole
    user_id: str
    user_name: Optional[str] = None
    organization_name: Optional[str] = None
    content_hash: str
    accepted_at: datetime
    acceptance_method: str

    model_config = ConfigDict(from_attributes=True)

class FreightAgreementOut(BaseModel):
    id: str
    booking_id: str
    load_id: str
    dealer_id: str
    dealer_name: Optional[str] = None
    dealer_user_id: str
    transporter_user_id: str
    transporter_name: Optional[str] = None
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    truck_id: str
    truck_registration_no: Optional[str] = None
    version: int
    status: AgreementStatus
    agreed_freight: float
    additional_charges: Dict[str, Any]
    cargo_details: Dict[str, Any]
    vehicle_details: Dict[str, Any]
    driver_details: Dict[str, Any]
    pickup_terms: str
    delivery_terms: str
    insurance_requirements: str
    cancellation_terms: str
    delay_detention_rules: str
    claims_dispute_conditions: str
    content_hash: str
    created_at: datetime
    updated_at: datetime
    acceptances: List[AgreementAcceptanceOut] = []
    is_accepted_by_dealer: bool = False
    is_accepted_by_transporter: bool = False
    is_mutually_accepted: bool = False

    model_config = ConfigDict(from_attributes=True)

class BookingStateHistoryOut(BaseModel):
    id: str
    booking_id: str
    from_status: Optional[BookingStatus] = None
    to_status: BookingStatus
    changed_by_name: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

# --- AI & Dashboard Summary Schemas ---
class DashboardSummaryOut(BaseModel):
    available_trucks: int
    open_loads: int
    bookings: int
    in_transit: int
    trucks: int
    loads: int

class AIMatchResult(BaseModel):
    truck_id: str
    eligible: bool
    score: float
    distance_km: float
    reasons: List[str]
    components: Dict[str, float]
    rules_score: float
    ai_score: float
    neural_network_score: Optional[float] = None
    ranking_method: str = "Deterministic 7-Factor Corridor Optimization Engine"
    is_demo: Optional[bool] = False

class AIMatchingResponse(BaseModel):
    load_id: str
    ranking_method: str
    results: List[AIMatchResult]

# --- Shipment & State Machine Schemas ---
class StateTransitionRequest(BaseModel):
    target_state: ShipmentState
    idempotency_key: Optional[str] = None
    note: Optional[str] = None

class ShipmentOut(BaseModel):
    id: str
    booking_id: str
    load_id: str
    truck_id: str
    truck_registration_no: Optional[str] = None
    truck_type: Optional[TruckType] = None
    driver_id: str
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    dealer_id: str
    dealer_name: Optional[str] = None
    state: ShipmentState
    origin_name: str
    origin_lat: float
    origin_lon: float
    destination_name: str
    destination_lat: float
    destination_lon: float
    cargo_type: str
    cargo_weight_tons: float
    agreed_freight: float
    distance_km: float
    pickup_eta: Optional[datetime]
    delivery_eta: Optional[datetime]
    actual_pickup_time: Optional[datetime]
    actual_delivery_time: Optional[datetime]
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    last_location_time: Optional[datetime] = None
    is_location_stale: bool = False
    created_at: datetime
    updated_at: datetime
    has_pod: bool = False
    pod_verification_status: Optional[PODStatus] = None

    model_config = ConfigDict(from_attributes=True)

# --- POD Schemas ---
class PODSubmitRequest(BaseModel):
    receiver_name: str
    receiver_phone: Optional[str] = None
    receiver_signature_notes: Optional[str] = None
    file_base64: Optional[str] = None  # Or file upload

class PODVerifyRequest(BaseModel):
    action: str  # VERIFY, REJECT
    rejection_reason: Optional[str] = None

class PODOut(BaseModel):
    id: str
    shipment_id: str
    file_url: str
    file_name: str
    receiver_name: str
    receiver_phone: Optional[str]
    receiver_signature_notes: Optional[str]
    submitted_at: datetime
    verification_status: PODStatus
    verified_at: Optional[datetime]
    rejection_reason: Optional[str]

    model_config = ConfigDict(from_attributes=True)

# --- Rating Schemas ---
class RatingCreate(BaseModel):
    shipment_id: str
    score: int = Field(..., ge=1, le=5)
    tags: List[str] = []
    comment: Optional[str] = None

class RatingOut(BaseModel):
    id: str
    shipment_id: str
    rater_name: str
    score: int
    tags: List[str]
    comment: Optional[str]
    created_at: datetime

# --- Admin & Analytics Schemas ---
class AdminKPIOut(BaseModel):
    total_users: int
    verified_drivers: int
    verified_dealers: int
    active_trucks_online: int
    total_loads_posted: int
    total_active_shipments: int
    completed_shipments: int
    total_gmv: float
    match_rate_percentage: float
    booking_conversion_rate: float
    average_on_time_percentage: float

class AuditLogOut(BaseModel):
    id: str
    actor_name: Optional[str]
    action: str
    entity_name: str
    entity_id: str
    state_before: Optional[str]
    state_after: Optional[str]
    timestamp: datetime
    metadata_json: Dict[str, Any]

class ReturnLoadOpportunity(BaseModel):
    load_id: str
    origin_name: str
    destination_name: str
    cargo_weight_tons: float
    target_budget: float
    pickup_window_start: datetime
    extra_earnings_estimate: float
    distance_from_delivery_km: float
    match_score: float

# --- Master Prompt 2 Schemas ---

# 1. Digital Custody & Handover
class LoadingHandoverCreate(BaseModel):
    seal_number: Optional[str] = None
    seal_intact: bool = True
    cargo_condition: CargoCondition = CargoCondition.INTACT
    recorded_weight_tons: Optional[float] = None
    recorded_quantity: Optional[float] = None
    photographs: List[str] = Field(default_factory=list)
    location_name: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    driver_acknowledged: bool = True
    driver_notes: Optional[str] = None

class TransitIncidentCreate(BaseModel):
    cargo_condition: CargoCondition = CargoCondition.DAMAGED
    seal_number: Optional[str] = None
    seal_intact: bool = True
    damage_reported: bool = True
    damage_description: str
    photographs: List[str] = Field(default_factory=list)
    location_name: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)

class DeliveryHandoverCreate(BaseModel):
    delivery_type: DeliveryType = DeliveryType.FULL_DELIVERY
    receiver_name: str
    receiver_phone: Optional[str] = None
    receiver_acknowledged: bool = True
    recorded_weight_tons: Optional[float] = None
    recorded_quantity: Optional[float] = None
    weight_discrepancy_tons: Optional[float] = None
    quantity_discrepancy: Optional[float] = None
    seal_number: Optional[str] = None
    seal_intact: bool = True
    cargo_condition: CargoCondition = CargoCondition.INTACT
    delivery_otp: Optional[str] = None
    photographs: List[str] = Field(default_factory=list)
    damage_reported: bool = False
    damage_description: Optional[str] = None
    driver_notes: Optional[str] = None
    location_name: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None

class CustodyEventOut(BaseModel):
    id: str
    shipment_id: str
    booking_id: Optional[str] = None
    event_type: CustodyEventType
    seal_number: Optional[str] = None
    seal_intact: bool
    cargo_condition: CargoCondition
    recorded_weight_tons: Optional[float] = None
    recorded_quantity: Optional[float] = None
    weight_discrepancy_tons: float = 0.0
    quantity_discrepancy: float = 0.0
    photographs: List[str] = Field(default_factory=list)
    location_name: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    driver_acknowledged: bool
    driver_acknowledgement_time: Optional[datetime] = None
    driver_notes: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_phone: Optional[str] = None
    receiver_acknowledged: bool
    delivery_type: DeliveryType
    delivery_otp: Optional[str] = None
    otp_verified: bool
    damage_reported: bool
    damage_description: Optional[str] = None
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    recorded_by_user_id: Optional[str] = None
    recorded_by_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
# 2. Risk-Based Insurance
class InsurancePolicyRuleCreate(BaseModel):
    policy_name: str
    max_uninsured_value_inr: float = 200000.0
    hazardous_requires_insurance: bool = True
    fragile_high_requires_insurance: bool = True
    review_threshold_inr: float = 2000000.0

class InsurancePolicyRuleOut(BaseModel):
    id: str
    version: int
    policy_name: str
    max_uninsured_value_inr: float
    hazardous_requires_insurance: bool
    fragile_high_requires_insurance: bool
    review_threshold_inr: float
    is_active: bool
    approved_by_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class InsuranceAssessmentRequest(BaseModel):
    cargo_category: CargoCategory
    declared_value_inr: float
    fragility: FragilityLevel = FragilityLevel.LOW
    hazard_class: HazardClass = HazardClass.NONE
    route: Optional[str] = "Kolkata ↔ Durgapur"
    transit_duration_hours: Optional[float] = 6.0

class InsuranceAssessmentOut(BaseModel):
    assessment_result: InsuranceAssessmentResult
    reasons: List[str]
    max_uninsured_threshold_inr: float
    review_threshold_inr: float
    policy_version: int

class CargoInsuranceUpload(BaseModel):
    policy_number: str
    insurer_name: str
    policyholder_name: str
    insured_party: str
    coverage_amount_inr: float
    valid_from: datetime
    valid_to: datetime
    exclusions: Optional[str] = None
    certificate_url: Optional[str] = None

class CargoInsuranceVerify(BaseModel):
    action: str  # "VERIFY", "REJECT", "APPROVE_EXCEPTION"
    rejection_reason: Optional[str] = None
    exception_reason: Optional[str] = None

class CargoInsuranceOut(BaseModel):
    id: str
    shipment_id: Optional[str] = None
    booking_id: Optional[str] = None
    load_id: Optional[str] = None
    assessment_result: InsuranceAssessmentResult
    assessment_reasons: List[str]
    policy_number: Optional[str] = None
    insurer_name: Optional[str] = None
    policyholder_name: Optional[str] = None
    insured_party: Optional[str] = None
    coverage_amount_inr: float
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    exclusions: Optional[str] = None
    certificate_url: Optional[str] = None
    verification_status: InsuranceVerificationStatus
    verified_by_name: Optional[str] = None
    verified_at: Optional[datetime] = None
    exception_permitted: bool
    exception_reason: Optional[str] = None
    is_dispatch_allowed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
# 3. Direct Freight Payment
class DirectPaymentReport(BaseModel):
    amount_paid_inr: float
    payment_method: PaymentMethod = PaymentMethod.NEFT
    payment_reference: str  # UTR / Bank reference number
    payment_evidence_url: Optional[str] = None
    dealer_notes: Optional[str] = None

class DirectPaymentAcknowledge(BaseModel):
    action: str  # "CONFIRM", "DISPUTE"
    transporter_notes: Optional[str] = None
    dispute_reason: Optional[str] = None

class DirectPaymentOut(BaseModel):
    id: str
    booking_id: str
    shipment_id: Optional[str] = None
    payer_dealer_name: Optional[str] = None
    payee_transporter_name: Optional[str] = None
    agreed_freight_inr: float
    amount_paid_inr: float
    payment_status: DirectPaymentStatus
    due_date: Optional[datetime] = None
    payment_method: PaymentMethod
    payment_reference: Optional[str] = None
    payment_evidence_url: Optional[str] = None
    dealer_reported_at: Optional[datetime] = None
    dealer_notes: Optional[str] = None
    transporter_acknowledged_at: Optional[datetime] = None
    transporter_notes: Optional[str] = None
    is_partial: bool
    remaining_balance_inr: float
    dispute_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
# 4. Separate Platform Fee Invoices
class PlatformInvoiceOut(BaseModel):
    id: str
    invoice_number: str
    booking_id: str
    billed_to_name: Optional[str] = None
    fee_type: FeeType
    freight_benchmark_inr: float
    base_fee_inr: float
    gst_rate_percent: float
    gst_amount_inr: float
    total_payable_inr: float
    status: InvoiceStatus
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
# 5. Disputes & Grievances
class DisputeCreate(BaseModel):
    booking_id: Optional[str] = None
    shipment_id: Optional[str] = None
    category: DisputeCategory
    title: str
    description: str
    disputed_amount_inr: Optional[float] = None
    evidence_urls: List[str] = Field(default_factory=list)

class DisputeEvidenceCreate(BaseModel):
    title: str
    file_url: str
    evidence_type: str = "PHOTO_DAMAGE"
    notes: Optional[str] = None

class DisputeEvidenceOut(BaseModel):
    id: str
    dispute_id: str
    uploaded_by_name: Optional[str] = None
    title: str
    file_url: str
    evidence_type: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class DisputeMessageCreate(BaseModel):
    message: str
    is_officer_internal_note: bool = False

class DisputeMessageOut(BaseModel):
    id: str
    dispute_id: str
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    message: str
    is_officer_internal_note: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class DisputeResolutionPropose(BaseModel):
    proposal_text: str
    is_escalated: bool = False

class DisputeCaseOut(BaseModel):
    id: str
    case_number: str
    shipment_id: Optional[str] = None
    booking_id: Optional[str] = None
    raised_by_name: Optional[str] = None
    respondent_name: Optional[str] = None
    category: DisputeCategory
    title: str
    description: str
    disputed_amount_inr: Optional[float] = None
    status: DisputeStatus
    assigned_officer_name: Optional[str] = None
    resolution_proposal: Optional[str] = None
    resolution_accepted_by_complainant: bool
    resolution_accepted_by_respondent: bool
    resolved_at: Optional[datetime] = None
    ai_classification: Dict[str, Any]
    evidence: List[DisputeEvidenceOut] = Field(default_factory=list)
    messages: List[DisputeMessageOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class GrievanceCreate(BaseModel):
    category: str = "GENERAL_SERVICE"
    subject: str
    description: str

class GrievanceUpdate(BaseModel):
    assigned_officer_id: Optional[str] = None
    status: Optional[GrievanceStatus] = None
    resolution_notes: Optional[str] = None

class GrievanceOut(BaseModel):
    id: str
    ticket_number: str
    user_name: Optional[str] = None
    category: str
    subject: str
    description: str
    assigned_officer_name: Optional[str] = None
    status: GrievanceStatus
    acknowledged_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==============================================================================
# 6. Master Prompt 3 Schemas: SOS, Maintenance, Safety & Tracking
# ==============================================================================

# --- SOS Emergency Schemas ---
class SOSTriggerIn(BaseModel):
    event_id: str
    truck_id: str
    shipment_id: Optional[str] = None
    booking_id: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float = Field(default=5.0, ge=0.0)
    incident_category: SOSCategory = SOSCategory.ACCIDENT
    network_status: NetworkStatus = NetworkStatus.ONLINE
    device_timestamp: datetime
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    audio_or_media_url: Optional[str] = None

class SOSActionIn(BaseModel):
    action: str = "ACKNOWLEDGE" # ACKNOWLEDGE, RESPOND, RESOLVE, FALSE_ALARM
    notes: Optional[str] = None
    assigned_responder_id: Optional[str] = None

class SOSEventOut(BaseModel):
    id: str
    event_id: str
    driver_id: str
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    truck_id: str
    truck_registration_no: Optional[str] = None
    shipment_id: Optional[str] = None
    booking_id: Optional[str] = None
    latitude: float
    longitude: float
    accuracy_meters: float
    incident_category: SOSCategory
    network_status: NetworkStatus
    device_timestamp: datetime
    server_timestamp: datetime
    status: SOSStatus
    control_room_notified: bool
    control_room_notified_at: Optional[datetime] = None
    dealer_notified: bool
    dealer_notified_at: Optional[datetime] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_notified: bool
    emergency_contact_notified_at: Optional[datetime] = None
    assigned_responder_name: Optional[str] = None
    assigned_responder_notes: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    audio_or_media_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Vehicle Breakdown Schemas ---
class BreakdownReportIn(BaseModel):
    truck_id: str
    shipment_id: Optional[str] = None
    issue_type: BreakdownIssueType
    description: str
    photo_url: Optional[str] = None
    video_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_timestamp: datetime

class BreakdownAssignSupportIn(BaseModel):
    assigned_mechanic_or_service: str
    estimated_repair_hours: Optional[float] = 2.0
    notes: Optional[str] = None

class BreakdownResolveIn(BaseModel):
    resolution_notes: str
    repaired_pending_inspection: bool = False

class VehicleBreakdownOut(BaseModel):
    id: str
    truck_id: str
    truck_registration_no: Optional[str] = None
    driver_id: str
    driver_name: Optional[str] = None
    shipment_id: Optional[str] = None
    issue_type: BreakdownIssueType
    description: str
    photo_url: Optional[str] = None
    video_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_timestamp: datetime
    reported_at: datetime
    status: BreakdownStatus
    assigned_mechanic_or_service: Optional[str] = None
    estimated_repair_hours: Optional[float] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Pre-Trip Inspection Schemas ---
class PreTripInspectionIn(BaseModel):
    truck_id: str
    tyres_ok: bool = True
    brakes_ok: bool = True
    lights_ok: bool = True
    indicators_ok: bool = True
    mirrors_ok: bool = True
    steering_ok: bool = True
    engine_indicators_ok: bool = True
    oil_level_ok: bool = True
    coolant_level_ok: bool = True
    documents_valid: bool = True
    cargo_securing_equipment_ok: bool = True
    defect_description: Optional[str] = None
    inspection_evidence_photos: List[str] = Field(default_factory=list)

class SafetyHoldClearIn(BaseModel):
    clearance_notes: str
    repair_evidence_url: Optional[str] = None

class PreTripInspectionOut(BaseModel):
    id: str
    truck_id: str
    truck_registration_no: Optional[str] = None
    driver_id: str
    driver_name: Optional[str] = None
    inspected_at: datetime
    tyres_ok: bool
    brakes_ok: bool
    lights_ok: bool
    indicators_ok: bool
    mirrors_ok: bool
    steering_ok: bool
    engine_indicators_ok: bool
    oil_level_ok: bool
    coolant_level_ok: bool
    documents_valid: bool
    cargo_securing_equipment_ok: bool
    critical_defect_found: bool
    defect_description: Optional[str] = None
    inspection_evidence_photos: List[str] = Field(default_factory=list)
    safety_hold_triggered: bool
    safety_hold_cleared_by_name: Optional[str] = None
    safety_hold_cleared_at: Optional[datetime] = None
    repair_evidence_url: Optional[str] = None
    clearance_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Truck Replacement Schemas ---
class ReplacementInitiateIn(BaseModel):
    shipment_id: str
    replacement_truck_id: str
    replacement_driver_id: str
    breakdown_id: Optional[str] = None
    reason: str

class ReplacementApprovalIn(BaseModel):
    approver_role: str # "DEALER" or "TRANSPORTER"
    approved: bool = True
    notes: Optional[str] = None

class ReplacementCustodyTransferIn(BaseModel):
    transfer_cargo_condition: CargoCondition = CargoCondition.INTACT
    new_seal_number: str
    transfer_photos: List[str] = Field(default_factory=list)
    driver_acknowledgement: bool = True

class TruckReplacementOut(BaseModel):
    id: str
    shipment_id: str
    original_truck_id: str
    original_truck_reg: Optional[str] = None
    original_driver_name: Optional[str] = None
    replacement_truck_id: Optional[str] = None
    replacement_truck_reg: Optional[str] = None
    replacement_driver_name: Optional[str] = None
    breakdown_id: Optional[str] = None
    reason: str
    transporter_approved: bool
    transporter_approved_at: Optional[datetime] = None
    dealer_approved: bool
    dealer_approved_at: Optional[datetime] = None
    custody_transfer_verified: bool
    transfer_cargo_condition: CargoCondition
    new_seal_number: Optional[str] = None
    transfer_photos: List[str] = Field(default_factory=list)
    driver_acknowledgement: bool
    status: ReplacementStatus
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- High-Integrity GPS Batch Tracking Schemas ---
class GPSBreadcrumbIn(BaseModel):
    driver_id: str
    truck_id: str
    shipment_id: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float = Field(default=5.0, ge=0.0)
    speed_kmh: float = 0.0
    heading: float = 0.0
    device_timestamp: datetime
    sequence_number: int = 0

class GPSBatchIngestIn(BaseModel):
    breadcrumbs: List[GPSBreadcrumbIn]

class GPSBatchIngestOut(BaseModel):
    ingested_count: int
    anomalies_detected: int
    suspicious_points: List[int] = Field(default_factory=list)
    latest_latitude: Optional[float] = None
    latest_longitude: Optional[float] = None
    is_stale: bool = False
    server_timestamp: datetime

