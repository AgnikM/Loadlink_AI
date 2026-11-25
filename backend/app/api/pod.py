import os
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import settings
from app.api.auth import get_current_user
from app.models.entities import POD, Shipment, User, AuditLog
from app.models.enums import UserRole, PODStatus, ShipmentState
from app.schemas.all_schemas import PODOut, PODVerifyRequest
from app.services.storage_service import storage_service
from app.services.state_machine import state_machine

router = APIRouter(prefix="/shipments", tags=["pod"])

@router.post("/{shipment_id}/pod", response_model=PODOut)
async def submit_pod(
    shipment_id: str,
    receiver_name: str = Form(...),
    receiver_phone: Optional[str] = Form(None),
    receiver_signature_notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.DRIVER or not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned driver can submit Proof of Delivery (POD).",
        )

    # 1. Fetch shipment
    q = select(Shipment).where(Shipment.id == shipment_id).options(selectinload(Shipment.pod))
    res = await db.execute(q)
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    if s.driver_id != current_user.driver_profile.id:
        raise HTTPException(status_code=403, detail="Driver is not assigned to this shipment.")

    # 2. Save uploaded file securely
    file_url = await storage_service.save_upload_file(file, folder="pods")
    now = datetime.now(timezone.utc)

    # 3. Create or update POD
    pod = s.pod
    if not pod:
        pod = POD(
            shipment_id=s.id,
            file_url=file_url,
            file_name=file.filename or "pod_document.jpg",
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            receiver_signature_notes=receiver_signature_notes,
            submitted_by_driver_id=current_user.driver_profile.id,
            submitted_at=now,
            verification_status=PODStatus.PENDING_REVIEW,
        )
        db.add(pod)
    else:
        pod.file_url = file_url
        pod.file_name = file.filename or pod.file_name
        pod.receiver_name = receiver_name
        pod.receiver_phone = receiver_phone
        pod.receiver_signature_notes = receiver_signature_notes
        pod.submitted_at = now
        pod.verification_status = PODStatus.PENDING_REVIEW

    # 4. Advance shipment state to POD_SUBMITTED (if not already)
    if s.state in [ShipmentState.DELIVERED, ShipmentState.IN_TRANSIT, ShipmentState.NEAR_DESTINATION]:
        s.state = ShipmentState.POD_SUBMITTED
        s.updated_at = now

    audit = AuditLog(
        actor_id=current_user.id,
        action="POD_SUBMITTED",
        entity_name="POD",
        entity_id=pod.id if pod.id else s.id,
        state_after="PENDING_REVIEW",
        metadata_json={"file_name": pod.file_name, "receiver_name": receiver_name},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(pod)

    return PODOut(
        id=pod.id,
        shipment_id=pod.shipment_id,
        file_url=pod.file_url,
        file_name=pod.file_name,
        receiver_name=pod.receiver_name,
        receiver_phone=pod.receiver_phone,
        receiver_signature_notes=pod.receiver_signature_notes,
        submitted_at=pod.submitted_at,
        verification_status=pod.verification_status,
        verified_at=pod.verified_at,
        rejection_reason=pod.rejection_reason,
    )

@router.patch("/{shipment_id}/pod/verify", response_model=PODOut)
async def verify_pod(
    shipment_id: str,
    req: PODVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.DEALER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Dealer or Admin can verify Proof of Delivery.",
        )

    q = (
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(
            selectinload(Shipment.pod),
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver),
        )
    )
    res = await db.execute(q)
    s = res.scalar_one_or_none()
    if not s or not s.pod:
        raise HTTPException(status_code=404, detail="Shipment or POD not found")

    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if s.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(status_code=403, detail="Access denied: Cannot verify POD for another dealer's shipment.")

    now = datetime.now(timezone.utc)
    pod = s.pod

    if req.action.upper() == "VERIFY":
        pod.verification_status = PODStatus.VERIFIED
        pod.verified_by_user_id = current_user.id
        pod.verified_at = now
        # Advance shipment to COMPLETED
        await state_machine.transition(
            session=db,
            shipment=s,
            target_state=ShipmentState.COMPLETED,
            actor_user=current_user,
            note="POD verified and approved.",
        )
    elif req.action.upper() == "REJECT":
        pod.verification_status = PODStatus.REJECTED
        pod.rejection_reason = req.rejection_reason or "Document unreadable / signature mismatch"
        pod.verified_by_user_id = current_user.id
        pod.verified_at = now
        # Shift to DISPUTED / review state
        s.state = ShipmentState.DISPUTED

    await db.commit()
    await db.refresh(pod)

    return PODOut(
        id=pod.id,
        shipment_id=pod.shipment_id,
        file_url=pod.file_url,
        file_name=pod.file_name,
        receiver_name=pod.receiver_name,
        receiver_phone=pod.receiver_phone,
        receiver_signature_notes=pod.receiver_signature_notes,
        submitted_at=pod.submitted_at,
        verification_status=pod.verification_status,
        verified_at=pod.verified_at,
        rejection_reason=pod.rejection_reason,
    )

@router.get("/{shipment_id}/pod/file")
async def download_pod_file(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Secure file streaming endpoint (PRD FR-14, Sec 14).
    Validates user authorization before serving delivery documents.
    """
    q = select(Shipment).where(Shipment.id == shipment_id).options(selectinload(Shipment.pod))
    res = await db.execute(q)
    s = res.scalar_one_or_none()
    if not s or not s.pod:
        raise HTTPException(status_code=404, detail="Shipment or POD file not found")

    # Verify authorization
    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if s.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == UserRole.DRIVER and current_user.driver_profile:
        if s.driver_id != current_user.driver_profile.id:
            raise HTTPException(status_code=403, detail="Access denied")

    # Determine local file path
    rel_path = s.pod.file_url.lstrip("/uploads/")
    full_path = os.path.join(settings.UPLOAD_DIR, rel_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File on disk not found")

    return FileResponse(full_path, filename=s.pod.file_name)
