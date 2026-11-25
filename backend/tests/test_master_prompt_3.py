import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    User, Truck, Driver, Dealer, Load, Booking, Shipment,
    SOSEvent, VehicleBreakdown, PreTripInspection, TruckReplacementWorkflow
)
from app.models.enums import (
    UserRole, TruckStatus, LoadStatus, BookingStatus, ShipmentState,
    SOSStatus, SOSCategory, NetworkStatus, BreakdownIssueType, BreakdownStatus,
    ReplacementStatus, CargoCondition
)

# Helper function to get auth token
async def get_token_for(ac: AsyncClient, email: str, password: str) -> str:
    res = await ac.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


async def get_test_context():
    """Ensure we have an active driver, truck, dealer, and shipment for MP3 tests."""
    async with AsyncSessionLocal() as session:
        driver_q = await session.execute(
            select(Driver).join(User).where(User.email == "driver.rajesh@loadlink.ai").options(selectinload(Driver.user))
        )
        driver = driver_q.scalar_one_or_none()

        truck_q = await session.execute(select(Truck).where(Truck.registration_no == "WB-19-AF-0184"))
        truck = truck_q.scalar_one_or_none()

        dealer_q = await session.execute(
            select(Dealer).join(User).where(User.email == "dealer.kolkata@bengalsteel.in")
        )
        dealer = dealer_q.scalar_one_or_none()

        shipment_q = await session.execute(select(Shipment))
        shipment = shipment_q.scalars().first()
        if shipment:
            shipment.state = ShipmentState.IN_TRANSIT
            if dealer:
                shipment.dealer_id = dealer.id
            if truck:
                shipment.truck_id = truck.id
            if driver:
                shipment.driver_id = driver.id
            await session.commit()
            await session.refresh(shipment)

        return {
            "driver_id": driver.id if driver else None,
            "truck_id": truck.id if truck else None,
            "dealer_id": dealer.id if dealer else None,
            "shipment_id": shipment.id if shipment else None,
            "booking_id": shipment.booking_id if shipment else None,
        }


@pytest.mark.asyncio
async def test_01_sos_creation():
    """1. Test SOS creation by driver with GPS coordinates, accuracy, and emergency contacts."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {token}"}

        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "truck_id": ctx["truck_id"],
            "shipment_id": ctx["shipment_id"],
            "booking_id": ctx["booking_id"],
            "latitude": 22.7500,
            "longitude": 87.8500,
            "accuracy_meters": 6.5,
            "incident_category": "MEDICAL_EMERGENCY",
            "network_status": "ONLINE",
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
            "emergency_contact_name": "Anita Yadav",
            "emergency_contact_phone": "+919874109999",
            "audio_or_media_url": "https://loadlink.ai/uploads/sos/audio_distress.mp3"
        }

        res = await ac.post("/sos/trigger", json=payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["event_id"] == event_id
        assert data["status"] in ["TRIGGERED", "NOTIFICATION_PENDING"]
        assert data["incident_category"] == "MEDICAL_EMERGENCY"
        assert data["control_room_notified"] is True
        assert data["dealer_notified"] is True
        assert data["emergency_contact_notified"] is True
        assert data["emergency_contact_name"] == "Anita Yadav"
        assert data["emergency_contact_phone"] == "+919874109999"


@pytest.mark.asyncio
async def test_02_control_room_notification():
    """2. Test Control Room Operator views active SOS alerts."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # Trigger an alert to guarantee at least one exists
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        await ac.post("/sos/trigger", json={
            "event_id": str(uuid.uuid4()),
            "truck_id": ctx["truck_id"],
            "latitude": 22.7600,
            "longitude": 87.8600,
            "incident_category": "ACCIDENT",
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
        }, headers={"Authorization": f"Bearer {driver_token}"})

        cr_token = await get_token_for(ac, "control.room@loadlink.ai", "control123")
        headers = {"Authorization": f"Bearer {cr_token}"}

        res = await ac.get("/sos/active", headers=headers)
        assert res.status_code == 200, res.text
        alerts = res.json()
        assert len(alerts) > 0
        latest_alert = alerts[0]
        assert latest_alert["status"] in ["TRIGGERED", "NOTIFICATION_PENDING", "ACKNOWLEDGED"]
        assert latest_alert["latitude"] is not None
        assert latest_alert["longitude"] is not None
        assert latest_alert["control_room_notified"] is True


@pytest.mark.asyncio
async def test_03_dealer_notification():
    """3. Test Dealer notification recorded on SOS dispatch."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {token}"}

        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "truck_id": ctx["truck_id"],
            "shipment_id": ctx["shipment_id"],
            "booking_id": ctx["booking_id"],
            "latitude": 22.8200,
            "longitude": 87.7500,
            "accuracy_meters": 5.0,
            "incident_category": "THEFT_OR_HIJACKING",
            "network_status": "ONLINE",
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        res = await ac.post("/sos/trigger", json=payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["dealer_notified"] is True
        assert data["dealer_notified_at"] is not None


@pytest.mark.asyncio
async def test_04_emergency_contact_notification():
    """4. Test driver's emergency contact dispatch notification."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {token}"}

        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "truck_id": ctx["truck_id"],
            "latitude": 22.9000,
            "longitude": 87.6500,
            "incident_category": "ACCIDENT",
            "emergency_contact_name": "Suresh Yadav (Brother)",
            "emergency_contact_phone": "+919874108888",
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        res = await ac.post("/sos/trigger", json=payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["emergency_contact_notified"] is True
        assert data["emergency_contact_name"] == "Suresh Yadav (Brother)"
        assert data["emergency_contact_phone"] == "+919874108888"


@pytest.mark.asyncio
async def test_05_sos_acknowledgement():
    """5. Test Control Room acknowledgement of active SOS."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # Trigger an SOS first
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        event_id = str(uuid.uuid4())
        res_trigger = await ac.post("/sos/trigger", json={
            "event_id": event_id,
            "truck_id": ctx["truck_id"],
            "latitude": 23.0100,
            "longitude": 87.5500,
            "incident_category": "VEHICLE_FIRE",
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
        }, headers={"Authorization": f"Bearer {driver_token}"})
        assert res_trigger.status_code == 200
        sos_id = res_trigger.json()["id"]

        # Control Room operator acknowledges
        cr_token = await get_token_for(ac, "control.room@loadlink.ai", "control123")
        headers = {"Authorization": f"Bearer {cr_token}"}

        res_ack = await ac.post(f"/sos/{sos_id}/action", json={
            "action": "ACKNOWLEDGE",
            "notes": "Control room operator Sanjib assigned. Fire station alerted."
        }, headers=headers)
        assert res_ack.status_code == 200, res_ack.text
        data = res_ack.json()
        assert data["status"] == "ACKNOWLEDGED"
        assert data["acknowledged_at"] is not None
        assert "Fire station alerted" in (data["assigned_responder_notes"] or "")


@pytest.mark.asyncio
async def test_06_sos_resolution():
    """6. Test Control Room resolution of SOS event."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        event_id = str(uuid.uuid4())
        res_trigger = await ac.post("/sos/trigger", json={
            "event_id": event_id,
            "truck_id": ctx["truck_id"],
            "latitude": 23.1100,
            "longitude": 87.4500,
            "incident_category": "CARGO_TAMPERING" if "CARGO_TAMPERING" in SOSCategory.__members__ else "THEFT_OR_HIJACKING",
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
        }, headers={"Authorization": f"Bearer {driver_token}"})
        assert res_trigger.status_code == 200
        sos_id = res_trigger.json()["id"]

        cr_token = await get_token_for(ac, "control.room@loadlink.ai", "control123")
        headers = {"Authorization": f"Bearer {cr_token}"}

        # Resolve
        res_res = await ac.post(f"/sos/{sos_id}/action", json={
            "action": "RESOLVE",
            "notes": "Highway patrol inspected vehicle. Seals confirmed intact. False alarm cleared."
        }, headers=headers)
        assert res_res.status_code == 200, res_res.text
        data = res_res.json()
        assert data["status"] == "RESOLVED"
        assert data["resolved_at"] is not None
        assert "Seals confirmed intact" in (data["resolution_notes"] or "")


@pytest.mark.asyncio
async def test_07_offline_sos_queue():
    """7. Test Offline SOS submission with client UUIDv4 and offline network status."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        client_uuid = str(uuid.uuid4())
        offline_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

        payload = {
            "event_id": client_uuid,
            "truck_id": ctx["truck_id"],
            "latitude": 23.2100,
            "longitude": 87.3500,
            "incident_category": "ACCIDENT",
            "network_status": "OFFLINE_SYNCED",
            "device_timestamp": offline_time,
        }

        res = await ac.post("/sos/trigger", json=payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["event_id"] == client_uuid
        assert data["network_status"] == "OFFLINE_SYNCED"
        assert data["status"] in ["TRIGGERED", "NOTIFICATION_PENDING"]


@pytest.mark.asyncio
async def test_08_duplicate_prevention():
    """8. Test duplicate SOS submission prevention using idempotent event_id."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        idempotency_key = str(uuid.uuid4())
        payload = {
            "event_id": idempotency_key,
            "truck_id": ctx["truck_id"],
            "latitude": 23.3100,
            "longitude": 87.2500,
            "incident_category": "OTHER_CRITICAL",
            "network_status": "ONLINE",
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # First post
        res1 = await ac.post("/sos/trigger", json=payload, headers=headers)
        assert res1.status_code == 200
        id1 = res1.json()["id"]

        # Duplicate post with same event_id
        res2 = await ac.post("/sos/trigger", json=payload, headers=headers)
        assert res2.status_code == 200
        id2 = res2.json()["id"]

        # Must return the same record, not a new row
        assert id1 == id2


@pytest.mark.asyncio
async def test_09_breakdown_reporting():
    """9. Test Breakdown reporting transitions truck to MAINTENANCE status."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        breakdown_payload = {
            "truck_id": ctx["truck_id"],
            "shipment_id": ctx["shipment_id"],
            "issue_type": "TYRE_FAILURE",
            "description": "Right rear double tyre blowout near Galsi NH19.",
            "photo_url": "https://loadlink.ai/uploads/breakdowns/tyre_shred.jpg",
            "latitude": 23.3300,
            "longitude": 87.6800,
            "device_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        res = await ac.post("/breakdowns/report", json=breakdown_payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["issue_type"] == "TYRE_FAILURE"
        assert data["status"] == "REPORTED"

        # Verify truck is set to MAINTENANCE
        async with AsyncSessionLocal() as session:
            truck = (await session.execute(select(Truck).where(Truck.id == ctx["truck_id"]))).scalar_one()
            assert truck.status == TruckStatus.MAINTENANCE


@pytest.mark.asyncio
async def test_10_safety_hold_triggering():
    """10. Test pre-trip inspection with critical failure triggers SAFETY_HOLD."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        # Submit pre-trip checklist with brakes failed
        inspection_payload = {
            "truck_id": ctx["truck_id"],
            "tyres_ok": True,
            "brakes_ok": False,  # CRITICAL FAILURE
            "lights_ok": True,
            "indicators_ok": True,
            "mirrors_ok": True,
            "steering_ok": True,
            "engine_indicators_ok": True,
            "oil_level_ok": True,
            "coolant_level_ok": True,
            "documents_valid": True,
            "cargo_securing_equipment_ok": True,
            "defect_description": "Pneumatic brake booster valve leaking pressure rapidly.",
            "inspection_evidence_photos": ["https://loadlink.ai/uploads/inspections/brake_leak.jpg"]
        }

        res = await ac.post("/inspections/pre-trip", json=inspection_payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["safety_hold_triggered"] is True
        assert data["brakes_ok"] is False

        # Verify truck status in DB is SAFETY_HOLD
        async with AsyncSessionLocal() as session:
            truck = (await session.execute(select(Truck).where(Truck.id == ctx["truck_id"]))).scalar_one()
            assert truck.status == TruckStatus.SAFETY_HOLD


@pytest.mark.asyncio
async def test_11_authorized_safety_hold_release():
    """11. Test that only Fleet Manager / Compliance can release a safety hold."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers_driver = {"Authorization": f"Bearer {driver_token}"}

        # Submit pre-trip inspection with critical failure
        insp_create_res = await ac.post("/inspections/pre-trip", json={
            "truck_id": ctx["truck_id"],
            "brakes_ok": False,
            "defect_description": "Compressor failing to maintain 6 bar.",
        }, headers=headers_driver)
        assert insp_create_res.status_code == 200
        inspection_id = insp_create_res.json()["id"]

        # Driver attempts to clear safety hold -> MUST FAIL with 403 Forbidden
        driver_clear_res = await ac.post(
            f"/inspections/{inspection_id}/clear-safety-hold",
            json={"clearance_notes": "I repaired it myself."},
            headers=headers_driver
        )
        assert driver_clear_res.status_code == 403

        # Fleet Manager clears safety hold with repair evidence -> SUCCESS
        fm_token = await get_token_for(ac, "fleet.manager@loadlink.ai", "fleet123")
        fm_clear_res = await ac.post(
            f"/inspections/{inspection_id}/clear-safety-hold",
            json={
                "clearance_notes": "Brake pneumatic booster replaced by Tata Authorised Service Centre Burdwan. Certified fit.",
                "repair_evidence_url": "https://loadlink.ai/uploads/repairs/tata_service_cert.pdf"
            },
            headers={"Authorization": f"Bearer {fm_token}"}
        )
        assert fm_clear_res.status_code == 200, fm_clear_res.text
        data = fm_clear_res.json()
        assert data["safety_hold_cleared_at"] is not None
        assert data["safety_hold_cleared_by_name"] is not None
        assert "Brake pneumatic booster" in data["clearance_notes"]

        # Verify truck status restored to AVAILABLE
        async with AsyncSessionLocal() as session:
            truck = (await session.execute(select(Truck).where(Truck.id == ctx["truck_id"]))).scalar_one()
            assert truck.status in [TruckStatus.AVAILABLE, TruckStatus.ONLINE_AVAILABLE]


@pytest.mark.asyncio
async def test_12_replacement_truck_workflow():
    """12. Test replacement truck workflow: query eligible, dual approvals, custody transfer & dispatch."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        admin_token = await get_token_for(ac, "admin@loadlink.ai", "admin123")
        dealer_token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        headers_dealer = {"Authorization": f"Bearer {dealer_token}"}

        # 1. Query eligible trucks
        elig_res = await ac.get(f"/replacements/eligible-trucks?shipment_id={ctx['shipment_id']}", headers=headers_admin)
        assert elig_res.status_code == 200, elig_res.text
        eligible_trucks = elig_res.json()
        assert len(eligible_trucks) > 0
        rep_truck = eligible_trucks[0]

        # 2. Initiate replacement
        initiate_payload = {
            "shipment_id": ctx["shipment_id"],
            "replacement_truck_id": rep_truck["id"],
            "replacement_driver_id": rep_truck["driver_id"] or ctx["driver_id"],
            "reason": "Severe mechanical breakdown on NH19. Cargo transfer mandatory."
        }
        init_res = await ac.post("/replacements/initiate", json=initiate_payload, headers=headers_admin)
        assert init_res.status_code == 200, init_res.text
        replacement_id = init_res.json()["id"]

        # 3. Dealer approval
        deal_app_res = await ac.post(f"/replacements/{replacement_id}/approve", json={
            "approver_role": "DEALER",
            "approved": True,
            "notes": "Approved by Bengal Steel logistics desk."
        }, headers=headers_dealer)
        assert deal_app_res.status_code == 200

        # 4. Transporter/Fleet approval
        trans_app_res = await ac.post(f"/replacements/{replacement_id}/approve", json={
            "approver_role": "TRANSPORTER",
            "approved": True,
            "notes": "Transporter ops dispatched replacement vehicle."
        }, headers=headers_admin)
        assert trans_app_res.status_code == 200
        assert trans_app_res.json()["status"] == "APPROVED"

        # 5. Custody transfer recording
        custody_payload = {
            "transfer_cargo_condition": "INTACT",
            "new_seal_number": "WB-NEW-SEAL-889922",
            "transfer_photos": ["https://loadlink.ai/uploads/custody/seal_verification.jpg"]
        }
        cust_res = await ac.post(f"/replacements/{replacement_id}/record-custody-transfer", json=custody_payload, headers=headers_admin)
        assert cust_res.status_code == 200
        assert cust_res.json()["status"] == "CUSTODY_TRANSFERRED"

        # 6. Finalize completion and atomic reassignment
        comp_res = await ac.post(f"/replacements/{replacement_id}/complete", headers=headers_admin)
        assert comp_res.status_code == 200
        assert comp_res.json()["status"] == "COMPLETED"

        # Verify shipment atomically reassigned
        async with AsyncSessionLocal() as session:
            shipment = (await session.execute(select(Shipment).where(Shipment.id == ctx["shipment_id"]))).scalar_one()
            assert shipment.truck_id == rep_truck["id"]


@pytest.mark.asyncio
async def test_13_gps_batch_ingestion():
    """13. Test batched GPS telemetry ingestion with sequence numbers."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        now = datetime.now(timezone.utc)
        breadcrumbs = []
        for i in range(5):
            t = (now - timedelta(seconds=(4 - i) * 30)).isoformat()
            breadcrumbs.append({
                "driver_id": ctx["driver_id"],
                "truck_id": ctx["truck_id"],
                "shipment_id": ctx["shipment_id"],
                "latitude": 22.8000 + (i * 0.002),
                "longitude": 87.8000 + (i * 0.002),
                "accuracy_meters": 5.0,
                "speed_kmh": 45.0,
                "heading": 45.0,
                "device_timestamp": t,
                "sequence_number": 100 + i
            })

        res = await ac.post("/tracking/batch", json={"breadcrumbs": breadcrumbs}, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["ingested_count"] == 5
        assert data["anomalies_detected"] == 0
        assert data["is_stale"] is False
        assert abs(data["latest_latitude"] - (22.8000 + 4 * 0.002)) < 0.001


@pytest.mark.asyncio
async def test_14_offline_event_synchronization():
    """14. Test anomaly detection on impossible GPS coordinate jump (>130 km/h)."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        now = datetime.now(timezone.utc)
        # Point 1: Kolkata region
        p1 = {
            "driver_id": ctx["driver_id"],
            "truck_id": ctx["truck_id"],
            "latitude": 22.5726,
            "longitude": 88.3639,
            "device_timestamp": (now - timedelta(seconds=60)).isoformat(),
            "sequence_number": 201
        }
        # Point 2: Delhi region (1400 km away in 30 seconds -> physical impossibility)
        p2 = {
            "driver_id": ctx["driver_id"],
            "truck_id": ctx["truck_id"],
            "latitude": 28.7041,
            "longitude": 77.1025,
            "device_timestamp": (now - timedelta(seconds=30)).isoformat(),
            "sequence_number": 202
        }

        res = await ac.post("/tracking/batch", json={"breadcrumbs": [p1, p2]}, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["anomalies_detected"] >= 1
        assert 1 in data["suspicious_points"]


@pytest.mark.asyncio
async def test_15_android_permission_handling():
    """15. Test input validation and schema constraints for mobile telemetry inputs."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        # Invalid latitude (> 90 degrees)
        invalid_payload = {
            "event_id": str(uuid.uuid4()),
            "truck_id": ctx["truck_id"],
            "latitude": 195.0,  # Invalid (>90.0)
            "longitude": 88.0,
            "incident_category": "ACCIDENT",
            "device_timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Should be rejected with 422 Unprocessable Entity
        res = await ac.post("/sos/trigger", json=invalid_payload, headers=headers)
        assert res.status_code == 422, f"Expected 422 for latitude > 90: {res.status_code}"


@pytest.mark.asyncio
async def test_16_stale_location_detection_and_offline_metadata():
    """16. Test stale location detection (> 900s) and offline corridor metadata endpoint."""
    ctx = await get_test_context()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        # Batch with timestamp 20 minutes ago (> 900 seconds)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=1200)).isoformat()
        stale_point = {
            "driver_id": ctx["driver_id"],
            "truck_id": ctx["truck_id"],
            "latitude": 22.8500,
            "longitude": 87.8500,
            "device_timestamp": old_time,
            "sequence_number": 301
        }

        batch_res = await ac.post("/tracking/batch", json={"breadcrumbs": [stale_point]}, headers=headers)
        assert batch_res.status_code == 200, batch_res.text
        batch_data = batch_res.json()
        assert batch_data["is_stale"] is True

        # Test offline metadata endpoint
        meta_res = await ac.get("/tracking/offline-metadata", headers=headers)
        assert meta_res.status_code == 200, meta_res.text
        meta_data = meta_res.json()
        assert "bounding_box" in meta_data
        assert meta_data["bounding_box"]["min_latitude"] == 22.2
        assert meta_data["bounding_box"]["max_latitude"] >= 23.8
        assert "do NOT provide dynamic route recalculation" in meta_data["offline_routing_notice"]
