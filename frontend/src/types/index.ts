export type UserRole =
  | "DEALER"
  | "DRIVER"
  | "TRANSPORTER"
  | "FLEET_MANAGER"
  | "ADMIN"
  | "CONTROL_ROOM"
  | "COMPLIANCE_OFFICER"
  | "DISPUTE_OFFICER";

export type FleetOwnershipType = "LOADLINK_OWNED" | "EXTERNAL_TRANSPORTER";
export type AgreementStatus = "DRAFT" | "PENDING_ACCEPTANCE" | "ACCEPTED" | "SUPERSEDED" | "CANCELLED";

export type VerificationStatus = "PENDING" | "VERIFIED" | "REJECTED" | "SUSPENDED";
export type TruckType = "OPEN_BODY" | "CLOSED_CONTAINER" | "FLATBED" | "TRAILER" | "TIPPER";
export type TruckStatus =
  | "OFFLINE"
  | "ONLINE_AVAILABLE"
  | "AVAILABLE"
  | "RESERVED"
  | "ASSIGNED"
  | "IN_TRANSIT"
  | "MAINTENANCE"
  | "SAFETY_HOLD";
export type LoadStatus = "DRAFT" | "POSTED" | "MATCHING" | "BOOKING_REQUESTED" | "CONFIRMED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
export type BookingStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "EXPIRED" | "CANCELLED";
export type ShipmentState = 
  | "DRAFT"
  | "POSTED"
  | "MATCHING"
  | "BOOKING_REQUESTED"
  | "CONFIRMED"
  | "DRIVER_EN_ROUTE"
  | "ARRIVED_PICKUP"
  | "LOADING"
  | "LOADED"
  | "IN_TRANSIT"
  | "NEAR_DESTINATION"
  | "DELIVERED"
  | "POD_SUBMITTED"
  | "COMPLETED"
  | "CANCELLED"
  | "DISPUTED";
export type PODStatus = "PENDING_REVIEW" | "VERIFIED" | "REJECTED";

export interface User {
  id: string;
  email: string;
  phone: string;
  name: string;
  role: UserRole;
  verification_status: VerificationStatus;
  dealer_id?: string;
  driver_id?: string;
  transporter_id?: string;
  organization_id?: string;
  organization_name?: string;
  truck_id?: string;
  trust_or_reliability_score?: number;
}

export interface Truck {
  id: string;
  driver_id?: string;
  driver_name?: string;
  driver_phone?: string;
  driver_reliability_score?: number;
  ownership_type?: FleetOwnershipType;
  organization_id?: string;
  organization_name?: string;
  registration_no: string;
  truck_type: TruckType;
  capacity_tons: number;
  status: TruckStatus;
  verification_status: VerificationStatus;
  current_lat?: number;
  current_lon?: number;
  current_location_name?: string;
  last_location_time?: string;
  is_demo?: boolean;
}

export type TruckOut = Truck;

export interface VehicleAssignment {
  id: string;
  truck_id: string;
  truck_registration_no: string;
  driver_id: string;
  driver_name?: string;
  driver_license?: string;
  driver_phone?: string;
  is_active: boolean;
  assigned_at: string;
  unassigned_at?: string;
  assignment_notes?: string;
  assigned_by_name?: string;
}

export interface AgreementAcceptance {
  id: string;
  agreement_id: string;
  version: number;
  user_id: string;
  user_name?: string;
  user_role: string;
  organization_id?: string;
  organization_name?: string;
  accepted_at: string;
  signature_text?: string;
  notes?: string;
}

export interface FreightAgreement {
  id: string;
  booking_id: string;
  version: number;
  agreement_status: AgreementStatus;
  dealer_user_id: string;
  dealer_name?: string;
  dealer_org_name?: string;
  transporter_user_id?: string;
  transporter_name?: string;
  transporter_org_name?: string;
  cargo_details: string;
  vehicle_details: Record<string, any>;
  driver_details: Record<string, any>;
  agreed_freight_inr: number;
  additional_charges_inr: number;
  total_contract_value_inr: number;
  pickup_delivery_terms: string;
  insurance_requirements: string;
  cancellation_terms: string;
  delay_detention_rules: string;
  claims_dispute_conditions: string;
  content_sha256: string;
  created_at: string;
  is_accepted_by_dealer: boolean;
  is_accepted_by_transporter: boolean;
  is_fully_executed: boolean;
  acceptances: AgreementAcceptance[];
}

export interface BookingStateHistory {
  id: string;
  booking_id: string;
  previous_state?: string;
  new_state: string;
  trigger_action: string;
  changed_by_user_id?: string;
  changed_by_name?: string;
  notes?: string;
  created_at: string;
}

export interface Load {
  id: string;
  dealer_id: string;
  dealer_name?: string;
  origin_name: string;
  origin_lat: number;
  origin_lon: number;
  destination_name: string;
  destination_lat: number;
  destination_lon: number;
  cargo_type: string;
  cargo_category?: CargoCategory;
  cargo_description?: string;
  cargo_weight_tons: number;
  declared_value_inr?: number;
  fragility?: FragilityLevel;
  hazard_classification?: HazardClass;
  handling_instructions?: string;
  supporting_documents?: string[];
  required_truck_type?: TruckType;
  min_capacity_tons: number;
  max_capacity_tons: number;
  pickup_window_start: string;
  pickup_window_end: string;
  target_budget?: number;
  estimated_benchmark_price?: number;
  cargo_notes?: string;
  status: LoadStatus;
  is_demo?: boolean;
  created_at: string;
  matches_count?: number;
}

export interface FactorBreakdown {
  route_compatibility: number;
  availability_feasibility: number;
  pickup_proximity: number;
  capacity_fit: number;
  price_competitiveness: number;
  reliability: number;
  return_load_potential: number;
}

export interface Match {
  id: string;
  load_id: string;
  truck_id: string;
  truck_registration_no: string;
  truck_type: TruckType;
  truck_capacity_tons: number;
  driver_id: string;
  driver_name: string;
  driver_phone: string;
  driver_reliability_score: number;
  total_score: number;
  factor_breakdown: FactorBreakdown;
  road_eta_km: number;
  road_eta_mins: number;
  explanation_summary: string;
  is_coming_near_you: boolean;
  estimated_arrival_at_pickup?: string;
  truck_current_lat?: number;
  truck_current_lon?: number;
  truck_location_name?: string;
  is_demo?: boolean;
}

export interface Booking {
  id: string;
  load_id: string;
  truck_id: string;
  truck_registration_no?: string;
  driver_id: string;
  driver_name?: string;
  dealer_id: string;
  dealer_name?: string;
  origin_name?: string;
  destination_name?: string;
  cargo_weight_tons?: number;
  offered_price: number;
  status: BookingStatus;
  rejection_reason?: string;
  requested_at: string;
  responded_at?: string;
  shipment_id?: string;
}

export interface Shipment {
  id: string;
  booking_id: string;
  load_id: string;
  truck_id: string;
  truck_registration_no?: string;
  truck_type?: TruckType;
  driver_id: string;
  driver_name?: string;
  driver_phone?: string;
  dealer_id: string;
  dealer_name?: string;
  state: ShipmentState;
  origin_name: string;
  origin_lat: number;
  origin_lon: number;
  destination_name: string;
  destination_lat: number;
  destination_lon: number;
  cargo_type: string;
  cargo_weight_tons: number;
  agreed_freight: number;
  distance_km: number;
  pickup_eta?: string;
  delivery_eta?: string;
  actual_pickup_time?: string;
  actual_delivery_time?: string;
  current_lat?: number;
  current_lon?: number;
  last_location_time?: string;
  is_location_stale: boolean;
  created_at: string;
  updated_at: string;
  has_pod: boolean;
  pod_verification_status?: PODStatus;
}

export interface ReturnLoadOpportunity {
  load_id: string;
  origin_name: string;
  destination_name: string;
  cargo_type: string;
  cargo_weight_tons: number;
  target_budget: number;
  pickup_window_start: string;
  extra_earnings_estimate: number;
  distance_from_delivery_km: number;
  match_score: number;
}

export interface AdminKPIs {
  total_users: number;
  verified_drivers: number;
  verified_dealers: number;
  active_trucks_online: number;
  total_loads_posted: number;
  total_active_shipments: number;
  completed_shipments: number;
  total_gmv: number;
  match_rate_percentage: number;
  booking_conversion_rate: number;
  average_on_time_percentage: number;
}

export interface AuditLog {
  id: string;
  actor_name?: string;
  action: string;
  entity_name: string;
  entity_id: string;
  state_before?: string;
  state_after?: string;
  timestamp: string;
  metadata_json: Record<string, any>;
}

// ==========================================
// MASTER PROMPT 2: TYPES & INTERFACES
// ==========================================

export type CargoCategory =
  | "STEEL_AND_METALS"
  | "CEMENT_AND_CONSTRUCTION"
  | "INDUSTRIAL_EQUIPMENT"
  | "ELECTRONICS_HIGH_VALUE"
  | "CHEMICALS_HAZARDOUS"
  | "FMCG_PACKAGED"
  | "AGRICULTURE_GRAINS"
  | "AUTOMOTIVE_PARTS"
  | "GENERAL_MERCHANDISE";

export type FragilityLevel = "LOW" | "MEDIUM" | "HIGH";

export type HazardClass =
  | "NONE"
  | "CLASS_1_EXPLOSIVES"
  | "CLASS_2_GASES"
  | "CLASS_3_FLAMMABLE_LIQUIDS"
  | "CLASS_4_FLAMMABLE_SOLIDS"
  | "CLASS_5_OXIDIZING"
  | "CLASS_6_TOXIC"
  | "CLASS_7_RADIOACTIVE"
  | "CLASS_8_CORROSIVE"
  | "CLASS_9_MISCELLANEOUS";

export type CustodyEventType = "LOADING_HANDOVER" | "TRANSIT_INCIDENT" | "DELIVERY_HANDOVER";
export type CargoCondition = "INTACT" | "SEAL_COMPROMISED" | "PARTIALLY_DAMAGED" | "DAMAGED" | "WET_RAIN_DAMAGE";
export type DeliveryType = "FULL_DELIVERY" | "PARTIAL_DELIVERY" | "REFUSAL";

export interface CustodyEvent {
  id: string;
  shipment_id: string;
  booking_id?: string;
  event_type: CustodyEventType;
  seal_number?: string;
  seal_intact: boolean;
  cargo_condition: CargoCondition;
  recorded_weight_tons?: number;
  recorded_quantity?: number;
  weight_discrepancy_tons?: number;
  quantity_discrepancy?: number;
  photographs: string[];
  location_name?: string;
  location_lat?: number;
  location_lon?: number;
  driver_acknowledged: boolean;
  driver_acknowledgement_time?: string;
  driver_notes?: string;
  receiver_name?: string;
  receiver_phone?: string;
  receiver_acknowledged: boolean;
  delivery_type?: DeliveryType;
  delivery_otp?: string;
  otp_verified: boolean;
  damage_reported: boolean;
  damage_description?: string;
  supporting_evidence?: any[];
  recorded_by_user_id?: string;
  recorded_by_name?: string;
  created_at: string;
}

export type InsuranceAssessmentResult = "NOT_REQUIRED" | "REQUIRED" | "REVIEW_REQUIRED";
export type InsuranceVerificationStatus =
  | "UNASSESSED"
  | "PENDING_VERIFICATION"
  | "VERIFIED"
  | "REJECTED"
  | "EXCEPTION_APPROVED"
  | "EXPIRED";

export interface InsurancePolicyRule {
  id: string;
  version: number;
  policy_name: string;
  max_uninsured_value_inr: number;
  hazardous_requires_insurance: boolean;
  fragile_high_requires_insurance: boolean;
  review_threshold_inr: number;
  is_active: boolean;
  approved_by_name?: string;
  created_at: string;
}

export interface CargoInsurance {
  id: string;
  shipment_id?: string;
  booking_id?: string;
  load_id?: string;
  assessment_result: InsuranceAssessmentResult;
  assessment_reasons: string[];
  policy_number?: string;
  insurer_name?: string;
  policyholder_name?: string;
  insured_party?: string;
  coverage_amount_inr: number;
  valid_from?: string;
  valid_to?: string;
  exclusions?: string;
  certificate_url?: string;
  verification_status: InsuranceVerificationStatus;
  verified_by_name?: string;
  verified_at?: string;
  exception_permitted: boolean;
  exception_reason?: string;
  is_dispatch_allowed: boolean;
  created_at: string;
}

export type DirectPaymentStatus =
  | "PENDING"
  | "REPORTED_BY_DEALER"
  | "CONFIRMED_BY_TRANSPORTER"
  | "DISPUTED_BY_TRANSPORTER"
  | "OVERDUE";

export type PaymentMethod = "BANK_TRANSFER" | "NEFT" | "RTGS" | "IMPS" | "UPI" | "CHEQUE";
export type FeeType = "FIXED_BOOKING_FEE" | "PERCENTAGE_COMMISSION" | "SUBSCRIPTION_TIER";
export type InvoiceStatus = "ISSUED" | "PAID" | "OVERDUE" | "CANCELLED";

export interface DirectPayment {
  id: string;
  booking_id: string;
  shipment_id?: string;
  payer_dealer_name?: string;
  payee_transporter_name?: string;
  agreed_freight_inr: number;
  amount_paid_inr: number;
  payment_status: DirectPaymentStatus;
  due_date?: string;
  payment_method?: PaymentMethod;
  payment_reference?: string;
  payment_evidence_url?: string;
  dealer_reported_at?: string;
  dealer_notes?: string;
  transporter_acknowledged_at?: string;
  transporter_notes?: string;
  is_partial: boolean;
  remaining_balance_inr: number;
  dispute_reason?: string;
  created_at: string;
}

export interface PlatformInvoice {
  id: string;
  invoice_number: string;
  booking_id: string;
  billed_to_name?: string;
  fee_type: FeeType;
  freight_benchmark_inr: number;
  base_fee_inr: number;
  gst_rate_percent: number;
  gst_amount_inr: number;
  total_payable_inr: number;
  status: InvoiceStatus;
  due_date: string;
  paid_at?: string;
  created_at: string;
}

export type DisputeCategory =
  | "CARGO_DAMAGE"
  | "CARGO_SHORTAGE"
  | "NON_DELIVERY"
  | "DELIVERY_REFUSAL"
  | "UNAUTHORIZED_CANCELLATION"
  | "PAYMENT_DEFAULT"
  | "FREIGHT_AMOUNT_DISPUTE"
  | "UNREASONABLE_TRANSIT_DELAY"
  | "ADDITIONAL_CHARGES_DETENTION"
  | "DRIVER_TRANSPORTER_MISCONDUCT"
  | "DOCUMENTATION_DISCREPANCY";

export type DisputeStatus =
  | "OPEN"
  | "UNDER_REVIEW"
  | "EVIDENCE_REQUESTED"
  | "RESOLUTION_PROPOSED"
  | "ESCALATED"
  | "RESOLVED"
  | "CLOSED";

export interface DisputeEvidence {
  id: string;
  dispute_id: string;
  uploaded_by_name?: string;
  title: string;
  file_url: string;
  evidence_type: string;
  notes?: string;
  created_at: string;
}

export interface DisputeMessage {
  id: string;
  dispute_id: string;
  sender_name?: string;
  sender_role?: string;
  message: string;
  is_officer_internal_note: boolean;
  created_at: string;
}

export interface DisputeCase {
  id: string;
  case_number: string;
  shipment_id?: string;
  booking_id?: string;
  raised_by_name?: string;
  respondent_name?: string;
  category: DisputeCategory;
  title: string;
  description: string;
  disputed_amount_inr?: number;
  status: DisputeStatus;
  assigned_officer_name?: string;
  resolution_proposal?: string;
  resolution_accepted_by_complainant: boolean;
  resolution_accepted_by_respondent: boolean;
  resolved_at?: string;
  ai_classification?: Record<string, any>;
  evidence: DisputeEvidence[];
  messages: DisputeMessage[];
  created_at: string;
  updated_at: string;
}

export type GrievanceStatus = "OPEN" | "ACKNOWLEDGED" | "INVESTIGATING" | "RESOLVED" | "CLOSED";

export interface Grievance {
  id: string;
  ticket_number: string;
  user_name?: string;
  category: string;
  subject: string;
  description: string;
  assigned_officer_name?: string;
  status: GrievanceStatus;
  acknowledged_at?: string;
  due_date: string;
  resolution_notes?: string;
  created_at: string;
}

// --- Master Prompt 3 Types: SOS, Breakdowns, Safety & Offline Tracking ---

export type SOSStatus =
  | "TRIGGERED"
  | "NOTIFICATION_PENDING"
  | "ACKNOWLEDGED"
  | "RESPONDING"
  | "RESOLVED"
  | "FALSE_ALARM";

export type SOSCategory =
  | "ACCIDENT"
  | "MEDICAL_EMERGENCY"
  | "VEHICLE_FIRE"
  | "THEFT_OR_HIJACKING"
  | "HIGHWAY_HARASSMENT"
  | "MECHANICAL_CRITICAL"
  | "OTHER_CRITICAL";

export type NetworkStatus = "ONLINE" | "OFFLINE_SYNCED" | "CELLULAR_FALLBACK" | "SMS_QUEUED";

export interface SOSEvent {
  id: string;
  event_id: string;
  driver_id: string;
  driver_name?: string;
  driver_phone?: string;
  truck_id: string;
  truck_registration_no?: string;
  shipment_id?: string;
  booking_id?: string;
  latitude: number;
  longitude: number;
  accuracy_meters: number;
  incident_category: SOSCategory;
  network_status: NetworkStatus;
  device_timestamp: string;
  server_timestamp: string;
  status: SOSStatus;
  control_room_notified: boolean;
  control_room_notified_at?: string;
  dealer_notified: boolean;
  dealer_notified_at?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_notified: boolean;
  emergency_contact_notified_at?: string;
  assigned_responder_name?: string;
  assigned_responder_notes?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  resolution_notes?: string;
  audio_or_media_url?: string;
}

export type BreakdownIssueType =
  | "TYRE_FAILURE"
  | "BRAKE_ISSUE"
  | "ENGINE_OVERHEATING"
  | "BATTERY_FAILURE"
  | "ACCIDENT"
  | "MECHANICAL_FAILURE"
  | "OTHER";

export type BreakdownStatus =
  | "REPORTED"
  | "SUPPORT_ASSIGNED"
  | "IN_REPAIR"
  | "REPAIRED_PENDING_INSPECTION"
  | "RESOLVED"
  | "REPLACEMENT_REQUIRED";

export interface VehicleBreakdown {
  id: string;
  truck_id: string;
  truck_registration_no?: string;
  driver_id: string;
  driver_name?: string;
  shipment_id?: string;
  issue_type: BreakdownIssueType;
  description: string;
  photo_url?: string;
  video_url?: string;
  latitude?: number;
  longitude?: number;
  device_timestamp: string;
  reported_at: string;
  status: BreakdownStatus;
  assigned_mechanic_or_service?: string;
  estimated_repair_hours?: number;
  resolution_notes?: string;
  resolved_at?: string;
}

export interface PreTripInspection {
  id: string;
  truck_id: string;
  truck_registration_no?: string;
  driver_id: string;
  driver_name?: string;
  inspected_at: string;
  tyres_ok: boolean;
  brakes_ok: boolean;
  lights_ok: boolean;
  indicators_ok: boolean;
  mirrors_ok: boolean;
  steering_ok: boolean;
  engine_indicators_ok: boolean;
  oil_level_ok: boolean;
  coolant_level_ok: boolean;
  documents_valid: boolean;
  cargo_securing_equipment_ok: boolean;
  critical_defect_found: boolean;
  defect_description?: string;
  inspection_evidence_photos: string[];
  safety_hold_triggered: boolean;
  safety_hold_cleared_by_name?: string;
  safety_hold_cleared_at?: string;
  repair_evidence_url?: string;
  clearance_notes?: string;
}

export type ReplacementStatus =
  | "INITIATED"
  | "PENDING_APPROVALS"
  | "APPROVED"
  | "CUSTODY_TRANSFERRED"
  | "DISPATCHED_NEW_TRUCK"
  | "COMPLETED"
  | "CANCELLED";

export interface TruckReplacement {
  id: string;
  shipment_id: string;
  original_truck_id: string;
  original_truck_reg?: string;
  original_driver_name?: string;
  replacement_truck_id?: string;
  replacement_truck_reg?: string;
  replacement_driver_name?: string;
  breakdown_id?: string;
  reason: string;
  transporter_approved: boolean;
  transporter_approved_at?: string;
  dealer_approved: boolean;
  dealer_approved_at?: string;
  custody_transfer_verified: boolean;
  transfer_cargo_condition: string;
  new_seal_number?: string;
  transfer_photos: string[];
  driver_acknowledgement: boolean;
  status: ReplacementStatus;
  created_at: string;
  completed_at?: string;
}

export interface GPSBreadcrumb {
  driver_id: string;
  truck_id: string;
  shipment_id?: string;
  latitude: number;
  longitude: number;
  accuracy_meters: number;
  speed_kmh: number;
  heading: number;
  device_timestamp: string;
  sequence_number: number;
}

export interface GPSBatchIngestResult {
  ingested_count: number;
  anomalies_detected: number;
  suspicious_points: number[];
  latest_latitude?: number;
  latest_longitude?: number;
  is_stale: boolean;
  server_timestamp: string;
}

export interface OfflineCorridorMetadata {
  corridor_name: string;
  bounding_box: {
    min_latitude: number;
    min_longitude: number;
    max_latitude: number;
    max_longitude: number;
  };
  tile_pack_id: string;
  tile_url_template: string;
  min_zoom: number;
  max_zoom: number;
  estimated_size_mb: number;
  offline_routing_notice: string;
  waypoints: Array<{ name: string; lat: number; lon: number }>;
}

