import os
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.main import app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    User, Truck, Driver, Dealer, Load, Booking, Shipment, POD,
    CargoInsurance, DirectPayment, VehicleAssignment
)
from app.models.enums import (
    UserRole, TruckStatus, LoadStatus, BookingStatus, ShipmentState,
    PODStatus, CargoCategory, FragilityLevel, HazardClass
)

async def get_token_for(ac: AsyncClient, email: str, password: str) -> str:
    res = await ac.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_01_sqlite_foreign_key_enforcement():
    """TASK 3: Verify PRAGMA foreign_keys = ON is active and rejects orphaned foreign keys."""
    async with AsyncSessionLocal() as session:
        # Check pragma
        res = await session.execute(text("PRAGMA foreign_keys;"))
        fk_status = res.scalar()
        assert fk_status == 1, f"Expected PRAGMA foreign_keys=1, got {fk_status}"

        # Attempt to insert orphan POD referencing non-existent shipment
        orphan_pod = POD(
            id=str(uuid.uuid4()),
            shipment_id="non-existent-shipment-id-12345",
            file_url="/uploads/pods/orphan_pod.pdf",
            file_name="orphan_pod.pdf",
            receiver_name="Orphan Receiver",
            verification_status=PODStatus.PENDING_REVIEW,
        )
        session.add(orphan_pod)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_02_mime_validation_executable_rejected():
    """TASK 4: Verify uploading Windows PE / EXE file disguised as .pdf is rejected with 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {token}"}

        # Find shipment assigned to driver Rajesh
        async with AsyncSessionLocal() as session:
            q_u = select(User).where(User.email == "driver.rajesh@loadlink.ai").options(selectinload(User.driver_profile))
            rajesh_user = (await session.execute(q_u)).scalar_one()

            q = select(Shipment)
            ship = (await session.execute(q)).scalars().first()
            assert ship is not None
            ship.driver_id = rajesh_user.driver_profile.id
            await session.commit()
            shipment_id = ship.id

        # Fake executable file content: starts with MZ
        fake_exe_content = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00malicious_payload"
        files = {
            "file": ("malicious.pdf", fake_exe_content, "application/pdf")
        }
        data = {
            "receiver_name": "Test Receiver",
            "receiver_phone": "9876543210",
        }
        res = await ac.post(f"/shipments/{shipment_id}/pod", data=data, files=files, headers=headers)
        assert res.status_code == 400
        assert "Executable files are strictly prohibited" in res.json()["detail"]


@pytest.mark.asyncio
async def test_03_mime_validation_spoofed_pdf_rejected():
    """TASK 4: Verify text/script disguised with .pdf extension is rejected for invalid signature."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncSessionLocal() as session:
            q_u = select(User).where(User.email == "driver.rajesh@loadlink.ai").options(selectinload(User.driver_profile))
            rajesh_user = (await session.execute(q_u)).scalar_one()

            ship = (await session.execute(select(Shipment))).scalars().first()
            ship.driver_id = rajesh_user.driver_profile.id
            await session.commit()
            shipment_id = ship.id

        # Fake HTML content disguised as PDF
        fake_html_content = b"<html><head><title>Fake PDF</title></head><body>Bad Content</body></html>"
        files = {
            "file": ("test.pdf", fake_html_content, "application/pdf")
        }
        data = {
            "receiver_name": "Test Receiver",
            "receiver_phone": "9876543210",
        }
        res = await ac.post(f"/shipments/{shipment_id}/pod", data=data, files=files, headers=headers)
        assert res.status_code == 400
        assert "does not match valid PDF binary signature" in res.json()["detail"]


@pytest.mark.asyncio
async def test_04_mime_validation_valid_pdf_accepted():
    """TASK 4: Verify genuine PDF with %PDF- header is accepted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncSessionLocal() as session:
            q_u = select(User).where(User.email == "driver.rajesh@loadlink.ai").options(selectinload(User.driver_profile))
            rajesh_user = (await session.execute(q_u)).scalar_one()

            ship = (await session.execute(select(Shipment))).scalars().first()
            ship.driver_id = rajesh_user.driver_profile.id
            await session.commit()
            shipment_id = ship.id

        # Genuine PDF file content
        valid_pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Title (Real POD Document) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {
            "file": ("signed_pod_doc.pdf", valid_pdf_content, "application/pdf")
        }
        data = {
            "receiver_name": "Asansol Receiving Officer",
            "receiver_phone": "9830112233",
            "receiver_signature_notes": "Received 20 drums intact",
        }
        res = await ac.post(f"/shipments/{shipment_id}/pod", data=data, files=files, headers=headers)
        assert res.status_code in [200, 201], res.text
        res_data = res.json()
        assert res_data["file_name"] == "signed_pod_doc.pdf"
        assert res_data["verification_status"] == "PENDING_REVIEW"


@pytest.mark.asyncio
async def test_05_unauthenticated_document_access_rejected():
    """TASK 1: Verify unauthenticated requests to /uploads documents receive HTTP 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res = await ac.get("/uploads/pods/secret_document.pdf")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        assert "Authentication required" in res.json()["detail"]


@pytest.mark.asyncio
async def test_06_unauthorized_cross_user_document_access_rejected():
    """TASK 1: Verify User B cannot access User A's private POD or document."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # Create a real test POD on disk
        target_dir = os.path.join(settings.UPLOAD_DIR, "pods")
        os.makedirs(target_dir, exist_ok=True)
        unique_file = f"private_pod_{uuid.uuid4().hex[:8]}.pdf"
        file_path = os.path.join(target_dir, unique_file)
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4\nPrivate Content\n%%EOF")

        # Register POD in DB linked to Rajesh & Kolkata dealer
        async with AsyncSessionLocal() as session:
            q_ship = (
                select(Shipment)
                .options(
                    selectinload(Shipment.driver),
                    selectinload(Shipment.dealer),
                    selectinload(Shipment.pod),
                )
            )
            ship = (await session.execute(q_ship)).scalars().first()
            if ship.pod:
                ship.pod.file_url = f"/uploads/pods/{unique_file}"
                ship.pod.file_name = unique_file
            else:
                pod = POD(
                    id=str(uuid.uuid4()),
                    shipment_id=ship.id,
                    file_url=f"/uploads/pods/{unique_file}",
                    file_name=unique_file,
                    receiver_name="Authorized Consignee",
                    submitted_by_driver_id=ship.driver_id,
                    verification_status=PODStatus.PENDING_REVIEW,
                )
                session.add(pod)
            await session.commit()

        # Login as an UNRELATED user (dealer durgapur)
        unrelated_token = await get_token_for(ac, "dealer.durgapur@durgapuralloys.com", "dealer123")
        headers = {"Authorization": f"Bearer {unrelated_token}"}

        res = await ac.get(f"/uploads/pods/{unique_file}", headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden for cross-user document access, got {res.status_code}"
        assert "Access denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_07_authorized_document_access_succeeds():
    """TASK 1: Verify authorized admin can access the document via Bearer or query token."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        target_dir = os.path.join(settings.UPLOAD_DIR, "pods")
        os.makedirs(target_dir, exist_ok=True)
        unique_file = f"pod_authorized_{uuid.uuid4().hex[:8]}.pdf"
        file_path = os.path.join(target_dir, unique_file)
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4\nAuthorized Content\n%%EOF")

        # Login as Admin
        admin_token = await get_token_for(ac, "admin@loadlink.ai", "admin123")

        # 1. Access with Bearer Header
        res_bearer = await ac.get(f"/uploads/pods/{unique_file}", headers={"Authorization": f"Bearer {admin_token}"})
        assert res_bearer.status_code == 200
        assert res_bearer.content == b"%PDF-1.4\nAuthorized Content\n%%EOF"

        # 2. Access with Query Param ?token=... (for <img> or <a href>)
        res_query = await ac.get(f"/uploads/pods/{unique_file}?token={admin_token}")
        assert res_query.status_code == 200
        assert res_query.content == b"%PDF-1.4\nAuthorized Content\n%%EOF"


@pytest.mark.asyncio
async def test_08_path_traversal_document_access_rejected():
    """TASK 1: Verify path traversal attempt (..) is rejected with 400 Bad Request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        admin_token = await get_token_for(ac, "admin@loadlink.ai", "admin123")
        headers = {"Authorization": f"Bearer {admin_token}"}

        res = await ac.get("/uploads/..%2Floadlink.db", headers=headers)
        assert res.status_code in [400, 404], f"Expected 400/404, got {res.status_code}"


@pytest.mark.asyncio
async def test_09_custody_loading_unauthorized_actor_rejected():
    """TASK 2: Verify unassigned driver attempting to record loading custody gets 403 Forbidden."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        unassigned_token = await get_token_for(ac, "driver.amit@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {unassigned_token}"}

        async with AsyncSessionLocal() as session:
            # Pick a shipment assigned to Rajesh, NOT Amit
            q = select(Shipment).options(selectinload(Shipment.driver).selectinload(Driver.user))
            ship = (await session.execute(q)).scalars().first()
            q_rajesh = select(User).where(User.email == "driver.rajesh@loadlink.ai").options(selectinload(User.driver_profile))
            rajesh_user = (await session.execute(q_rajesh)).scalar_one()
            ship.driver_id = rajesh_user.driver_profile.id
            await session.commit()
            shipment_id = ship.id

        payload = {
            "seal_number": "SL-998811",
            "recorded_weight_tons": 18.0,
            "cargo_condition": "INTACT",
            "driver_acknowledged": True,
        }
        res = await ac.post(f"/custody/shipments/{shipment_id}/loading", json=payload, headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
        assert "Access denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_10_custody_incident_unauthorized_actor_rejected():
    """TASK 2: Verify unrelated dealer attempting to report transit incident gets 403 Forbidden."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        unrelated_dealer_token = await get_token_for(ac, "dealer.durgapur@durgapuralloys.com", "dealer123")
        headers = {"Authorization": f"Bearer {unrelated_dealer_token}"}

        async with AsyncSessionLocal() as session:
            # Pick a shipment owned by Kolkata dealer
            q_kolkata = select(User).where(User.email == "dealer.kolkata@bengalsteel.in").options(selectinload(User.dealer_profile))
            kolkata_user = (await session.execute(q_kolkata)).scalar_one()

            q = select(Shipment).options(selectinload(Shipment.dealer).selectinload(Dealer.user))
            ship = (await session.execute(q)).scalars().first()
            ship.dealer_id = kolkata_user.dealer_profile.id
            await session.commit()
            shipment_id = ship.id

        payload = {
            "damage_description": "Fake highway incident report",
            "cargo_condition": "DAMAGED",
            "location_name": "NH19 Burdwan",
        }
        res = await ac.post(f"/custody/shipments/{shipment_id}/incident", json=payload, headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
        assert "Access denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_11_custody_delivery_unauthorized_actor_rejected():
    """TASK 2: Verify unassigned driver attempting to record delivery handover gets 403 Forbidden."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        unassigned_token = await get_token_for(ac, "driver.amit@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {unassigned_token}"}

        async with AsyncSessionLocal() as session:
            q_rajesh = select(User).where(User.email == "driver.rajesh@loadlink.ai").options(selectinload(User.driver_profile))
            rajesh_user = (await session.execute(q_rajesh)).scalar_one()

            q = select(Shipment)
            ship = (await session.execute(q)).scalars().first()
            ship.driver_id = rajesh_user.driver_profile.id
            await session.commit()
            shipment_id = ship.id

        payload = {
            "delivery_type": "FULL_DELIVERY",
            "receiver_name": "Unauthorized Delivery Officer",
            "receiver_phone": "9811223344",
            "delivery_otp": "123456",
        }
        res = await ac.post(f"/custody/shipments/{shipment_id}/delivery", json=payload, headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
        assert "Access denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_12_custody_events_unauthorized_actor_rejected():
    """TASK 2: Verify unrelated dealer cannot view private custody audit events."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        unrelated_token = await get_token_for(ac, "dealer.durgapur@durgapuralloys.com", "dealer123")
        headers = {"Authorization": f"Bearer {unrelated_token}"}

        async with AsyncSessionLocal() as session:
            q_kolkata = select(User).where(User.email == "dealer.kolkata@bengalsteel.in").options(selectinload(User.dealer_profile))
            kolkata_user = (await session.execute(q_kolkata)).scalar_one()

            q = select(Shipment)
            ship = (await session.execute(q)).scalars().first()
            ship.dealer_id = kolkata_user.dealer_profile.id
            await session.commit()
            shipment_id = ship.id

        res = await ac.get(f"/custody/shipments/{shipment_id}/events", headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
        assert "Access denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_13_concurrency_driver_reassignment_during_in_transit_blocked():
    """TASK 5: Verify attempting to reassign or unassign a truck that is IN_TRANSIT returns 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        admin_token = await get_token_for(ac, "admin@loadlink.ai", "admin123")
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Put a truck in active IN_TRANSIT consignment
        async with AsyncSessionLocal() as session:
            q_truck = select(Truck).where(Truck.driver_id.isnot(None))
            truck = (await session.execute(q_truck)).scalars().first()
            truck.status = TruckStatus.IN_TRANSIT
            truck_id = truck.id
            await session.commit()

        # Attempt to reassign driver while truck is IN_TRANSIT
        assign_payload = {
            "driver_id": "any-driver-id",
            "assignment_notes": "Attempted swap while on highway",
        }
        res_assign = await ac.post(f"/trucks/{truck_id}/assign", json=assign_payload, headers=headers)
        assert res_assign.status_code == 409, f"Expected 409 Conflict, got {res_assign.status_code}: {res_assign.text}"
        assert "IN_TRANSIT" in res_assign.json()["detail"]

        # Attempt to unassign driver while truck is IN_TRANSIT
        res_unassign = await ac.post(f"/trucks/{truck_id}/unassign", headers=headers)
        assert res_unassign.status_code == 409, f"Expected 409 Conflict, got {res_unassign.status_code}: {res_unassign.text}"
        assert "IN_TRANSIT" in res_unassign.json()["detail"]

        # Restore truck status to ONLINE_AVAILABLE
        async with AsyncSessionLocal() as session:
            t = await session.get(Truck, truck_id)
            t.status = TruckStatus.ONLINE_AVAILABLE
            await session.commit()


@pytest.mark.asyncio
async def test_14_concurrency_duplicate_truck_dispatch_blocked():
    """TASK 5: Verify dispatching a truck that is in SAFETY_HOLD or active transit returns 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        admin_token = await get_token_for(ac, "admin@loadlink.ai", "admin123")
        headers = {"Authorization": f"Bearer {admin_token}"}

        async with AsyncSessionLocal() as session:
            q_ship = (
                select(Shipment)
                .options(selectinload(Shipment.truck))
            )
            ship = (await session.execute(q_ship)).scalars().first()
            ship.state = ShipmentState.CONFIRMED
            ship.truck.status = TruckStatus.SAFETY_HOLD
            await session.commit()
            shipment_id = ship.id

        # Attempt to transition to DRIVER_EN_ROUTE when truck is on SAFETY_HOLD
        payload = {
            "target_state": "DRIVER_EN_ROUTE",
            "note": "Dispatch attempt under safety hold",
        }
        res = await ac.patch(f"/shipments/{shipment_id}/status", json=payload, headers=headers)
        assert res.status_code == 409, f"Expected 409 Conflict, got {res.status_code}: {res.text}"
        assert "SAFETY_HOLD" in res.json()["detail"]

        # Restore truck status
        async with AsyncSessionLocal() as session:
            s = await session.get(Shipment, shipment_id)
            q_t = select(Truck).where(Truck.id == s.truck_id)
            t = (await session.execute(q_t)).scalar_one()
            t.status = TruckStatus.ONLINE_AVAILABLE
            await session.commit()
