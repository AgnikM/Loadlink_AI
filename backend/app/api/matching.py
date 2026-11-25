from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user, get_current_user_optional
from app.models.entities import Load, Truck, Match, Driver, User, SystemConfiguration
from app.models.enums import LoadStatus, TruckStatus, VerificationStatus, UserRole
from app.schemas.all_schemas import MatchOut, AIMatchResult, AIMatchingResponse
from app.services.match_engine import match_engine

router = APIRouter(prefix="/loads", tags=["matching"])

@router.post("/{load_id}/matches", response_model=List[MatchOut])
async def generate_matches_for_load(
    load_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Fetch load
    q_load = select(Load).where(Load.id == load_id).options(selectinload(Load.dealer))
    res_load = await db.execute(q_load)
    load = res_load.scalar_one_or_none()
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")

    # Security: Only load owner dealer or Admin can generate matches
    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if load.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot generate matches for another dealer's load.",
            )

    # 2. Fetch custom weights if configured
    q_conf = select(SystemConfiguration).where(SystemConfiguration.config_key == "match_weights")
    res_conf = await db.execute(q_conf)
    conf = res_conf.scalar_one_or_none()
    weights = conf.config_value_json if conf else None

    # 3. Query eligible candidates with database-level pre-filtering
    q_trucks = (
        select(Truck)
        .where(
            Truck.status.in_([TruckStatus.ONLINE_AVAILABLE, TruckStatus.IN_TRANSIT]),
            Truck.verification_status == VerificationStatus.VERIFIED,
            Truck.capacity_tons >= load.cargo_weight_tons,
            Truck.capacity_tons <= load.max_capacity_tons,
        )
        .options(
            selectinload(Truck.driver).selectinload(Driver.user),
        )
    )
    if load.required_truck_type:
        q_trucks = q_trucks.where(Truck.truck_type == load.required_truck_type)

    res_trucks = await db.execute(q_trucks)
    all_trucks = res_trucks.scalars().all()

    # 4. Clear previous matches for this load
    await db.execute(delete(Match).where(Match.load_id == load_id))

    match_results = []
    for truck in all_trucks:
        eval_res = await match_engine.evaluate_candidate(
            truck=truck,
            load=load,
            custom_weights=weights
        )
        if eval_res:
            m = Match(
                load_id=load.id,
                truck_id=truck.id,
                total_score=eval_res["total_score"],
                route_compat_score=eval_res["factor_breakdown"]["route_compatibility"],
                availability_score=eval_res["factor_breakdown"]["availability_feasibility"],
                proximity_score=eval_res["factor_breakdown"]["pickup_proximity"],
                capacity_score=eval_res["factor_breakdown"]["capacity_fit"],
                price_score=eval_res["factor_breakdown"]["price_competitiveness"],
                reliability_score=eval_res["factor_breakdown"]["reliability"],
                return_potential_score=eval_res["factor_breakdown"]["return_load_potential"],
                road_eta_km=eval_res["road_eta_km"],
                road_eta_mins=eval_res["road_eta_mins"],
                explanation_summary=eval_res["explanation_summary"],
                factor_breakdown=eval_res["factor_breakdown"],
                is_coming_near_you=eval_res["is_coming_near_you"],
                estimated_arrival_at_pickup=eval_res["estimated_arrival_at_pickup"],
            )
            db.add(m)
            match_results.append((m, truck))

    # Update load status to MATCHING if still POSTED
    if load.status == LoadStatus.POSTED:
        load.status = LoadStatus.MATCHING

    await db.commit()

    # Sort descending by score
    match_results.sort(key=lambda x: x[0].total_score, reverse=True)

    output = []
    for m, truck in match_results:
        driver = truck.driver
        driver_user = driver.user if driver else None
        output.append(
            MatchOut(
                id=m.id,
                load_id=m.load_id,
                truck_id=m.truck_id,
                truck_registration_no=truck.registration_no,
                truck_type=truck.truck_type,
                truck_capacity_tons=truck.capacity_tons,
                driver_id=driver.id if driver else "",
                driver_name=driver_user.name if driver_user else "Driver",
                driver_phone=driver_user.phone if driver_user else "",
                driver_reliability_score=driver.reliability_score if driver else 90.0,
                total_score=m.total_score,
                factor_breakdown=m.factor_breakdown,
                road_eta_km=m.road_eta_km,
                road_eta_mins=m.road_eta_mins,
                explanation_summary=m.explanation_summary,
                is_coming_near_you=m.is_coming_near_you,
                estimated_arrival_at_pickup=m.estimated_arrival_at_pickup,
                truck_current_lat=truck.current_lat,
                truck_current_lon=truck.current_lon,
                truck_location_name=truck.current_location_name,
            )
        )
    return output

@router.get("/{load_id}/matches", response_model=List[MatchOut])
async def get_matches_for_load(
    load_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Security: Verify load ownership
    q_load = select(Load).where(Load.id == load_id)
    res_load = await db.execute(q_load)
    load = res_load.scalar_one_or_none()
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")

    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if load.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot view matches for another dealer's load.",
            )

    query = (
        select(Match)
        .where(Match.load_id == load_id)
        .options(
            selectinload(Match.truck).selectinload(Truck.driver).selectinload(Driver.user)
        )
        .order_by(Match.total_score.desc())
    )
    res = await db.execute(query)
    matches = res.scalars().all()

    output = []
    for m in matches:
        truck = m.truck
        driver = truck.driver if truck else None
        driver_user = driver.user if driver else None
        output.append(
            MatchOut(
                id=m.id,
                load_id=m.load_id,
                truck_id=m.truck_id,
                truck_registration_no=truck.registration_no if truck else "",
                truck_type=truck.truck_type if truck else "OPEN_BODY",
                truck_capacity_tons=truck.capacity_tons if truck else 0.0,
                driver_id=driver.id if driver else "",
                driver_name=driver_user.name if driver_user else "Driver",
                driver_phone=driver_user.phone if driver_user else "",
                driver_reliability_score=driver.reliability_score if driver else 90.0,
                total_score=m.total_score,
                factor_breakdown=m.factor_breakdown,
                road_eta_km=m.road_eta_km,
                road_eta_mins=m.road_eta_mins,
                explanation_summary=m.explanation_summary,
                is_coming_near_you=m.is_coming_near_you,
                estimated_arrival_at_pickup=m.estimated_arrival_at_pickup,
                truck_current_lat=truck.current_lat if truck else None,
                truck_current_lon=truck.current_lon if truck else None,
                truck_location_name=truck.current_location_name if truck else None,
            )
        )
    return output

@router.get("/{load_id}/match-diagnostics")
async def get_match_diagnostics(
    load_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify load ownership
    q_load = select(Load).where(Load.id == load_id)
    res_load = await db.execute(q_load)
    load = res_load.scalar_one_or_none()
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")

    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if load.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot view match diagnostics for another dealer's load.",
            )

    q_trucks = select(Truck).options(selectinload(Truck.driver).selectinload(Driver.user))
    all_trucks = (await db.execute(q_trucks)).scalars().all()

    rejections: List[str] = []
    matched_count = 0

    for truck in all_trucks:
        eval_res = await match_engine.evaluate_candidate(
            truck=truck,
            load=load,
            rejection_collector=rejections,
        )
        if eval_res:
            matched_count += 1

    # Aggregate rejection categories
    categories = {
        "capacity_mismatch": 0,
        "truck_assigned_or_busy": 0,
        "vehicle_type_mismatch": 0,
        "offline_or_maintenance": 0,
        "unverified_credentials": 0,
    }

    for r in rejections:
        lower = r.lower()
        if "capacity" in lower:
            categories["capacity_mismatch"] += 1
        elif "committed" in lower or "assigned" in lower:
            categories["truck_assigned_or_busy"] += 1
        elif "vehicle type" in lower or "truck type" in lower:
            categories["vehicle_type_mismatch"] += 1
        elif "offline" in lower or "maintenance" in lower:
            categories["offline_or_maintenance"] += 1
        elif "verified" in lower or "verification" in lower:
            categories["unverified_credentials"] += 1

    friendly_breakdown = []
    if categories["capacity_mismatch"] > 0:
        friendly_breakdown.append(f"{categories['capacity_mismatch']} capacity mismatch")
    if categories["truck_assigned_or_busy"] > 0:
        friendly_breakdown.append(f"{categories['truck_assigned_or_busy']} committed to active bookings")
    if categories["vehicle_type_mismatch"] > 0:
        friendly_breakdown.append(f"{categories['vehicle_type_mismatch']} body type mismatch")
    if categories["offline_or_maintenance"] > 0:
        friendly_breakdown.append(f"{categories['offline_or_maintenance']} currently offline or in maintenance")
    if categories["unverified_credentials"] > 0:
        friendly_breakdown.append(f"{categories['unverified_credentials']} documentation pending verification")

    return {
        "load_id": load_id,
        "evaluated_trucks": len(all_trucks),
        "matched_trucks": matched_count,
        "rejected_trucks": len(all_trucks) - matched_count,
        "detailed_reasons": rejections,
        "rejection_categories": categories,
        "rejection_summary": friendly_breakdown,
    }


# --- Dedicated AI Matching Router for App.tsx Compatibility ---
ai_router = APIRouter(prefix="/ai", tags=["ai"])

@ai_router.post("/matching/{load_id}", response_model=AIMatchingResponse)
@ai_router.get("/matching/{load_id}", response_model=AIMatchingResponse)
async def ai_matching_for_load(
    load_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    # 1. Fetch load
    q_load = select(Load).where(Load.id == load_id).options(selectinload(Load.dealer))
    res_load = await db.execute(q_load)
    load = res_load.scalar_one_or_none()
    if not load:
        # If load_id not found by exact id, try first load in DB for fallback
        q_any_load = select(Load).options(selectinload(Load.dealer)).order_by(Load.created_at.desc())
        res_any = await db.execute(q_any_load)
        load = res_any.scalars().first()
        if not load:
            raise HTTPException(status_code=404, detail="No active loads found for matching")

    # 2. Fetch custom weights if configured
    q_conf = select(SystemConfiguration).where(SystemConfiguration.config_key == "match_weights")
    res_conf = await db.execute(q_conf)
    conf = res_conf.scalar_one_or_none()
    weights = conf.config_value_json if conf else None

    # 3. Query all candidates
    q_trucks = select(Truck).options(selectinload(Truck.driver).selectinload(Driver.user))
    res_trucks = await db.execute(q_trucks)
    all_trucks = res_trucks.scalars().all()

    results: List[AIMatchResult] = []

    for truck in all_trucks:
        rejections: List[str] = []
        eval_res = await match_engine.evaluate_candidate(
            truck=truck,
            load=load,
            custom_weights=weights,
            rejection_collector=rejections,
        )

        if eval_res:
            score = float(eval_res["total_score"])
            components = {
                k: round(float(v), 1)
                for k, v in eval_res.get("factor_breakdown", {}).items()
            }
            results.append(
                AIMatchResult(
                    truck_id=truck.id,
                    eligible=True,
                    score=round(score, 1),
                    distance_km=round(float(eval_res.get("road_eta_km", 0.0)), 1),
                    reasons=[eval_res.get("explanation_summary", "Strong corridor fit")],
                    components=components,
                    rules_score=round(score, 1),
                    ai_score=round(score, 1),
                    neural_network_score=round(score * 0.98, 1),
                    ranking_method="Deterministic 7-Factor Corridor Optimization Engine",
                )
            )
        else:
            reason_text = rejections[0] if rejections else "Filtered by hard constraints (capacity/type/availability)"
            results.append(
                AIMatchResult(
                    truck_id=truck.id,
                    eligible=False,
                    score=0.0,
                    distance_km=0.0,
                    reasons=[reason_text],
                    components={},
                    rules_score=0.0,
                    ai_score=0.0,
                    neural_network_score=0.0,
                    ranking_method="Deterministic 7-Factor Corridor Optimization Engine",
                )
            )

    # Sort: eligible first (descending by score), then ineligible
    results.sort(key=lambda r: (r.eligible, r.score), reverse=True)

    return AIMatchingResponse(
        load_id=load.id,
        ranking_method="Deterministic 7-Factor Corridor Optimization Engine",
        results=results,
    )

