import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import DirectPayment, PlatformInvoice, Booking, User, AuditLog, Dealer, Driver
from app.models.enums import DirectPaymentStatus, PaymentMethod, FeeType, InvoiceStatus, UserRole
from app.schemas.all_schemas import (
    DirectPaymentReport, DirectPaymentAcknowledge, DirectPaymentOut, PlatformInvoiceOut
)
from app.services.billing_service import BillingService

router = APIRouter(prefix="/payments", tags=["payments-billing"])

def _build_payment_out(p: DirectPayment) -> DirectPaymentOut:
    return DirectPaymentOut(
        id=p.id,
        booking_id=p.booking_id,
        shipment_id=p.shipment_id,
        payer_dealer_name=p.payer_user.name if p.payer_user else "Shipper",
        payee_transporter_name=p.payee_user.name if p.payee_user else "Carrier",
        agreed_freight_inr=p.agreed_freight_inr,
        amount_paid_inr=p.amount_paid_inr,
        payment_status=p.payment_status,
        due_date=p.due_date,
        payment_method=p.payment_method,
        payment_reference=p.payment_reference,
        payment_evidence_url=p.payment_evidence_url,
        dealer_reported_at=p.dealer_reported_at,
        dealer_notes=p.dealer_notes,
        transporter_acknowledged_at=p.transporter_acknowledged_at,
        transporter_notes=p.transporter_notes,
        is_partial=p.is_partial,
        remaining_balance_inr=p.remaining_balance_inr,
        dispute_reason=p.dispute_reason,
        created_at=p.created_at,
    )

def _build_invoice_out(inv: PlatformInvoice) -> PlatformInvoiceOut:
    return PlatformInvoiceOut(
        id=inv.id,
        invoice_number=inv.invoice_number,
        booking_id=inv.booking_id,
        billed_to_name=inv.billed_to.name if inv.billed_to else "Customer",
        fee_type=inv.fee_type,
        freight_benchmark_inr=inv.freight_benchmark_inr,
        base_fee_inr=inv.base_fee_inr,
        gst_rate_percent=inv.gst_rate_percent,
        gst_amount_inr=inv.gst_amount_inr,
        total_payable_inr=inv.total_payable_inr,
        status=inv.status,
        due_date=inv.due_date,
        paid_at=inv.paid_at,
        created_at=inv.created_at,
    )

@router.post("/direct/{booking_id}", response_model=DirectPaymentOut)
async def report_direct_freight_payment(
    booking_id: str,
    req: DirectPaymentReport,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dealer reports direct payment to transporter.
    LoadLink does NOT hold or pool funds.
    A reported payment does NOT automatically become confirmed.
    """
    q_b = (
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.driver).selectinload(Driver.user),
            selectinload(Booking.shipment),
        )
    )
    booking = (await db.execute(q_b)).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    payment = await BillingService.report_direct_payment(
        booking=booking,
        dealer_user=current_user,
        amount_paid=req.amount_paid_inr,
        payment_method=req.payment_method,
        payment_reference=req.payment_reference,
        payment_evidence_url=req.payment_evidence_url,
        dealer_notes=req.dealer_notes,
        db=db,
    )

    # Re-fetch with relationships
    q_p = (
        select(DirectPayment)
        .where(DirectPayment.id == payment.id)
        .options(selectinload(DirectPayment.payer_user), selectinload(DirectPayment.payee_user))
    )
    p_loaded = (await db.execute(q_p)).scalar_one()
    return _build_payment_out(p_loaded)

@router.patch("/direct/{payment_id}/acknowledge", response_model=DirectPaymentOut)
async def acknowledge_direct_payment(
    payment_id: str,
    req: DirectPaymentAcknowledge,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Transporter reviews bank statement and confirms or disputes payment.
    """
    q = (
        select(DirectPayment)
        .where((DirectPayment.id == payment_id) | (DirectPayment.booking_id == payment_id))
        .options(selectinload(DirectPayment.payer_user), selectinload(DirectPayment.payee_user))
    )
    payment = (await db.execute(q)).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    updated = await BillingService.acknowledge_direct_payment(
        payment=payment,
        transporter_user=current_user,
        action=req.action,
        notes=req.transporter_notes,
        dispute_reason=req.dispute_reason,
        db=db,
    )
    q_p = (
        select(DirectPayment)
        .where(DirectPayment.id == updated.id)
        .options(selectinload(DirectPayment.payer_user), selectinload(DirectPayment.payee_user))
    )
    reloaded = (await db.execute(q_p)).scalar_one()
    return _build_payment_out(reloaded)

@router.get("/direct/{booking_id}", response_model=DirectPaymentOut)
async def get_direct_payment(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(DirectPayment)
        .where((DirectPayment.booking_id == booking_id) | (DirectPayment.id == booking_id))
        .options(selectinload(DirectPayment.payer_user), selectinload(DirectPayment.payee_user))
    )
    payment = (await db.execute(q)).scalar_one_or_none()
    if not payment:
        # Create initial PENDING record if booking exists
        q_b = select(Booking).where(Booking.id == booking_id).options(selectinload(Booking.driver).selectinload(Driver.user))
        booking = (await db.execute(q_b)).scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        payee_uid = booking.driver.user.id if (booking.driver and booking.driver.user) else None
        payment = DirectPayment(
            id=str(uuid.uuid4()),
            booking_id=booking.id,
            agreed_freight_inr=booking.offered_price or 18000.0,
            amount_paid_inr=0.0,
            payment_status=DirectPaymentStatus.PENDING,
            payer_user_id=current_user.id,
            payee_user_id=payee_uid,
            remaining_balance_inr=booking.offered_price or 18000.0,
        )
        db.add(payment)
        await db.commit()
        q_p = (
            select(DirectPayment)
            .where(DirectPayment.id == payment.id)
            .options(selectinload(DirectPayment.payer_user), selectinload(DirectPayment.payee_user))
        )
        payment = (await db.execute(q_p)).scalar_one()

    return _build_payment_out(payment)

@router.get("/invoices/{booking_id}", response_model=PlatformInvoiceOut)
async def get_or_create_platform_invoice(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate or retrieve separate platform fee invoice.
    Platform fee is NOT deducted from transporter freight.
    """
    q_inv = (
        select(PlatformInvoice)
        .where(PlatformInvoice.booking_id == booking_id)
        .options(selectinload(PlatformInvoice.billed_to))
    )
    inv = (await db.execute(q_inv)).scalar_one_or_none()

    if not inv:
        q_b = select(Booking).where(Booking.id == booking_id)
        booking = (await db.execute(q_b)).scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        inv = await BillingService.create_platform_invoice(
            booking=booking,
            billed_to_user_id=current_user.id,
            db=db,
            fee_type=FeeType.FIXED_BOOKING_FEE,
        )
        q_inv_reload = (
            select(PlatformInvoice)
            .where(PlatformInvoice.id == inv.id)
            .options(selectinload(PlatformInvoice.billed_to))
        )
        inv = (await db.execute(q_inv_reload)).scalar_one()

    return _build_invoice_out(inv)

@router.get("/invoices", response_model=List[PlatformInvoiceOut])
async def list_platform_invoices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(PlatformInvoice).options(selectinload(PlatformInvoice.billed_to)).order_by(PlatformInvoice.created_at.desc())
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        q = q.where(PlatformInvoice.billed_to_user_id == current_user.id)

    invoices = (await db.execute(q)).scalars().all()
    return [_build_invoice_out(i) for i in invoices]
