import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "loadlink.db")

def verify():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("================================================================")
    print("LOADLINK AI - DEMO FLEET INTEGRATION DATABASE AUDIT")
    print("================================================================")

    tables = ['trucks', 'drivers', 'loads', 'bookings', 'shipments', 'truck_locations']
    for table in tables:
        c.execute(f"SELECT count(*), sum(case when is_demo = 1 then 1 else 0 end), sum(case when is_demo = 0 or is_demo is null then 1 else 0 end) FROM {table}")
        total, demo, real = c.fetchone()
        demo = demo or 0
        real = real or 0
        print(f"  • Table {table:16}: Total = {total:3d} | Demo = {demo:3d} | Real/Production = {real:3d}")

    # 1. Check verification status of demo trucks
    c.execute("SELECT count(*) FROM trucks WHERE is_demo = 1 AND verification_status = 'VERIFIED'")
    verified_demo_trucks = c.fetchone()[0]
    print(f"\n[SECURITY CHECK 1] Verified Demo Trucks (MUST BE 0): {verified_demo_trucks}")
    assert verified_demo_trucks == 0, "FAILED: Demo trucks were marked VERIFIED!"

    # 2. Check verification status of demo drivers
    c.execute("SELECT count(*) FROM drivers WHERE is_demo = 1 AND verification_status = 'VERIFIED'")
    verified_demo_drivers = c.fetchone()[0]
    print(f"[SECURITY CHECK 2] Verified Demo Drivers (MUST BE 0): {verified_demo_drivers}")
    assert verified_demo_drivers == 0, "FAILED: Demo drivers were marked VERIFIED!"

    # 3. Check simulated GPS location source
    c.execute("SELECT DISTINCT source FROM truck_locations WHERE is_demo = 1")
    demo_loc_sources = [r[0] for r in c.fetchall()]
    print(f"[SECURITY CHECK 3] Demo Location Sources: {demo_loc_sources}")
    assert demo_loc_sources == ["SYNTHETIC_SIMULATED_GPS"], f"FAILED: Unexpected demo source {demo_loc_sources}"

    # 4. Check that demo locations have no live shipment_id attached
    c.execute("SELECT count(*) FROM truck_locations WHERE is_demo = 1 AND shipment_id IS NOT NULL")
    attached_demo_locs = c.fetchone()[0]
    print(f"[SECURITY CHECK 4] Demo Locations Attached to Live Shipments (MUST BE 0): {attached_demo_locs}")
    assert attached_demo_locs == 0, "FAILED: Demo locations attached to live shipments!"

    # 5. Check foreign key integrity
    c.execute("PRAGMA foreign_key_check")
    fk_violations = c.fetchall()
    print(f"[INTEGRITY CHECK 5] Foreign Key Violations (MUST BE 0): {len(fk_violations)}")
    assert len(fk_violations) == 0, f"FAILED: Found FK violations: {fk_violations}"

    print("\n✅ All 5 Security & Database Integrity Checks Passed 100%!")
    print("================================================================")
    conn.close()

if __name__ == "__main__":
    verify()
