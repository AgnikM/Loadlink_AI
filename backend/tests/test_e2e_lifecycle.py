import pytest
import httpx

@pytest.mark.asyncio
async def test_full_marketplace_e2e_lifecycle():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000/api/v1", timeout=10.0) as client:
        # 1. Dealer Login
        r = await client.post("/auth/login", json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create Fresh Test Load
        now = "2026-09-07T10:00:00Z"
        later = "2026-09-07T18:00:00Z"
        load_payload = {
            "origin_name": "Kolkata Port Docks",
            "origin_lat": 22.5448,
            "origin_lon": 88.3186,
            "destination_name": "Durgapur Steel Complex",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "Industrial Steel Bars",
            "cargo_weight_tons": 15.0,
            "required_truck_type": "OPEN_BODY",
            "min_capacity_tons": 10.0,
            "max_capacity_tons": 18.0,
            "pickup_window_start": now,
            "pickup_window_end": later,
            "target_budget": 19000.0,
            "cargo_notes": "Urgent industrial order"
        }
        r_load = await client.post("/loads", headers=headers, json=load_payload)
        assert r_load.status_code == 200, f"Load creation failed: {r_load.text}"
        load_id = r_load.json()["id"]
        print(f"\n[PASS] Dealer authenticated and created fresh test load: {load_id}")

        # 3. Generate Matches
        r = await client.post(f"/loads/{load_id}/matches", headers=headers)
        assert r.status_code == 200
        matches = r.json()
        assert len(matches) > 0
        top_match = matches[0]
        reg = top_match["truck_registration_no"]
        score = top_match["total_score"]
        print(f"[PASS] Match Engine generated {len(matches)} ranked candidates. Top match: {reg} with Score {score}/100")
        print(f"       Explanation: {top_match['explanation_summary']}")

        # 4. Create Booking
        r = await client.post("/bookings", headers=headers, json={
            "load_id": load_id,
            "truck_id": top_match["truck_id"],
            "offered_price": 19000.0
        })
        assert r.status_code == 200
        booking = r.json()
        booking_id = booking["id"]
        print(f"[PASS] Booking requested successfully. Booking ID: {booking_id}")

        # 5. Driver Login & Accept Booking
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
        drv_token = r_drv.json()["access_token"]
        drv_headers = {"Authorization": f"Bearer {drv_token}"}


        r_accept = await client.patch(f"/bookings/{booking_id}", headers=drv_headers, json={"action": "ACCEPT"})
        assert r_accept.status_code == 200, f"Accept failed: {r_accept.text}"
        accepted_data = r_accept.json()
        shipment_id = accepted_data["shipment_id"]
        print(f"[PASS] Driver accepted booking. Shipment instantiated: {shipment_id}")

        # 6. State Machine Transitions (CONFIRMED -> DRIVER_EN_ROUTE -> ARRIVED_PICKUP -> LOADING -> LOADED -> IN_TRANSIT -> NEAR_DESTINATION)
        states = ["DRIVER_EN_ROUTE", "ARRIVED_PICKUP", "LOADING", "LOADED", "IN_TRANSIT", "NEAR_DESTINATION"]
        for st in states:
            r_st = await client.patch(f"/shipments/{shipment_id}/status", headers=drv_headers, json={"target_state": st})
            assert r_st.status_code == 200, f"Failed transition to {st}: {r_st.text}"
            print(f"[PASS] Shipment transitioned to {st}")

        # 7. Return Load Discovery at NEAR_DESTINATION
        r_ret = await client.get(f"/shipments/{shipment_id}/return-loads", headers=drv_headers)
        assert r_ret.status_code == 200
        ret_opps = r_ret.json()
        print(f"[PASS] Automated Return Load Discovery found {len(ret_opps)} backhaul opportunities near delivery destination.")

        # 8. Mark DELIVERED
        r_deliv = await client.patch(f"/shipments/{shipment_id}/status", headers=drv_headers, json={"target_state": "DELIVERED"})
        assert r_deliv.status_code == 200
        print("[PASS] Shipment marked DELIVERED.")

        # 9. Admin Metrics
        r_adm = await client.post("/auth/login", json={"email": "admin@loadlink.ai", "password": "admin123"})
        adm_headers = {"Authorization": f"Bearer {r_adm.json()['access_token']}"}
        r_kpi = await client.get("/admin/metrics", headers=adm_headers)
        assert r_kpi.status_code == 200
        kpis = r_kpi.json()
        print(f"[PASS] Admin KPI Metrics verified. Active shipments: {kpis['total_active_shipments']}")
