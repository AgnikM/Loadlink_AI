import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import DisputeCase, DisputeEvidence, DisputeMessage, Grievance, User, AuditLog
from app.models.enums import DisputeCategory, DisputeStatus, GrievanceStatus, UserRole

class DisputeService:
    @staticmethod
    def classify_dispute_ai(
        category: DisputeCategory,
        title: str,
        description: str,
        disputed_amount: Optional[float],
    ) -> Dict[str, Any]:
        """
        AI-assisted dispute triage.
        NOTE: AI may help classify or prioritize disputes but must NOT automatically
        decide liability or deduct money.
        """
        urgency = "MEDIUM"
        priority_score = 50
        recommended_focus = "Standard operational review"
        tags = [category.value.lower()]

        desc_lower = (title + " " + description).lower()

        if category in [DisputeCategory.CARGO_DAMAGE, DisputeCategory.CARGO_SHORTAGE]:
            urgency = "HIGH"
            priority_score = 85
            recommended_focus = "Inspect loading seal photographs, digital POD, and weight bridge slips"
            tags.extend(["cargo_integrity", "inspection_required"])

        if category in [DisputeCategory.NON_DELIVERY, DisputeCategory.DELIVERY_REFUSAL]:
            urgency = "URGENT"
            priority_score = 95
            recommended_focus = "Contact driver telematics and receiving warehouse manager immediately"
            tags.extend(["critical_route", "escalate_to_control_room"])

        if disputed_amount and disputed_amount >= 100000.0:
            priority_score = min(100, priority_score + 15)
            tags.append("high_financial_impact")

        if any(w in desc_lower for w in ["theft", "stolen", "accident", "police", "fir"]):
            urgency = "URGENT"
            priority_score = 100
            tags.extend(["legal_escalation", "emergency"])

        return {
            "ai_triage_model": "LoadLink-Dispute-Triage-Heuristic-v2",
            "urgency": urgency,
            "priority_score": priority_score,
            "recommended_focus": recommended_focus,
            "tags": tags,
            "automated_financial_action": False,  # Explicitly zero automated deductions
            "liability_auto_decided": False,      # AI must NEVER auto-decide liability
            "liability_decision": "PENDING_HUMAN_OFFICER_REVIEW",
        }

    @staticmethod
    async def create_dispute(
        raised_by: User,
        category: DisputeCategory,
        title: str,
        description: str,
        db: AsyncSession,
        disputed_amount: Optional[float] = None,
        booking_id: Optional[str] = None,
        shipment_id: Optional[str] = None,
        respondent_user_id: Optional[str] = None,
        evidence_urls: Optional[List[str]] = None,
    ) -> DisputeCase:
        now = datetime.now(timezone.utc)
        case_no = f"DSP-{now.year}-{int(now.timestamp()) % 1000000:06d}"
        ai_meta = DisputeService.classify_dispute_ai(category, title, description, disputed_amount)

        # Auto-assign first available Dispute Officer if exists
        q_officer = select(User).where(User.role == UserRole.DISPUTE_OFFICER)
        officer = (await db.execute(q_officer)).scalars().first()

        dispute = DisputeCase(
            id=str(uuid.uuid4()),
            case_number=case_no,
            shipment_id=shipment_id,
            booking_id=booking_id,
            raised_by_user_id=raised_by.id,
            respondent_user_id=respondent_user_id,
            category=category,
            title=title,
            description=description,
            disputed_amount_inr=disputed_amount,
            status=DisputeStatus.OPEN,
            assigned_officer_id=officer.id if officer else None,
            ai_classification=ai_meta,
            created_at=now,
            updated_at=now,
        )
        db.add(dispute)
        await db.flush()

        # Add initial evidence items if provided
        if evidence_urls:
            for url in evidence_urls:
                ev = DisputeEvidence(
                    id=str(uuid.uuid4()),
                    dispute_id=dispute.id,
                    uploaded_by_user_id=raised_by.id,
                    title="Supporting Evidence",
                    file_url=url,
                    evidence_type="PHOTO_DAMAGE" if "damage" in category.value.lower() else "DOCUMENT",
                    notes="Attached upon case filing",
                    created_at=now,
                )
                db.add(ev)

        audit = AuditLog(
            actor_id=raised_by.id,
            action="DISPUTE_CASE_OPENED",
            entity_name="DisputeCase",
            entity_id=dispute.id,
            state_after="OPEN",
            metadata_json={
                "case_number": case_no,
                "category": category.value,
                "urgency": ai_meta["urgency"],
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(dispute)
        return dispute

    @staticmethod
    async def create_grievance(
        user: User,
        subject: str,
        description: str,
        category: str,
        db: AsyncSession,
    ) -> Grievance:
        now = datetime.now(timezone.utc)
        t_no = f"GRV-{now.year}-{int(now.timestamp()) % 1000000:06d}"

        # Assign dispute officer or admin
        q_officer = select(User).where(User.role.in_([UserRole.DISPUTE_OFFICER, UserRole.ADMIN]))
        officer = (await db.execute(q_officer)).scalars().first()

        grievance = Grievance(
            id=str(uuid.uuid4()),
            ticket_number=t_no,
            user_id=user.id,
            category=category or "GENERAL_SERVICE",
            subject=subject,
            description=description,
            assigned_officer_id=officer.id if officer else None,
            status=GrievanceStatus.ACKNOWLEDGED,
            acknowledged_at=now,
            due_date=now + timedelta(days=3),  # 3-day SLA
            created_at=now,
        )
        db.add(grievance)

        audit = AuditLog(
            actor_id=user.id,
            action="GRIEVANCE_TICKET_FILED",
            entity_name="Grievance",
            entity_id=grievance.id,
            state_after="ACKNOWLEDGED",
            metadata_json={
                "ticket_number": t_no,
                "due_date": grievance.due_date.isoformat(),
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(grievance)
        return grievance
