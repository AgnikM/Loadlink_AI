import sys
import os
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from app.core.database import AsyncSessionLocal
from app.models.entities import Truck, Driver, Load, Booking, TruckLocation
from app.models.enums import VerificationStatus, TruckStatus, TruckType
from app.services.match_engine import match_engine
from scripts.import_fleet_dataset import import_fleet_dataset

@pytest.fixture(autouse=True)
def setup_fleet_dataset():
    """Import demo fleet dataset into the test database for testing."""
    import_fleet_dataset()

@pytest.mark.asyncio
async def test_demo_isolation_and_unverified_safety():
    """Verify that all demo trucks and drivers are strictly unverified and flagged is_demo=True."""
    async with AsyncSessionLocal() as db_session:
        q_trucks = select(Truck).where(Truck.is_demo == True)
        res_trucks = await db_session.execute(q_trucks)
        demo_trucks = res_trucks.scalars().all()
        assert len(demo_trucks) == 60, f"Expected 60 demo trucks, found {len(demo_trucks)}"

        for t in demo_trucks:
            assert t.verification_status != VerificationStatus.VERIFIED, (
                f"SECURITY BREACH: Demo truck {t.registration_no} was marked VERIFIED!"
            )
            assert t.id.startswith("DEMO-TRK-")
            assert t.registration_no.startswith("TEST-WB-")

        q_drivers = select(Driver).where(Driver.is_demo == True)
        res_drivers = await db_session.execute(q_drivers)
        demo_drivers = res_drivers.scalars().all()
        assert len(demo_drivers) == 60, f"Expected 60 demo drivers, found {len(demo_drivers)}"

        for d in demo_drivers:
            assert d.verification_status != VerificationStatus.VERIFIED, (
                f"SECURITY BREACH: Demo driver {d.id} was marked VERIFIED!"
            )

@pytest.mark.asyncio
async def test_simulated_locations_isolation():
    """Verify simulated GPS events are never tied to live shipments and clearly identified."""
    async with AsyncSessionLocal() as db_session:
        q_locs = select(TruckLocation).where(TruckLocation.is_demo == True)
        res = await db_session.execute(q_locs)
        demo_locs = res.scalars().all()
        assert len(demo_locs) == 150, f"Expected 150 simulated location events, got {len(demo_locs)}"

        for loc in demo_locs:
            assert loc.source == "SYNTHETIC_SIMULATED_GPS"
            assert loc.shipment_id is None, f"Demo location {loc.id} attached to shipment {loc.shipment_id}"

@pytest.mark.asyncio
async def test_production_load_rejects_demo_trucks():
    """Verify that the matching engine strictly forbids demo trucks from matching real production loads."""
    async with AsyncSessionLocal() as db_session:
        # Fetch a real production load (is_demo == False)
        q_prod_load = select(Load).where((Load.is_demo == False) | (Load.is_demo.is_(None))).order_by(Load.created_at.desc())
        res_load = await db_session.execute(q_prod_load)
        prod_load = res_load.scalars().first()
        assert prod_load is not None, "No production load found in database for test"

        # Fetch a demo truck (is_demo == True)
        q_demo_truck = select(Truck).where(Truck.is_demo == True).options(selectinload(Truck.driver))
        res_truck = await db_session.execute(q_demo_truck)
        demo_truck = res_truck.scalars().first()
        assert demo_truck is not None, "No demo truck found in database for test"

        rejections = []
        eval_result = await match_engine.evaluate_candidate(
            truck=demo_truck,
            load=prod_load,
            rejection_collector=rejections
        )

        # Must be completely rejected
        assert eval_result is None, "SECURITY FAILURE: Demo truck matched with production load!"
        assert any("Demo vehicle cannot be dispatched on production load" in r for r in rejections), (
            f"Expected demo vehicle rejection reason, got: {rejections}"
        )

@pytest.mark.asyncio
async def test_demo_load_to_demo_truck_matching():
    """Verify that eligible demo trucks can match with demo loads while respecting vehicle constraints."""
    async with AsyncSessionLocal() as db_session:
        # Fetch a demo load with small required weight
        q_demo_load = select(Load).where(Load.is_demo == True, Load.cargo_weight_tons <= 10.0).order_by(Load.id.asc())
        res_load = await db_session.execute(q_demo_load)
        demo_load = res_load.scalars().first()
        assert demo_load is not None, "No demo load found for test"

        # Find a compatible demo truck with matching type, capacity, and available status
        q_truck = (
            select(Truck)
            .where(
                Truck.is_demo == True,
                Truck.truck_type == demo_load.required_truck_type,
                Truck.capacity_tons >= demo_load.cargo_weight_tons,
                Truck.capacity_tons <= demo_load.max_capacity_tons,
                Truck.status == TruckStatus.ONLINE_AVAILABLE,
            )
            .options(selectinload(Truck.driver))
        )
        res_truck = await db_session.execute(q_truck)
        compatible_truck = res_truck.scalars().first()

        if compatible_truck:
            eval_result = await match_engine.evaluate_candidate(
                truck=compatible_truck,
                load=demo_load
            )
            assert eval_result is not None, "Eligible demo truck failed to match demo load"
            assert eval_result["is_demo"] is True
            assert eval_result["total_score"] > 0
            assert "synthetic demo score (unverified)" in eval_result["explanation_summary"], (
                f"Expected synthetic demo attribution in explanation: {eval_result['explanation_summary']}"
            )

@pytest.mark.asyncio
async def test_demo_truck_capacity_filtering():
    """Verify that capacity filters still strictly apply to demo trucks on demo loads."""
    async with AsyncSessionLocal() as db_session:
        # Find a small capacity demo truck (e.g. 9T)
        q_small_truck = select(Truck).where(Truck.is_demo == True, Truck.capacity_tons <= 10.0).options(selectinload(Truck.driver))
        small_truck = (await db_session.execute(q_small_truck)).scalars().first()
        assert small_truck is not None

        # Find a heavy demo load (e.g. 28T)
        q_heavy_load = select(Load).where(Load.is_demo == True, Load.cargo_weight_tons >= 24.0)
        heavy_load = (await db_session.execute(q_heavy_load)).scalars().first()
        assert heavy_load is not None

        rejections = []
        res = await match_engine.evaluate_candidate(
            truck=small_truck,
            load=heavy_load,
            rejection_collector=rejections
        )
        assert res is None, "Small truck should NOT match heavy load"
        assert any("is below cargo" in r for r in rejections), f"Expected capacity rejection reason: {rejections}"
