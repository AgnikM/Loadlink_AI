import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import (
    DisputeCase, DisputeEvidence, DisputeMessage, Grievance, User, AuditLog, Booking, Shipment
)
from app.models.enums import DisputeCategory, DisputeStatus, GrievanceStatus, UserRole
from app.schemas.all_schemas import (
    DisputeCreate, DisputeEvidenceCreate, DisputeEvidenceOut,
    DisputeMessageCreate, DisputeMessageOut, DisputeResolutionPropose,
    DisputeCaseOut, GrievanceCreate, GrievanceUpdate, GrievanceOut
)
from app.services.dispute_service import DisputeService

router = APIRouter(prefix="/disputes", tags=["disputes-grievances"])

def _build_evidence_out(ev: DisputeEvidence) -> DisputeEvidenceOut:
    return DisputeEvidenceOut(
        id=ev.id,
        dispute_id=ev.dispute_id,
        uploaded_by_name=ev.uploaded_by.name if ev.uploaded_by else None,
        title=ev.title,
        file_url=ev.file_url,
        evidence_type=ev.evidence_type,
        notes=ev.notes,
        created_at=ev.created_at,
    )

def _build_message_out(m: DisputeMessage) -> DisputeMessageOut:
    return DisputeMessageOut(
        id=m.id,
        dispute_id=m.dispute_id,
        sender_name=m.sender.name if m.sender else None,
        sender_role=m.sender.role.value if m.sender else None,
        message=m.message,
        is_officer_internal_note=m.is_officer_internal_note,
        created_at=m.created_at,
    )

def _build_dispute_out(d: DisputeCase) -> DisputeCaseOut:
    return DisputeCaseOut(
        id=d.id,
        case_number=d.case_number,
        shipment_id=d.shipment_id,
        booking_id=d.booking_id,
        raised_by_name=d.raised_by.name if d.raised_by else None,
        respondent_name=d.respondent.name if d.respondent else None,
        category=d.category,
        title=d.title,
        description=d.description,
        disputed_amount_inr=d.disputed_amount_inr,
        status=d.status,
        assigned_officer_name=d.assigned_officer.name if d.assigned_officer else None,
        resolution_proposal=d.resolution_proposal,
        resolution_accepted_by_complainant=d.resolution_accepted_by_complainant,
        resolution_accepted_by_respondent=d.resolution_accepted_by_respondent,
        resolved_at=d.resolved_at,
        ai_classification=d.ai_classification or {},
        evidence=[_build_evidence_out(ev) for ev in (d.evidence or [])],
        messages=[_build_message_out(m) for m in (d.messages or [])],
        created_at=d.created_at,
        updated_at=d.updated_at,
    )

def _build_grievance_out(g: Grievance) -> GrievanceOut:
    return GrievanceOut(
        id=g.id,
        ticket_number=g.ticket_number,
        user_name=g.user.name if g.user else None,
        category=g.category,
        subject=g.subject,
        description=g.description,
        assigned_officer_name=g.assigned_officer.name if g.assigned_officer else None,
        status=g.status,
        acknowledged_at=g.acknowledged_at,
        due_date=g.due_date,
        resolution_notes=g.resolution_notes,
        created_at=g.created_at,
    )

@router.post("", response_model=DisputeCaseOut)
async def open_dispute_case(
    req: DisputeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    respondent_id = None
    if req.booking_id:
        q_b = select(Booking).where(Booking.id == req.booking_id).options(
            selectinload(Booking.driver),
            selectinload(Booking.dealer)
        )
        b = (await db.execute(q_b)).scalar_one_or_none()
        if b:
            if current_user.role == UserRole.DEALER:
                respondent_id = b.driver.user_id if b.driver else None
            else:
                respondent_id = b.dealer.user_id if b.dealer else None

    dispute = await DisputeService.create_dispute(
        raised_by=current_user,
        category=req.category,
        title=req.title,
        description=req.description,
        db=db,
        disputed_amount=req.disputed_amount_inr,
        booking_id=req.booking_id,
        shipment_id=req.shipment_id,
        respondent_user_id=respondent_id,
        evidence_urls=req.evidence_urls,
    )

    # Re-fetch with relations
    q_loaded = (
        select(DisputeCase)
        .where(DisputeCase.id == dispute.id)
        .options(
            selectinload(DisputeCase.raised_by),
            selectinload(DisputeCase.respondent),
            selectinload(DisputeCase.assigned_officer),
            selectinload(DisputeCase.evidence).selectinload(DisputeEvidence.uploaded_by),
            selectinload(DisputeCase.messages).selectinload(DisputeMessage.sender),
        )
    )
    d_loaded = (await db.execute(q_loaded)).scalar_one()
    return _build_dispute_out(d_loaded)

@router.get("", response_model=List[DisputeCaseOut])
async def list_dispute_cases(
    status_filter: Optional[DisputeStatus] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(DisputeCase)
        .options(
            selectinload(DisputeCase.raised_by),
            selectinload(DisputeCase.respondent),
            selectinload(DisputeCase.assigned_officer),
            selectinload(DisputeCase.evidence).selectinload(DisputeEvidence.uploaded_by),
            selectinload(DisputeCase.messages).selectinload(DisputeMessage.sender),
        )
        .order_by(DisputeCase.created_at.desc())
    )

    if current_user.role not in [UserRole.ADMIN, UserRole.DISPUTE_OFFICER]:
        q = q.where(
            (DisputeCase.raised_by_user_id == current_user.id)
            | (DisputeCase.respondent_user_id == current_user.id)
        )

    if status_filter:
        q = q.where(DisputeCase.status == status_filter)

    q = q.limit(limit).offset(offset)
    disputes = (await db.execute(q)).scalars().all()
    return [_build_dispute_out(d) for d in disputes]

@router.get("/{dispute_id}", response_model=DisputeCaseOut)
async def get_dispute_case(
    dispute_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(DisputeCase)
        .where((DisputeCase.id == dispute_id) | (DisputeCase.case_number == dispute_id))
        .options(
            selectinload(DisputeCase.raised_by),
            selectinload(DisputeCase.respondent),
            selectinload(DisputeCase.assigned_officer),
            selectinload(DisputeCase.evidence).selectinload(DisputeEvidence.uploaded_by),
            selectinload(DisputeCase.messages).selectinload(DisputeMessage.sender),
        )
    )
    dispute = (await db.execute(q)).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute case not found")
    return _build_dispute_out(dispute)

@router.post("/{dispute_id}/evidence", response_model=DisputeEvidenceOut)
async def upload_dispute_evidence(
    dispute_id: str,
    req: DisputeEvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(DisputeCase).where((DisputeCase.id == dispute_id) | (DisputeCase.case_number == dispute_id))
    dispute = (await db.execute(q)).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute case not found")

    ev = DisputeEvidence(
        id=str(uuid.uuid4()),
        dispute_id=dispute.id,
        uploaded_by_user_id=current_user.id,
        title=req.title,
        file_url=req.file_url,
        evidence_type=req.evidence_type,
        notes=req.notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ev)
    await db.commit()
    await db.refresh(ev)

    q_loaded = select(DisputeEvidence).where(DisputeEvidence.id == ev.id).options(selectinload(DisputeEvidence.uploaded_by))
    ev_loaded = (await db.execute(q_loaded)).scalar_one()
    return _build_evidence_out(ev_loaded)

@router.post("/{dispute_id}/messages", response_model=DisputeMessageOut)
async def post_dispute_message(
    dispute_id: str,
    req: DisputeMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(DisputeCase).where((DisputeCase.id == dispute_id) | (DisputeCase.case_number == dispute_id))
    dispute = (await db.execute(q)).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute case not found")

    msg = DisputeMessage(
        id=str(uuid.uuid4()),
        dispute_id=dispute.id,
        sender_user_id=current_user.id,
        message=req.message,
        is_officer_internal_note=req.is_officer_internal_note and current_user.role in [UserRole.DISPUTE_OFFICER, UserRole.ADMIN],
        created_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    q_loaded = select(DisputeMessage).where(DisputeMessage.id == msg.id).options(selectinload(DisputeMessage.sender))
    msg_loaded = (await db.execute(q_loaded)).scalar_one()
    return _build_message_out(msg_loaded)

@router.patch("/{dispute_id}/resolve", response_model=DisputeCaseOut)
async def propose_or_resolve_dispute(
    dispute_id: str,
    req: DisputeResolutionPropose,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.DISPUTE_OFFICER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only Dispute Officer or Admin can propose dispute resolutions or close cases")

    q = (
        select(DisputeCase)
        .where((DisputeCase.id == dispute_id) | (DisputeCase.case_number == dispute_id))
        .options(
            selectinload(DisputeCase.raised_by),
            selectinload(DisputeCase.respondent),
            selectinload(DisputeCase.assigned_officer),
            selectinload(DisputeCase.evidence).selectinload(DisputeEvidence.uploaded_by),
            selectinload(DisputeCase.messages).selectinload(DisputeMessage.sender),
        )
    )
    dispute = (await db.execute(q)).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute case not found")

    now = datetime.now(timezone.utc)
    dispute.resolution_proposal = req.proposal_text
    dispute.assigned_officer_id = current_user.id
    dispute.status = DisputeStatus.ESCALATED if req.is_escalated else DisputeStatus.RESOLUTION_PROPOSED
    dispute.updated_at = now

    audit = AuditLog(
        actor_id=current_user.id,
        action="DISPUTE_RESOLUTION_PROPOSED",
        entity_name="DisputeCase",
        entity_id=dispute.id,
        state_after=dispute.status.value,
        metadata_json={
            "proposal": req.proposal_text,
            "escalated": req.is_escalated,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(dispute)
    return _build_dispute_out(dispute)

# --- Grievances System ---

@router.post("/grievances/create", response_model=GrievanceOut)
async def file_grievance(
    req: GrievanceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    grievance = await DisputeService.create_grievance(
        user=current_user,
        subject=req.subject,
        description=req.description,
        category=req.category,
        db=db,
    )
    q_loaded = (
        select(Grievance)
        .where(Grievance.id == grievance.id)
        .options(selectinload(Grievance.user), selectinload(Grievance.assigned_officer))
    )
    g_loaded = (await db.execute(q_loaded)).scalar_one()
    return _build_grievance_out(g_loaded)

@router.get("/grievances/list", response_model=List[GrievanceOut])
async def list_grievances(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Grievance)
        .options(selectinload(Grievance.user), selectinload(Grievance.assigned_officer))
        .order_by(Grievance.created_at.desc())
    )
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPUTE_OFFICER]:
        q = q.where(Grievance.user_id == current_user.id)

    grievances = (await db.execute(q)).scalars().all()
    return [_build_grievance_out(g) for g in grievances]

@router.patch("/grievances/{grievance_id}", response_model=GrievanceOut)
async def update_grievance(
    grievance_id: str,
    req: GrievanceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPUTE_OFFICER]:
        raise HTTPException(status_code=403, detail="Only Dispute Officer or Admin can manage grievances")

    q = (
        select(Grievance)
        .where((Grievance.id == grievance_id) | (Grievance.ticket_number == grievance_id))
        .options(selectinload(Grievance.user), selectinload(Grievance.assigned_officer))
    )
    g = (await db.execute(q)).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grievance not found")

    if req.assigned_officer_id:
        g.assigned_officer_id = req.assigned_officer_id
    else:
        g.assigned_officer_id = current_user.id

    if req.status:
        g.status = req.status

    if req.resolution_notes:
        g.resolution_notes = req.resolution_notes

    audit = AuditLog(
        actor_id=current_user.id,
        action="GRIEVANCE_UPDATED",
        entity_name="Grievance",
        entity_id=g.id,
        state_after=g.status.value,
        metadata_json={
            "ticket_number": g.ticket_number,
            "resolution_notes": req.resolution_notes,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(g)
    return _build_grievance_out(g)
