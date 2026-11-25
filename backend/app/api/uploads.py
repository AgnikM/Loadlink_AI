import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token, oauth2_scheme_optional
from app.models.entities import (
    User, POD, CargoInsurance, DirectPayment, DisputeEvidence, Shipment, Dealer, Driver, Transporter, Truck
)
from app.models.enums import UserRole, VerificationStatus

router = APIRouter(tags=["documents-uploads"])

async def get_current_user_flexible(
    token_query: Optional[str] = Query(None, alias="token"),
    bearer_token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate user via Bearer header or query token parameter (?token=...).
    Enables authenticated document viewing in browser links and <img> tags.
    """
    token = bearer_token or token_query
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view sensitive documents.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    query = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.dealer_profile),
            selectinload(User.driver_profile),
            selectinload(User.transporter_profile),
        )
    )
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.verification_status == VerificationStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended.")

    return user

@router.get("/uploads/{file_path:path}")
@router.get(f"{settings.API_V1_STR}/uploads/{{file_path:path}}")
async def get_uploaded_document(
    file_path: str,
    current_user: User = Depends(get_current_user_flexible),
    db: AsyncSession = Depends(get_db),
):
    """
    Secure authenticated document retrieval (Master Prompt 2.1 Task 1).
    - Removes unauthenticated public file exposure.
    - Enforces document ownership and role-based access control.
    - Prevents directory traversal attacks.
    - Preserves existing /uploads/... URL paths.
    """
    # 1. Path traversal security check
    clean_rel = os.path.normpath(file_path).lstrip("/\\")
    if ".." in clean_rel.split(os.path.sep):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path sequence.")

    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    full_path = os.path.abspath(os.path.join(upload_root, clean_rel))
    if not full_path.startswith(upload_root):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access outside upload directory forbidden.")

    # 2. Check if file exists on disk
    if not os.path.exists(full_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested document not found.")

    # 3. Role & Ownership Access Control
    # Admins and Control Room operators have full operational oversight
    if current_user.role in [UserRole.ADMIN, UserRole.CONTROL_ROOM]:
        return FileResponse(full_path)

    filename_match = os.path.basename(clean_rel)

    # Check A: Proof of Delivery (POD) documents
    q_pod = (
        select(POD)
        .where(POD.file_url.like(f"%{filename_match}%"))
        .options(
            selectinload(POD.shipment).selectinload(Shipment.truck),
            selectinload(POD.shipment).selectinload(Shipment.driver),
            selectinload(POD.shipment).selectinload(Shipment.dealer),
        )
    )
    pod = (await db.execute(q_pod)).scalar_one_or_none()
    if pod:
        # Compliance officers and Fleet managers can review PODs
        if current_user.role in [UserRole.COMPLIANCE_OFFICER, UserRole.FLEET_MANAGER]:
            return FileResponse(full_path)

        # Check assigned driver
        if (
            current_user.role == UserRole.DRIVER
            and current_user.driver_profile
            and (
                pod.submitted_by_driver_id == current_user.driver_profile.id
                or (pod.shipment and pod.shipment.driver_id == current_user.driver_profile.id)
            )
        ):
            return FileResponse(full_path)

        # Check owning dealer
        if (
            current_user.role == UserRole.DEALER
            and current_user.dealer_profile
            and pod.shipment
            and pod.shipment.dealer_id == current_user.dealer_profile.id
        ):
            return FileResponse(full_path)

        # Check transporter of the vehicle
        if (
            current_user.role == UserRole.TRANSPORTER
            and current_user.transporter_profile
            and pod.shipment
            and pod.shipment.truck
            and (
                pod.shipment.truck.transporter_id == current_user.transporter_profile.id
                or pod.shipment.truck.organization_id == current_user.transporter_profile.organization_id
            )
        ):
            return FileResponse(full_path)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view this Proof of Delivery (POD).",
        )

    # Check B: Cargo Insurance certificates
    q_ins = (
        select(CargoInsurance)
        .where(CargoInsurance.certificate_url.like(f"%{filename_match}%"))
        .options(
            selectinload(CargoInsurance.shipment).selectinload(Shipment.truck),
            selectinload(CargoInsurance.shipment).selectinload(Shipment.driver),
            selectinload(CargoInsurance.shipment).selectinload(Shipment.dealer),
        )
    )
    ins = (await db.execute(q_ins)).scalar_one_or_none()
    if ins:
        if current_user.role in [UserRole.COMPLIANCE_OFFICER, UserRole.FLEET_MANAGER]:
            return FileResponse(full_path)

        if ins.shipment:
            if current_user.role == UserRole.DEALER and current_user.dealer_profile and ins.shipment.dealer_id == current_user.dealer_profile.id:
                return FileResponse(full_path)
            if current_user.role == UserRole.DRIVER and current_user.driver_profile and ins.shipment.driver_id == current_user.driver_profile.id:
                return FileResponse(full_path)
            if current_user.role == UserRole.TRANSPORTER and current_user.transporter_profile and ins.shipment.truck and ins.shipment.truck.organization_id == current_user.transporter_profile.organization_id:
                return FileResponse(full_path)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view this cargo insurance certificate.",
        )

    # Check C: Direct Payment receipts / bank evidence
    q_pay = select(DirectPayment).where(DirectPayment.payment_evidence_url.like(f"%{filename_match}%"))
    pay = (await db.execute(q_pay)).scalar_one_or_none()
    if pay:
        if current_user.role in [UserRole.COMPLIANCE_OFFICER, UserRole.DISPUTE_OFFICER]:
            return FileResponse(full_path)

        if pay.payer_user_id == current_user.id or pay.payee_user_id == current_user.id:
            return FileResponse(full_path)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not a party to this payment transaction.",
        )

    # Check D: Dispute evidence files
    q_disp = (
        select(DisputeEvidence)
        .where(DisputeEvidence.file_url.like(f"%{filename_match}%"))
        .options(selectinload(DisputeEvidence.dispute))
    )
    disp_ev = (await db.execute(q_disp)).scalar_one_or_none()
    if disp_ev:
        if current_user.role == UserRole.DISPUTE_OFFICER:
            return FileResponse(full_path)

        if disp_ev.uploaded_by_user_id == current_user.id:
            return FileResponse(full_path)

        if disp_ev.dispute and (
            disp_ev.dispute.raised_by_user_id == current_user.id
            or disp_ev.dispute.respondent_user_id == current_user.id
        ):
            return FileResponse(full_path)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view this dispute evidence.",
        )

    # Default fallback: If file is in storage but not registered under a private entity,
    # allow authenticated platform users (dealer, driver, transporter, staff)
    return FileResponse(full_path)
