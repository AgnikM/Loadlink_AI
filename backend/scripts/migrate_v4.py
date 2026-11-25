import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "loadlink.db")

def migrate():
    print(f"Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Add new columns to `drivers` table
    driver_cols = [r[1] for r in cursor.execute("PRAGMA table_info(drivers)").fetchall()]
    new_driver_cols = [
        ("emergency_contact_name", "VARCHAR(255) DEFAULT 'Paramjeet Yadav (Brother)'"),
        ("emergency_contact_phone", "VARCHAR(50) DEFAULT '+919830099881'"),
    ]
    for col_name, col_def in new_driver_cols:
        if col_name not in driver_cols:
            print(f"Adding column {col_name} to drivers...")
            cursor.execute(f"ALTER TABLE drivers ADD COLUMN {col_name} {col_def}")

    # 2. Add new columns to `truck_locations` table
    loc_cols = [r[1] for r in cursor.execute("PRAGMA table_info(truck_locations)").fetchall()]
    new_loc_cols = [
        ("sequence_number", "INTEGER DEFAULT 0"),
        ("is_suspicious_jump", "BOOLEAN DEFAULT 0"),
    ]
    for col_name, col_def in new_loc_cols:
        if col_name not in loc_cols:
            print(f"Adding column {col_name} to truck_locations...")
            cursor.execute(f"ALTER TABLE truck_locations ADD COLUMN {col_name} {col_def}")

    # 3. Create `sos_events` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sos_events (
        id VARCHAR(36) PRIMARY KEY,
        event_id VARCHAR(64) UNIQUE NOT NULL,
        driver_id VARCHAR(36) NOT NULL REFERENCES drivers(id),
        truck_id VARCHAR(36) NOT NULL REFERENCES trucks(id),
        shipment_id VARCHAR(36) REFERENCES shipments(id),
        booking_id VARCHAR(36) REFERENCES bookings(id),
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        accuracy_meters FLOAT DEFAULT 5.0,
        incident_category VARCHAR(50) DEFAULT 'ACCIDENT',
        network_status VARCHAR(50) DEFAULT 'ONLINE',
        device_timestamp DATETIME NOT NULL,
        server_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        status VARCHAR(50) DEFAULT 'TRIGGERED',
        control_room_notified BOOLEAN DEFAULT 0,
        control_room_notified_at DATETIME,
        dealer_notified BOOLEAN DEFAULT 0,
        dealer_notified_at DATETIME,
        emergency_contact_name VARCHAR(255),
        emergency_contact_phone VARCHAR(50),
        emergency_contact_notified BOOLEAN DEFAULT 0,
        emergency_contact_notified_at DATETIME,
        assigned_responder_id VARCHAR(36) REFERENCES users(id),
        assigned_responder_notes TEXT,
        acknowledged_at DATETIME,
        resolved_at DATETIME,
        resolution_notes TEXT,
        audio_or_media_url VARCHAR(500)
    )
    """)

    # 4. Create `vehicle_breakdowns` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_breakdowns (
        id VARCHAR(36) PRIMARY KEY,
        truck_id VARCHAR(36) NOT NULL REFERENCES trucks(id),
        driver_id VARCHAR(36) NOT NULL REFERENCES drivers(id),
        shipment_id VARCHAR(36) REFERENCES shipments(id),
        issue_type VARCHAR(50) NOT NULL,
        description TEXT NOT NULL,
        photo_url VARCHAR(500),
        video_url VARCHAR(500),
        latitude FLOAT,
        longitude FLOAT,
        device_timestamp DATETIME NOT NULL,
        reported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status VARCHAR(50) DEFAULT 'REPORTED',
        assigned_mechanic_or_service VARCHAR(255),
        estimated_repair_hours FLOAT,
        resolution_notes TEXT,
        resolved_at DATETIME
    )
    """)

    # 5. Create `pre_trip_inspections` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pre_trip_inspections (
        id VARCHAR(36) PRIMARY KEY,
        truck_id VARCHAR(36) NOT NULL REFERENCES trucks(id),
        driver_id VARCHAR(36) NOT NULL REFERENCES drivers(id),
        inspected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        tyres_ok BOOLEAN DEFAULT 1,
        brakes_ok BOOLEAN DEFAULT 1,
        lights_ok BOOLEAN DEFAULT 1,
        indicators_ok BOOLEAN DEFAULT 1,
        mirrors_ok BOOLEAN DEFAULT 1,
        steering_ok BOOLEAN DEFAULT 1,
        engine_indicators_ok BOOLEAN DEFAULT 1,
        oil_level_ok BOOLEAN DEFAULT 1,
        coolant_level_ok BOOLEAN DEFAULT 1,
        documents_valid BOOLEAN DEFAULT 1,
        cargo_securing_equipment_ok BOOLEAN DEFAULT 1,
        critical_defect_found BOOLEAN DEFAULT 0,
        defect_description TEXT,
        inspection_evidence_photos JSON DEFAULT '[]',
        safety_hold_triggered BOOLEAN DEFAULT 0,
        safety_hold_cleared_by_id VARCHAR(36) REFERENCES users(id),
        safety_hold_cleared_at DATETIME,
        repair_evidence_url VARCHAR(500),
        clearance_notes TEXT
    )
    """)

    # 6. Create `truck_replacement_workflows` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS truck_replacement_workflows (
        id VARCHAR(36) PRIMARY KEY,
        shipment_id VARCHAR(36) NOT NULL REFERENCES shipments(id),
        original_truck_id VARCHAR(36) NOT NULL REFERENCES trucks(id),
        original_driver_id VARCHAR(36) NOT NULL REFERENCES drivers(id),
        replacement_truck_id VARCHAR(36) REFERENCES trucks(id),
        replacement_driver_id VARCHAR(36) REFERENCES drivers(id),
        breakdown_id VARCHAR(36) REFERENCES vehicle_breakdowns(id),
        reason TEXT NOT NULL,
        transporter_approved BOOLEAN DEFAULT 0,
        transporter_approved_at DATETIME,
        dealer_approved BOOLEAN DEFAULT 0,
        dealer_approved_at DATETIME,
        custody_transfer_verified BOOLEAN DEFAULT 0,
        transfer_cargo_condition VARCHAR(50) DEFAULT 'INTACT',
        new_seal_number VARCHAR(100),
        transfer_photos JSON DEFAULT '[]',
        driver_acknowledgement BOOLEAN DEFAULT 0,
        status VARCHAR(50) DEFAULT 'INITIATED',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME
    )
    """)

    conn.commit()
    conn.close()
    print("Master Prompt 3 schema migration completed successfully.")

if __name__ == "__main__":
    migrate()
