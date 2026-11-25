from typing import Dict, Any, Optional
from app.models.enums import TruckType

class PricingService:
    """
    Corridor Benchmark Freight Intelligence (PRD Section 11).
    Explicitly provides estimated ranges based on real distance, tonnage, and vehicle type heuristics.
    Never claims to be a factual market contract without completed records.
    """
    # Base rate per ton-km for NH19 (Kolkata - Durgapur - Asansol)
    BASE_RATE_PER_TON_KM = 3.85  # INR per ton-km
    
    # Base loading/handling overhead per trip
    FIXED_BASE_HANDLING_INR = 2500.0

    # Truck type multiplier
    TYPE_MULTIPLIERS = {
        TruckType.OPEN_BODY: 1.0,
        TruckType.CLOSED_CONTAINER: 1.15,
        TruckType.FLATBED: 1.10,
        TruckType.TRAILER: 1.25,
        TruckType.TIPPER: 1.05,
    }

    @classmethod
    def estimate_freight(
        cls,
        distance_km: float,
        weight_tons: float,
        truck_type: Optional[TruckType] = TruckType.OPEN_BODY,
        target_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        mult = cls.TYPE_MULTIPLIERS.get(truck_type or TruckType.OPEN_BODY, 1.0)
        
        # Variable cost: distance * weight * base_rate * type_multiplier
        variable_cost = distance_km * weight_tons * cls.BASE_RATE_PER_TON_KM * mult
        median_estimate = round(cls.FIXED_BASE_HANDLING_INR + variable_cost, -2) # round to nearest 100
        
        min_range = round(median_estimate * 0.90, -2)
        max_range = round(median_estimate * 1.12, -2)
        
        is_budget_competitive = True
        budget_variance_pct = 0.0
        if target_budget and target_budget > 0:
            budget_variance_pct = round(((target_budget - median_estimate) / median_estimate) * 100, 1)
            is_budget_competitive = target_budget >= min_range

        return {
            "estimated_median_inr": float(median_estimate),
            "estimated_range_min_inr": float(min_range),
            "estimated_range_max_inr": float(max_range),
            "suggested_offer_inr": float(median_estimate),
            "pricing_model": "Kolkata-Asansol Corridor Heuristic (Ton-KM Model v1)",
            "is_estimate": True,
            "data_confidence": "HIGH_CORRIDOR_BENCHMARK",
            "target_budget_variance_pct": budget_variance_pct,
            "is_budget_competitive": is_budget_competitive,
        }

pricing_service = PricingService()
