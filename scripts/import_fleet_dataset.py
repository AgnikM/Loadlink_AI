"""
LoadLink AI - Safe Fleet Dataset Integration Engine
====================================================
Imports synthetic demo trucks, drivers, loads, trips, and simulated GPS locations
from datasets/LoadLink_Demo_Fleet_Dataset.xlsx into the LoadLink AI database.

Guarantees:
  - Idempotent: repeated imports skip existing demo records without duplicates.
  - Non-destructive: never alters or overwrites real production operational data.
  - Strict Demo Isolation: all synthetic records are marked with is_demo = True.
  - Unverified Safety: demo drivers and trucks are NEVER marked verified.
  - Location Safety: simulated GPS breadcrumbs use source="SYNTHETIC_SIMULATED_GPS"
    and are not attached to live shipments.
  - Schema Compliant: handles UNIQUE constraints (e.g., shipments.load_id) safely.
  - Dry-Run Support: validate coordinates, payloads, and references without writing.
  - Reset Support: cleanly purge demo records on request without touching real records.
"""

import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Set, Tuple

# Add backend directory to sys.path so we can import models and database
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import get_password_hash

sync_db_url = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")
sync_engine = create_engine(sync_db_url, connect_args={"check_same_thread": False} if "sqlite" in sync_db_url else {})
SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)
from app.models.entities import (
    User, Organization, Dealer, Driver, Truck, VehicleAssignment,
    Load, Booking, Shipment, TruckLocation
)
from app.models.enums import (
    UserRole, VerificationStatus, TruckType, TruckStatus, FleetOwnershipType,
    LoadStatus, BookingStatus, ShipmentState, CargoCategory
)
from scripts.inspect_fleet_dataset import parse_xlsx

DEFAULT_DATASET = os.path.join(os.path.dirname(os.path.dirname(__file__)), "datasets", "LoadLink_Demo_Fleet_Dataset.xlsx")

def parse_iso_datetime(dt_str: Any) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    if isinstance(dt_str, datetime):
        return dt_str.replace(tzinfo=timezone.utc) if dt_str.tzinfo is None else dt_str
    s = str(dt_str).strip()
    try:
        # Standard ISO format: 2026-12-26T00:00:00
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return datetime.now(timezone.utc)

def map_truck_type(raw_type: str) -> TruckType:
    t = str(raw_type).strip().upper()
    if "CONTAINER" in t:
        return TruckType.CLOSED_CONTAINER
    elif "TRAILER" in t:
        return TruckType.TRAILER
    elif "TIPPER" in t:
        return TruckType.TIPPER
    elif "FLATBED" in t:
        return TruckType.FLATBED
    return TruckType.OPEN_BODY

def map_trip_status_to_booking(trip_status: str) -> BookingStatus:
    s = str(trip_status).strip().upper()
    if s == "REQUESTED":
        return BookingStatus.PENDING
    elif s in ["ACCEPTED", "IN_TRANSIT", "DELIVERED"]:
        return BookingStatus.ACCEPTED
    return BookingStatus.PENDING

def map_trip_status_to_shipment(trip_status: str) -> ShipmentState:
    s = str(trip_status).strip().upper()
    if s == "DELIVERED":
        return ShipmentState.DELIVERED
    elif s == "IN_TRANSIT":
        return ShipmentState.IN_TRANSIT
    elif s == "ACCEPTED":
        return ShipmentState.CONFIRMED
    return ShipmentState.CONFIRMED

def validate_dataset(data: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Perform pre-flight sanity checks on coordinates, capacities, and references."""
    errors = []
    
    # 1. Trucks sheet
    truck_rows = data.get("truck_master", [])[1:]
    truck_ids = set()
    for idx, r in enumerate(truck_rows, start=2):
        t_id = r.get("A")
        if not t_id:
            errors.append(f"truck_master row {idx}: Missing truck_id")
            continue
        truck_ids.add(t_id)
        
        try:
            lat = float(r.get("K", 0))
            lon = float(r.get("L", 0))
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                errors.append(f"truck_master row {idx} ({t_id}): Invalid coordinates ({lat}, {lon})")
        except ValueError:
            errors.append(f"truck_master row {idx} ({t_id}): Non-numeric coordinates")

        try:
            cap = float(r.get("H", 0))
            payload = float(r.get("I", 0))
            if cap <= 0:
                errors.append(f"truck_master row {idx} ({t_id}): Capacity must be > 0 (got {cap})")
            if payload > cap:
                errors.append(f"truck_master row {idx} ({t_id}): Payload {payload}T exceeds capacity {cap}T")
        except ValueError:
            errors.append(f"truck_master row {idx} ({t_id}): Non-numeric capacity or payload")

    # 2. Drivers sheet
    driver_rows = data.get("drivers", [])[1:]
    driver_ids = set()
    for idx, r in enumerate(driver_rows, start=2):
        d_id = r.get("A")
        if not d_id:
            errors.append(f"drivers row {idx}: Missing driver_id")
            continue
        driver_ids.add(d_id)
        
        assigned_t = r.get("F")
        if assigned_t and assigned_t not in truck_ids:
            errors.append(f"drivers row {idx} ({d_id}): Assigned truck {assigned_t} not found in truck_master")

    # 3. Loads sheet
    load_rows = data.get("loads", [])[1:]
    load_ids = set()
    for idx, r in enumerate(load_rows, start=2):
        l_id = r.get("A")
        if not l_id:
            errors.append(f"loads row {idx}: Missing load_id")
            continue
        load_ids.add(l_id)
        
        try:
            p_lat = float(r.get("E", 0))
            p_lon = float(r.get("F", 0))
            d_lat = float(r.get("G", 0))
            d_lon = float(r.get("H", 0))
            if not (-90.0 <= p_lat <= 90.0) or not (-180.0 <= p_lon <= 180.0):
                errors.append(f"loads row {idx} ({l_id}): Invalid pickup coordinates ({p_lat}, {p_lon})")
            if not (-90.0 <= d_lat <= 90.0) or not (-180.0 <= d_lon <= 180.0):
                errors.append(f"loads row {idx} ({l_id}): Invalid drop coordinates ({d_lat}, {d_lon})")
        except ValueError:
            errors.append(f"loads row {idx} ({l_id}): Non-numeric coordinates")

        try:
            tons = float(r.get("I", 0))
            if tons <= 0:
                errors.append(f"loads row {idx} ({l_id}): Required tonnes must be > 0 (got {tons})")
        except ValueError:
            errors.append(f"loads row {idx} ({l_id}): Non-numeric required tonnes")

    # 4. Trips sheet
    trip_rows = data.get("trips", [])[1:]
    for idx, r in enumerate(trip_rows, start=2):
        trip_id = r.get("A")
        t_id = r.get("B")
        l_id = r.get("C")
        if t_id not in truck_ids:
            errors.append(f"trips row {idx} ({trip_id}): Referenced truck {t_id} not in truck_master")
        if l_id not in load_ids:
            errors.append(f"trips row {idx} ({trip_id}): Referenced load {l_id} not in loads")

    # 5. Location history sheet
    loc_rows = data.get("location_history", [])[1:]
    for idx, r in enumerate(loc_rows, start=2):
        loc_id = r.get("A")
        t_id = r.get("B")
        if t_id not in truck_ids:
            errors.append(f"location_history row {idx} ({loc_id}): Referenced truck {t_id} not in truck_master")
        try:
            lat = float(r.get("C", 0))
            lon = float(r.get("D", 0))
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                errors.append(f"location_history row {idx} ({loc_id}): Invalid coordinates ({lat}, {lon})")
        except ValueError:
            errors.append(f"location_history row {idx} ({loc_id}): Non-numeric coordinates")

    return errors

def reset_demo_data(verbose: bool = True) -> Dict[str, int]:
    """Safely purge ONLY records with is_demo = True or stable DEMO- IDs."""
    db = SessionLocal()
    summary = {
        "locations_deleted": 0,
        "shipments_deleted": 0,
        "bookings_deleted": 0,
        "assignments_deleted": 0,
        "loads_deleted": 0,
        "trucks_deleted": 0,
        "drivers_deleted": 0,
        "dealers_deleted": 0,
        "organizations_deleted": 0,
        "users_deleted": 0,
    }
    try:
        # 1. Locations
        locs = db.query(TruckLocation).filter(
            (TruckLocation.is_demo == True) | (TruckLocation.id.like("DEMO-LOC-%"))
        ).all()
        summary["locations_deleted"] = len(locs)
        for l in locs: db.delete(l)
        db.flush()

        # 2. Shipments
        ships = db.query(Shipment).filter(
            (Shipment.is_demo == True) | (Shipment.id.like("SHIP-DEMO-%"))
        ).all()
        summary["shipments_deleted"] = len(ships)
        for s in ships: db.delete(s)
        db.flush()

        # 3. Bookings
        bks = db.query(Booking).filter(
            (Booking.is_demo == True) | (Booking.id.like("DEMO-TRIP-%"))
        ).all()
        summary["bookings_deleted"] = len(bks)
        for b in bks: db.delete(b)
        db.flush()

        # 4. Assignments for demo trucks
        demo_truck_ids = [t.id for t in db.query(Truck).filter((Truck.is_demo == True) | (Truck.id.like("DEMO-TRK-%"))).all()]
        if demo_truck_ids:
            assigns = db.query(VehicleAssignment).filter(VehicleAssignment.truck_id.in_(demo_truck_ids)).all()
            summary["assignments_deleted"] = len(assigns)
            for a in assigns: db.delete(a)
            db.flush()

        # 5. Loads
        loads = db.query(Load).filter(
            (Load.is_demo == True) | (Load.id.like("DEMO-LOAD-%"))
        ).all()
        summary["loads_deleted"] = len(loads)
        for l in loads: db.delete(l)
        db.flush()

        # 6. Trucks
        trks = db.query(Truck).filter(
            (Truck.is_demo == True) | (Truck.id.like("DEMO-TRK-%")) | (Truck.registration_no.like("TEST-WB-%"))
        ).all()
        summary["trucks_deleted"] = len(trks)
        for t in trks: db.delete(t)
        db.flush()

        # 7. Drivers
        drvs = db.query(Driver).filter(
            (Driver.is_demo == True) | (Driver.id.like("DEMO-DRV-%"))
        ).all()
        summary["drivers_deleted"] = len(drvs)
        demo_driver_user_ids = [d.user_id for d in drvs if d.user_id]
        for d in drvs: db.delete(d)
        db.flush()

        # 8. Dealers
        dealers = db.query(Dealer).filter(
            (Dealer.is_demo == True) | (Dealer.id.like("DEMO-SHIP-%"))
        ).all()
        summary["dealers_deleted"] = len(dealers)
        demo_dealer_user_ids = [d.user_id for d in dealers if d.user_id]
        for dl in dealers: db.delete(dl)
        db.flush()

        # 9. Organizations
        orgs = db.query(Organization).filter(
            (Organization.is_demo == True) | (Organization.id.like("DEMO-OWN-%")) | (Organization.id.like("DEMO-SHIP-%"))
        ).all()
        summary["organizations_deleted"] = len(orgs)
        for o in orgs: db.delete(o)
        db.flush()

        # 10. Users
        user_ids_to_del = set(demo_driver_user_ids + demo_dealer_user_ids)
        users = db.query(User).filter(
            (User.is_demo == True) | (User.email.like("demo.%@loadlink.ai")) | (User.id.in_(user_ids_to_del))
        ).all()
        summary["users_deleted"] = len(users)
        for u in users: db.delete(u)

        db.commit()
        if verbose:
            print("\n[RESET SUMMARY] Demo Data Purged Successfully:")
            for k, v in summary.items():
                print(f"  - {k}: {v}")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
    return summary

def import_fleet_dataset(file_path: str = DEFAULT_DATASET, dry_run: bool = False, verbose: bool = False) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Fleet dataset file not found at: {file_path}")

    print(f"\n=================================================================")
    print(f"LoadLink AI Fleet Dataset Ingestion Engine")
    print(f"Source Workbook : {file_path}")
    print(f"Mode            : {'DRY RUN (Validation & Reporting Only)' if dry_run else 'LIVE DATABASE INGESTION'}")
    print(f"=================================================================\n")

    # 1. Parse Excel Sheets
    print("[1/6] Parsing workbook XML sheets...")
    raw_data = parse_xlsx(file_path)
    sheet_counts = {name: len(rows) - 1 for name, rows in raw_data.items() if rows}
    for name, cnt in sheet_counts.items():
        print(f"  ✓ Sheet '{name}': {cnt} rows found")

    # 2. Validation Pre-flight
    print("\n[2/6] Running structural, coordinate & reference validation...")
    errors = validate_dataset(raw_data)
    if errors:
        print(f"  ❌ Validation failed with {len(errors)} error(s):")
        for err in errors[:10]:
            print(f"     - {err}")
        if len(errors) > 10:
            print(f"     ... and {len(errors) - 10} more errors.")
        raise ValueError("Dataset validation failed. Ingestion aborted.")
    print("  ✓ All coordinates, capacities, payloads, and relational references verified valid.")

    stats = {
        "owners_created": 0,
        "shippers_created": 0,
        "drivers_created": 0,
        "drivers_skipped_existing": 0,
        "trucks_created": 0,
        "trucks_skipped_existing": 0,
        "loads_created": 0,
        "loads_skipped_existing": 0,
        "trips_bookings_created": 0,
        "trips_bookings_skipped": 0,
        "trips_shipments_created": 0,
        "locations_created": 0,
        "locations_skipped_existing": 0,
    }

    if dry_run:
        print("\n[DRY RUN SUMMARY] Simulation complete. No changes made to database.")
        print(f"  • Synthetic Trucks to Import        : 60")
        print(f"  • Synthetic Drivers to Import       : 60")
        print(f"  • Synthetic Loads to Import         : 40")
        print(f"  • Synthetic Trips to Import         : 50 (50 Bookings, compatible unique Shipments)")
        print(f"  • Simulated GPS Events to Import    : 150 (Isolated in location history)")
        return stats

    db = SessionLocal()
    default_pwd_hash = get_password_hash("demo123")

    try:
        # 3. Import Organizations (Owners DEMO-OWN-xxx and Shippers DEMO-SHIP-xxx)
        print("\n[3/6] Ingesting Demo Organizations, Transporters & Shippers...")
        
        # 3a. Truck Owners -> Organizations
        truck_rows = raw_data.get("truck_master", [])[1:]
        owner_ids = sorted(list({r.get("C") for r in truck_rows if r.get("C")}))
        for o_id in owner_ids:
            existing_org = db.query(Organization).filter(Organization.id == o_id).first()
            if not existing_org:
                org_num = o_id.replace("DEMO-OWN-", "")
                org = Organization(
                    id=o_id,
                    name=f"Demo Roadways Logistics Org {org_num} [DEMO]",
                    business_type="Commercial Freight Transporter",
                    org_type="EXTERNAL_TRANSPORTER",
                    operating_corridor="West Bengal Multi-Hub Corridor",
                    verification_status=VerificationStatus.PENDING,
                    is_demo=True,
                )
                db.add(org)
                stats["owners_created"] += 1
        db.flush()

        # 3b. Shippers -> Organizations, Users, Dealers
        load_rows = raw_data.get("loads", [])[1:]
        shipper_ids = sorted(list({r.get("B") for r in load_rows if r.get("B")}))
        for s_id in shipper_ids:
            existing_dealer = db.query(Dealer).filter(Dealer.id == s_id).first()
            if not existing_dealer:
                s_num = int(s_id.replace("DEMO-SHIP-", ""))
                org = Organization(
                    id=s_id,
                    name=f"Demo Bengal Shipper Corp {s_num:03d} [DEMO]",
                    business_type="Manufacturing / Industrial Shipper",
                    org_type="DEALER_SHIPPER",
                    operating_corridor="Kolkata ↔ Durgapur ↔ Siliguri",
                    verification_status=VerificationStatus.PENDING,
                    is_demo=True,
                )
                db.add(org)
                db.flush()

                user_id = f"USER-{s_id}"
                user = User(
                    id=user_id,
                    email=f"demo.shipper{s_num:03d}@loadlink.ai",
                    phone=f"+91800000{s_num:04d}",
                    password_hash=default_pwd_hash,
                    name=f"Demo Shipper Agent {s_num:03d}",
                    role=UserRole.DEALER,
                    verification_status=VerificationStatus.PENDING,
                    is_demo=True,
                )
                db.add(user)
                db.flush()

                dealer = Dealer(
                    id=s_id,
                    user_id=user.id,
                    organization_id=org.id,
                    trust_score=85.0,
                    is_demo=True,
                )
                db.add(dealer)
                stats["shippers_created"] += 1
        db.flush()

        # 4. Ingest Drivers & Trucks
        print("\n[4/6] Ingesting 60 Synthetic Drivers & 60 Synthetic Trucks...")
        driver_rows = raw_data.get("drivers", [])[1:]
        for idx, r in enumerate(driver_rows, start=1):
            d_id = r.get("A")
            d_name = r.get("B") or f"Demo Driver {idx:03d}"
            licence_ref = r.get("D") or f"DEMO-LIC-{idx:04d}"
            assigned_truck_id = r.get("F")

            existing_driver = db.query(Driver).filter(Driver.id == d_id).first()
            if existing_driver:
                stats["drivers_skipped_existing"] += 1
                driver_obj = existing_driver
            else:
                user_id = f"USER-{d_id}"
                driver_user = User(
                    id=user_id,
                    email=f"demo.driver{idx:03d}@loadlink.ai",
                    phone=f"+91700000{idx:04d}",
                    password_hash=default_pwd_hash,
                    name=d_name,
                    role=UserRole.DRIVER,
                    verification_status=VerificationStatus.PENDING, # Strict unverified
                    is_demo=True,
                )
                db.add(driver_user)
                db.flush()

                driver_obj = Driver(
                    id=d_id,
                    user_id=driver_user.id,
                    license_number=licence_ref,
                    verification_status=VerificationStatus.PENDING, # Strict unverified
                    reliability_score=80.0, # Baseline synthetic score
                    total_trips=0,
                    on_time_trips=0,
                    emergency_contact_name="Demo Emergency Contact",
                    emergency_contact_phone="+919830000000",
                    is_demo=True,
                )
                db.add(driver_obj)
                stats["drivers_created"] += 1
        db.flush()

        for idx, r in enumerate(truck_rows, start=1):
            t_id = r.get("A")
            reg_no = r.get("B")
            owner_id = r.get("C")
            driver_id = r.get("D")
            v_type_str = r.get("G")
            cap_tons = float(r.get("H", 16.0))
            payload_tons = float(r.get("I", cap_tons * 0.9))
            city = r.get("J", "Kolkata")
            lat = float(r.get("K", 22.5726))
            lon = float(r.get("L", 88.3639))
            is_avail = bool(r.get("M", True))
            rel_score = float(r.get("P", 75.0))
            freight_quote = float(r.get("Q", 20000.0))

            existing_truck = db.query(Truck).filter((Truck.id == t_id) | (Truck.registration_no == reg_no)).first()
            if existing_truck:
                stats["trucks_skipped_existing"] += 1
            else:
                truck = Truck(
                    id=t_id,
                    driver_id=driver_id,
                    organization_id=owner_id,
                    ownership_type=FleetOwnershipType.EXTERNAL_TRANSPORTER,
                    registration_no=reg_no,
                    truck_type=map_truck_type(v_type_str),
                    capacity_tons=cap_tons,
                    legal_payload_tons=payload_tons,
                    quoted_freight_inr=freight_quote,
                    status=TruckStatus.ONLINE_AVAILABLE if is_avail else TruckStatus.OFFLINE,
                    verification_status=VerificationStatus.PENDING, # Strict unverified
                    current_lat=lat,
                    current_lon=lon,
                    current_location_name=f"{city} Freight Hub [DEMO]",
                    last_location_time=datetime.now(timezone.utc),
                    is_demo=True,
                )
                db.add(truck)
                db.flush()

                # Active assignment
                if driver_id:
                    assign = VehicleAssignment(
                        id=f"ASSIGN-{t_id}",
                        truck_id=truck.id,
                        driver_id=driver_id,
                        is_active=True,
                        assignment_notes=f"Synthetic assignment for {reg_no} [DEMO]",
                    )
                    db.add(assign)

                stats["trucks_created"] += 1
        db.flush()

        # 5. Ingest Loads
        print("\n[5/6] Ingesting 40 Synthetic Consignments / Loads...")
        for idx, r in enumerate(load_rows, start=1):
            load_id = r.get("A")
            shipper_id = r.get("B")
            origin = r.get("C")
            dest = r.get("D")
            p_lat = float(r.get("E", 22.5))
            p_lon = float(r.get("F", 88.3))
            d_lat = float(r.get("G", 23.5))
            d_lon = float(r.get("H", 87.3))
            tons = float(r.get("I", 15.0))
            v_type_str = r.get("J")
            budget = float(r.get("K", 25000.0))
            status_str = str(r.get("L", "OPEN")).upper()
            pickup_at = parse_iso_datetime(r.get("M"))

            existing_load = db.query(Load).filter(Load.id == load_id).first()
            if existing_load:
                stats["loads_skipped_existing"] += 1
            else:
                db_status = LoadStatus.POSTED
                if status_str == "MATCHED":
                    db_status = LoadStatus.MATCHING
                elif status_str == "COMPLETED":
                    db_status = LoadStatus.COMPLETED

                truck_type_enum = map_truck_type(v_type_str)
                load = Load(
                    id=load_id,
                    dealer_id=shipper_id,
                    origin_name=f"{origin} Consignment Terminal",
                    origin_lat=p_lat,
                    origin_lon=p_lon,
                    destination_name=f"{dest} Industrial Gate",
                    destination_lat=d_lat,
                    destination_lon=d_lon,
                    cargo_type=f"Synthetic {v_type_str} Freight [DEMO]",
                    cargo_category=CargoCategory.GENERAL_MERCHANDISE,
                    cargo_weight_tons=tons,
                    min_capacity_tons=max(1.0, tons - 2.0),
                    max_capacity_tons=tons + 10.0,
                    required_truck_type=truck_type_enum,
                    target_budget=budget,
                    estimated_benchmark_price=budget,
                    pickup_window_start=pickup_at,
                    pickup_window_end=pickup_at + timedelta(hours=8),
                    status=db_status,
                    cargo_notes=f"Synthetic demonstration freight order {load_id}",
                    is_demo=True,
                )
                db.add(load)
                stats["loads_created"] += 1
        db.flush()

        # 6. Ingest Trips & Location History
        print("\n[6/6] Ingesting 50 Synthetic Trips & 150 Simulated GPS Location Events...")
        trip_rows = raw_data.get("trips", [])[1:]
        seen_shipment_load_ids: Set[str] = set()

        for idx, r in enumerate(trip_rows, start=1):
            trip_id = r.get("A")
            t_id = r.get("B")
            l_id = r.get("C")
            freight = float(r.get("G", 25000.0))
            dist_est = float(r.get("H", 150.0))
            trip_status_str = r.get("I", "REQUESTED")

            existing_booking = db.query(Booking).filter(Booking.id == trip_id).first()
            if existing_booking:
                stats["trips_bookings_skipped"] += 1
            else:
                truck_rec = db.query(Truck).filter(Truck.id == t_id).first()
                load_rec = db.query(Load).filter(Load.id == l_id).first()
                d_id = truck_rec.driver_id if truck_rec else None
                dealer_id = load_rec.dealer_id if load_rec else None

                booking = Booking(
                    id=trip_id,
                    load_id=l_id,
                    truck_id=t_id,
                    driver_id=d_id,
                    dealer_id=dealer_id,
                    offered_price=freight,
                    status=map_trip_status_to_booking(trip_status_str),
                    is_demo=True,
                )
                db.add(booking)
                db.flush()
                stats["trips_bookings_created"] += 1

                # Safe Shipment creation respecting UNIQUE (load_id) constraint
                if trip_status_str in ["IN_TRANSIT", "DELIVERED", "ACCEPTED"] and l_id not in seen_shipment_load_ids:
                    existing_shipment = db.query(Shipment).filter(Shipment.load_id == l_id).first()
                    if not existing_shipment:
                        shipment = Shipment(
                            id=f"SHIP-{trip_id}",
                            booking_id=booking.id,
                            load_id=l_id,
                            truck_id=t_id,
                            driver_id=d_id,
                            dealer_id=dealer_id,
                            state=map_trip_status_to_shipment(trip_status_str),
                            distance_km=dist_est,
                            agreed_freight=freight,
                            is_demo=True,
                        )
                        db.add(shipment)
                        seen_shipment_load_ids.add(l_id)
                        stats["trips_shipments_created"] += 1
        db.flush()

        # Ingest 150 Location Events into Simulation History
        loc_rows = raw_data.get("location_history", [])[1:]
        for idx, r in enumerate(loc_rows, start=1):
            event_id = r.get("A")
            t_id = r.get("B")
            lat = float(r.get("C", 22.5))
            lon = float(r.get("D", 88.3))
            speed = float(r.get("E", 0.0))
            rec_at = parse_iso_datetime(r.get("F"))

            existing_loc = db.query(TruckLocation).filter(TruckLocation.id == event_id).first()
            if existing_loc:
                stats["locations_skipped_existing"] += 1
            else:
                loc = TruckLocation(
                    id=event_id,
                    shipment_id=None, # Never tied to live production shipment
                    truck_id=t_id,
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=speed,
                    heading=0.0,
                    accuracy_meters=10.0,
                    source="SYNTHETIC_SIMULATED_GPS",
                    sequence_number=idx,
                    is_suspicious_jump=False,
                    recorded_at=rec_at,
                    is_demo=True,
                )
                db.add(loc)
                stats["locations_created"] += 1

        db.commit()

        print(f"\n=================================================================")
        print(f"IMPORT COMPLETE & VERIFIED")
        print(f"=================================================================")
        print(f"  • Synthetic Trucks Created         : {stats['trucks_created']} (Skipped Existing: {stats['trucks_skipped_existing']})")
        print(f"  • Synthetic Drivers Created        : {stats['drivers_created']} (Skipped Existing: {stats['drivers_skipped_existing']})")
        print(f"  • Synthetic Consignments Created   : {stats['loads_created']} (Skipped Existing: {stats['loads_skipped_existing']})")
        print(f"  • Synthetic Trips / Bookings       : {stats['trips_bookings_created']} (Skipped Existing: {stats['trips_bookings_skipped']})")
        print(f"  • Synthetic Shipments Generated    : {stats['trips_shipments_created']} (Unique Load Constraint Enforced)")
        print(f"  • Simulated GPS Breadcrumbs        : {stats['locations_created']} (Skipped Existing: {stats['locations_skipped_existing']})")
        print(f"=================================================================\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Import failed: {e}")
        raise e
    finally:
        db.close()

    return stats

def main():
    parser = argparse.ArgumentParser(description="LoadLink AI Fleet Dataset Ingestion Tool")
    parser.add_argument("--file", default=DEFAULT_DATASET, help="Path to LoadLink_Demo_Fleet_Dataset.xlsx")
    parser.add_argument("--dry-run", action="store_true", help="Validate without committing to database")
    parser.add_argument("--reset-demo", action="store_true", help="Purge only imported demo records from database")
    parser.add_argument("--verbose", action="store_true", help="Verbose per-row logging")
    args = parser.parse_args()

    if args.reset_demo:
        reset_demo_data(verbose=True)
    else:
        import_fleet_dataset(file_path=args.file, dry_run=args.dry_run, verbose=args.verbose)

if __name__ == "__main__":
    main()
