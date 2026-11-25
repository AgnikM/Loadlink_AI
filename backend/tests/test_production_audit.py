import pytest
import httpx
from datetime import datetime, timezone, timedelta

BASE_URL = "http://127.0.0.1:8000/api/v1"

@pytest.mark.asyncio
async def test_invalid_cargo_tonnage_rejection():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        r_auth = await client.post("/auth/login", json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"})
        headers = {"Authorization": f"Bearer {r_auth.json()['access_token']}"}

        # Negative tonnage
        payload = {
            "origin_name": "Kolkata Port",
            "origin_lat": 22.5448,
            "origin_lon": 88.3186,
            "destination_name": "Durgapur",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "Steel",
            "cargo_weight_tons": -5.0,
            "min_capacity_tons": 10.0,
            "max_capacity_tons": 18.0,
            "pickup_window_start": "2026-09-08T10:00:00Z",
            "pickup_window_end": "2026-09-08T18:00:00Z",
        }
        r = await client.post("/loads", headers=headers, json=payload)
        assert r.status_code == 422 or r.status_code == 400

        # Excessive tonnage (> 55T)
        payload["cargo_weight_tons"] = 80.0
        r2 = await client.post("/loads", headers=headers, json=payload)
        assert r2.status_code == 422 or r2.status_code == 400

@pytest.mark.asyncio
async def test_unauthorized_dealer_access_isolation():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Dealer 1 creates a load
        r_d1 = await client.post("/auth/login", json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"})
        h_d1 = {"Authorization": f"Bearer {r_d1.json()['access_token']}"}

        r_load = await client.post("/loads", headers=h_d1, json={
            "origin_name": "Kolkata Port Docks",
            "origin_lat": 22.5448,
            "origin_lon": 88.3186,
            "destination_name": "Durgapur Steel Complex",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "Private Steel Consignment",
            "cargo_weight_tons": 12.0,
            "min_capacity_tons": 10.0,
            "max_capacity_tons": 16.0,
            "pickup_window_start": "2026-09-09T10:00:00Z",
            "pickup_window_end": "2026-09-09T18:00:00Z",
            "target_budget": 16000.0,
        })
        assert r_load.status_code == 200
        load_id = r_load.json()["id"]

        # Dealer 2 logs in and attempts to access Dealer 1's private load
        r_d2 = await client.post("/auth/login", json={"email": "dealer.durgapur@durgapuralloys.com", "password": "dealer123"})
        h_d2 = {"Authorization": f"Bearer {r_d2.json()['access_token']}"}

        r_access = await client.get(f"/loads/{load_id}", headers=h_d2)
        assert r_access.status_code == 403, "Dealer 2 must be blocked from inspecting Dealer 1's private load"

        # Dealer 2 attempts to trigger match generation for Dealer 1's load
        r_match = await client.post(f"/loads/{load_id}/matches", headers=h_d2)
        assert r_match.status_code == 403, "Dealer 2 must be blocked from generating matches for Dealer 1's load"

@pytest.mark.asyncio
async def test_unauthorized_driver_booking_acceptance_blocked():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Dealer creates load & sends booking request to Driver 2 (Amit Das WB-39-B-0521)
        r_d1 = await client.post("/auth/login", json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"})
        h_d1 = {"Authorization": f"Bearer {r_d1.json()['access_token']}"}

        r_load = await client.post("/loads", headers=h_d1, json={
            "origin_name": "Kolkata Port",
            "origin_lat": 22.5448,
            "origin_lon": 88.3186,
            "destination_name": "Durgapur",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "TMT Bars",
            "cargo_weight_tons": 14.0,
            "min_capacity_tons": 10.0,
            "max_capacity_tons": 18.0,
            "pickup_window_start": "2026-09-09T10:00:00Z",
            "pickup_window_end": "2026-09-09T18:00:00Z",
            "target_budget": 18500.0,
        })
        load_id = r_load.json()["id"]

        matches = (await client.post(f"/loads/{load_id}/matches", headers=h_d1)).json()
        target_truck = matches[0]

        r_book = await client.post("/bookings", headers=h_d1, json={
            "load_id": load_id,
            "truck_id": target_truck["truck_id"],
            "offered_price": 18500.0,
        })
        booking_id = r_book.json()["id"]

        # Driver 1 and Driver 2 credentials
        r_drv1 = await client.post("/auth/login", json={"email": "driver.rajesh@loadlink.ai", "password": "driver123"})
        r_drv2 = await client.post("/auth/login", json={"email": "driver.amit@loadlink.ai", "password": "driver123"})
        h_drv1 = {"Authorization": f"Bearer {r_drv1.json()['access_token']}"}
        h_drv2 = {"Authorization": f"Bearer {r_drv2.json()['access_token']}"}

        me_drv1 = (await client.get("/auth/me", headers=h_drv1)).json()
        unauthorized_headers = h_drv2 if target_truck["driver_id"] == me_drv1["driver_id"] else h_drv1

        r_illegal_accept = await client.patch(f"/bookings/{booking_id}", headers=unauthorized_headers, json={"action": "ACCEPT"})
        assert r_illegal_accept.status_code == 403, "Unauthorized driver must be blocked from accepting another driver's booking"

@pytest.mark.asyncio
async def test_illegal_state_machine_transition_rejection():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Dealer creates load, books, and assigned driver accepts
        r_d1 = await client.post("/auth/login", json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"})
        h_d1 = {"Authorization": f"Bearer {r_d1.json()['access_token']}"}

        r_load = await client.post("/loads", headers=h_d1, json={
            "origin_name": "Kolkata Port",
            "origin_lat": 22.5448,
            "origin_lon": 88.3186,
            "destination_name": "Durgapur",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "State Machine Test Cargo",
            "cargo_weight_tons": 14.0,
            "min_capacity_tons": 10.0,
            "max_capacity_tons": 18.0,
            "pickup_window_start": "2026-09-09T10:00:00Z",
            "pickup_window_end": "2026-09-09T18:00:00Z",
            "target_budget": 18500.0,
        })
        load_id = r_load.json()["id"]
        matches = (await client.post(f"/loads/{load_id}/matches", headers=h_d1)).json()
        target_truck = matches[0]

        r_book = await client.post("/bookings", headers=h_d1, json={
            "load_id": load_id,
            "truck_id": target_truck["truck_id"],
            "offered_price": 18500.0,
        })
        booking_id = r_book.json()["id"]

        # Driver accepts - accurately map registration to email
        reg = target_truck["truck_registration_no"]
        if "0521" in reg:
            driver_email = "driver.amit@loadlink.ai"
        elif "0184" in reg:
            driver_email = "driver.rajesh@loadlink.ai"
        elif "0728" in reg:
            driver_email = "driver.gurmeet@loadlink.ai"
        elif "0310" in reg:
            driver_email = "driver.sunil@loadlink.ai"
        else:
            driver_email = "driver.rajesh@loadlink.ai"

        r_drv = await client.post("/auth/login", json={"email": driver_email, "password": "driver123"})
        h_drv = {"Authorization": f"Bearer {r_drv.json()['access_token']}"}

        r_accept = await client.patch(f"/bookings/{booking_id}", headers=h_drv, json={"action": "ACCEPT"})
        assert r_accept.status_code == 200, f"Assigned driver acceptance failed: {r_accept.text}"
        shipment_id = r_accept.json()["shipment_id"]

        # Attempt illegal jump: from CONFIRMED directly to DELIVERED (must fail with 400)
        r_illegal = await client.patch(f"/shipments/{shipment_id}/status", headers=h_drv, json={"target_state": "DELIVERED"})
        assert r_illegal.status_code == 400, "Illegal skip from CONFIRMED directly to DELIVERED must be rejected"

        # Attempt illegal jump: from CONFIRMED directly to COMPLETED (must fail with 400)
        r_illegal2 = await client.patch(f"/shipments/{shipment_id}/status", headers=h_drv, json={"target_state": "COMPLETED"})
        assert r_illegal2.status_code == 400

@pytest.mark.asyncio
async def test_invalid_gps_coordinates_rejection():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        r_drv = await client.post("/auth/login", json={"email": "driver.rajesh@loadlink.ai", "password": "driver123"})
        h_drv = {"Authorization": f"Bearer {r_drv.json()['access_token']}"}
        r_me = await client.get("/auth/me", headers=h_drv)
        truck_id = r_me.json()["truck_id"]

        # Bogus latitude > 90
        r_bad_lat = await client.post(f"/trucks/{truck_id}/locations", headers=h_drv, json={"latitude": 125.0, "longitude": 88.0})
        assert r_bad_lat.status_code == 400

        # Bogus longitude < -180
        r_bad_lon = await client.post(f"/trucks/{truck_id}/locations", headers=h_drv, json={"latitude": 22.0, "longitude": -200.0})
        assert r_bad_lon.status_code == 400

@pytest.mark.asyncio
async def test_duplicate_rating_prevention():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Complete a shipment lifecycle
        r_d1 = await client.post("/auth/login", json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"})
        h_d1 = {"Authorization": f"Bearer {r_d1.json()['access_token']}"}

        r_load = await client.post("/loads", headers=h_d1, json={
            "origin_name": "Kolkata Port",
            "origin_lat": 22.5448,
            "origin_lon": 88.3186,
            "destination_name": "Durgapur",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "Rating Test Cargo",
            "cargo_weight_tons": 14.0,
            "min_capacity_tons": 10.0,
            "max_capacity_tons": 18.0,
            "pickup_window_start": "2026-09-09T10:00:00Z",
            "pickup_window_end": "2026-09-09T18:00:00Z",
            "target_budget": 18500.0,
        })
        load_id = r_load.json()["id"]
        matches = (await client.post(f"/loads/{load_id}/matches", headers=h_d1)).json()
        target_truck = matches[0]

        r_book = await client.post("/bookings", headers=h_d1, json={
            "load_id": load_id,
            "truck_id": target_truck["truck_id"],
            "offered_price": 18500.0,
        })
        booking_id = r_book.json()["id"]

        reg = target_truck["truck_registration_no"]
        if "0521" in reg:
            driver_email = "driver.amit@loadlink.ai"
        elif "0184" in reg:
            driver_email = "driver.rajesh@loadlink.ai"
        elif "0728" in reg:
            driver_email = "driver.gurmeet@loadlink.ai"
        elif "0310" in reg:
            driver_email = "driver.sunil@loadlink.ai"
        else:
            driver_email = "driver.rajesh@loadlink.ai"

        r_drv = await client.post("/auth/login", json={"email": driver_email, "password": "driver123"})
        h_drv = {"Authorization": f"Bearer {r_drv.json()['access_token']}"}

        r_accept = await client.patch(f"/bookings/{booking_id}", headers=h_drv, json={"action": "ACCEPT"})
        assert r_accept.status_code == 200, f"Assigned driver acceptance failed: {r_accept.text}"
        shipment_id = r_accept.json()["shipment_id"]


        # Progress to DELIVERED
        states = ["DRIVER_EN_ROUTE", "ARRIVED_PICKUP", "LOADING", "LOADED", "IN_TRANSIT", "NEAR_DESTINATION", "DELIVERED"]
        for st in states:
            await client.patch(f"/shipments/{shipment_id}/status", headers=h_drv, json={"target_state": st})

        # Submit first rating (must succeed)
        r_rate1 = await client.post("/ratings", headers=h_d1, json={"shipment_id": shipment_id, "score": 5, "comment": "Excellent"})
        assert r_rate1.status_code == 200

        # Submit duplicate rating on the same shipment (must fail with 400)
        r_rate2 = await client.post("/ratings", headers=h_d1, json={"shipment_id": shipment_id, "score": 4, "comment": "Duplicate"})
        assert r_rate2.status_code == 400, "Duplicate rating submission must be rejected"

@pytest.mark.asyncio
async def test_no_match_scenario_for_impossible_capacity():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        r_d1 = await client.post("/auth/login", json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"})
        h_d1 = {"Authorization": f"Bearer {r_d1.json()['access_token']}"}

        # Create impossible load requiring 48T (when active fleet max capacity is 25T)
        r_load = await client.post("/loads", headers=h_d1, json={
            "origin_name": "Kolkata Port",
            "origin_lat": 22.5448,
            "origin_lon": 88.3186,
            "destination_name": "Durgapur",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "Super Heavy Transformer",
            "cargo_weight_tons": 48.0,
            "min_capacity_tons": 45.0,
            "max_capacity_tons": 55.0,
            "pickup_window_start": "2026-09-09T10:00:00Z",
            "pickup_window_end": "2026-09-09T18:00:00Z",
            "target_budget": 50000.0,
        })
        load_id = r_load.json()["id"]

        matches = (await client.post(f"/loads/{load_id}/matches", headers=h_d1)).json()
        assert len(matches) == 0, "No matches should be returned when no available fleet vehicle satisfies 48T capacity"

@pytest.mark.asyncio
async def test_match_factor_weights_normalization_and_validation():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        r_adm = await client.post("/auth/login", json={"email": "admin@loadlink.ai", "password": "admin123"})
        h_adm = {"Authorization": f"Bearer {r_adm.json()['access_token']}"}

        # Update weights with valid values summing to 1.0
        valid_weights = {
            "route_compatibility": 0.30,
            "availability_feasibility": 0.20,
            "pickup_proximity": 0.10,
            "capacity_fit": 0.10,
            "price_competitiveness": 0.10,
            "reliability": 0.10,
            "return_load_potential": 0.10,
        }
        r_update = await client.post("/admin/config/weights", headers=h_adm, json=valid_weights)
        assert r_update.status_code == 200

        # Attempt invalid key (must fail with 400)
        invalid_key_weights = {**valid_weights, "invalid_random_factor": 0.10}
        r_bad = await client.post("/admin/config/weights", headers=h_adm, json=invalid_key_weights)
        assert r_bad.status_code == 400
