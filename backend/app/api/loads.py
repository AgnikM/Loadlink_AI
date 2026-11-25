from typing import List, Optional
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user, get_current_user_optional
from app.models.entities import Load, Dealer, User, Match, CargoInsurance
from app.models.enums import (
    UserRole, LoadStatus, CargoCategory, FragilityLevel, HazardClass,
    InsuranceAssessmentResult, InsuranceVerificationStatus
)
from app.schemas.all_schemas import LoadCreate, LoadOut
from app.services.routing_service import routing_service
from app.services.pricing_service import pricing_service
from app.services.insurance_service import InsuranceService

router = APIRouter(prefix="/loads", tags=["loads"])

def _build_load_out(load: Load, dealer_name: Optional[str] = None, matches_count: int = 0) -> LoadOut:
    return LoadOut(
        id=load.id,
        dealer_id=load.dealer_id,
        dealer_name=dealer_name or (load.dealer.user.name if (load.dealer and load.dealer.user) else "Bengal Steel"),
        origin_name=load.origin_name,
        origin_lat=load.origin_lat,
        origin_lon=load.origin_lon,
        destination_name=load.destination_name,
        destination_lat=load.destination_lat,
        destination_lon=load.destination_lon,
        cargo_type=load.cargo_type,
        cargo_category=load.cargo_category or CargoCategory.GENERAL_MERCHANDISE,
        cargo_description=load.cargo_description,
        cargo_weight_tons=load.cargo_weight_tons,
        declared_value_inr=load.declared_value_inr or 100000.0,
        fragility=load.fragility or FragilityLevel.LOW,
        hazard_classification=load.hazard_classification or HazardClass.NONE,
        handling_instructions=load.handling_instructions,
        supporting_documents=load.supporting_documents or [],
        required_truck_type=load.required_truck_type,
        min_capacity_tons=load.min_capacity_tons,
        max_capacity_tons=load.max_capacity_tons,
        pickup_window_start=load.pickup_window_start,
        pickup_window_end=load.pickup_window_end,
        target_budget=load.target_budget,
        estimated_benchmark_price=load.estimated_benchmark_price,
        cargo_notes=load.cargo_notes,
        status=load.status,
        created_at=load.created_at,
        matches_count=matches_count,
    )

@router.post("", response_model=LoadOut)
async def create_load(
    req: LoadCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    dealer_id = None
    dealer_user = None

    if current_user and current_user.role == UserRole.DEALER and current_user.dealer_profile:
        dealer_id = current_user.dealer_profile.id
        dealer_user = current_user
    else:
        # Fallback to demo dealer
        q_dealer = select(Dealer).options(selectinload(Dealer.user))
        res_dealer = await db.execute(q_dealer)
        dealer_obj = res_dealer.scalars().first()
        if dealer_obj:
            dealer_id = dealer_obj.id
            dealer_user = dealer_obj.user
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No registered dealer profile found to create load under.",
            )

    cargo_weight = req.cargo_weight_tons or 15.0
    min_cap = req.min_capacity_tons or max(1.0, cargo_weight - 2.0)
    max_cap = req.max_capacity_tons or (cargo_weight + 10.0)

    # 1. Validation (PRD FR-06)
    if cargo_weight <= 0.0 or cargo_weight > 55.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cargo weight. Weight must be between 0.1 and 55.0 metric tons.",
        )
    if min_cap > max_cap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum truck capacity cannot exceed maximum truck capacity.",
        )
    if cargo_weight > max_cap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cargo weight exceeds specified maximum truck capacity.",
        )
    
    # Coordinate boundary sanity checks
    origin_lat = req.origin_lat if req.origin_lat is not None else 22.5448
    origin_lon = req.origin_lon if req.origin_lon is not None else 88.3186
    dest_lat = req.destination_lat if req.destination_lat is not None else 23.5204
    dest_lon = req.destination_lon if req.destination_lon is not None else 87.3119

    if not (-90 <= origin_lat <= 90 and -180 <= origin_lon <= 180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid origin coordinates.")
    if not (-90 <= dest_lat <= 90 and -180 <= dest_lon <= 180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid destination coordinates.")

    p_start = req.pickup_window_start or datetime.now(timezone.utc)
    p_end = req.pickup_window_end or (p_start + timezone.timedelta(hours=18) if hasattr(timezone, "timedelta") else p_start)
    if p_start >= p_end:
        p_end = datetime.fromtimestamp(p_start.timestamp() + 3600 * 18, tz=timezone.utc)

    # 2. Estimate corridor distance and benchmark price
    route_info = await routing_service.get_route(origin_lat, origin_lon, dest_lat, dest_lon)
    dist_km = route_info["distance_km"]
    price_est = pricing_service.estimate_freight(
        distance_km=dist_km,
        weight_tons=cargo_weight,
        truck_type=req.required_truck_type,
        target_budget=req.target_budget
    )

    cat = req.cargo_category or CargoCategory.GENERAL_MERCHANDISE
    decl_val = req.declared_value_inr or 100000.0
    frag = req.fragility or FragilityLevel.LOW
    haz = req.hazard_classification or HazardClass.NONE

    load = Load(
        dealer_id=dealer_id,
        origin_name=req.origin_name or "Kolkata Port / Docks",
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        destination_name=req.destination_name or "Durgapur Steel Complex",
        destination_lat=dest_lat,
        destination_lon=dest_lon,
        cargo_type=req.cargo_type or "Industrial Freight",
        cargo_category=cat,
        cargo_description=req.cargo_description,
        cargo_weight_tons=cargo_weight,
        declared_value_inr=decl_val,
        fragility=frag,
        hazard_classification=haz,
        handling_instructions=req.handling_instructions,
        supporting_documents=req.supporting_documents or [],
        required_truck_type=req.required_truck_type,
        min_capacity_tons=min_cap,
        max_capacity_tons=max_cap,
        pickup_window_start=p_start,
        pickup_window_end=p_end,
        target_budget=req.target_budget or price_est["estimated_median_inr"],
        estimated_benchmark_price=price_est["estimated_median_inr"],
        cargo_notes=req.cargo_notes,
        status=LoadStatus.POSTED,
    )
    db.add(load)
    
    if current_user and current_user.dealer_profile:
        current_user.dealer_profile.total_loads_posted += 1

    # Automated Risk-Based Insurance Assessment on Load Creation
    res_assessment, reasons, _ = await InsuranceService.assess_risk(cat, decl_val, frag, haz, db)
    ins = CargoInsurance(
        id=str(uuid.uuid4()),
        load_id=load.id,
        assessment_result=res_assessment,
        assessment_reasons=reasons,
        coverage_amount_inr=decl_val if res_assessment != InsuranceAssessmentResult.NOT_REQUIRED else 0.0,
        verification_status=InsuranceVerificationStatus.UNASSESSED if res_assessment != InsuranceAssessmentResult.NOT_REQUIRED else InsuranceVerificationStatus.VERIFIED,
    )
    db.add(ins)
    
    await db.commit()
    await db.refresh(load)

    return _build_load_out(load, dealer_name=dealer_user.name if dealer_user else "Bengal Steel", matches_count=0)

@router.get("", response_model=List[LoadOut])
async def list_loads(
    status_filter: Optional[LoadStatus] = None,
    only_my_loads: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Load)
        .options(
            selectinload(Load.dealer).selectinload(Dealer.user),
            selectinload(Load.matches),
        )
        .order_by(Load.created_at.desc())
    )

    if only_my_loads and current_user and current_user.role == UserRole.DEALER and current_user.dealer_profile:
        query = query.where(Load.dealer_id == current_user.dealer_profile.id)
    elif status_filter:
        query = query.where(Load.status == status_filter)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    loads = result.scalars().all()

    return [_build_load_out(l, matches_count=len(l.matches)) for l in loads]

@router.get("/{load_id}", response_model=LoadOut)
async def get_load_detail(
    load_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Load)
        .where(Load.id == load_id)
        .options(
            selectinload(Load.dealer).selectinload(Dealer.user),
            selectinload(Load.matches),
        )
    )
    result = await db.execute(query)
    l = result.scalar_one_or_none()
    if not l:
        raise HTTPException(status_code=404, detail="Load not found")

    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if l.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to inspect another dealer's private load.",
            )

    return _build_load_out(l, matches_count=len(l.matches))
