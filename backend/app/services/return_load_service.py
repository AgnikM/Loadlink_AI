from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import Load, Truck, Shipment
from app.models.enums import LoadStatus, TruckType
from app.services.routing_service import routing_service

class ReturnLoadService:
    """
    Return-Load Matching Engine (PRD Section 9).
    Discovers compatible backhaul loads originating near the truck's delivery destination
    and traveling toward the truck's base or home corridor (e.g. Durgapur/Asansol -> Kolkata).
    """

    @classmethod
    async def find_return_loads(
        cls,
        session: AsyncSession,
        delivery_lat: float,
        delivery_lon: float,
        truck_capacity_tons: float,
        truck_type: TruckType,
        max_pickup_radius_km: float = 45.0,
    ) -> List[Dict[str, Any]]:
        # Fetch all open posted loads
        query = (
            select(Load)
            .where(Load.status.in_([LoadStatus.POSTED, LoadStatus.MATCHING]))
            .options(selectinload(Load.dealer))
        )
        result = await session.execute(query)
        open_loads = result.scalars().all()

        opportunities = []

        for load in open_loads:
            # 1. Capacity and truck type compatibility
            if load.cargo_weight_tons > truck_capacity_tons:
                continue
            if load.required_truck_type and load.required_truck_type != truck_type:
                continue

            # 2. Origin proximity to delivery destination
            dist_to_new_origin = routing_service.haversine_distance_km(
                delivery_lat, delivery_lon, load.origin_lat, load.origin_lon
            )
            if dist_to_new_origin > max_pickup_radius_km:
                continue

            # 3. Calculate backhaul suitability score (0-100)
            proximity_score = max(0.0, 100.0 * (1.0 - (dist_to_new_origin / max_pickup_radius_km)))
            capacity_score = (load.cargo_weight_tons / truck_capacity_tons) * 100.0
            
            match_score = round(0.55 * proximity_score + 0.45 * capacity_score, 1)

            opportunities.append({
                "load_id": load.id,
                "origin_name": load.origin_name,
                "destination_name": load.destination_name,
                "cargo_type": load.cargo_type,
                "cargo_weight_tons": load.cargo_weight_tons,
                "target_budget": load.target_budget or (load.cargo_weight_tons * 1100.0),
                "pickup_window_start": load.pickup_window_start,
                "pickup_window_end": load.pickup_window_end,
                "distance_from_delivery_km": dist_to_new_origin,
                "extra_earnings_estimate": round((load.target_budget or (load.cargo_weight_tons * 1100.0)) * 0.95, 2),
                "match_score": match_score,
            })

        # Sort descending by match score
        opportunities.sort(key=lambda x: x["match_score"], reverse=True)
        return opportunities

return_load_service = ReturnLoadService()
