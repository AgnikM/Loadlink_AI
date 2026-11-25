import sqlite3
import os
import uuid
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "loadlink.db")

def migrate():
    print(f"Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Add new columns to `loads` table
    existing_cols = [r[1] for r in cursor.execute("PRAGMA table_info(loads)").fetchall()]
    print(f"Existing loads columns: {existing_cols}")

    new_cols = [
        ("cargo_category", "VARCHAR(50) DEFAULT 'GENERAL_MERCHANDISE'"),
        ("cargo_description", "TEXT"),
        ("declared_value_inr", "FLOAT DEFAULT 100000.0"),
        ("fragility", "VARCHAR(20) DEFAULT 'LOW'"),
        ("hazard_classification", "VARCHAR(50) DEFAULT 'NONE'"),
        ("handling_instructions", "TEXT"),
        ("supporting_documents", "JSON DEFAULT '[]'"),
    ]

    for col_name, col_def in new_cols:
        if col_name not in existing_cols:
            print(f"Adding column {col_name} to loads...")
            cursor.execute(f"ALTER TABLE loads ADD COLUMN {col_name} {col_def}")

    # 2. Create `custody_events` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS custody_events (
        id VARCHAR(36) PRIMARY KEY,
        shipment_id VARCHAR(36) NOT NULL,
        booking_id VARCHAR(36),
        event_type VARCHAR(50) NOT NULL,
        seal_number VARCHAR(100),
        seal_intact BOOLEAN DEFAULT 1,
        cargo_condition VARCHAR(50) DEFAULT 'INTACT',
        recorded_weight_tons FLOAT,
        recorded_quantity FLOAT,
        weight_discrepancy_tons FLOAT DEFAULT 0.0,
        quantity_discrepancy FLOAT DEFAULT 0.0,
        photographs JSON DEFAULT '[]',
        location_name VARCHAR(255),
        location_lat FLOAT,
        location_lon FLOAT,
        driver_acknowledged BOOLEAN DEFAULT 0,
        driver_acknowledgement_time DATETIME,
        driver_notes TEXT,
        receiver_name VARCHAR(255),
        receiver_phone VARCHAR(50),
        receiver_acknowledged BOOLEAN DEFAULT 0,
        delivery_type VARCHAR(50) DEFAULT 'FULL_DELIVERY',
        delivery_otp VARCHAR(10),
        otp_verified BOOLEAN DEFAULT 0,
        damage_reported BOOLEAN DEFAULT 0,
        damage_description TEXT,
        supporting_evidence JSON DEFAULT '[]',
        recorded_by_user_id VARCHAR(36),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shipment_id) REFERENCES shipments(id),
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (recorded_by_user_id) REFERENCES users(id)
    )
    """)

    # 3. Create `insurance_policy_rules` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_policy_rules (
        id VARCHAR(36) PRIMARY KEY,
        version INTEGER NOT NULL DEFAULT 1,
        policy_name VARCHAR(255) DEFAULT 'Standard Corridor Freight Insurance Policy',
        max_uninsured_value_inr FLOAT DEFAULT 200000.0,
        hazardous_requires_insurance BOOLEAN DEFAULT 1,
        fragile_high_requires_insurance BOOLEAN DEFAULT 1,
        review_threshold_inr FLOAT DEFAULT 2000000.0,
        is_active BOOLEAN DEFAULT 1,
        approved_by_user_id VARCHAR(36),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (approved_by_user_id) REFERENCES users(id)
    )
    """)

    # 4. Create `cargo_insurances` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cargo_insurances (
        id VARCHAR(36) PRIMARY KEY,
        shipment_id VARCHAR(36),
        booking_id VARCHAR(36),
        load_id VARCHAR(36),
        assessment_result VARCHAR(50) DEFAULT 'NOT_REQUIRED',
        assessment_reasons JSON DEFAULT '[]',
        policy_number VARCHAR(100),
        insurer_name VARCHAR(255),
        policyholder_name VARCHAR(255),
        insured_party VARCHAR(255),
        coverage_amount_inr FLOAT DEFAULT 0.0,
        valid_from DATETIME,
        valid_to DATETIME,
        exclusions TEXT,
        certificate_url VARCHAR(500),
        verification_status VARCHAR(50) DEFAULT 'UNASSESSED',
        verified_by_user_id VARCHAR(36),
        verified_at DATETIME,
        exception_permitted BOOLEAN DEFAULT 0,
        exception_reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shipment_id) REFERENCES shipments(id),
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (load_id) REFERENCES loads(id),
        FOREIGN KEY (verified_by_user_id) REFERENCES users(id)
    )
    """)

    # 5. Create `direct_payments` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS direct_payments (
        id VARCHAR(36) PRIMARY KEY,
        booking_id VARCHAR(36) NOT NULL,
        shipment_id VARCHAR(36),
        payer_dealer_id VARCHAR(36),
        payer_user_id VARCHAR(36),
        payee_user_id VARCHAR(36),
        agreed_freight_inr FLOAT NOT NULL,
        amount_paid_inr FLOAT DEFAULT 0.0,
        payment_status VARCHAR(50) DEFAULT 'PENDING',
        due_date DATETIME,
        payment_method VARCHAR(50) DEFAULT 'NEFT',
        payment_reference VARCHAR(100),
        payment_evidence_url VARCHAR(500),
        dealer_reported_at DATETIME,
        dealer_notes TEXT,
        transporter_acknowledged_at DATETIME,
        transporter_notes TEXT,
        is_partial BOOLEAN DEFAULT 0,
        remaining_balance_inr FLOAT DEFAULT 0.0,
        dispute_reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (shipment_id) REFERENCES shipments(id),
        FOREIGN KEY (payer_dealer_id) REFERENCES dealers(id),
        FOREIGN KEY (payer_user_id) REFERENCES users(id),
        FOREIGN KEY (payee_user_id) REFERENCES users(id)
    )
    """)

    # 6. Create `platform_invoices` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS platform_invoices (
        id VARCHAR(36) PRIMARY KEY,
        invoice_number VARCHAR(50) UNIQUE NOT NULL,
        booking_id VARCHAR(36) NOT NULL,
        billed_to_user_id VARCHAR(36) NOT NULL,
        fee_type VARCHAR(50) DEFAULT 'FIXED_BOOKING_FEE',
        freight_benchmark_inr FLOAT DEFAULT 0.0,
        base_fee_inr FLOAT NOT NULL,
        gst_rate_percent FLOAT DEFAULT 18.0,
        gst_amount_inr FLOAT NOT NULL,
        total_payable_inr FLOAT NOT NULL,
        status VARCHAR(50) DEFAULT 'ISSUED',
        due_date DATETIME,
        paid_at DATETIME,
        payment_gateway_ref VARCHAR(100),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (billed_to_user_id) REFERENCES users(id)
    )
    """)

    # 7. Create `dispute_cases` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dispute_cases (
        id VARCHAR(36) PRIMARY KEY,
        case_number VARCHAR(50) UNIQUE NOT NULL,
        shipment_id VARCHAR(36),
        booking_id VARCHAR(36),
        raised_by_user_id VARCHAR(36) NOT NULL,
        respondent_user_id VARCHAR(36),
        category VARCHAR(50) NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        disputed_amount_inr FLOAT,
        status VARCHAR(50) DEFAULT 'OPEN',
        assigned_officer_id VARCHAR(36),
        resolution_proposal TEXT,
        resolution_accepted_by_complainant BOOLEAN DEFAULT 0,
        resolution_accepted_by_respondent BOOLEAN DEFAULT 0,
        resolved_at DATETIME,
        ai_classification JSON DEFAULT '{}',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shipment_id) REFERENCES shipments(id),
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (raised_by_user_id) REFERENCES users(id),
        FOREIGN KEY (respondent_user_id) REFERENCES users(id),
        FOREIGN KEY (assigned_officer_id) REFERENCES users(id)
    )
    """)

    # 8. Create `dispute_evidence` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dispute_evidence (
        id VARCHAR(36) PRIMARY KEY,
        dispute_id VARCHAR(36) NOT NULL,
        uploaded_by_user_id VARCHAR(36) NOT NULL,
        title VARCHAR(255) NOT NULL,
        file_url VARCHAR(500) NOT NULL,
        evidence_type VARCHAR(100) DEFAULT 'PHOTO_DAMAGE',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dispute_id) REFERENCES dispute_cases(id),
        FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
    )
    """)

    # 9. Create `dispute_messages` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dispute_messages (
        id VARCHAR(36) PRIMARY KEY,
        dispute_id VARCHAR(36) NOT NULL,
        sender_user_id VARCHAR(36) NOT NULL,
        message TEXT NOT NULL,
        is_officer_internal_note BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dispute_id) REFERENCES dispute_cases(id),
        FOREIGN KEY (sender_user_id) REFERENCES users(id)
    )
    """)

    # 10. Create `grievances` table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS grievances (
        id VARCHAR(36) PRIMARY KEY,
        ticket_number VARCHAR(50) UNIQUE NOT NULL,
        user_id VARCHAR(36) NOT NULL,
        category VARCHAR(100) DEFAULT 'GENERAL_SERVICE',
        subject VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        assigned_officer_id VARCHAR(36),
        status VARCHAR(50) DEFAULT 'SUBMITTED',
        acknowledged_at DATETIME,
        due_date DATETIME,
        resolution_notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (assigned_officer_id) REFERENCES users(id)
    )
    """)

    # Seed baseline approved insurance policy if none exists
    rules = cursor.execute("SELECT id FROM insurance_policy_rules WHERE is_active = 1").fetchall()
    if not rules:
        print("Seeding baseline approved insurance policy rule...")
        admin = cursor.execute("SELECT id FROM users WHERE role = 'ADMIN'").fetchone()
        admin_id = admin[0] if admin else None
        cursor.execute("""
        INSERT INTO insurance_policy_rules (
            id, version, policy_name, max_uninsured_value_inr,
            hazardous_requires_insurance, fragile_high_requires_insurance,
            review_threshold_inr, is_active, approved_by_user_id
        ) VALUES (?, 1, 'Standard Bengal Corridor Freight Policy', 200000.0, 1, 1, 2000000.0, 1, ?)
        """, (str(uuid.uuid4()), admin_id))

    conn.commit()
    conn.close()
    print("Migration v3 completed successfully!")

if __name__ == "__main__":
    migrate()
