import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DirectPayment, PlatformInvoice, Booking, User, AuditLog
from app.models.enums import DirectPaymentStatus, PaymentMethod, FeeType, InvoiceStatus

class BillingService:
    @staticmethod
    async def create_platform_invoice(
        booking: Booking,
        billed_to_user_id: str,
        db: AsyncSession,
        fee_type: FeeType = FeeType.FIXED_BOOKING_FEE,
    ) -> PlatformInvoice:
        """
        LoadLink charges a separate platform fee.
        Generates separate invoice for LoadLink services.
        Explicitly does NOT deduct fee from transporter freight!
        """
        now = datetime.now(timezone.utc)
        inv_no = f"LL-INV-{now.year}-{int(now.timestamp()) % 1000000:06d}"

        # Configurable fee schedule:
        # Fixed booking fee: ₹250 flat
        # Percentage commission: 1.5% of agreed freight
        agreed_freight = booking.offered_price or 18000.0
        if fee_type == FeeType.PERCENTAGE_COMMISSION:
            base_fee = round(agreed_freight * 0.015, 2)
        else:
            base_fee = 250.0

        gst_rate = 18.0
        gst_amt = round(base_fee * (gst_rate / 100.0), 2)
        total_payable = round(base_fee + gst_amt, 2)

        invoice = PlatformInvoice(
            id=str(uuid.uuid4()),
            invoice_number=inv_no,
            booking_id=booking.id,
            billed_to_user_id=billed_to_user_id,
            fee_type=fee_type,
            freight_benchmark_inr=agreed_freight,
            base_fee_inr=base_fee,
            gst_rate_percent=gst_rate,
            gst_amount_inr=gst_amt,
            total_payable_inr=total_payable,
            status=InvoiceStatus.ISSUED,
            due_date=now + timedelta(days=7),
            created_at=now,
        )
        db.add(invoice)

        audit = AuditLog(
            actor_id=billed_to_user_id,
            action="PLATFORM_INVOICE_GENERATED",
            entity_name="PlatformInvoice",
            entity_id=invoice.id,
            state_after="ISSUED",
            metadata_json={
                "invoice_number": inv_no,
                "base_fee": base_fee,
                "gst_amount": gst_amt,
                "total_payable": total_payable,
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(invoice)
        return invoice

    @staticmethod
    async def report_direct_payment(
        booking: Booking,
        dealer_user: User,
        amount_paid: float,
        payment_method: PaymentMethod,
        payment_reference: str,
        payment_evidence_url: Optional[str],
        dealer_notes: Optional[str],
        db: AsyncSession,
    ) -> DirectPayment:
        now = datetime.now(timezone.utc)
        agreed = booking.offered_price or 18000.0
        is_part = amount_paid < agreed
        rem_balance = max(0.0, agreed - amount_paid)

        # Check if direct payment record already exists
        q = select(DirectPayment).where(DirectPayment.booking_id == booking.id)
        existing = (await db.execute(q)).scalar_one_or_none()

        if existing:
            payment = existing
            payment.amount_paid_inr = amount_paid
            payment.payment_method = payment_method
            payment.payment_reference = payment_reference
            payment.payment_evidence_url = payment_evidence_url
            payment.dealer_reported_at = now
            payment.dealer_notes = dealer_notes
            payment.is_partial = is_part
            payment.remaining_balance_inr = rem_balance
            payment.payment_status = DirectPaymentStatus.REPORTED_BY_DEALER
        else:
            payee_uid = None
            if booking.driver and booking.driver.user:
                payee_uid = booking.driver.user.id

            payment = DirectPayment(
                id=str(uuid.uuid4()),
                booking_id=booking.id,
                shipment_id=booking.shipment.id if booking.shipment else None,
                payer_dealer_id=booking.dealer_id,
                payer_user_id=dealer_user.id,
                payee_user_id=payee_uid,
                agreed_freight_inr=agreed,
                amount_paid_inr=amount_paid,
                payment_status=DirectPaymentStatus.REPORTED_BY_DEALER,
                due_date=now + timedelta(days=2),
                payment_method=payment_method,
                payment_reference=payment_reference,
                payment_evidence_url=payment_evidence_url,
                dealer_reported_at=now,
                dealer_notes=dealer_notes,
                is_partial=is_part,
                remaining_balance_inr=rem_balance,
                created_at=now,
            )
            db.add(payment)

        audit = AuditLog(
            actor_id=dealer_user.id,
            action="DIRECT_FREIGHT_PAYMENT_REPORTED",
            entity_name="DirectPayment",
            entity_id=payment.id,
            state_after=DirectPaymentStatus.REPORTED_BY_DEALER.value,
            metadata_json={
                "amount_paid": amount_paid,
                "payment_reference": payment_reference,
                "is_partial": is_part,
                "remaining_balance": rem_balance,
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(payment)
        return payment

    @staticmethod
    async def acknowledge_direct_payment(
        payment: DirectPayment,
        transporter_user: User,
        action: str,  # "CONFIRM", "DISPUTE"
        notes: Optional[str],
        dispute_reason: Optional[str],
        db: AsyncSession,
    ) -> DirectPayment:
        now = datetime.now(timezone.utc)
        before = payment.payment_status.value

        if action == "CONFIRM":
            payment.payment_status = (
                DirectPaymentStatus.PARTIALLY_PAID if payment.is_partial else DirectPaymentStatus.CONFIRMED_BY_TRANSPORTER
            )
            payment.transporter_acknowledged_at = now
            payment.transporter_notes = notes or "Payment received and verified in bank account."
        else:
            payment.payment_status = DirectPaymentStatus.DISPUTED
            payment.dispute_reason = dispute_reason or notes or "Payment reference mismatch or remittance not received"
            payment.transporter_notes = notes

        audit = AuditLog(
            actor_id=transporter_user.id,
            action=f"DIRECT_PAYMENT_{action}",
            entity_name="DirectPayment",
            entity_id=payment.id,
            state_before=before,
            state_after=payment.payment_status.value,
            metadata_json={
                "action": action,
                "notes": notes,
                "dispute_reason": dispute_reason,
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(payment)
        return payment
