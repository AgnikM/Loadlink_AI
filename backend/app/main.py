import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.rate_limit import RateLimiterMiddleware
from app.core.logging_middleware import StructuredLoggingMiddleware, metrics
from app.api.auth import get_current_user
from app.models.entities import Truck, Load, Booking, Shipment, User
from app.models.enums import TruckStatus, LoadStatus, ShipmentState
from app.schemas.all_schemas import DashboardSummaryOut
from app.api import (
    auth, loads, trucks, matching, bookings, shipments, tracking, pod, ratings, notifications, admin,
    custody, insurance, payments, disputes, uploads,
    sos, breakdowns, inspections, replacements
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Deterministic B2B Freight Marketplace MVP (Kolkata ↔ Durgapur ↔ Asansol)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration: strict explicit origins and trusted subdomains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.0\.2\.2)(:[0-9]+)?$|^https://([a-zA-Z0-9-]+\.)*loadlink\.ai$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured JSON Application Logging Middleware
app.add_middleware(StructuredLoggingMiddleware)

# API Rate Limiter Middleware (Anti-abuse & Brute-force protection)
app.add_middleware(RateLimiterMiddleware)

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Secure Document Uploads & Retrieval Router (Master Prompt 2.1 Task 1)
# Replaces public StaticFiles mount with authenticated, role-gated retrieval
app.include_router(uploads.router)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(loads.router, prefix=settings.API_V1_STR)
app.include_router(trucks.router, prefix=settings.API_V1_STR)
app.include_router(matching.router, prefix=settings.API_V1_STR)
app.include_router(matching.ai_router, prefix=settings.API_V1_STR)
app.include_router(bookings.router, prefix=settings.API_V1_STR)
app.include_router(shipments.router, prefix=settings.API_V1_STR)
app.include_router(pod.router, prefix=settings.API_V1_STR)
app.include_router(ratings.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(tracking.router, prefix=settings.API_V1_STR)
app.include_router(custody.router, prefix=settings.API_V1_STR)
app.include_router(insurance.router, prefix=settings.API_V1_STR)
app.include_router(payments.router, prefix=settings.API_V1_STR)
app.include_router(disputes.router, prefix=settings.API_V1_STR)
app.include_router(sos.router, prefix=settings.API_V1_STR)
app.include_router(breakdowns.router, prefix=settings.API_V1_STR)
app.include_router(inspections.router, prefix=settings.API_V1_STR)
app.include_router(replacements.router, prefix=settings.API_V1_STR)

@app.get(f"{settings.API_V1_STR}/dashboard/summary", response_model=DashboardSummaryOut)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    q_available_trucks = select(func.count(Truck.id)).where(Truck.status == TruckStatus.ONLINE_AVAILABLE)
    q_open_loads = select(func.count(Load.id)).where(Load.status.in_([LoadStatus.POSTED, LoadStatus.MATCHING, LoadStatus.BOOKING_REQUESTED]))
    q_bookings = select(func.count(Booking.id))
    q_in_transit = select(func.count(Shipment.id)).where(Shipment.state == ShipmentState.IN_TRANSIT)
    q_total_trucks = select(func.count(Truck.id))
    q_total_loads = select(func.count(Load.id))

    av_trucks = (await db.execute(q_available_trucks)).scalar_one() or 0
    op_loads = (await db.execute(q_open_loads)).scalar_one() or 0
    tot_bookings = (await db.execute(q_bookings)).scalar_one() or 0
    in_trans = (await db.execute(q_in_transit)).scalar_one() or 0
    tot_trucks = (await db.execute(q_total_trucks)).scalar_one() or 0
    tot_loads = (await db.execute(q_total_loads)).scalar_one() or 0

    return DashboardSummaryOut(
        available_trucks=av_trucks,
        open_loads=op_loads,
        bookings=tot_bookings,
        in_transit=in_trans,
        trucks=tot_trucks,
        loads=tot_loads,
    )

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    start = time.time()
    db_status = "healthy"
    try:
        await db.execute(select(func.count(User.id)))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    latency_ms = round((time.time() - start) * 1000, 2)

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "database_latency_ms": latency_ms,
        "corridor": "Kolkata ↔ Durgapur ↔ Asansol",
        "matching_engine": "Deterministic 7-Factor Engine (Active)",
        "version": "1.0.0"
    }

@app.get("/health/metrics")
async def health_metrics():
    return {
        "system": "LoadLink AI Core Engine",
        "status": "operational",
        "metrics": metrics.get_summary()
    }
