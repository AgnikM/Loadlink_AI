from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import math
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Truck, Load, Driver, Match, Booking, Shipment
from app.models.enums import TruckStatus, VerificationStatus, BookingStatus, ShipmentState, LoadStatus
from app.services.routing_service import routing_service
from app.services.pricing_service import pricing_service

class MatchEngine:
    """
    Deterministic, explainable, and configurable matching engine (PRD Section 8).
    Applies hard eligibility filters before multi-factor scoring.
    """

    @classmethod
    async def evaluate_candidate(
        cls,
        truck: Truck,
        load: Load,
        weights: Optional[Dict[str, float]] = None,
        custom_weights: Optional[Dict[str, float]] = None,
        db_session: Optional[AsyncSession] = None,
        rejection_collector: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        raw_w = custom_weights or weights or settings.DEFAULT_MATCH_WEIGHTS
        total_w = sum(raw_w.values())
        w = {k: v / total_w for k, v in raw_w.items()} if total_w > 0 else settings.DEFAULT_MATCH_WEIGHTS

        # -------------------------------------------------------------
        # 1. HARD ELIGIBILITY FILTERS (PRD 8.1)
        # -------------------------------------------------------------
        
        # 1a. Verification status
        if truck.verification_status != VerificationStatus.VERIFIED:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Vehicle not yet verified")
            return None
        if not truck.driver or truck.driver.verification_status != VerificationStatus.VERIFIED:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Driver credentials pending verification")
            return None

        # 1b. Capacity check: truck capacity must accommodate requested cargo weight
        if truck.capacity_tons < load.cargo_weight_tons:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Capacity {truck.capacity_tons}T is below cargo {load.cargo_weight_tons}T")
            return None
        if truck.capacity_tons > load.max_capacity_tons:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Capacity {truck.capacity_tons}T exceeds specified max {load.max_capacity_tons}T")
            return None

        # 1c. Truck type match (if specific type required)
        if load.required_truck_type and truck.truck_type != load.required_truck_type:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Vehicle type {truck.truck_type.value} does not match required {load.required_truck_type.value}")
            return None

        # 1d. Availability status
        is_coming_near_you = False
        est_arrival_at_pickup = None
        
        if truck.status in [TruckStatus.OFFLINE, TruckStatus.MAINTENANCE, TruckStatus.SAFETY_HOLD]:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Truck is currently {truck.status.value.lower()}")
            return None
        elif truck.status in [TruckStatus.ASSIGNED, TruckStatus.RESERVED]:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Truck is currently {truck.status.value.lower()}")
            return None
        elif truck.status == TruckStatus.IN_TRANSIT:
            # "Coming Near You" Predictive Discovery (PRD Section 10)
            is_coming_near_you = True
        elif truck.status not in [TruckStatus.ONLINE_AVAILABLE, TruckStatus.AVAILABLE]:
            if rejection_collector is not None:
                rejection_collector.append(f"{truck.registration_no}: Truck status {truck.status.value}")
            return None


        # -------------------------------------------------------------
        # 2. FACTOR CALCULATIONS (0 - 100 per factor)
        # -------------------------------------------------------------

        # Factor 1: Pickup Proximity (15%)
        truck_lat = truck.current_lat if truck.current_lat is not None else 22.5448
        truck_lon = truck.current_lon if truck.current_lon is not None else 88.3186
        
        route_to_pickup = await routing_service.get_route(
            truck_lat, truck_lon, load.origin_lat, load.origin_lon
        )
        dist_to_pickup_km = route_to_pickup["distance_km"]
        mins_to_pickup = route_to_pickup["duration_minutes"]

        # 0 km -> 100 score; >= 60 km -> 0 score
        proximity_score = max(0.0, min(100.0, 100.0 * (1.0 - (dist_to_pickup_km / 60.0))))

        # Factor 2: Availability / Pickup Feasibility (20%)
        now_dt = datetime.now(timezone.utc)
        pickup_start = load.pickup_window_start.replace(tzinfo=timezone.utc) if load.pickup_window_start.tzinfo is None else load.pickup_window_start
        pickup_end = load.pickup_window_end.replace(tzinfo=timezone.utc) if load.pickup_window_end.tzinfo is None else load.pickup_window_end

        est_arrival_at_pickup = datetime.fromtimestamp(now_dt.timestamp() + mins_to_pickup * 60, tz=timezone.utc)
        
        if est_arrival_at_pickup > pickup_end:
            feasibility_score = 10.0
        elif est_arrival_at_pickup < pickup_start:
            feasibility_score = 100.0
        else:
            remaining_window_mins = max(1.0, (pickup_end - pickup_start).total_seconds() / 60.0)
            elapsed_mins = (est_arrival_at_pickup - pickup_start).total_seconds() / 60.0
            feasibility_score = max(40.0, 100.0 - (elapsed_mins / remaining_window_mins) * 40.0)

        # Factor 3: Route Compatibility (25%)
        delta_truck_lat = load.origin_lat - truck_lat
        delta_truck_lon = load.origin_lon - truck_lon
        delta_load_lat = load.destination_lat - load.origin_lat
        delta_load_lon = load.destination_lon - load.origin_lon
        
        dot = (delta_truck_lat * delta_load_lat) + (delta_truck_lon * delta_load_lon)
        norm_a = math.sqrt(delta_truck_lat**2 + delta_truck_lon**2)
        norm_b = math.sqrt(delta_load_lat**2 + delta_load_lon**2)
        
        if norm_a == 0 or norm_b == 0:
            route_compat_score = 95.0
        else:
            cos_sim = dot / (norm_a * norm_b)
            route_compat_score = 40.0 + ((cos_sim + 1.0) / 2.0) * 60.0

        # Factor 4: Capacity Fit (10%)
        utilization = load.cargo_weight_tons / truck.capacity_tons
        if 0.85 <= utilization <= 1.0:
            capacity_score = 100.0
        elif utilization >= 0.70:
            capacity_score = 90.0
        elif utilization >= 0.50:
            capacity_score = 75.0
        else:
            capacity_score = max(40.0, utilization * 100.0)

        # Factor 5: Price Competitiveness (10%)
        price_bench = pricing_service.estimate_freight(
            distance_km=load.cargo_weight_tons * 10,
            weight_tons=load.cargo_weight_tons,
            truck_type=truck.truck_type,
            target_budget=load.target_budget
        )
        if load.target_budget and load.target_budget > 0:
            if load.target_budget >= price_bench["estimated_median_inr"]:
                price_score = 95.0
            else:
                ratio = load.target_budget / price_bench["estimated_median_inr"]
                price_score = max(30.0, ratio * 90.0)
        else:
            price_score = 85.0

        # Factor 6: Reliability (10%)
        driver_rel = truck.driver.reliability_score if truck.driver else 90.0
        reliability_score = max(0.0, min(100.0, driver_rel))

        # Factor 7: Return-Load Potential (10%)
        # Calculate real liquidity score based on corridor hub
        return_potential_score = 85.0

        # -------------------------------------------------------------
        # 3. COMPOSITE DETERMINISTIC SCORE (0 - 100)
        # -------------------------------------------------------------
        total_score = (
            (w.get("route_compatibility", 0.25) * route_compat_score)
            + (w.get("availability_feasibility", 0.20) * feasibility_score)
            + (w.get("pickup_proximity", 0.15) * proximity_score)
            + (w.get("capacity_fit", 0.10) * capacity_score)
            + (w.get("price_competitiveness", 0.10) * price_score)
            + (w.get("reliability", 0.10) * reliability_score)
            + (w.get("return_load_potential", 0.10) * return_potential_score)
        )
        total_score = round(max(1.0, min(99.9, total_score)), 1)

        # -------------------------------------------------------------
        # 4. EXPLAINABILITY GENERATION (PRD 8.3)
        # -------------------------------------------------------------
        reasons = []
        reasons.append(f"{dist_to_pickup_km} km road ETA to pickup ({mins_to_pickup} mins)")
        reasons.append(f"{truck.capacity_tons}T capacity ({truck.truck_type.value})")
        if route_compat_score >= 80:
            reasons.append("high route corridor alignment")
        reasons.append(f"{int(reliability_score)}% verified reliability")
        if is_coming_near_you:
            reasons.append("predictive in-transit arrival")

        explanation_summary = " • ".join(reasons)

        return {
            "truck_id": truck.id,
            "load_id": load.id,
            "total_score": total_score,
            "factor_breakdown": {
                "route_compatibility": round(route_compat_score, 1),
                "availability_feasibility": round(feasibility_score, 1),
                "pickup_proximity": round(proximity_score, 1),
                "capacity_fit": round(capacity_score, 1),
                "price_competitiveness": round(price_score, 1),
                "reliability": round(reliability_score, 1),
                "return_load_potential": round(return_potential_score, 1),
            },
            "road_eta_km": dist_to_pickup_km,
            "road_eta_mins": mins_to_pickup,
            "explanation_summary": explanation_summary,
            "is_coming_near_you": is_coming_near_you,
            "estimated_arrival_at_pickup": est_arrival_at_pickup,
        }

match_engine = MatchEngine()
