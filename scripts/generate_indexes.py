import sqlite3
import os

def create_optimal_indexes(db_path: str):
    if not os.path.exists(db_path):
        print(f"File {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    # 1. Get all user tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]

    statements = []

    # 2. Add an index for EVERY Foreign Key in every table
    for t in tables:
        cur.execute(f"PRAGMA foreign_key_list({t});")
        fks = cur.fetchall()
        for fk in fks:
            from_col = fk[3]
            idx_name = f"ix_{t}_{from_col}"
            stmt = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {t} ({from_col});"
            statements.append((idx_name, t, stmt))

    # 3. Add explicit high-value compound / query indexes
    high_value_indexes = [
        # Users & Orgs
        ("ix_users_role_active", "users", ["role", "is_active"]),
        ("ix_orgs_type_status", "organizations", ["type", "status"]),

        # Trucks & Loads
        ("ix_trucks_status_type", "trucks", ["status", "truck_type"]),
        ("ix_trucks_status_capacity", "trucks", ["status", "capacity_tonnage"]),
        ("ix_trucks_current_hub", "trucks", ["current_hub"]),
        ("ix_loads_status_pickup", "loads", ["status", "pickup_window_start"]),
        ("ix_loads_status_hubs", "loads", ["status", "origin_hub", "destination_hub"]),
        ("ix_loads_created_at", "loads", ["created_at"]),

        # Matching & Bookings
        ("ix_matches_load_score", "matches", ["load_id", "score"]),
        ("ix_matches_truck_status", "matches", ["truck_id", "status"]),
        ("ix_bookings_truck_status", "bookings", ["truck_id", "status"]),
        ("ix_bookings_load_status", "bookings", ["load_id", "status"]),
        ("ix_bookings_created_at", "bookings", ["created_at"]),

        # Shipments & Telematics
        ("ix_shipments_truck_state", "shipments", ["truck_id", "state"]),
        ("ix_shipments_driver_state", "shipments", ["driver_id", "state"]),
        ("ix_shipments_created_at", "shipments", ["created_at"]),
        ("ix_truck_locations_shipment_rec", "truck_locations", ["shipment_id", "recorded_at"]),
        ("ix_truck_locations_truck_rec", "truck_locations", ["truck_id", "recorded_at"]),

        # SOS & Safety
        ("ix_sos_events_status_created", "sos_events", ["status", "created_at"]),
        ("ix_sos_events_driver_status", "sos_events", ["driver_id", "status"]),

        # Payments & Custody
        ("ix_direct_payments_created_at", "direct_payments", ["created_at"]),
        ("ix_custody_events_shipment_type", "custody_events", ["shipment_id", "event_type"]),

        # Disputes, Breakdowns & Inspections
        ("ix_dispute_cases_status_created", "dispute_cases", ["status", "created_at"]),
        ("ix_vehicle_breakdowns_status", "vehicle_breakdowns", ["status"]),
        ("ix_pre_trip_truck_passed", "pre_trip_inspections", ["truck_id", "passed"]),
        ("ix_notifications_user_unread", "notifications", ["user_id", "is_read"]),
        ("ix_audit_logs_actor_time", "audit_logs", ["actor_id", "timestamp"]),
    ]

    for idx_name, t, cols in high_value_indexes:
        cur.execute(f"PRAGMA table_info({t});")
        t_cols = {r[1] for r in cur.fetchall()}
        if all(c in t_cols for c in cols):
            col_str = ", ".join(cols)
            stmt = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {t} ({col_str});"
            statements.append((idx_name, t, stmt))

    # Apply all statements
    applied = 0
    for idx_name, t, stmt in statements:
        try:
            cur.execute(stmt)
            applied += 1
        except Exception as e:
            print(f"Error creating {idx_name} on {t}: {e}")

    conn.commit()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
    total_idx = cur.fetchone()[0]
    print(f"Successfully processed {applied} indexes on {db_path}. Total explicit indexes: {total_idx}")

    # Check for foreign key integrity
    cur.execute("PRAGMA foreign_key_check;")
    violations = cur.fetchall()
    print(f"Foreign Key check on {db_path}: {len(violations)} violations.")
    conn.close()

if __name__ == "__main__":
    create_optimal_indexes("backend/loadlink.db")
    if os.path.exists("backend/tests/test_isolated.db"):
        create_optimal_indexes("backend/tests/test_isolated.db")
