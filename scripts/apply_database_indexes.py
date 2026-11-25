import sqlite3
import os

INDEX_STATEMENTS = [
    # Users & Orgs
    "CREATE INDEX IF NOT EXISTS ix_users_org_id ON users (organization_id);",
    "CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);",
    "CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active);",
    "CREATE INDEX IF NOT EXISTS ix_orgs_type ON organizations (type);",
    "CREATE INDEX IF NOT EXISTS ix_orgs_status ON organizations (status);",
    "CREATE INDEX IF NOT EXISTS ix_dealers_user_id ON dealers (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_dealers_org_id ON dealers (organization_id);",
    "CREATE INDEX IF NOT EXISTS ix_transporters_user_id ON transporters (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_transporters_org_id ON transporters (organization_id);",
    "CREATE INDEX IF NOT EXISTS ix_drivers_user_id ON drivers (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_drivers_transporter_id ON drivers (transporter_id);",
    "CREATE INDEX IF NOT EXISTS ix_drivers_status ON drivers (status);",

    # Trucks & Loads
    "CREATE INDEX IF NOT EXISTS ix_trucks_transporter_id ON trucks (transporter_id);",
    "CREATE INDEX IF NOT EXISTS ix_trucks_status ON trucks (status);",
    "CREATE INDEX IF NOT EXISTS ix_trucks_truck_type ON trucks (truck_type);",
    "CREATE INDEX IF NOT EXISTS ix_trucks_current_hub ON trucks (current_hub);",
    "CREATE INDEX IF NOT EXISTS ix_trucks_status_type ON trucks (status, truck_type);",
    "CREATE INDEX IF NOT EXISTS ix_trucks_status_capacity ON trucks (status, capacity_tonnage);",
    "CREATE INDEX IF NOT EXISTS ix_loads_dealer_id ON loads (dealer_id);",
    "CREATE INDEX IF NOT EXISTS ix_loads_status ON loads (status);",
    "CREATE INDEX IF NOT EXISTS ix_loads_origin_hub ON loads (origin_hub);",
    "CREATE INDEX IF NOT EXISTS ix_loads_destination_hub ON loads (destination_hub);",
    "CREATE INDEX IF NOT EXISTS ix_loads_pickup_window_start ON loads (pickup_window_start);",
    "CREATE INDEX IF NOT EXISTS ix_loads_status_pickup ON loads (status, pickup_window_start);",
    "CREATE INDEX IF NOT EXISTS ix_loads_status_hubs ON loads (status, origin_hub, destination_hub);",

    # Matching & Bookings
    "CREATE INDEX IF NOT EXISTS ix_matches_load_id ON matches (load_id);",
    "CREATE INDEX IF NOT EXISTS ix_matches_truck_id ON matches (truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_matches_status ON matches (status);",
    "CREATE INDEX IF NOT EXISTS ix_matches_load_score ON matches (load_id, score);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_load_id ON bookings (load_id);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_truck_id ON bookings (truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_dealer_id ON bookings (dealer_id);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_driver_id ON bookings (driver_id);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_transporter_id ON bookings (transporter_id);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_status ON bookings (status);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_created_at ON bookings (created_at);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_truck_status ON bookings (truck_id, status);",
    "CREATE INDEX IF NOT EXISTS ix_bookings_load_status ON bookings (load_id, status);",

    # Shipments & Telematics
    "CREATE INDEX IF NOT EXISTS ix_shipments_booking_id ON shipments (booking_id);",
    "CREATE INDEX IF NOT EXISTS ix_shipments_load_id ON shipments (load_id);",
    "CREATE INDEX IF NOT EXISTS ix_shipments_truck_id ON shipments (truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_shipments_driver_id ON shipments (driver_id);",
    "CREATE INDEX IF NOT EXISTS ix_shipments_state ON shipments (state);",
    "CREATE INDEX IF NOT EXISTS ix_shipments_created_at ON shipments (created_at);",
    "CREATE INDEX IF NOT EXISTS ix_shipments_truck_state ON shipments (truck_id, state);",
    "CREATE INDEX IF NOT EXISTS ix_shipments_driver_state ON shipments (driver_id, state);",
    "CREATE INDEX IF NOT EXISTS ix_truck_locations_shipment_id ON truck_locations (shipment_id);",
    "CREATE INDEX IF NOT EXISTS ix_truck_locations_truck_id ON truck_locations (truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_truck_locations_recorded_at ON truck_locations (recorded_at);",
    "CREATE INDEX IF NOT EXISTS ix_truck_locations_shipment_recorded ON truck_locations (shipment_id, recorded_at);",
    "CREATE INDEX IF NOT EXISTS ix_truck_locations_truck_recorded ON truck_locations (truck_id, recorded_at);",

    # SOS & Safety
    "CREATE INDEX IF NOT EXISTS ix_sos_events_driver_id ON sos_events (driver_id);",
    "CREATE INDEX IF NOT EXISTS ix_sos_events_truck_id ON sos_events (truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_sos_events_booking_id ON sos_events (booking_id);",
    "CREATE INDEX IF NOT EXISTS ix_sos_events_status ON sos_events (status);",
    "CREATE INDEX IF NOT EXISTS ix_sos_events_created_at ON sos_events (created_at);",
    "CREATE INDEX IF NOT EXISTS ix_sos_events_status_created ON sos_events (status, created_at);",
    "CREATE INDEX IF NOT EXISTS ix_sos_events_driver_status ON sos_events (driver_id, status);",

    # Custody & Payments
    "CREATE INDEX IF NOT EXISTS ix_direct_payments_booking_id ON direct_payments (booking_id);",
    "CREATE INDEX IF NOT EXISTS ix_direct_payments_dealer_id ON direct_payments (dealer_id);",
    "CREATE INDEX IF NOT EXISTS ix_direct_payments_transporter_id ON direct_payments (transporter_id);",
    "CREATE INDEX IF NOT EXISTS ix_direct_payments_status ON direct_payments (status);",
    "CREATE INDEX IF NOT EXISTS ix_direct_payments_created_at ON direct_payments (created_at);",
    "CREATE INDEX IF NOT EXISTS ix_custody_events_shipment_id ON custody_events (shipment_id);",
    "CREATE INDEX IF NOT EXISTS ix_custody_events_actor_id ON custody_events (actor_id);",
    "CREATE INDEX IF NOT EXISTS ix_custody_events_event_type ON custody_events (event_type);",
    "CREATE INDEX IF NOT EXISTS ix_custody_events_timestamp ON custody_events (timestamp);",
    "CREATE INDEX IF NOT EXISTS ix_custody_events_shipment_type ON custody_events (shipment_id, event_type);",

    # Insurance, Disputes & Grievances
    "CREATE INDEX IF NOT EXISTS ix_cargo_insurances_load_id ON cargo_insurances (load_id);",
    "CREATE INDEX IF NOT EXISTS ix_cargo_insurances_verified_by ON cargo_insurances (verified_by_user_id);",
    "CREATE INDEX IF NOT EXISTS ix_cargo_insurances_risk_tier ON cargo_insurances (risk_tier);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_cases_booking_id ON dispute_cases (booking_id);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_cases_shipment_id ON dispute_cases (shipment_id);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_cases_raised_by ON dispute_cases (raised_by_user_id);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_cases_assigned_to ON dispute_cases (assigned_to_user_id);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_cases_status ON dispute_cases (status);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_cases_created_at ON dispute_cases (created_at);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_evidence_dispute_id ON dispute_evidence (dispute_id);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_evidence_uploaded_by ON dispute_evidence (uploaded_by_user_id);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_messages_dispute_id ON dispute_messages (dispute_id);",
    "CREATE INDEX IF NOT EXISTS ix_dispute_messages_sender_id ON dispute_messages (sender_id);",

    # Maintenance & Inspections
    "CREATE INDEX IF NOT EXISTS ix_vehicle_breakdowns_truck_id ON vehicle_breakdowns (truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_vehicle_breakdowns_booking_id ON vehicle_breakdowns (booking_id);",
    "CREATE INDEX IF NOT EXISTS ix_vehicle_breakdowns_reported_by ON vehicle_breakdowns (reported_by_driver_id);",
    "CREATE INDEX IF NOT EXISTS ix_vehicle_breakdowns_status ON vehicle_breakdowns (status);",
    "CREATE INDEX IF NOT EXISTS ix_truck_replacements_breakdown_id ON truck_replacement_workflows (breakdown_id);",
    "CREATE INDEX IF NOT EXISTS ix_truck_replacements_original_truck ON truck_replacement_workflows (original_truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_truck_replacements_repl_truck ON truck_replacement_workflows (replacement_truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_truck_replacements_status ON truck_replacement_workflows (status);",
    "CREATE INDEX IF NOT EXISTS ix_pre_trip_truck_id ON pre_trip_inspections (truck_id);",
    "CREATE INDEX IF NOT EXISTS ix_pre_trip_driver_id ON pre_trip_inspections (driver_id);",
    "CREATE INDEX IF NOT EXISTS ix_pre_trip_passed ON pre_trip_inspections (passed);",
    "CREATE INDEX IF NOT EXISTS ix_pre_trip_inspection_date ON pre_trip_inspections (inspection_date);",

    # Supporting POD, Ratings, Notifications, Audit
    "CREATE INDEX IF NOT EXISTS ix_pods_shipment_id ON pods (shipment_id);",
    "CREATE INDEX IF NOT EXISTS ix_pods_status ON pods (status);",
    "CREATE INDEX IF NOT EXISTS ix_ratings_booking_id ON ratings (booking_id);",
    "CREATE INDEX IF NOT EXISTS ix_ratings_from_user ON ratings (from_user_id);",
    "CREATE INDEX IF NOT EXISTS ix_ratings_to_user ON ratings (to_user_id);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at);",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_id ON audit_logs (actor_id);",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity ON audit_logs (entity_type, entity_id);",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs (timestamp);",
]

def apply_indexes(db_path: str):
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist.")
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    
    count = 0
    for stmt in INDEX_STATEMENTS:
        cur.execute(stmt)
        count += 1
    
    conn.commit()
    
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
    total_indexes = cur.fetchone()[0]
    print(f"Applied {count} indexes to {db_path}. Total explicit indexes in DB: {total_indexes}")
    
    # Check FK integrity
    cur.execute("PRAGMA foreign_key_check;")
    violations = cur.fetchall()
    print(f"Foreign Key check on {db_path}: {len(violations)} violations.")
    conn.close()

if __name__ == "__main__":
    apply_indexes("backend/loadlink.db")
    if os.path.exists("backend/tests/test_isolated.db"):
        apply_indexes("backend/tests/test_isolated.db")
