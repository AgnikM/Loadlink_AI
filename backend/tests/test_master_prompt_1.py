import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    User, Truck, Driver, Load, Booking, FreightAgreement,
    AgreementAcceptance, BookingStateHistory, VehicleAssignment, Transporter
)
from app.models.enums import (
    UserRole, FleetOwnershipType, TruckStatus, TruckType,
    AgreementStatus, BookingStatus, LoadStatus
)
from app.services.match_engine import match_engine

@pytest.mark.asyncio
async def test_01_dealer_login_and_access():
    """1. Test Dealer login and access to dealer resources."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res = await ac.post("/auth/login", json={
            "email": "dealer.kolkata@bengalsteel.in",
            "password": "dealer123"
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["role"] == "DEALER"
        token = data["access_token"]

        # Authenticated /me endpoint
        me_res = await ac.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "dealer.kolkata@bengalsteel.in"
        assert me_res.json()["role"] == "DEALER"

@pytest.mark.asyncio
async def test_02_driver_login_and_access():
    """2. Test Driver login and access."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res = await ac.post("/auth/login", json={
            "email": "driver.rajesh@loadlink.ai",
            "password": "driver123"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "DRIVER"
        token = data["access_token"]

        me_res = await ac.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.json()["role"] == "DRIVER"

@pytest.mark.asyncio
async def test_03_transporter_login_and_access():
    """3. Test Transporter login and access."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res = await ac.post("/auth/login", json={
            "email": "transporter@bengalroadways.in",
            "password": "transporter123"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "TRANSPORTER"
        token = data["access_token"]

        me_res = await ac.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        user_info = me_res.json()
        assert user_info["role"] == "TRANSPORTER"
        assert user_info["organization_name"] is not None

@pytest.mark.asyncio
async def test_04_admin_access():
    """4. Test Admin login and access to operational dashboards."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res = await ac.post("/auth/login", json={
            "email": "admin@loadlink.ai",
            "password": "admin123"
        })
        assert res.status_code == 200
        token = res.json()["access_token"]

        # Access dashboard summary
        dash_res = await ac.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
        assert dash_res.status_code == 200
        summary = dash_res.json()
        assert "open_loads" in summary
        assert "available_trucks" in summary
        assert "bookings" in summary

@pytest.mark.asyncio
async def test_05_unauthorized_api_access():
    """5. Test Unauthorized API access (role protection & RBAC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # 5a. Unauthenticated access to protected endpoint
        no_auth = await ac.get("/auth/me")
        assert no_auth.status_code == 401

        # 5b. Driver attempting an admin/compliance action (safety hold)
        driver_login = await ac.post("/auth/login", json={
            "email": "driver.rajesh@loadlink.ai",
            "password": "driver123"
        })
        driver_token = driver_login.json()["access_token"]

        # Fetch a truck id
        trucks_res = await ac.get("/trucks")
        truck_id = trucks_res.json()[0]["id"]

        forbidden_res = await ac.patch(
            f"/trucks/{truck_id}/safety-hold",
            headers={"Authorization": f"Bearer {driver_token}"},
            params={"hold_reason": "Malicious attempt"}
        )
        assert forbidden_res.status_code == 403

@pytest.mark.asyncio
async def test_06_owned_fleet_registration():
    """6. Test Owned fleet registration (LOADLINK_OWNED)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        admin_login = await ac.post("/auth/login", json={
            "email": "admin@loadlink.ai",
            "password": "admin123"
        })
        admin_token = admin_login.json()["access_token"]

        res = await ac.post(
            "/trucks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "registration_no": "WB-01-LL-9999",
                "truck_type": "OPEN_BODY",
                "capacity_tons": 25.0,
                "current_lat": 22.5726,
                "current_lon": 88.3639,
                "current_location_name": "Kolkata Central Depot",
                "ownership_type": "LOADLINK_OWNED"
            }
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["registration_no"] == "WB-01-LL-9999"
        assert data["ownership_type"] == "LOADLINK_OWNED"

@pytest.mark.asyncio
async def test_07_external_fleet_registration():
    """7. Test External fleet registration (EXTERNAL_TRANSPORTER)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        admin_login = await ac.post("/auth/login", json={
            "email": "admin@loadlink.ai",
            "password": "admin123"
        })
        admin_token = admin_login.json()["access_token"]

        # Get transporter org
        async with AsyncSessionLocal() as session:
            transporter_prof = (await session.execute(select(Transporter))).scalars().first()
            assert transporter_prof is not None
            org_id = transporter_prof.organization_id

        res = await ac.post(
            "/trucks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "registration_no": "WB-02-EXT-8888",
                "truck_type": "FLATBED",
                "capacity_tons": 30.0,
                "current_lat": 23.5204,
                "current_lon": 87.3119,
                "current_location_name": "Durgapur Industrial Complex",
                "ownership_type": "EXTERNAL_TRANSPORTER",
                "organization_id": org_id
            }
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["ownership_type"] == "EXTERNAL_TRANSPORTER"
        assert data["organization_id"] == org_id

@pytest.mark.asyncio
async def test_08_driver_to_vehicle_assignment_and_conflict_prevention():
    """8. Test Driver-to-vehicle assignment and conflict prevention."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        admin_login = await ac.post("/auth/login", json={
            "email": "admin@loadlink.ai",
            "password": "admin123"
        })
        admin_token = admin_login.json()["access_token"]

        async with AsyncSessionLocal() as session:
            drivers = (await session.execute(select(Driver))).scalars().all()
            trucks = (await session.execute(select(Truck))).scalars().all()
            driver_a = drivers[0]
            truck_1 = trucks[0]
            truck_2 = trucks[1]

        # Assign driver_a to truck_1
        assign_res_1 = await ac.post(
            f"/trucks/{truck_1.id}/assign",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "driver_id": driver_a.id,
                "assignment_notes": "Assigned to Truck 1"
            }
        )
        assert assign_res_1.status_code == 200
        assert assign_res_1.json()["driver_id"] == driver_a.id

        # Now assign same driver_a to truck_2
        assign_res_2 = await ac.post(
            f"/trucks/{truck_2.id}/assign",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "driver_id": driver_a.id,
                "assignment_notes": "Reassigned to Truck 2"
            }
        )
        assert assign_res_2.status_code == 200
        assert assign_res_2.json()["driver_id"] == driver_a.id

        # Check assignment history on truck_1: prior assignment should now be deactivated
        history_res_1 = await ac.get(f"/trucks/{truck_1.id}/assignments", headers={"Authorization": f"Bearer {admin_token}"})
        assert history_res_1.status_code == 200
        assignments_1 = history_res_1.json()
        # Active assignment for driver_a on truck_1 should be False
        for a in assignments_1:
            if a["driver_id"] == driver_a.id:
                assert a["is_active"] is False

        # Truck 1's current driver_id should be cleared or updated
        async with AsyncSessionLocal() as session:
            t1_db = await session.get(Truck, truck_1.id)
            assert t1_db.driver_id != driver_a.id

@pytest.mark.asyncio
async def test_09_safety_held_and_maintenance_exclusion():
    """9. Test Safety-held (SAFETY_HOLD) & MAINTENANCE vehicle exclusion from matching."""
    async with AsyncSessionLocal() as session:
        loads = (await session.execute(select(Load))).scalars().all()
        test_load = loads[0]
        trucks = (await session.execute(select(Truck).options(selectinload(Truck.driver)))).scalars().all()
        test_truck = trucks[0]

        # 9a. Normal available truck evaluates with candidate score > 0
        test_truck.status = TruckStatus.ONLINE_AVAILABLE
        eval_avail = await match_engine.evaluate_candidate(test_truck, test_load)
        assert eval_avail is not None
        assert eval_avail["total_score"] > 0

        # 9b. MAINTENANCE vehicle must be strictly excluded
        test_truck.status = TruckStatus.MAINTENANCE
        eval_maint = await match_engine.evaluate_candidate(test_truck, test_load)
        assert eval_maint is None

        # 9c. SAFETY_HOLD vehicle must be strictly excluded
        test_truck.status = TruckStatus.SAFETY_HOLD
        eval_hold = await match_engine.evaluate_candidate(test_truck, test_load)
        assert eval_hold is None

        # Reset back to ONLINE_AVAILABLE
        test_truck.status = TruckStatus.ONLINE_AVAILABLE
        await session.commit()

@pytest.mark.asyncio
async def test_10_direct_agreement_creation_with_hash():
    """10. Test Direct agreement creation with SHA-256 content hash."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_login = await ac.post("/auth/login", json={
            "email": "dealer.kolkata@bengalsteel.in",
            "password": "dealer123"
        })
        dealer_token = dealer_login.json()["access_token"]

        async with AsyncSessionLocal() as session:
            load = (await session.execute(select(Load).filter_by(status=LoadStatus.POSTED))).scalars().first()
            truck = (await session.execute(select(Truck).filter_by(status=TruckStatus.ONLINE_AVAILABLE).options(selectinload(Truck.driver)))).scalars().first()
            assert load is not None
            assert truck is not None

        booking_res = await ac.post(
            "/bookings",
            headers={"Authorization": f"Bearer {dealer_token}"},
            json={
                "load_id": load.id,
                "truck_id": truck.id,
                "driver_id": truck.driver_id,
                "dealer_id": load.dealer_id,
                "offered_price": 18500.0,
                "pickup_notes": "Gate 4 pickup"
            }
        )
        assert booking_res.status_code == 200, booking_res.text
        booking_data = booking_res.json()
        assert booking_data["status"] in ["PENDING", "AGREEMENT_PENDING"]
        booking_id = booking_data["id"]

        # Inspect generated direct freight agreement
        agr_res = await ac.get(f"/bookings/{booking_id}/agreement", headers={"Authorization": f"Bearer {dealer_token}"})
        assert agr_res.status_code == 200, agr_res.text
        agreement = agr_res.json()
        assert agreement["version"] == 1
        assert agreement["status"] == "PENDING_ACCEPTANCE"
        assert agreement["is_accepted_by_dealer"] is True
        assert agreement["is_accepted_by_transporter"] is False
        assert agreement["is_mutually_accepted"] is False
        assert len(agreement["content_hash"]) == 64 # Canonical SHA-256 hex string

@pytest.mark.asyncio
async def test_11_agreement_acceptance_by_both_parties():
    """11. Test Agreement acceptance by both parties & mutual acceptance transition."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # 1. Create a booking
        dealer_login = await ac.post("/auth/login", json={
            "email": "dealer.kolkata@bengalsteel.in",
            "password": "dealer123"
        })
        dealer_token = dealer_login.json()["access_token"]

        async with AsyncSessionLocal() as session:
            load = (await session.execute(select(Load).filter_by(status=LoadStatus.POSTED))).scalars().first()
            truck = (await session.execute(select(Truck).filter_by(status=TruckStatus.ONLINE_AVAILABLE).options(selectinload(Truck.driver)))).scalars().first()

        booking_res = await ac.post(
            "/bookings",
            headers={"Authorization": f"Bearer {dealer_token}"},
            json={
                "load_id": load.id,
                "truck_id": truck.id,
                "driver_id": truck.driver_id,
                "dealer_id": load.dealer_id,
                "offered_price": 19000.0,
                "pickup_notes": "Handle with care"
            }
        )
        booking_id = booking_res.json()["id"]

        # Driver login
        async with AsyncSessionLocal() as session:
            driver_db = await session.get(Driver, truck.driver_id)
            driver_user = await session.get(User, driver_db.user_id)
            driver_email = driver_user.email

        driver_login = await ac.post("/auth/login", json={
            "email": driver_email,
            "password": "driver123"
        })
        driver_token = driver_login.json()["access_token"]

        # Driver accepts the agreement
        accept_res = await ac.post(
            f"/bookings/{booking_id}/agreement/accept",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={
                "ip_address": "127.0.0.1",
                "notes": "Accepted agreed freight terms"
            }
        )
        assert accept_res.status_code == 200, accept_res.text
        updated_agr = accept_res.json()
        assert updated_agr["status"] == "MUTUALLY_ACCEPTED"
        assert updated_agr["is_accepted_by_dealer"] is True
        assert updated_agr["is_accepted_by_transporter"] is True
        assert updated_agr["is_mutually_accepted"] is True

@pytest.mark.asyncio
async def test_12_agreement_version_increment_on_terms_change():
    """12. Test Agreement version increment on terms change with renewed acceptance requirement."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_login = await ac.post("/auth/login", json={
            "email": "dealer.kolkata@bengalsteel.in",
            "password": "dealer123"
        })
        dealer_token = dealer_login.json()["access_token"]

        async with AsyncSessionLocal() as session:
            load = (await session.execute(select(Load).filter_by(status=LoadStatus.POSTED))).scalars().first()
            truck = (await session.execute(select(Truck).filter_by(status=TruckStatus.ONLINE_AVAILABLE).options(selectinload(Truck.driver)))).scalars().first()

        booking_res = await ac.post(
            "/bookings",
            headers={"Authorization": f"Bearer {dealer_token}"},
            json={
                "load_id": load.id,
                "truck_id": truck.id,
                "driver_id": truck.driver_id,
                "dealer_id": load.dealer_id,
                "offered_price": 20000.0,
            }
        )
        booking_id = booking_res.json()["id"]

        # Amend agreement terms: change freight to 21500
        amend_res = await ac.patch(
            f"/bookings/{booking_id}/agreement",
            headers={"Authorization": f"Bearer {dealer_token}"},
            json={
                "agreed_freight": 21500.0,
                "amendment_reason": "Diesel price surcharge adjustments",
                "additional_charges": {"fuel_surcharge": 1500.0}
            }
        )
        assert amend_res.status_code == 200, amend_res.text
        new_agr = amend_res.json()
        assert new_agr["version"] == 2
        assert new_agr["status"] == "PENDING_ACCEPTANCE"
        assert new_agr["agreed_freight"] == 21500.0
        assert new_agr["is_accepted_by_dealer"] is True
        assert new_agr["is_accepted_by_transporter"] is False
        assert new_agr["is_mutually_accepted"] is False

@pytest.mark.asyncio
async def test_13_booking_state_transitions_and_pre_dispatch():
    """13. Test Booking state transitions, pre-dispatch check enforcement, and state history."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # Create a booking
        dealer_login = await ac.post("/auth/login", json={
            "email": "dealer.kolkata@bengalsteel.in",
            "password": "dealer123"
        })
        dealer_token = dealer_login.json()["access_token"]

        async with AsyncSessionLocal() as session:
            load = (await session.execute(select(Load).filter_by(status=LoadStatus.POSTED))).scalars().first()
            truck = (await session.execute(select(Truck).filter_by(status=TruckStatus.ONLINE_AVAILABLE).options(selectinload(Truck.driver)))).scalars().first()

        booking_res = await ac.post(
            "/bookings",
            headers={"Authorization": f"Bearer {dealer_token}"},
            json={
                "load_id": load.id,
                "truck_id": truck.id,
                "driver_id": truck.driver_id,
                "dealer_id": load.dealer_id,
                "offered_price": 22000.0,
            }
        )
        booking_id = booking_res.json()["id"]

        # If truck is placed into SAFETY_HOLD, responding with ACCEPT must fail pre-dispatch checks
        async with AsyncSessionLocal() as session:
            t_db = await session.get(Truck, truck.id)
            t_db.status = TruckStatus.SAFETY_HOLD
            await session.commit()

        # Driver responds ACCEPT
        driver_db_user = None
        async with AsyncSessionLocal() as session:
            d_db = await session.get(Driver, truck.driver_id)
            driver_db_user = await session.get(User, d_db.user_id)
        driver_login = await ac.post("/auth/login", json={
            "email": driver_db_user.email,
            "password": "driver123"
        })
        driver_token = driver_login.json()["access_token"]

        fail_accept = await ac.post(
            f"/bookings/{booking_id}/respond",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"action": "ACCEPT"}
        )
        # Should fail because truck is on SAFETY_HOLD
        assert fail_accept.status_code == 400
        assert "SAFETY_HOLD" in fail_accept.text

        # Restore truck to ONLINE_AVAILABLE
        async with AsyncSessionLocal() as session:
            t_db = await session.get(Truck, truck.id)
            t_db.status = TruckStatus.ONLINE_AVAILABLE
            await session.commit()

        # Now respond ACCEPT with mutual agreement accepted
        success_accept = await ac.post(
            f"/bookings/{booking_id}/respond",
            headers={"Authorization": f"Bearer {driver_token}"},
            json={"action": "ACCEPT"}
        )
        assert success_accept.status_code == 200, success_accept.text
        assert success_accept.json()["status"] == "ACCEPTED"

        # Check booking history
        hist_res = await ac.get(f"/bookings/{booking_id}/history", headers={"Authorization": f"Bearer {dealer_token}"})
        assert hist_res.status_code == 200
        hist_list = hist_res.json()
        assert len(hist_list) >= 2 # Initial creation + state transition to ACCEPTED
