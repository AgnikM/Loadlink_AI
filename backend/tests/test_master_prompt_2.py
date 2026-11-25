import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    User, Truck, Driver, Dealer, Load, Booking, Shipment, POD,
    CargoInsurance, DirectPayment, PlatformInvoice, DisputeCase, DisputeEvidence, Grievance
)
from app.models.enums import (
    UserRole, TruckStatus, LoadStatus, BookingStatus, ShipmentState,
    CargoCategory, FragilityLevel, HazardClass,
    InsuranceAssessmentResult, InsuranceVerificationStatus,
    DirectPaymentStatus, PaymentMethod, FeeType,
    DisputeCategory, DisputeStatus, GrievanceStatus, DeliveryType, CargoCondition
)

# Helper function to get auth token
async def get_token_for(ac: AsyncClient, email: str, password: str) -> str:
    res = await ac.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_01_cargo_declaration():
    """1. Test cargo declaration with category, description, value, fragility, hazard class."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers = {"Authorization": f"Bearer {token}"}

        load_data = {
            "origin_name": "Dankuni Industrial Complex, Hooghly",
            "origin_lat": 22.6800,
            "origin_lon": 88.2900,
            "destination_name": "Durgapur Steel Plant, Paschim Bardhaman",
            "destination_lat": 23.5204,
            "destination_lon": 87.3119,
            "cargo_type": "Industrial Chemicals",
            "cargo_category": "CHEMICALS_HAZARDOUS",
            "cargo_description": "200L High-Purity Industrial Solvent Drums",
            "cargo_weight_tons": 18.0,
            "declared_value_inr": 1500000.0,
            "fragility": "MEDIUM",
            "hazard_classification": "CLASS_3_FLAMMABLE_LIQUIDS",
            "handling_instructions": "Store upright. Keep away from ignition sources.",
            "target_price": 28000.0,
            "pickup_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        }

        res = await ac.post("/loads", json=load_data, headers=headers)
        assert res.status_code in [200, 201], res.text
        data = res.json()
        assert data["cargo_category"] == "CHEMICALS_HAZARDOUS"
        assert data["cargo_description"] == "200L High-Purity Industrial Solvent Drums"
        assert data["declared_value_inr"] == 1500000.0
        assert data["hazard_classification"] == "CLASS_3_FLAMMABLE_LIQUIDS"
        assert data["fragility"] == "MEDIUM"

        # Verify DB persistence directly
        async with AsyncSessionLocal() as session:
            q = select(Load).where(Load.id == data["id"])
            saved = (await session.execute(q)).scalar_one()
            assert saved.cargo_category == CargoCategory.CHEMICALS_HAZARDOUS
            assert saved.declared_value_inr == 1500000.0
            assert saved.hazard_classification == HazardClass.CLASS_3_FLAMMABLE_LIQUIDS


@pytest.mark.asyncio
async def test_02_weight_validation():
    """2. Test pre-dispatch check rejecting booking when cargo weight exceeds legal vehicle payload."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers = {"Authorization": f"Bearer {token}"}

        # Create a heavy load of 45 tons
        load_data = {
            "origin_name": "Dankuni Yard",
            "origin_lat": 22.68,
            "origin_lon": 88.29,
            "destination_name": "Durgapur Depot",
            "destination_lat": 23.52,
            "destination_lon": 87.31,
            "cargo_type": "Heavy Steel Girders",
            "cargo_category": "STEEL_AND_METALS",
            "cargo_weight_tons": 45.0,  # Far exceeds 20T/25T standard trucks
            "declared_value_inr": 800000.0,
            "target_price": 40000.0,
            "pickup_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        }
        res_load = await ac.post("/loads", json=load_data, headers=headers)
        assert res_load.status_code in [200, 201], res_load.text
        load_id = res_load.json()["id"]

        # Find a truck with capacity 20 or 25 tons
        async with AsyncSessionLocal() as session:
            q_truck = select(Truck).where(Truck.capacity_tons < 45.0)
            truck = (await session.execute(q_truck)).scalars().first()
            assert truck is not None
            truck_id = truck.id

        # Attempt to book the truck with this overweight load
        booking_payload = {
            "load_id": load_id,
            "truck_id": truck_id,
            "offered_price": 38000.0,
        }
        res_book = await ac.post("/bookings", json=booking_payload, headers=headers)
        assert res_book.status_code == 400, "Overweight booking should be rejected"
        assert "exceeds vehicle payload capacity" in res_book.json()["detail"].lower()


@pytest.mark.asyncio
async def test_03_cargo_handover():
    """3. Test cargo loading handover workflow: photographs, condition, seal, weight, driver acknowledgement."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        # Find or create a shipment
        async with AsyncSessionLocal() as session:
            q = select(Shipment).options(selectinload(Shipment.load))
            shipment = (await session.execute(q)).scalars().first()
            assert shipment is not None
            shipment_id = shipment.id

        handover_data = {
            "seal_number": "SL-WB-778901",
            "seal_intact": True,
            "cargo_condition": "INTACT",
            "recorded_weight_tons": 18.0,
            "photographs": ["/uploads/loading_photo_1.jpg", "/uploads/seal_photo.jpg"],
            "driver_acknowledged": True,
            "driver_notes": "All drums loaded securely and strapped.",
        }

        res = await ac.post(f"/custody/shipments/{shipment_id}/loading", json=handover_data, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["event_type"] == "LOADING_HANDOVER"
        assert data["seal_number"] == "SL-WB-778901"
        assert data["driver_acknowledged"] is True
        assert len(data["photographs"]) == 2

        # Check shipment updated to LOADED
        async with AsyncSessionLocal() as session:
            q_s = select(Shipment).where(Shipment.id == shipment_id)
            updated_s = (await session.execute(q_s)).scalar_one()
            assert updated_s.state == ShipmentState.LOADED


@pytest.mark.asyncio
async def test_04_delivery_confirmation():
    """4. Test delivery confirmation with receiver acknowledgement, OTP, and digital POD generation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        async with AsyncSessionLocal() as session:
            q = select(Shipment).where(Shipment.state != ShipmentState.COMPLETED).options(selectinload(Shipment.load))
            shipment = (await session.execute(q)).scalars().first()
            if not shipment:
                q_any = select(Shipment).options(selectinload(Shipment.load))
                shipment = (await session.execute(q_any)).scalars().first()
            assert shipment is not None
            shipment_id = shipment.id

        delivery_data = {
            "delivery_type": "FULL_DELIVERY",
            "receiver_name": "Siddharth Sen (Store Manager)",
            "receiver_phone": "+919830099887",
            "delivery_otp": "654321",
            "receiver_acknowledged": True,
            "cargo_condition": "INTACT",
            "seal_intact": True,
            "photographs": ["/uploads/pod_signed_sheet.pdf"],
            "driver_notes": "Unloaded at Bay 4 without incident.",
        }

        res = await ac.post(f"/custody/shipments/{shipment_id}/delivery", json=delivery_data, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["event_type"] == "DELIVERY_HANDOVER"
        assert data["delivery_type"] == "FULL_DELIVERY"
        assert data["otp_verified"] is True
        assert data["receiver_acknowledged"] is True

        # Verify shipment status is POD_SUBMITTED or DELIVERED and digital POD was created
        async with AsyncSessionLocal() as session:
            q_s = select(Shipment).where(Shipment.id == shipment_id).options(selectinload(Shipment.pod))
            s = (await session.execute(q_s)).scalar_one()
            assert s.state in [ShipmentState.DELIVERED, ShipmentState.POD_SUBMITTED]
            assert s.pod is not None
            assert s.pod.receiver_name == "Siddharth Sen (Store Manager)"


@pytest.mark.asyncio
async def test_05_partial_delivery():
    """5. Test partial delivery recording with quantity and weight discrepancy."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        async with AsyncSessionLocal() as session:
            q = select(Shipment).options(selectinload(Shipment.load))
            shipment = (await session.execute(q)).scalars().first()
            shipment_id = shipment.id
            expected_weight = shipment.load.cargo_weight_tons if shipment.load else 15.0

        partial_data = {
            "delivery_type": "PARTIAL_DELIVERY",
            "receiver_name": "Asim Roy",
            "recorded_weight_tons": expected_weight - 4.0,  # 4 Tons short
            "recorded_quantity": 0.75,
            "quantity_discrepancy": 0.25,
            "damage_reported": True,
            "damage_description": "2 pallets rejected due to water damage on top layers.",
            "photographs": ["/uploads/damaged_pallets.jpg"],
            "receiver_acknowledged": True,
        }

        res = await ac.post(f"/custody/shipments/{shipment_id}/delivery", json=partial_data, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["delivery_type"] == "PARTIAL_DELIVERY"
        assert data["weight_discrepancy_tons"] == -4.0
        assert data["quantity_discrepancy"] == 0.25
        assert data["damage_reported"] is True


@pytest.mark.asyncio
async def test_06_delivery_refusal():
    """6. Test delivery refusal transitioning shipment to DISPUTED state."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        headers = {"Authorization": f"Bearer {driver_token}"}

        async with AsyncSessionLocal() as session:
            q = select(Shipment).options(selectinload(Shipment.load))
            shipment = (await session.execute(q)).scalars().first()
            shipment_id = shipment.id

        refusal_data = {
            "delivery_type": "REFUSAL",
            "receiver_name": "Gate Inspection Officer",
            "cargo_condition": "DAMAGED",
            "damage_reported": True,
            "damage_description": "Complete consignment rejected: seals were broken and solvent leaked into truck bed.",
            "receiver_acknowledged": False,
        }

        res = await ac.post(f"/custody/shipments/{shipment_id}/delivery", json=refusal_data, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["delivery_type"] == "REFUSAL"

        # Check shipment state transitioned to DISPUTED
        async with AsyncSessionLocal() as session:
            q_s = select(Shipment).where(Shipment.id == shipment_id)
            s = (await session.execute(q_s)).scalar_one()
            assert s.state == ShipmentState.DISPUTED


@pytest.mark.asyncio
async def test_07_insurance_required_result():
    """7. Test risk-based insurance assessment returning REQUIRED for high-value / hazardous cargo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers = {"Authorization": f"Bearer {token}"}

        assess_req = {
            "cargo_category": "CHEMICALS_HAZARDOUS",
            "declared_value_inr": 850000.0,  # Exceeds max uninsured limit (200k)
            "fragility": "HIGH",
            "hazard_class": "CLASS_3_FLAMMABLE_LIQUIDS",
        }

        res = await ac.post("/insurance/assess", json=assess_req, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["assessment_result"] == "REQUIRED"
        assert len(data["reasons"]) >= 1
        assert any("hazardous" in r.lower() or "un-insured" in r.lower() for r in data["reasons"])


@pytest.mark.asyncio
async def test_08_insurance_not_required_result():
    """8. Test risk-based insurance assessment returning NOT_REQUIRED for low-value general merchandise."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers = {"Authorization": f"Bearer {token}"}

        assess_req = {
            "cargo_category": "GENERAL_MERCHANDISE",
            "declared_value_inr": 120000.0,  # Below 200k uninsured ceiling
            "fragility": "LOW",
            "hazard_class": "NONE",
        }

        res = await ac.post("/insurance/assess", json=assess_req, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["assessment_result"] == "NOT_REQUIRED"


@pytest.mark.asyncio
async def test_09_expired_policy_rejection():
    """9. Test rejection of expired insurance certificate upon compliance verification."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        compliance_token = await get_token_for(ac, "compliance@loadlink.ai", "compliance123")

        # 1. Dealer uploads insurance certificate that expired last month
        async with AsyncSessionLocal() as session:
            q = select(Booking)
            booking = (await session.execute(q)).scalars().first()
            booking_id = booking.id

        upload_payload = {
            "policy_number": "EXP-NIC-882190",
            "insurer_name": "National Insurance Co",
            "policyholder_name": "Bengal Roadways Pvt Ltd",
            "insured_party": "Bengal Steel Ltd",
            "coverage_amount_inr": 1000000.0,
            "valid_from": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
            "valid_to": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),  # EXPIRED
            "certificate_url": "/uploads/expired_cert.pdf",
        }

        res_up = await ac.post(
            f"/insurance/{booking_id}/upload",
            json=upload_payload,
            headers={"Authorization": f"Bearer {dealer_token}"},
        )
        assert res_up.status_code == 200, res_up.text
        ins_id = res_up.json()["id"]

        # An uploaded document must NOT automatically become verified insurance
        assert res_up.json()["verification_status"] == "PENDING_VERIFICATION"

        # 2. Compliance Officer attempts to verify this expired certificate
        verify_payload = {
            "action": "VERIFY",
        }
        res_ver = await ac.patch(
            f"/insurance/{ins_id}/verify",
            json=verify_payload,
            headers={"Authorization": f"Bearer {compliance_token}"},
        )
        assert res_ver.status_code == 400, "Expired certificate verification must be rejected"
        assert "expired" in res_ver.json()["detail"].lower()


@pytest.mark.asyncio
async def test_10_unverified_insurance_dispatch_block():
    """10. Test that unverified required insurance blocks vehicle dispatch until verified."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        driver_token = await get_token_for(ac, "driver.rajesh@loadlink.ai", "driver123")
        compliance_token = await get_token_for(ac, "compliance@loadlink.ai", "compliance123")

        # Create or identify a shipment where insurance is REQUIRED but PENDING_VERIFICATION
        async with AsyncSessionLocal() as session:
            q = select(Shipment).options(selectinload(Shipment.load))
            s = (await session.execute(q)).scalars().first()
            shipment_id = s.id

            # Attach a REQUIRED and unverified insurance record
            q_ins = select(CargoInsurance).where(CargoInsurance.shipment_id == shipment_id)
            ins = (await session.execute(q_ins)).scalar_one_or_none()
            if not ins:
                ins = CargoInsurance(
                    shipment_id=s.id,
                    booking_id=s.booking_id,
                    load_id=s.load_id,
                    assessment_result=InsuranceAssessmentResult.REQUIRED,
                    verification_status=InsuranceVerificationStatus.PENDING_VERIFICATION,
                )
                session.add(ins)
            else:
                ins.assessment_result = InsuranceAssessmentResult.REQUIRED
                ins.verification_status = InsuranceVerificationStatus.PENDING_VERIFICATION
                ins.exception_permitted = False

            s.state = ShipmentState.CONFIRMED
            await session.commit()
            insurance_id = ins.id

        # Driver attempts to dispatch (transition to DRIVER_EN_ROUTE)
        res_dispatch = await ac.patch(
            f"/shipments/{shipment_id}/status",
            json={"target_state": "DRIVER_EN_ROUTE", "note": "Attempting departure"},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert res_dispatch.status_code == 400, "Dispatch must be blocked for unverified required insurance"
        assert "dispatch blocked" in res_dispatch.json()["detail"].lower()

        # Compliance Officer approves policy verification
        res_verify = await ac.patch(
            f"/insurance/{insurance_id}/verify",
            json={"action": "APPROVE_EXCEPTION", "exception_reason": "Verified under fleet master policy coverage"},
            headers={"Authorization": f"Bearer {compliance_token}"},
        )
        assert res_verify.status_code == 200, res_verify.text
        assert res_verify.json()["is_dispatch_allowed"] is True

        # Now Driver re-attempts transition to DRIVER_EN_ROUTE -> must succeed
        res_dispatch_ok = await ac.patch(
            f"/shipments/{shipment_id}/status",
            json={"target_state": "DRIVER_EN_ROUTE", "note": "Departure authorized after compliance clearance"},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert res_dispatch_ok.status_code == 200, res_dispatch_ok.text
        assert res_dispatch_ok.json()["state"] == "DRIVER_EN_ROUTE"


@pytest.mark.asyncio
async def test_11_direct_payment_reporting():
    """11. Test dealer reporting direct freight payment with UTR reference and evidence."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers = {"Authorization": f"Bearer {dealer_token}"}

        async with AsyncSessionLocal() as session:
            q = select(Booking)
            booking = (await session.execute(q)).scalars().first()
            booking_id = booking.id

        payment_data = {
            "amount_paid_inr": 22000.0,
            "payment_method": "NEFT",
            "payment_reference": "UTR-SBIN-20261122-88990",
            "payment_evidence_url": "/uploads/bank_transfer_receipt.pdf",
            "dealer_notes": "Paid directly to transporter current account via SBI Corporate Banking.",
        }

        res = await ac.post(f"/payments/direct/{booking_id}", json=payment_data, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["payment_status"] == "REPORTED_BY_DEALER"
        assert data["amount_paid_inr"] == 22000.0
        assert data["payment_reference"] == "UTR-SBIN-20261122-88990"
        # Verify it did not auto-confirm
        assert data["payment_status"] != "CONFIRMED_BY_TRANSPORTER"


@pytest.mark.asyncio
async def test_12_transporter_payment_acknowledgement():
    """12. Test transporter acknowledging and confirming reported direct payment."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        transporter_token = await get_token_for(ac, "transporter@bengalroadways.in", "transporter123")

        # 1. First report a payment on booking
        async with AsyncSessionLocal() as session:
            q = select(Booking)
            booking = (await session.execute(q)).scalars().first()
            booking_id = booking.id

        report_payload = {
            "amount_paid_inr": 20000.0,
            "payment_method": "RTGS",
            "payment_reference": "UTR-HDFC-9912048",
            "payment_evidence_url": "/uploads/rtgs_receipt.pdf",
            "dealer_notes": "Full freight transfer via RTGS.",
        }
        res_rep = await ac.post(
            f"/payments/direct/{booking_id}",
            json=report_payload,
            headers={"Authorization": f"Bearer {dealer_token}"},
        )
        assert res_rep.status_code == 200, res_rep.text
        payment_id = res_rep.json()["id"]

        # 2. Transporter acknowledges receipt
        ack_data = {
            "action": "CONFIRM",
            "transporter_notes": "Verified receipt in ICICI A/C 0029314421. Full payment received.",
        }

        res = await ac.patch(
            f"/payments/direct/{payment_id}/acknowledge",
            json=ack_data,
            headers={"Authorization": f"Bearer {transporter_token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["payment_status"] == "CONFIRMED_BY_TRANSPORTER"
        assert data["transporter_notes"] == "Verified receipt in ICICI A/C 0029314421. Full payment received."


@pytest.mark.asyncio
async def test_13_separate_platform_fee_invoice():
    """13. Test generation of separate platform fee invoice (not deducted from transporter freight)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers = {"Authorization": f"Bearer {dealer_token}"}

        async with AsyncSessionLocal() as session:
            q = select(Booking)
            booking = (await session.execute(q)).scalars().first()
            booking_id = booking.id

        res = await ac.get(f"/payments/invoices/{booking_id}", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "INV-" in data["invoice_number"]
        assert data["fee_type"] in ["FIXED_BOOKING_FEE", "PERCENTAGE_COMMISSION"]
        assert data["base_fee_inr"] > 0
        assert data["gst_rate_percent"] == 18.0
        assert data["total_payable_inr"] == round(data["base_fee_inr"] + data["gst_amount_inr"], 2)


@pytest.mark.asyncio
async def test_14_dispute_creation_and_evidence():
    """14. Test dispute case creation with unique DSP-XXXX ID, AI triage, and evidence upload."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        headers = {"Authorization": f"Bearer {dealer_token}"}

        async with AsyncSessionLocal() as session:
            q = select(Booking)
            booking = (await session.execute(q)).scalars().first()
            booking_id = booking.id

        dispute_data = {
            "booking_id": booking_id,
            "category": "CARGO_DAMAGE",
            "title": "Severe drum puncture and chemical spillage",
            "description": "Upon opening the container doors, 4 drums were observed dented and breached with solvent leaking.",
            "disputed_amount_inr": 65000.0,
            "evidence_urls": ["/uploads/spill_photo_1.jpg", "/uploads/spill_photo_2.jpg"],
        }

        res = await ac.post("/disputes", json=dispute_data, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["case_number"].startswith("DSP-")
        assert data["status"] in ["OPEN", "UNDER_REVIEW"]
        assert data["category"] == "CARGO_DAMAGE"
        assert data["disputed_amount_inr"] == 65000.0

        # Verify AI triage provided classification without automated financial deduction
        ai = data["ai_classification"]
        assert ai is not None
        assert ai.get("liability_auto_decided") is False  # AI must NEVER auto-decide liability
        dispute_id = data["id"]

        # Upload additional formal survey report evidence
        ev_data = {
            "title": "Independent Surveyor Inspection Report",
            "file_url": "/uploads/surveyor_report_kolkata.pdf",
            "evidence_type": "DAMAGE_REPORT",
            "notes": "Verified ₹65,000 net damage to chemical consignment.",
        }
        res_ev = await ac.post(f"/disputes/{dispute_id}/evidence", json=ev_data, headers=headers)
        assert res_ev.status_code == 200, res_ev.text
        assert res_ev.json()["evidence_type"] == "DAMAGE_REPORT"


@pytest.mark.asyncio
async def test_15_grievance_assignment_and_closure():
    """15. Test user grievance creation with 3-day SLA, officer assignment, and resolution closure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        dealer_token = await get_token_for(ac, "dealer.kolkata@bengalsteel.in", "dealer123")
        officer_token = await get_token_for(ac, "disputes@loadlink.ai", "dispute123")

        # 1. Dealer files a platform grievance
        grievance_data = {
            "category": "OPERATIONAL_GRIEVANCE",
            "subject": "Delay in transporter response during gate inspection",
            "description": "Transporter driver refused to wait 15 minutes for consignee weighbridge certification.",
        }
        res_g = await ac.post(
            "/disputes/grievances/create",
            json=grievance_data,
            headers={"Authorization": f"Bearer {dealer_token}"},
        )
        assert res_g.status_code == 200, res_g.text
        g_data = res_g.json()
        assert g_data["ticket_number"].startswith("GRV-")
        assert g_data["status"] in ["OPEN", "ACKNOWLEDGED"]
        assert g_data["due_date"] is not None
        g_id = g_data["id"]

        # 2. Dispute Officer reviews and resolves the grievance ticket
        update_data = {
            "status": "RESOLVED",
            "resolution_notes": "Contacted transporter fleet supervisor. Driver counseled on corridor SOP guidelines.",
        }
        res_up = await ac.patch(
            f"/disputes/grievances/{g_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert res_up.status_code == 200, res_up.text
        resolved_data = res_up.json()
        assert resolved_data["status"] == "RESOLVED"
        assert resolved_data["assigned_officer_name"] is not None
        assert "corridor SOP" in resolved_data["resolution_notes"]
