"""
Safe Migration Script for Master Prompt 1.
Preserves all existing data in loadlink.db while adding new tables,
columns, and relationships.
"""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from sqlalchemy import select
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.entities import (
    User, Organization, Dealer, Driver, Transporter,
    Truck, Load, Match, Booking, Shipment,
    VehicleAssignment, FreightAgreement, AgreementAcceptance,
    BookingStateHistory
)
from app.models.enums import (
    UserRole, FleetOwnershipType, TruckStatus,
    AgreementStatus, BookingStatus
)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'loadlink.db'))

async def migrate_database():
    print(f"[*] Starting safe migration on: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print(f"[!] Database file {DB_PATH} not found.")
        return

    # 1. Add missing columns using sqlite3 directly
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    def get_columns(table_name):
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]

    print("[*] Checking and updating column schemas...")
    truck_cols = get_columns('trucks')
    if 'ownership_type' not in truck_cols:
        print("  - Adding column 'ownership_type' to trucks table")
        cursor.execute("ALTER TABLE trucks ADD COLUMN ownership_type VARCHAR(50) DEFAULT 'EXTERNAL_TRANSPORTER'")
    if 'organization_id' not in truck_cols:
        print("  - Adding column 'organization_id' to trucks table")
        cursor.execute("ALTER TABLE trucks ADD COLUMN organization_id VARCHAR(36)")

    driver_cols = get_columns('drivers')
    if 'organization_id' not in driver_cols:
        print("  - Adding column 'organization_id' to drivers table")
        cursor.execute("ALTER TABLE drivers ADD COLUMN organization_id VARCHAR(36)")

    org_cols = get_columns('organizations')
    if 'org_type' not in org_cols:
        print("  - Adding column 'org_type' to organizations table")
        cursor.execute("ALTER TABLE organizations ADD COLUMN org_type VARCHAR(50) DEFAULT 'DEALER_SHIPPER'")

    conn.commit()
    conn.close()

    # 2. Create new tables via async run_sync
    print("[*] Creating new tables if they do not exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  - Verified tables: transporters, vehicle_assignments, freight_agreements, agreement_acceptances, booking_state_history")

    # 3. Seed initial assignment records for trucks that currently have an assigned driver
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Truck).filter(Truck.driver_id.isnot(None)))
        trucks_with_drivers = result.scalars().all()
        print(f"[*] Found {len(trucks_with_drivers)} trucks with driver_id assigned.")
        
        seeded_count = 0
        for truck in trucks_with_drivers:
            chk = await session.execute(
                select(VehicleAssignment).filter_by(
                    truck_id=truck.id,
                    driver_id=truck.driver_id,
                    is_active=True
                )
            )
            existing_assignment = chk.scalars().first()
            
            if not existing_assignment:
                assignment = VehicleAssignment(
                    id=str(uuid.uuid4()),
                    truck_id=truck.id,
                    driver_id=truck.driver_id,
                    assigned_by_user_id=None,
                    is_active=True,
                    assignment_notes="Migrated historical active assignment"
                )
                session.add(assignment)
                seeded_count += 1

        # Seed initial state history for existing bookings
        b_res = await session.execute(select(Booking))
        bookings = b_res.scalars().all()
        history_count = 0
        for b in bookings:
            chk_hist = await session.execute(
                select(BookingStateHistory).filter_by(booking_id=b.id)
            )
            existing_hist = chk_hist.scalars().first()
            if not existing_hist:
                hist = BookingStateHistory(
                    id=str(uuid.uuid4()),
                    booking_id=b.id,
                    from_status=None,
                    to_status=b.status.value if hasattr(b.status, 'value') else str(b.status),
                    changed_by_user_id=b.dealer_id,
                    reason="Migrated historical booking state"
                )
                session.add(hist)
                history_count += 1

        await session.commit()
        print(f"[*] Migrated {seeded_count} active vehicle assignments.")
        print(f"[*] Migrated {history_count} booking state histories.")

    await engine.dispose()
    print("[SUCCESS] Safe database migration completed successfully!")

if __name__ == '__main__':
    asyncio.run(migrate_database())
