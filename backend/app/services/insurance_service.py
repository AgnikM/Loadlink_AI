from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import InsurancePolicyRule, CargoInsurance, Load, Shipment
from app.models.enums import (
    InsuranceAssessmentResult, InsuranceVerificationStatus,
    CargoCategory, FragilityLevel, HazardClass
)

class InsuranceService:
    @staticmethod
    async def get_active_policy(db: AsyncSession) -> InsurancePolicyRule:
        q = (
            select(InsurancePolicyRule)
            .where(InsurancePolicyRule.is_active == True)
            .order_by(InsurancePolicyRule.version.desc())
        )
        res = await db.execute(q)
        policy = res.scalars().first()
        if not policy:
            # Fallback policy rule
            policy = InsurancePolicyRule(
                version=1,
                policy_name="Standard Bengal Corridor Freight Policy",
                max_uninsured_value_inr=200000.0,
                hazardous_requires_insurance=True,
                fragile_high_requires_insurance=True,
                review_threshold_inr=2000000.0,
                is_active=True,
            )
            db.add(policy)
            await db.flush()
        return policy

    @staticmethod
    async def assess_risk(
        cargo_category: CargoCategory,
        declared_value_inr: float,
        fragility: FragilityLevel,
        hazard_class: HazardClass,
        db: AsyncSession,
        route: str = "Kolkata ↔ Durgapur",
        transit_duration_hours: float = 6.0,
    ) -> Tuple[InsuranceAssessmentResult, List[str], InsurancePolicyRule]:
        policy = await InsuranceService.get_active_policy(db)
        reasons: List[str] = []

        # 1. High value threshold requiring review
        if declared_value_inr >= policy.review_threshold_inr:
            reasons.append(
                f"Declared value of ₹{declared_value_inr:,.0f} exceeds high-risk underwriting threshold of ₹{policy.review_threshold_inr:,.0f}. Compliance Officer review required."
            )
            return InsuranceAssessmentResult.REVIEW_REQUIRED, reasons, policy

        # 2. Hazardous material requirement
        if hazard_class != HazardClass.NONE and policy.hazardous_requires_insurance:
            reasons.append(
                f"Hazardous classification [{hazard_class.value}] requires mandatory carrier transit insurance under Motor Vehicles Act."
            )

        # 3. Fragility requirement
        if fragility == FragilityLevel.HIGH and policy.fragile_high_requires_insurance:
            reasons.append(
                "High cargo fragility indicates elevated damage risk along highway corridor. Insurance required."
            )

        # 4. Cargo Category specific risk
        if cargo_category in [CargoCategory.ELECTRONICS_HIGH_VALUE, CargoCategory.CHEMICALS_HAZARDOUS]:
            reasons.append(
                f"Cargo category [{cargo_category.value}] carries elevated theft or environmental liability risk."
            )

        # 5. Value exceeds uninsured ceiling
        if declared_value_inr > policy.max_uninsured_value_inr:
            reasons.append(
                f"Declared value of ₹{declared_value_inr:,.0f} exceeds approved un-insured threshold of ₹{policy.max_uninsured_value_inr:,.0f} under Policy v{policy.version}."
            )

        if reasons:
            return InsuranceAssessmentResult.REQUIRED, reasons, policy

        reasons.append(
            f"Consignment value ₹{declared_value_inr:,.0f} falls within approved low-risk uninsured corridor limit (₹{policy.max_uninsured_value_inr:,.0f})."
        )
        return InsuranceAssessmentResult.NOT_REQUIRED, reasons, policy

    @staticmethod
    def is_dispatch_permitted(insurance: CargoInsurance) -> Tuple[bool, str]:
        if not insurance:
            return True, "No insurance assessment on file"

        if insurance.assessment_result == InsuranceAssessmentResult.NOT_REQUIRED:
            return True, "Insurance not required under active risk policy"

        now = datetime.now(timezone.utc)

        # Check for policy expiration if dates provided
        if insurance.valid_to:
            v_to = insurance.valid_to
            if v_to.tzinfo is None:
                v_to = v_to.replace(tzinfo=timezone.utc)
            if v_to < now:
                return False, f"Cargo insurance policy expired on {v_to.strftime('%Y-%m-%d')}. Dispatch blocked until policy renewed."

        if insurance.verification_status in [
            InsuranceVerificationStatus.VERIFIED,
            InsuranceVerificationStatus.EXCEPTION_APPROVED,
        ]:
            return True, f"Insurance approved ({insurance.verification_status.value})"

        return (
            False,
            f"Insurance status is {insurance.verification_status.value}. Dispatch blocked until verified by Compliance Officer or an authorized exception is granted.",
        )
