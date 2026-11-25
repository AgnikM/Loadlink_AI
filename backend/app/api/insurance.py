import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.entities import InsurancePolicyRule, CargoInsurance, Load, Shipment, User, AuditLog
from app.models.enums import (
    UserRole, InsuranceAssessmentResult, InsuranceVerificationStatus,
    CargoCategory, FragilityLevel, HazardClass
)
from app.schemas.all_schemas import (
    InsuranceAssessmentRequest, InsuranceAssessmentOut,
    InsurancePolicyRuleCreate, InsurancePolicyRuleOut,
    CargoInsuranceUpload, CargoInsuranceVerify, CargoInsuranceOut
)
from app.services.insurance_service import InsuranceService

router = APIRouter(prefix="/insurance", tags=["cargo-insurance"])

def _build_rule_out(r: InsurancePolicyRule) -> InsurancePolicyRuleOut:
    return InsurancePolicyRuleOut(
        id=r.id,
        version=r.version,
        policy_name=r.policy_name,
        max_uninsured_value_inr=r.max_uninsured_value_inr,
        hazardous_requires_insurance=r.hazardous_requires_insurance,
        fragile_high_requires_insurance=r.fragile_high_requires_insurance,
        review_threshold_inr=r.review_threshold_inr,
        is_active=r.is_active,
        approved_by_name=r.approved_by.name if r.approved_by else None,
        created_at=r.created_at,
    )

def _build_insurance_out(ci: CargoInsurance) -> CargoInsuranceOut:
    permitted, _ = InsuranceService.is_dispatch_permitted(ci)
    return CargoInsuranceOut(
        id=ci.id,
        shipment_id=ci.shipment_id,
        booking_id=ci.booking_id,
        load_id=ci.load_id,
        assessment_result=ci.assessment_result,
        assessment_reasons=ci.assessment_reasons or [],
        policy_number=ci.policy_number,
        insurer_name=ci.insurer_name,
        policyholder_name=ci.policyholder_name,
        insured_party=ci.insured_party,
        coverage_amount_inr=ci.coverage_amount_inr or 0.0,
        valid_from=ci.valid_from,
        valid_to=ci.valid_to,
        exclusions=ci.exclusions,
        certificate_url=ci.certificate_url,
        verification_status=ci.verification_status,
        verified_by_name=ci.verified_by.name if ci.verified_by else None,
        verified_at=ci.verified_at,
        exception_permitted=ci.exception_permitted,
        exception_reason=ci.exception_reason,
        is_dispatch_allowed=permitted,
        created_at=ci.created_at,
    )

@router.post("/assess", response_model=InsuranceAssessmentOut)
async def assess_insurance_risk(
    req: InsuranceAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result, reasons, policy = await InsuranceService.assess_risk(
        cargo_category=req.cargo_category,
        declared_value_inr=req.declared_value_inr,
        fragility=req.fragility,
        hazard_class=req.hazard_class,
        db=db,
        route=req.route or "Kolkata ↔ Durgapur",
        transit_duration_hours=req.transit_duration_hours or 6.0,
    )
    return InsuranceAssessmentOut(
        assessment_result=result,
        reasons=reasons,
        max_uninsured_threshold_inr=policy.max_uninsured_value_inr,
        review_threshold_inr=policy.review_threshold_inr,
        policy_version=policy.version,
    )

@router.get("/policy-rules", response_model=List[InsurancePolicyRuleOut])
async def list_policy_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(InsurancePolicyRule).options(selectinload(InsurancePolicyRule.approved_by)).order_by(InsurancePolicyRule.version.desc())
    rules = (await db.execute(q)).scalars().all()
    return [_build_rule_out(r) for r in rules]

@router.post("/policy-rules", response_model=InsurancePolicyRuleOut)
async def create_policy_rule(
    req: InsurancePolicyRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(status_code=403, detail="Only Compliance Officer or Admin can configure insurance policy rules")

    # Get max current version
    q = select(InsurancePolicyRule).order_by(InsurancePolicyRule.version.desc())
    latest = (await db.execute(q)).scalars().first()
    new_version = (latest.version + 1) if latest else 1

    # Deactivate existing active rules
    q_all = select(InsurancePolicyRule).where(InsurancePolicyRule.is_active == True)
    actives = (await db.execute(q_all)).scalars().all()
    for a in actives:
        a.is_active = False

    rule = InsurancePolicyRule(
        id=str(uuid.uuid4()),
        version=new_version,
        policy_name=req.policy_name,
        max_uninsured_value_inr=req.max_uninsured_value_inr,
        hazardous_requires_insurance=req.hazardous_requires_insurance,
        fragile_high_requires_insurance=req.fragile_high_requires_insurance,
        review_threshold_inr=req.review_threshold_inr,
        is_active=True,
        approved_by_user_id=current_user.id,
    )
    db.add(rule)

    audit = AuditLog(
        actor_id=current_user.id,
        action="INSURANCE_POLICY_RULE_UPDATED",
        entity_name="InsurancePolicyRule",
        entity_id=rule.id,
        state_after=f"VERSION_{new_version}",
        metadata_json={
            "max_uninsured": req.max_uninsured_value_inr,
            "version": new_version,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(rule)
    return _build_rule_out(rule)

@router.post("/{target_id}/upload", response_model=CargoInsuranceOut)
async def upload_cargo_insurance(
    target_id: str,
    req: CargoInsuranceUpload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload policy information.
    NOTE: An uploaded document must NOT automatically become verified insurance.
    It enters PENDING_VERIFICATION until a Compliance Officer verifies it.
    """
    now = datetime.now(timezone.utc)

    # Check target (can be shipment_id, booking_id, or load_id)
    q_ship = select(Shipment).where((Shipment.id == target_id) | (Shipment.booking_id == target_id))
    shipment = (await db.execute(q_ship)).scalar_one_or_none()

    q_load = select(Load).where(Load.id == target_id)
    load = (await db.execute(q_load)).scalar_one_or_none()

    shipment_id = shipment.id if shipment else None
    booking_id = shipment.booking_id if shipment else target_id
    load_id = shipment.load_id if shipment else (load.id if load else None)

    # Find existing or create new
    q_ins = select(CargoInsurance).where(
        (CargoInsurance.shipment_id == target_id)
        | (CargoInsurance.booking_id == target_id)
        | (CargoInsurance.load_id == target_id)
        | (CargoInsurance.id == target_id)
    ).options(selectinload(CargoInsurance.verified_by))
    insurance = (await db.execute(q_ins)).scalar_one_or_none()

    # Assess risk if not assessed
    cat = load.cargo_category if load else CargoCategory.GENERAL_MERCHANDISE
    val = load.declared_value_inr if load else 250000.0
    frag = load.fragility if load else FragilityLevel.LOW
    haz = load.hazard_classification if load else HazardClass.NONE

    res, reasons, _ = await InsuranceService.assess_risk(cat, val, frag, haz, db)

    if not insurance:
        insurance = CargoInsurance(
            id=str(uuid.uuid4()),
            shipment_id=shipment_id,
            booking_id=booking_id,
            load_id=load_id,
            assessment_result=res,
            assessment_reasons=reasons,
        )
        db.add(insurance)

    insurance.policy_number = req.policy_number
    insurance.insurer_name = req.insurer_name
    insurance.policyholder_name = req.policyholder_name
    insurance.insured_party = req.insured_party
    insurance.coverage_amount_inr = req.coverage_amount_inr
    insurance.valid_from = req.valid_from
    insurance.valid_to = req.valid_to
    insurance.exclusions = req.exclusions
    insurance.certificate_url = req.certificate_url or "/uploads/insurance_cert.pdf"
    # An uploaded document must NOT automatically become verified insurance
    insurance.verification_status = InsuranceVerificationStatus.PENDING_VERIFICATION
    insurance.verified_by_user_id = None
    insurance.verified_at = None

    audit = AuditLog(
        actor_id=current_user.id,
        action="CARGO_INSURANCE_CERTIFICATE_UPLOADED",
        entity_name="CargoInsurance",
        entity_id=insurance.id,
        state_after="PENDING_VERIFICATION",
        metadata_json={
            "policy_number": req.policy_number,
            "insurer": req.insurer_name,
            "coverage_inr": req.coverage_amount_inr,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(insurance)
    return _build_insurance_out(insurance)

@router.patch("/{insurance_id}/verify", response_model=CargoInsuranceOut)
async def verify_cargo_insurance(
    insurance_id: str,
    req: CargoInsuranceVerify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(
            status_code=403,
            detail="Only Compliance Officer or Admin can verify insurance policies or approve exceptions",
        )

    q = select(CargoInsurance).where(
        (CargoInsurance.id == insurance_id)
        | (CargoInsurance.shipment_id == insurance_id)
        | (CargoInsurance.booking_id == insurance_id)
    ).options(selectinload(CargoInsurance.verified_by))
    insurance = (await db.execute(q)).scalar_one_or_none()
    if not insurance:
        raise HTTPException(status_code=404, detail="Cargo insurance record not found")

    now = datetime.now(timezone.utc)
    before = insurance.verification_status.value

    if req.action == "VERIFY":
        # Check if expired
        if insurance.valid_to:
            v_to = insurance.valid_to
            if v_to.tzinfo is None:
                v_to = v_to.replace(tzinfo=timezone.utc)
            if v_to < now:
                insurance.verification_status = InsuranceVerificationStatus.EXPIRED
                raise HTTPException(status_code=400, detail="Cannot verify an expired insurance certificate.")

        insurance.verification_status = InsuranceVerificationStatus.VERIFIED
        insurance.verified_by_user_id = current_user.id
        insurance.verified_at = now
        insurance.exception_permitted = False
    elif req.action == "APPROVE_EXCEPTION":
        insurance.verification_status = InsuranceVerificationStatus.EXCEPTION_APPROVED
        insurance.exception_permitted = True
        insurance.exception_reason = req.exception_reason or "Authorized executive waiver granted under approved policy"
        insurance.verified_by_user_id = current_user.id
        insurance.verified_at = now
    else:  # REJECT
        insurance.verification_status = InsuranceVerificationStatus.REJECTED
        insurance.verified_by_user_id = current_user.id
        insurance.verified_at = now

    audit = AuditLog(
        actor_id=current_user.id,
        action=f"CARGO_INSURANCE_{req.action}",
        entity_name="CargoInsurance",
        entity_id=insurance.id,
        state_before=before,
        state_after=insurance.verification_status.value,
        metadata_json={
            "action": req.action,
            "rejection_reason": req.rejection_reason,
            "exception_reason": req.exception_reason,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(insurance)
    return _build_insurance_out(insurance)

@router.get("/{target_id}", response_model=CargoInsuranceOut)
async def get_cargo_insurance(
    target_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(CargoInsurance).where(
        (CargoInsurance.id == target_id)
        | (CargoInsurance.shipment_id == target_id)
        | (CargoInsurance.booking_id == target_id)
        | (CargoInsurance.load_id == target_id)
    ).options(selectinload(CargoInsurance.verified_by))
    insurance = (await db.execute(q)).scalar_one_or_none()

    if not insurance:
        # Check if target is a load or booking and run auto-assessment
        q_load = select(Load).where((Load.id == target_id))
        load = (await db.execute(q_load)).scalar_one_or_none()
        if not load:
            q_ship = select(Shipment).where((Shipment.id == target_id) | (Shipment.booking_id == target_id)).options(selectinload(Shipment.load))
            ship = (await db.execute(q_ship)).scalar_one_or_none()
            load = ship.load if ship else None

        cat = load.cargo_category if load else CargoCategory.GENERAL_MERCHANDISE
        val = load.declared_value_inr if load else 100000.0
        frag = load.fragility if load else FragilityLevel.LOW
        haz = load.hazard_classification if load else HazardClass.NONE

        res, reasons, _ = await InsuranceService.assess_risk(cat, val, frag, haz, db)
        insurance = CargoInsurance(
            id=str(uuid.uuid4()),
            booking_id=target_id,
            load_id=load.id if load else None,
            assessment_result=res,
            assessment_reasons=reasons,
            verification_status=InsuranceVerificationStatus.UNASSESSED if res != InsuranceAssessmentResult.NOT_REQUIRED else InsuranceVerificationStatus.VERIFIED,
        )
        db.add(insurance)
        await db.commit()
        await db.refresh(insurance)

    return _build_insurance_out(insurance)
