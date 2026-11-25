import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.core.database import engine, Base, AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.entities import (
    User, Organization, Dealer, Driver, Transporter, Truck, Load, Match, Booking, Shipment, POD, Rating, SystemConfiguration,
    VehicleAssignment, FreightAgreement, AgreementAcceptance, BookingStateHistory, InsurancePolicyRule
)
from app.models.enums import (
    UserRole, FleetOwnershipType, VerificationStatus, TruckType, TruckStatus, LoadStatus, BookingStatus, ShipmentState, PODStatus, AgreementStatus
)
from app.services.pricing_service import pricing_service
from app.services.routing_service import routing_service
from app.services.match_engine import match_engine

async def seed_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        print("[INFO] Seeding LoadLink AI Multi-Hub West Bengal Freight Logistics Database...")

        # 1. System Configurations
        config_weights = SystemConfiguration(
            config_key="match_weights",
            config_value_json={
                "route_compatibility": 0.25,
                "availability_feasibility": 0.20,
                "pickup_proximity": 0.15,
                "capacity_fit": 0.10,
                "price_competitiveness": 0.10,
                "reliability": 0.10,
                "return_load_potential": 0.10,
            },
            description="7-Factor Deterministic Match Weights [DEMO SYSTEM CONFIG]",
        )
        session.add(config_weights)

        # Baseline Insurance Policy Rule (v1)
        base_insurance_policy = InsurancePolicyRule(
            version=1,
            policy_name="Standard Bengal Corridor Freight Policy",
            max_uninsured_value_inr=200000.0,
            hazardous_requires_insurance=True,
            fragile_high_requires_insurance=True,
            review_threshold_inr=2000000.0,
            is_active=True,
        )
        session.add(base_insurance_policy)

        # 2. Admin & Specialized Role Users
        admin_user = User(
            email="admin@loadlink.ai",
            phone="+919830000001",
            password_hash=get_password_hash("admin123"),
            name="Operations Control Tower",
            role=UserRole.ADMIN,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(admin_user)

        fleet_manager_user = User(
            email="fleet.manager@loadlink.ai",
            phone="+919830000002",
            password_hash=get_password_hash("fleet123"),
            name="Arijit Mukherjee",
            role=UserRole.FLEET_MANAGER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(fleet_manager_user)

        compliance_user = User(
            email="compliance@loadlink.ai",
            phone="+919830000003",
            password_hash=get_password_hash("compliance123"),
            name="Poulomi Sengupta",
            role=UserRole.COMPLIANCE_OFFICER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(compliance_user)

        dispute_user = User(
            email="disputes@loadlink.ai",
            phone="+919830000004",
            password_hash=get_password_hash("dispute123"),
            name="Subrata Banerjee",
            role=UserRole.DISPUTE_OFFICER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(dispute_user)

        control_room_user = User(
            email="control.room@loadlink.ai",
            phone="+919830000005",
            password_hash=get_password_hash("control123"),
            name="Sanjib Ghosh",
            role=UserRole.CONTROL_ROOM,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(control_room_user)

        # Transporter User & Org
        transporter_user = User(
            email="transporter@bengalroadways.in",
            phone="+919830000006",
            password_hash=get_password_hash("transporter123"),
            name="Vikramjit Singh",
            role=UserRole.TRANSPORTER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(transporter_user)
        await session.flush()

        transporter_org = Organization(
            name="Bengal Super Roadways Logistics [DEMO TRANSPORTER]",
            business_type="Commercial Freight Carrier",
            gstin="19AABCS1234F1Z8",
            operating_corridor="Kolkata ↔ Durgapur ↔ Siliguri",
            org_type="EXTERNAL_TRANSPORTER",
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(transporter_org)
        await session.flush()

        transporter_profile = Transporter(
            user_id=transporter_user.id,
            organization_id=transporter_org.id,
            fleet_size=12,
            trust_score=95.0,
        )
        session.add(transporter_profile)

        # 3. Dealers
        # Dealer 1: Dankuni / Kolkata - Bengal Steel
        dealer1_user = User(
            email="dealer.kolkata@bengalsteel.in",
            phone="+919830011111",
            password_hash=get_password_hash("dealer123"),
            name="Debashis Roy",
            role=UserRole.DEALER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(dealer1_user)
        await session.flush()

        org1 = Organization(
            name="Bengal Steel & Tubes Pvt Ltd [DEMO SHIPPERS]",
            business_type="Steel Manufacturing & Trading",
            gstin="19AAACB4821M1Z5",
            operating_corridor="Kolkata ↔ Durgapur ↔ Asansol Corridor",
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(org1)
        await session.flush()

        dealer1 = Dealer(
            user_id=dealer1_user.id,
            organization_id=org1.id,
            trust_score=96.0,
            total_loads_posted=14,
            total_completed_loads=12,
        )
        session.add(dealer1)

        # Dealer 2: Durgapur Alloys
        dealer2_user = User(
            email="dealer.durgapur@durgapuralloys.com",
            phone="+919830022222",
            password_hash=get_password_hash("dealer123"),
            name="Siddharth Sen",
            role=UserRole.DEALER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(dealer2_user)
        await session.flush()

        org2 = Organization(
            name="Durgapur Heavy Alloys & Structurals Ltd [DEMO SHIPPERS]",
            business_type="Heavy Industrial Fabrication",
            gstin="19AAACD9182L1ZX",
            operating_corridor="Durgapur ↔ Kolkata Port",
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(org2)
        await session.flush()

        dealer2 = Dealer(
            user_id=dealer2_user.id,
            organization_id=org2.id,
            trust_score=94.0,
            total_loads_posted=9,
            total_completed_loads=8,
        )
        session.add(dealer2)

        # Dealer 3: Haldia Petrochemicals & Polymers
        dealer3_user = User(
            email="dealer.haldia@haldiapetro.in",
            phone="+919830033333",
            password_hash=get_password_hash("dealer123"),
            name="Ananya Banerjee",
            role=UserRole.DEALER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(dealer3_user)
        await session.flush()

        org3 = Organization(
            name="Haldia Petrochem Logistics Corp [DEMO SHIPPERS]",
            business_type="Petrochemicals & Bulk Commodities",
            gstin="19AAACH9918K1ZZ",
            operating_corridor="Haldia Port ↔ Kharagpur ↔ Kolkata",
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(org3)
        await session.flush()

        dealer3 = Dealer(
            user_id=dealer3_user.id,
            organization_id=org3.id,
            trust_score=95.0,
            total_loads_posted=6,
            total_completed_loads=5,
        )
        session.add(dealer3)

        # 4. Drivers & Fleet Trucks across West Bengal
        now = datetime.now(timezone.utc)

        # Driver 1: Rajesh Yadav (Truck #184) - Dankuni / Kolkata
        d1_user = User(
            email="driver.rajesh@loadlink.ai",
            phone="+919874100184",
            password_hash=get_password_hash("driver123"),
            name="Rajesh Yadav",
            role=UserRole.DRIVER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(d1_user)
        await session.flush()

        driver1 = Driver(
            user_id=d1_user.id,
            license_number="WB-02-2018-004812",
            verification_status=VerificationStatus.VERIFIED,
            reliability_score=96.0,
            total_trips=48,
            on_time_trips=46,
            cancellations_count=1,
        )
        session.add(driver1)
        await session.flush()

        truck1 = Truck(
            driver_id=driver1.id,
            registration_no="WB-19-AF-0184",
            truck_type=TruckType.OPEN_BODY,
            capacity_tons=16.0,
            status=TruckStatus.ONLINE_AVAILABLE,
            verification_status=VerificationStatus.VERIFIED,
            current_lat=22.6842, # Dankuni
            current_lon=88.2934,
            current_location_name="Dankuni Freight Terminal (NH19)",
            last_location_time=now,
        )
        session.add(truck1)

        # Driver 2: Amit Das (Truck #521) - Kolkata Port / Docks
        d2_user = User(
            email="driver.amit@loadlink.ai",
            phone="+919874100521",
            password_hash=get_password_hash("driver123"),
            name="Amit Das",
            role=UserRole.DRIVER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(d2_user)
        await session.flush()

        driver2 = Driver(
            user_id=d2_user.id,
            license_number="WB-11-2019-009124",
            verification_status=VerificationStatus.VERIFIED,
            reliability_score=94.0,
            total_trips=34,
            on_time_trips=32,
            cancellations_count=1,
        )
        session.add(driver2)
        await session.flush()

        truck2 = Truck(
            driver_id=driver2.id,
            registration_no="WB-39-B-0521",
            truck_type=TruckType.OPEN_BODY,
            capacity_tons=15.0,
            status=TruckStatus.ONLINE_AVAILABLE,
            verification_status=VerificationStatus.VERIFIED, # explicitly VERIFIED
            current_lat=22.5448, # Kolkata Port
            current_lon=88.3186,
            current_location_name="Kolkata Port Container Terminal",
            last_location_time=now,
        )
        session.add(truck2)

        # Driver 3: Gurmeet Singh (Truck #728) - Raniganj
        d3_user = User(
            email="driver.gurmeet@loadlink.ai",
            phone="+919874100728",
            password_hash=get_password_hash("driver123"),
            name="Gurmeet Singh",
            role=UserRole.DRIVER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(d3_user)
        await session.flush()

        driver3 = Driver(
            user_id=d3_user.id,
            license_number="WB-41-2017-003319",
            verification_status=VerificationStatus.VERIFIED,
            reliability_score=92.0,
            total_trips=62,
            on_time_trips=57,
            cancellations_count=2,
        )
        session.add(driver3)
        await session.flush()

        truck3 = Truck(
            driver_id=driver3.id,
            registration_no="WB-41-C-0728",
            truck_type=TruckType.FLATBED,
            capacity_tons=22.0,
            status=TruckStatus.ONLINE_AVAILABLE,
            verification_status=VerificationStatus.VERIFIED,
            current_lat=23.6210, # Raniganj
            current_lon=87.1265,
            current_location_name="Raniganj Coal & Cement Bypass",
            last_location_time=now,
        )
        session.add(truck3)

        # Driver 4: Sunil Soren (Truck #310) - Panagarh / Durgapur
        d4_user = User(
            email="driver.sunil@loadlink.ai",
            phone="+919874100310",
            password_hash=get_password_hash("driver123"),
            name="Sunil Soren",
            role=UserRole.DRIVER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(d4_user)
        await session.flush()

        driver4 = Driver(
            user_id=d4_user.id,
            license_number="WB-38-2021-008102",
            verification_status=VerificationStatus.VERIFIED,
            reliability_score=95.0,
            total_trips=29,
            on_time_trips=28,
            cancellations_count=0,
        )
        session.add(driver4)
        await session.flush()

        truck4 = Truck(
            driver_id=driver4.id,
            registration_no="WB-38-E-0310",
            truck_type=TruckType.OPEN_BODY,
            capacity_tons=16.0,
            status=TruckStatus.ONLINE_AVAILABLE,
            verification_status=VerificationStatus.VERIFIED,
            current_lat=23.3500,
            current_lon=87.5200,
            current_location_name="NH19 Express Highway (Near Panagarh)",
            last_location_time=now,
        )
        session.add(truck4)

        # Driver 5: Bikash Mukherjee (Truck #1108) - Haldia / Kharagpur (Closed Container)
        d5_user = User(
            email="driver.bikash@loadlink.ai",
            phone="+919874101108",
            password_hash=get_password_hash("driver123"),
            name="Bikash Mukherjee",
            role=UserRole.DRIVER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(d5_user)
        await session.flush()

        driver5 = Driver(
            user_id=d5_user.id,
            license_number="WB-29-2020-001108",
            verification_status=VerificationStatus.VERIFIED,
            reliability_score=97.0,
            total_trips=42,
            on_time_trips=41,
            cancellations_count=0,
        )
        session.add(driver5)
        await session.flush()

        truck5 = Truck(
            driver_id=driver5.id,
            registration_no="WB-29-D-1108",
            truck_type=TruckType.CLOSED_CONTAINER,
            capacity_tons=25.0,
            status=TruckStatus.ONLINE_AVAILABLE,
            verification_status=VerificationStatus.VERIFIED,
            current_lat=22.0667, # Haldia
            current_lon=88.0698,
            current_location_name="Haldia Deep Port Logistics Gate 1",
            last_location_time=now,
        )
        session.add(truck5)

        # Driver 6: Pradeep Roy (Truck #4490) - Siliguri Gateway (40T Trailer)
        d6_user = User(
            email="driver.pradeep@loadlink.ai",
            phone="+919874104490",
            password_hash=get_password_hash("driver123"),
            name="Pradeep Roy",
            role=UserRole.DRIVER,
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(d6_user)
        await session.flush()

        driver6 = Driver(
            user_id=d6_user.id,
            license_number="WB-74-2016-004490",
            verification_status=VerificationStatus.VERIFIED,
            reliability_score=93.0,
            total_trips=71,
            on_time_trips=65,
            cancellations_count=2,
        )
        session.add(driver6)
        await session.flush()

        truck6 = Truck(
            driver_id=driver6.id,
            registration_no="WB-74-A-4490",
            truck_type=TruckType.TRAILER,
            capacity_tons=40.0,
            status=TruckStatus.ONLINE_AVAILABLE,
            verification_status=VerificationStatus.VERIFIED,
            current_lat=26.7271, # Siliguri
            current_lon=88.3953,
            current_location_name="Siliguri North Bengal Transport Hub",
            last_location_time=now,
        )
        session.add(truck6)

        await session.flush()

        # Fleet Ownership & Vehicle Assignments
        truck1.ownership_type = FleetOwnershipType.LOADLINK_OWNED
        truck2.ownership_type = FleetOwnershipType.EXTERNAL_TRANSPORTER
        truck2.organization_id = transporter_org.id
        truck3.ownership_type = FleetOwnershipType.EXTERNAL_TRANSPORTER
        truck3.organization_id = transporter_org.id
        truck4.ownership_type = FleetOwnershipType.LOADLINK_OWNED
        truck5.ownership_type = FleetOwnershipType.EXTERNAL_TRANSPORTER
        truck6.ownership_type = FleetOwnershipType.EXTERNAL_TRANSPORTER

        for t, d in [(truck1, driver1), (truck2, driver2), (truck3, driver3), (truck4, driver4), (truck5, driver5), (truck6, driver6)]:
            assign = VehicleAssignment(
                truck_id=t.id,
                driver_id=d.id,
                assigned_by_user_id=admin_user.id,
                is_active=True,
                assignment_notes=f"Initial seeded active assignment for {t.registration_no}"
            )
            session.add(assign)

        # 5. Active Loads
        tomorrow_10am = now + timedelta(days=1)
        tomorrow_10am = tomorrow_10am.replace(hour=10, minute=0, second=0, microsecond=0)
        tomorrow_2pm = tomorrow_10am + timedelta(hours=4)

        load1 = Load(
            dealer_id=dealer1.id,
            origin_name="Kolkata Port Docks (Warehouse 4)",
            origin_lat=22.5448,
            origin_lon=88.3186,
            destination_name="Durgapur Steel Complex (Gate 2)",
            destination_lat=23.5204,
            destination_lon=87.3119,
            cargo_type="TMT Steel Billets",
            cargo_weight_tons=15.0,
            required_truck_type=TruckType.OPEN_BODY,
            min_capacity_tons=10.0,
            max_capacity_tons=18.0,
            pickup_window_start=tomorrow_10am,
            pickup_window_end=tomorrow_2pm,
            target_budget=19000.0,
            estimated_benchmark_price=18800.0,
            cargo_notes="[DEMO RECORD] Industrial consignment with valid e-Way Bill. Requires crane loading assistance.",
            status=LoadStatus.MATCHING,
        )
        session.add(load1)

        load_return = Load(
            dealer_id=dealer2.id,
            origin_name="Durgapur Alloy Yard (Durgapur)",
            origin_lat=23.5204,
            origin_lon=87.3119,
            destination_name="Dankuni Freight Hub (Kolkata Outskirts)",
            destination_lat=22.6842,
            destination_lon=88.2934,
            cargo_type="Machined Iron Castings",
            cargo_weight_tons=14.0,
            required_truck_type=TruckType.OPEN_BODY,
            min_capacity_tons=12.0,
            max_capacity_tons=18.0,
            pickup_window_start=tomorrow_2pm + timedelta(hours=3),
            pickup_window_end=tomorrow_2pm + timedelta(hours=8),
            target_budget=20500.0,
            estimated_benchmark_price=19800.0,
            cargo_notes="[DEMO RECORD] Return consignment. Immediate loading available upon arrival at Durgapur.",
            status=LoadStatus.POSTED,
        )
        session.add(load_return)

        load_haldia = Load(
            dealer_id=dealer3.id,
            origin_name="Haldia Deep Port Terminal",
            origin_lat=22.0667,
            origin_lon=88.0698,
            destination_name="Kharagpur Engineering Complex",
            destination_lat=22.3460,
            destination_lon=87.2320,
            cargo_type="Polymer Granules (Palletized)",
            cargo_weight_tons=22.0,
            required_truck_type=TruckType.CLOSED_CONTAINER,
            min_capacity_tons=20.0,
            max_capacity_tons=28.0,
            pickup_window_start=now + timedelta(hours=6),
            pickup_window_end=now + timedelta(hours=14),
            target_budget=24000.0,
            estimated_benchmark_price=23500.0,
            cargo_notes="[DEMO RECORD] Moisture-proof sealed container required. Digital gate-pass enabled.",
            status=LoadStatus.POSTED,
        )
        session.add(load_haldia)

        await session.flush()

        # 6. Pre-generate matches for load1 so matches exist immediately on first load
        all_trucks = [truck1, truck2, truck3, truck4, truck5, truck6]
        for t in all_trucks:
            eval_res = await match_engine.evaluate_candidate(truck=t, load=load1)
            if eval_res:
                m = Match(
                    load_id=load1.id,
                    truck_id=t.id,
                    total_score=eval_res["total_score"],
                    route_compat_score=eval_res["factor_breakdown"]["route_compatibility"],
                    availability_score=eval_res["factor_breakdown"]["availability_feasibility"],
                    proximity_score=eval_res["factor_breakdown"]["pickup_proximity"],
                    capacity_score=eval_res["factor_breakdown"]["capacity_fit"],
                    price_score=eval_res["factor_breakdown"]["price_competitiveness"],
                    reliability_score=eval_res["factor_breakdown"]["reliability"],
                    return_potential_score=eval_res["factor_breakdown"]["return_load_potential"],
                    road_eta_km=eval_res["road_eta_km"],
                    road_eta_mins=eval_res["road_eta_mins"],
                    explanation_summary=eval_res["explanation_summary"],
                    factor_breakdown=eval_res["factor_breakdown"],
                    is_coming_near_you=eval_res["is_coming_near_you"],
                    estimated_arrival_at_pickup=eval_res["estimated_arrival_at_pickup"],
                )
                session.add(m)

        # 7. Seed 1 Historical Completed Shipment with POD & Rating (for operational metrics & history)
        hist_load = Load(
            dealer_id=dealer1.id,
            origin_name="Dankuni Freight Terminal (NH19)",
            origin_lat=22.6842,
            origin_lon=88.2934,
            destination_name="Bardhaman Agricultural Warehouse",
            destination_lat=23.2324,
            destination_lon=87.8615,
            cargo_type="Agricultural Irrigation Pipes",
            cargo_weight_tons=12.0,
            required_truck_type=TruckType.OPEN_BODY,
            min_capacity_tons=10.0,
            max_capacity_tons=16.0,
            pickup_window_start=now - timedelta(days=2),
            pickup_window_end=now - timedelta(days=2, hours=-4),
            target_budget=14500.0,
            estimated_benchmark_price=14200.0,
            cargo_notes="[DEMO RECORD] Delivered and verified consignment.",
            status=LoadStatus.COMPLETED,
        )
        session.add(hist_load)
        await session.flush()

        hist_booking = Booking(
            load_id=hist_load.id,
            truck_id=truck1.id,
            driver_id=driver1.id,
            dealer_id=dealer1.id,
            offered_price=14500.0,
            status=BookingStatus.ACCEPTED,
            requested_at=now - timedelta(days=2, hours=2),
            responded_at=now - timedelta(days=2, hours=1),
        )
        session.add(hist_booking)
        await session.flush()

        import hashlib, json
        agr_payload = {
            "load_id": hist_load.id,
            "agreed_freight": 14500.0,
            "terms": "Standard LoadLink Direct Freight Agreement"
        }
        agr_hash = hashlib.sha256(json.dumps(agr_payload, sort_keys=True).encode()).hexdigest()
        hist_agreement = FreightAgreement(
            booking_id=hist_booking.id,
            load_id=hist_load.id,
            dealer_id=dealer1.id,
            dealer_user_id=dealer1_user.id,
            transporter_user_id=d1_user.id,
            driver_id=driver1.id,
            truck_id=truck1.id,
            version=1,
            status=AgreementStatus.MUTUALLY_ACCEPTED,
            agreed_freight=14500.0,
            additional_charges={},
            cargo_details={"type": hist_load.cargo_type, "weight_tons": hist_load.cargo_weight_tons},
            vehicle_details={"registration_no": truck1.registration_no, "truck_type": truck1.truck_type.value},
            driver_details={"name": d1_user.name, "license_number": driver1.license_number},
            pickup_terms="Standard Dankuni pickup",
            delivery_terms="Direct transit to Bardhaman",
            insurance_requirements="Statutory carriage rules",
            cancellation_terms="Standard terms",
            delay_detention_rules="Free window 3 hours",
            claims_dispute_conditions="Jurisdiction: Kolkata Courts",
            content_hash=agr_hash,
        )
        session.add(hist_agreement)
        await session.flush()

        dealer_acc = AgreementAcceptance(
            agreement_id=hist_agreement.id,
            version=1,
            user_id=dealer1_user.id,
            party_role=UserRole.DEALER,
            content_hash=agr_hash,
            accepted_at=now - timedelta(days=2, hours=2),
        )
        session.add(dealer_acc)

        carrier_acc = AgreementAcceptance(
            agreement_id=hist_agreement.id,
            version=1,
            user_id=d1_user.id,
            party_role=UserRole.DRIVER,
            content_hash=agr_hash,
            accepted_at=now - timedelta(days=2, hours=1),
        )
        session.add(carrier_acc)

        hist_state_hist = BookingStateHistory(
            booking_id=hist_booking.id,
            from_status="PENDING",
            to_status="ACCEPTED",
            changed_by_user_id=d1_user.id,
            reason="Accepted after mutual agreement execution"
        )
        session.add(hist_state_hist)

        hist_shipment = Shipment(
            booking_id=hist_booking.id,
            load_id=hist_load.id,
            truck_id=truck1.id,
            driver_id=driver1.id,
            dealer_id=dealer1.id,
            state=ShipmentState.COMPLETED,
            distance_km=82.0,
            agreed_freight=14500.0,
            pickup_eta=now - timedelta(days=2),
            delivery_eta=now - timedelta(days=2, hours=-3),
            actual_pickup_time=now - timedelta(days=2),
            actual_delivery_time=now - timedelta(days=2, hours=-2, minutes=-45),
        )
        session.add(hist_shipment)
        await session.flush()

        hist_pod = POD(
            shipment_id=hist_shipment.id,
            file_url="/uploads/pods/sample_pod_consignment.png",
            file_name="delivery_receipt_signed.png",
            receiver_name="Manoj Karmakar (Store Incharge)",
            receiver_phone="+919832145521",
            receiver_signature_notes="Received 12 MT pipes intact without transit damage. Verified by gate staff.",
            submitted_by_driver_id=driver1.id,
            submitted_at=now - timedelta(days=2, hours=-2),
            verification_status=PODStatus.VERIFIED,
            verified_by_user_id=dealer1_user.id,
            verified_at=now - timedelta(days=2, hours=-1),
        )
        session.add(hist_pod)

        hist_rating = Rating(
            shipment_id=hist_shipment.id,
            rater_user_id=dealer1_user.id,
            rated_user_id=d1_user.id,
            score=5,
            tags=["On-Time Pickup", "Professional Driver", "Fast Delivery"],
            comment="Excellent execution on the Dankuni to Bardhaman route. Driver coordinated loading efficiently.",
            created_at=now - timedelta(days=2, hours=-1),
        )
        session.add(hist_rating)

        await session.commit()
        print("[SUCCESS] West Bengal multi-hub logistics seed data generated successfully!")

if __name__ == "__main__":
    asyncio.run(seed_database())
