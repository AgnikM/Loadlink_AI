from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Driver, Dealer, Shipment, Rating, POD
from app.models.enums import ShipmentState, PODStatus

class TrustService:
    """
    Derived Trust & Reliability Score Service (PRD Section 15).
    Uses Bayesian / Laplace smoothing with minimum-sample rules so a new user
    with 1 completion does not outrank an established 100-trip counterparty.
    """

    PRIOR_SAMPLE_WEIGHT = 5.0  # Base pseudo-counts to stabilize small samples
    PRIOR_DEFAULT_SCORE = 88.0 # Starting baseline score for new verified users

    @classmethod
    async def recalculate_driver_reliability(cls, session: AsyncSession, driver_id: str) -> float:
        driver = await session.get(Driver, driver_id)
        if not driver:
            return cls.PRIOR_DEFAULT_SCORE

        # Query all finished shipments for this driver
        query = select(Shipment).where(
            Shipment.driver_id == driver_id,
            Shipment.state.in_([ShipmentState.COMPLETED, ShipmentState.CANCELLED, ShipmentState.DISPUTED])
        )
        res = await session.execute(query)
        shipments = res.scalars().all()

        n = len(shipments)
        if n == 0:
            return round(cls.PRIOR_DEFAULT_SCORE, 1)

        on_time_count = 0
        completed_count = 0
        disputes_count = 0
        pod_compliant_count = 0

        for s in shipments:
            if s.state == ShipmentState.COMPLETED:
                completed_count += 1
                if s.actual_delivery_time and s.delivery_eta:
                    if s.actual_delivery_time <= s.delivery_eta:
                        on_time_count += 1
                    else:
                        # Grace period of 30 mins
                        delay_secs = (s.actual_delivery_time - s.delivery_eta).total_seconds()
                        if delay_secs <= 1800:
                            on_time_count += 0.8
                else:
                    on_time_count += 1
            elif s.state == ShipmentState.DISPUTED:
                disputes_count += 1

        # Query ratings
        r_query = select(func.avg(Rating.score)).where(Rating.rated_user_id == driver.user_id)
        r_res = await session.execute(r_query)
        avg_rating_5 = r_res.scalar() or 4.5
        avg_rating_pct = (avg_rating_5 / 5.0) * 100.0

        # Empirical weighted performance (0-100)
        completion_rate = (completed_count / n) * 100.0
        on_time_rate = (on_time_count / max(1, completed_count)) * 100.0
        sample_metric = (
            0.40 * completion_rate +
            0.30 * on_time_rate +
            0.20 * avg_rating_pct +
            0.10 * max(0.0, 100.0 - (disputes_count * 25.0))
        )

        # Bayesian smoothing
        smoothed_score = (
            (cls.PRIOR_SAMPLE_WEIGHT * cls.PRIOR_DEFAULT_SCORE) + (n * sample_metric)
        ) / (cls.PRIOR_SAMPLE_WEIGHT + n)

        driver.reliability_score = round(max(10.0, min(99.0, smoothed_score)), 1)
        driver.total_trips = n
        driver.on_time_trips = int(on_time_count)
        await session.flush()
        return driver.reliability_score

    @classmethod
    async def recalculate_dealer_trust(cls, session: AsyncSession, dealer_id: str) -> float:
        dealer = await session.get(Dealer, dealer_id)
        if not dealer:
            return cls.PRIOR_DEFAULT_SCORE

        query = select(Shipment).where(
            Shipment.dealer_id == dealer_id,
            Shipment.state.in_([ShipmentState.COMPLETED, ShipmentState.CANCELLED, ShipmentState.DISPUTED])
        )
        res = await session.execute(query)
        shipments = res.scalars().all()

        n = len(shipments)
        if n == 0:
            return round(cls.PRIOR_DEFAULT_SCORE, 1)

        completed_count = sum(1 for s in shipments if s.state == ShipmentState.COMPLETED)
        disputed_count = sum(1 for s in shipments if s.state == ShipmentState.DISPUTED)

        completion_rate = (completed_count / n) * 100.0
        sample_metric = max(20.0, completion_rate - (disputed_count * 20.0))

        smoothed_score = (
            (cls.PRIOR_SAMPLE_WEIGHT * cls.PRIOR_DEFAULT_SCORE) + (n * sample_metric)
        ) / (cls.PRIOR_SAMPLE_WEIGHT + n)

        dealer.trust_score = round(max(10.0, min(99.0, smoothed_score)), 1)
        dealer.total_completed_loads = completed_count
        await session.flush()
        return dealer.trust_score

trust_service = TrustService()
