import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from app.models.entities import Truck, Load, Driver, User
from app.models.enums import TruckType, TruckStatus, VerificationStatus, UserRole, ShipmentState
from app.services.match_engine import match_engine
from app.services.pricing_service import pricing_service
from app.services.state_machine import ShipmentStateMachine

@pytest.mark.asyncio
async def test_deterministic_match_engine_ranking():
    driver_user = User(id="u1", name="Test Driver", phone="123", email="d@d.com", password_hash="x", role=UserRole.DRIVER)
    driver = Driver(id="d1", user_id="u1", license_number="WB123", verification_status=VerificationStatus.VERIFIED, reliability_score=96.0)
    driver.user = driver_user

    # Eligible Truck (16T, close to Kolkata)
    truck_a = Truck(
        id="t1",
        driver_id="d1",
        registration_no="WB-19-0184",
        truck_type=TruckType.OPEN_BODY,
        capacity_tons=16.0,
        status=TruckStatus.ONLINE_AVAILABLE,
        verification_status=VerificationStatus.VERIFIED,
        current_lat=22.6842, # Dankuni
        current_lon=88.2934,
    )
    truck_a.driver = driver

    # Overcapacity Truck (40T trailer)
    truck_b = Truck(
        id="t2",
        driver_id="d1",
        registration_no="WB-41-9999",
        truck_type=TruckType.TRAILER,
        capacity_tons=40.0,
        status=TruckStatus.ONLINE_AVAILABLE,
        verification_status=VerificationStatus.VERIFIED,
        current_lat=22.5448,
        current_lon=88.3186,
    )
    truck_b.driver = driver

    # Offline Truck
    truck_offline = Truck(
        id="t3",
        driver_id="d1",
        registration_no="WB-19-OFFLINE",
        truck_type=TruckType.OPEN_BODY,
        capacity_tons=16.0,
        status=TruckStatus.OFFLINE,
        verification_status=VerificationStatus.VERIFIED,
        current_lat=22.6842,
        current_lon=88.2934,
    )
    truck_offline.driver = driver

    now = datetime.now(timezone.utc)
    load = Load(
        id="l1",
        dealer_id="deal1",
        origin_name="Kolkata Port",
        origin_lat=22.5448,
        origin_lon=88.3186,
        destination_name="Durgapur",
        destination_lat=23.5204,
        destination_lon=87.3119,
        cargo_weight_tons=15.0,
        required_truck_type=TruckType.OPEN_BODY,
        min_capacity_tons=10.0,
        max_capacity_tons=18.0,
        pickup_window_start=now + timedelta(hours=2),
        pickup_window_end=now + timedelta(hours=6),
        target_budget=19000.0,
    )

    # Evaluate Truck A
    res_a = await match_engine.evaluate_candidate(truck_a, load)
    assert res_a is not None
    assert res_a["total_score"] >= 75.0
    assert "explanation_summary" in res_a
    assert "16.0T capacity" in res_a["explanation_summary"]

    # Evaluate Overcapacity Truck B (should be excluded by hard filter max_capacity_tons=18)
    res_b = await match_engine.evaluate_candidate(truck_b, load)
    assert res_b is None

    # Evaluate Offline Truck (should be excluded)
    res_off = await match_engine.evaluate_candidate(truck_offline, load)
    assert res_off is None

def test_pricing_service_heuristics():
    est = pricing_service.estimate_freight(
        distance_km=180.0,
        weight_tons=15.0,
        truck_type=TruckType.OPEN_BODY,
        target_budget=19000.0,
    )
    assert est["is_estimate"] is True
    assert est["estimated_median_inr"] > 10000.0
    assert est["estimated_range_min_inr"] <= est["estimated_median_inr"] <= est["estimated_range_max_inr"]
    assert est["is_budget_competitive"] is True

def test_state_machine_transitions():
    allowed_from_confirmed = ShipmentStateMachine.ALLOWED_TRANSITIONS[ShipmentState.CONFIRMED]
    assert ShipmentState.DRIVER_EN_ROUTE in allowed_from_confirmed
    assert ShipmentState.CANCELLED in allowed_from_confirmed
    assert ShipmentState.DELIVERED not in allowed_from_confirmed
