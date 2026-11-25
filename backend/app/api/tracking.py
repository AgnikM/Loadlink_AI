import json
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db, AsyncSessionLocal
from app.api.auth import get_current_user
from app.models.entities import Shipment, Truck, TruckLocation, User
from app.models.enums import UserRole, ShipmentState
from app.schemas.all_schemas import GPSBatchIngestIn, GPSBatchIngestOut
from app.services.routing_service import routing_service

router = APIRouter(tags=["tracking"])

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class ConnectionManager:
    def __init__(self):
        # shipment_id -> list of active websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, shipment_id: str, websocket: WebSocket):
        await websocket.accept()
        if shipment_id not in self.active_connections:
            self.active_connections[shipment_id] = []
        self.active_connections[shipment_id].append(websocket)

    def disconnect(self, shipment_id: str, websocket: WebSocket):
        if shipment_id in self.active_connections:
            if websocket in self.active_connections[shipment_id]:
                self.active_connections[shipment_id].remove(websocket)
            if len(self.active_connections[shipment_id]) == 0:
                del self.active_connections[shipment_id]

    async def broadcast_to_shipment(self, shipment_id: str, message: dict):
        if shipment_id in self.active_connections:
            for connection in self.active_connections[shipment_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

@router.get("/shipments/{shipment_id}/tracking")
async def get_tracking_info(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(
            selectinload(Shipment.load),
            selectinload(Shipment.truck),
            selectinload(Shipment.driver).selectinload(User),
            selectinload(Shipment.dealer).selectinload(User),
            selectinload(Shipment.locations),
        )
    )
    res = await db.execute(query)
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Security / Authorization: only the load's dealer, assigned driver, or admin can track
    if current_user.role == UserRole.DEALER and current_user.dealer_profile:
        if s.dealer_id != current_user.dealer_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot track another dealer's shipment.",
            )
    elif current_user.role == UserRole.DRIVER and current_user.driver_profile:
        if s.driver_id != current_user.driver_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not assigned to this shipment.",
            )

    # Privacy Rule (PRD FR-11, Sec 12, Sec 32):
    # Location tracking is active and accessible only when required by active shipment state
    active_tracking_states = [
        ShipmentState.DRIVER_EN_ROUTE,
        ShipmentState.ARRIVED_PICKUP,
        ShipmentState.LOADING,
        ShipmentState.LOADED,
        ShipmentState.IN_TRANSIT,
        ShipmentState.NEAR_DESTINATION,
        ShipmentState.DELIVERED,
    ]

    is_active = s.state in active_tracking_states
    truck = s.truck
    truck_lat = truck.current_lat if (truck and is_active) else None
    truck_lon = truck.current_lon if (truck and is_active) else None

    # Stale location calculation: if last update > 15 mins (900 seconds)
    is_stale = False
    if truck and truck.last_location_time and is_active:
        now = datetime.now(timezone.utc)
        loc_time = truck.last_location_time.replace(tzinfo=timezone.utc) if truck.last_location_time.tzinfo is None else truck.last_location_time
        if (now - loc_time).total_seconds() > 900:
            is_stale = True

    # Calculate remaining ETA if in transit
    remaining_km = 0.0
    remaining_mins = 0
    if truck_lat and truck_lon and s.load:
        target_lat = s.load.destination_lat if s.state in [ShipmentState.LOADED, ShipmentState.IN_TRANSIT, ShipmentState.NEAR_DESTINATION] else s.load.origin_lat
        target_lon = s.load.destination_lon if s.state in [ShipmentState.LOADED, ShipmentState.IN_TRANSIT, ShipmentState.NEAR_DESTINATION] else s.load.origin_lon
        route = await routing_service.get_route(truck_lat, truck_lon, target_lat, target_lon)
        remaining_km = route["distance_km"]
        remaining_mins = route["duration_minutes"]

    # History trail points (only during active tracking)
    loc_history = []
    if is_active:
        loc_history = [
            {
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "speed_kmh": loc.speed_kmh,
                "recorded_at": loc.recorded_at,
            }
            for loc in s.locations[-30:] # Last 30 coordinates
        ]

    return {
        "shipment_id": s.id,
        "shipment_state": s.state,
        "is_tracking_active": is_active,
        "is_location_stale": is_stale,
        "current_latitude": truck_lat,
        "current_longitude": truck_lon,
        "last_location_time": truck.last_location_time if (truck and is_active) else None,
        "remaining_distance_km": remaining_km,
        "remaining_time_minutes": remaining_mins,
        "origin": {
            "name": s.load.origin_name if s.load else "Origin",
            "lat": s.load.origin_lat if s.load else 22.5448,
            "lon": s.load.origin_lon if s.load else 88.3186,
        },
        "destination": {
            "name": s.load.destination_name if s.load else "Destination",
            "lat": s.load.destination_lat if s.load else 23.5204,
            "lon": s.load.destination_lon if s.load else 87.3119,
        },
        "location_history": loc_history,
    }

@router.websocket("/ws/shipments/{shipment_id}")
async def websocket_tracking(websocket: WebSocket, shipment_id: str):
    token = websocket.query_params.get("token")
    user_id = None
    role = None
    if token:
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub")
            role = payload.get("role")
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await manager.connect(shipment_id, websocket)
    try:
        while True:
            # Client can emit live driver GPS coordinate pings
            data = await websocket.receive_text()
            payload = json.loads(data)

            # If client provides auth message after connection
            if payload.get("type") == "AUTH":
                try:
                    from app.core.security import decode_token
                    decoded = decode_token(payload.get("token", ""))
                    user_id = decoded.get("sub")
                    role = decoded.get("role")
                    await websocket.send_json({"type": "AUTH_SUCCESS", "user_id": user_id})
                except Exception:
                    await websocket.send_json({"type": "AUTH_ERROR", "detail": "Invalid token"})
                continue
            
            # If driver pushes GPS update over WS:
            if payload.get("type") == "LOCATION_UPDATE":
                lat = payload.get("latitude")
                lon = payload.get("longitude")
                speed = payload.get("speed_kmh", 45.0)

                # Validate GPS sanity
                if lat is not None and lon is not None and (-90 <= lat <= 90) and (-180 <= lon <= 180):
                    async with AsyncSessionLocal() as session:
                        s = await session.get(Shipment, shipment_id)
                        if s and s.truck_id:
                            # Verify actor permission if authenticated
                            if user_id:
                                q_driver = select(Driver).where(Driver.user_id == user_id)
                                d_res = await session.execute(q_driver)
                                driver_obj = d_res.scalar_one_or_none()
                                if driver_obj and s.driver_id and s.driver_id != driver_obj.id and role != "ADMIN":
                                    continue

                            truck = await session.get(Truck, s.truck_id)
                            if truck:
                                now = datetime.now(timezone.utc)
                                truck.current_lat = lat
                                truck.current_lon = lon
                                truck.last_location_time = now
                                loc = TruckLocation(
                                    shipment_id=s.id,
                                    truck_id=truck.id,
                                    latitude=lat,
                                    longitude=lon,
                                    speed_kmh=speed,
                                    recorded_at=now,
                                )
                                session.add(loc)
                                await session.commit()

                    # Broadcast position to all connected dealers/admins watching this shipment
                    await manager.broadcast_to_shipment(
                        shipment_id,
                        {
                            "type": "POSITION_STREAM",
                            "shipment_id": shipment_id,
                            "latitude": lat,
                            "longitude": lon,
                            "speed_kmh": speed,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
    except WebSocketDisconnect:
        manager.disconnect(shipment_id, websocket)

@router.post("/tracking/batch", response_model=GPSBatchIngestOut)
async def ingest_batch_gps(
    payload: GPSBatchIngestIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Batched GPS Breadcrumbs Ingestion (Master Prompt 3 Task I & Master Prompt 4 Scalability).
    Sorts chronologically, deduplicates contiguous identical coordinates, validates bounds,
    detects speed jumps (>130 km/h), updates live truck location, and preserves server timestamps.
    """
    if not payload.breadcrumbs:
        raise HTTPException(status_code=400, detail="Empty breadcrumbs batch")

    now = datetime.now(timezone.utc)
    truck_id = payload.breadcrumbs[0].truck_id
    truck = await db.get(Truck, truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    # Chronologically sort breadcrumbs to handle out-of-order offline syncing
    sorted_breadcrumbs = sorted(
        payload.breadcrumbs,
        key=lambda b: (
            b.device_timestamp.replace(tzinfo=timezone.utc) if b.device_timestamp.tzinfo is None else b.device_timestamp,
            b.sequence_number or 0
        )
    )

    # In-batch deduplication: filter out redundant identical coordinates with same timestamp
    unique_breadcrumbs = []
    seen_points = set()
    for b in sorted_breadcrumbs:
        b_time = b.device_timestamp.replace(tzinfo=timezone.utc) if b.device_timestamp.tzinfo is None else b.device_timestamp
        key = (round(b.latitude, 6), round(b.longitude, 6), b_time.isoformat(), b.sequence_number)
        if key not in seen_points:
            seen_points.add(key)
            unique_breadcrumbs.append(b)

    ingested = 0
    anomalies = 0
    suspicious_indices = []
    latest_lat = None
    latest_lon = None
    prev_lat = truck.current_lat
    prev_lon = truck.current_lon
    prev_time = truck.last_location_time
    latest_device_time = None

    for idx, b in enumerate(unique_breadcrumbs):
        # Validate coordinate boundaries
        if not (-90 <= b.latitude <= 90) or not (-180 <= b.longitude <= 180):
            continue

        b_time = b.device_timestamp.replace(tzinfo=timezone.utc) if b.device_timestamp.tzinfo is None else b.device_timestamp
        is_jump = False

        # If consecutive points exist, check speed / jump
        if prev_lat is not None and prev_lon is not None and prev_time is not None:
            p_time = prev_time.replace(tzinfo=timezone.utc) if prev_time.tzinfo is None else prev_time
            time_delta_sec = (b_time - p_time).total_seconds()

            # For the first breadcrumb in batch, only compare against DB historical point if within 10 minutes
            if idx == 0 and (time_delta_sec <= 0 or time_delta_sec > 600.0):
                pass
            elif time_delta_sec > 0:
                time_diff_hours = time_delta_sec / 3600.0
                dist_km = haversine_km(prev_lat, prev_lon, b.latitude, b.longitude)
                calc_speed = dist_km / time_diff_hours
                if calc_speed > 130.0 or (dist_km > 50.0 and time_delta_sec < 60.0):
                    is_jump = True
                    anomalies += 1
                    suspicious_indices.append(idx)
        elif b.speed_kmh and b.speed_kmh > 130.0:
            is_jump = True
            anomalies += 1
            suspicious_indices.append(idx)

        loc = TruckLocation(
            shipment_id=b.shipment_id,
            truck_id=b.truck_id,
            latitude=b.latitude,
            longitude=b.longitude,
            speed_kmh=b.speed_kmh,
            heading=b.heading,
            accuracy_meters=b.accuracy_meters,
            sequence_number=b.sequence_number,
            is_suspicious_jump=is_jump,
            source="ANDROID_BATCH_GPS",
            recorded_at=b.device_timestamp,
        )
        db.add(loc)
        ingested += 1

        prev_lat = b.latitude
        prev_lon = b.longitude
        prev_time = b.device_timestamp
        latest_lat = b.latitude
        latest_lon = b.longitude
        latest_device_time = b_time

    # Update truck's latest location & last_location_time
    if latest_lat is not None and latest_lon is not None:
        truck.current_lat = latest_lat
        truck.current_lon = latest_lon
        truck.last_location_time = latest_device_time or now

    await db.commit()

    # Calculate staleness: if last update > 900 seconds (15 mins)
    is_stale = False
    if truck.last_location_time:
        loc_time = truck.last_location_time.replace(tzinfo=timezone.utc) if truck.last_location_time.tzinfo is None else truck.last_location_time
        if (now - loc_time).total_seconds() > 900:
            is_stale = True

    return GPSBatchIngestOut(
        ingested_count=ingested,
        anomalies_detected=anomalies,
        suspicious_points=suspicious_indices,
        latest_latitude=latest_lat,
        latest_longitude=latest_lon,
        is_stale=is_stale,
        server_timestamp=now,
    )

@router.get("/tracking/offline-metadata")
async def get_offline_metadata(
    current_user: User = Depends(get_current_user),
):
    """
    Offline Maps & Corridor Tile Metadata (Master Prompt 3 Task H).
    Returns regional bounding box, cached corridor route geometry,
    and offline synchronization limits.
    """
    return {
        "corridor_name": "Kolkata ↔ Durgapur ↔ Asansol Industrial Corridor (NH19)",
        "bounding_box": {
            "min_latitude": 22.2000,
            "min_longitude": 86.8000,
            "max_latitude": 23.8500,
            "max_longitude": 88.5000,
        },
        "tile_pack_id": "kolkata-asansol-nh19-v1",
        "tile_url_template": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "min_zoom": 8,
        "max_zoom": 15,
        "estimated_size_mb": 45.0,
        "offline_routing_notice": (
            "Downloaded vector or raster map tiles display spatial geography offline but do NOT "
            "provide dynamic route recalculation unless an embedded routing graph (e.g., GraphHopper/OSRM) "
            "is compiled natively on device."
        ),
        "waypoints": [
            {"name": "Kolkata Port & Dankuni Hub", "lat": 22.5448, "lon": 88.3186},
            {"name": "Burdwan NH19 Bypass", "lat": 23.2324, "lon": 87.8615},
            {"name": "Durgapur Steel Industrial Zone", "lat": 23.5204, "lon": 87.3119},
            {"name": "Asansol Logistics Hub", "lat": 23.6889, "lon": 86.9661},
        ],
    }

