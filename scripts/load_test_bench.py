import asyncio
import os
import sys
import time
import uuid
import statistics
import tracemalloc
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath("backend"))

from httpx import AsyncClient, ASGITransport
from app.main import app

async def get_auth_token(client: AsyncClient, email: str, password: str, client_ip: str) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": client_ip, "User-Agent": "pytest-benchmark-runner"}
    )
    if res.status_code == 200:
        return res.json()["access_token"]
    raise RuntimeError(f"Login failed for {email}: {res.status_code} {res.text}")

async def run_scenario(
    client: AsyncClient,
    token_map: Dict[str, str],
    context: Dict[str, str],
    worker_id: int,
    scenario_type: str
) -> Tuple[float, int]:
    """
    Executes a realistic workflow scenario and measures latency (ms) and status code.
    Simulates distinct client IPs via X-Forwarded-For.
    """
    client_ip = f"10.1.{worker_id // 250}.{worker_id % 250 + 1}"
    base_headers = {
        "X-Forwarded-For": client_ip,
        "User-Agent": "loadlink-load-test-worker"
    }

    start = time.perf_counter()
    status_code = 500

    try:
        dealer_headers = {**base_headers, "Authorization": f"Bearer {token_map['dealer']}"}
        driver_headers = {**base_headers, "Authorization": f"Bearer {token_map['driver']}"}
        admin_headers = {**base_headers, "Authorization": f"Bearer {token_map['admin']}"}

        if scenario_type == "auth_login":
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "dealer.kolkata@bengalsteel.in", "password": "dealer123"},
                headers=base_headers
            )
            status_code = res.status_code

        elif scenario_type == "truck_discovery":
            res = await client.get("/api/v1/trucks?limit=50", headers=dealer_headers)
            status_code = res.status_code

        elif scenario_type == "load_posting":
            now = datetime.now(timezone.utc)
            load_data = {
                "origin_name": "Kolkata Port / Docks",
                "destination_name": "Durgapur Steel Complex",
                "cargo_type": "TMT Rebars",
                "cargo_weight_tons": 18.0,
                "declared_value_inr": 250000.0,
                "pickup_window_start": (now + timedelta(hours=2)).isoformat(),
                "pickup_window_end": (now + timedelta(hours=8)).isoformat(),
                "target_budget": 24000.0,
            }
            res = await client.post("/api/v1/loads", json=load_data, headers=dealer_headers)
            status_code = res.status_code

        elif scenario_type == "freight_matching":
            lid = context.get("load_id")
            if lid:
                res = await client.post(f"/api/v1/loads/{lid}/matches", headers=dealer_headers)
                status_code = res.status_code
            else:
                res = await client.get("/api/v1/loads?limit=5", headers=dealer_headers)
                status_code = res.status_code

        elif scenario_type == "shipment_tracking":
            res = await client.get("/api/v1/shipments?limit=20", headers=dealer_headers)
            status_code = res.status_code

        elif scenario_type == "gps_batch_ingestion":
            now = datetime.now(timezone.utc)
            breadcrumbs = [
                {
                    "driver_id": context.get("driver_id"),
                    "truck_id": context.get("truck_id"),
                    "shipment_id": context.get("shipment_id"),
                    "latitude": 22.6842 + (worker_id * 0.0001),
                    "longitude": 88.2934 + (worker_id * 0.0001),
                    "accuracy_meters": 4.5,
                    "speed_kmh": 42.0,
                    "heading": 90.0,
                    "sequence_number": worker_id + 1,
                    "device_timestamp": now.isoformat(),
                }
            ]
            res = await client.post("/api/v1/tracking/batch", json={"breadcrumbs": breadcrumbs}, headers=driver_headers)
            status_code = res.status_code

        elif scenario_type == "sos_event_creation":
            now = datetime.now(timezone.utc)
            sos_payload = {
                "event_id": str(uuid.uuid4()),
                "truck_id": context.get("truck_id"),
                "shipment_id": context.get("shipment_id"),
                "latitude": 23.2324,
                "longitude": 87.8615,
                "accuracy_meters": 8.0,
                "incident_category": "BREAKDOWN_ACCIDENT",
                "device_timestamp": now.isoformat(),
                "network_status": "ONLINE",
            }
            res = await client.post("/api/v1/sos", json=sos_payload, headers=driver_headers)
            status_code = res.status_code

        elif scenario_type == "health_and_metadata":
            res = await client.get("/health", headers=base_headers)
            status_code = res.status_code

        else:
            res = await client.get("/api/v1/tracking/offline-metadata", headers=driver_headers)
            status_code = res.status_code

    except Exception:
        status_code = 500

    latency_ms = (time.perf_counter() - start) * 1000.0
    return latency_ms, status_code

async def run_concurrent_load_test(concurrency: int, total_requests: int) -> Dict[str, Any]:
    print(f"\n--- RUNNING LOAD TEST: {concurrency} CONCURRENT SIMULATED USERS ({total_requests} TOTAL REQUESTS) ---")
    tracemalloc.start()
    cpu_start = time.process_time()
    wall_start = time.perf_counter()

    scenarios = [
        "health_and_metadata",
        "truck_discovery",
        "shipment_tracking",
        "load_posting",
        "freight_matching",
        "gps_batch_ingestion",
        "health_and_metadata",
    ]

    latencies: List[float] = []
    status_codes: Dict[int, int] = {}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testload") as client:
        # Pre-authenticate representative actors with isolated IPs
        dealer_token = await get_auth_token(client, "dealer.kolkata@bengalsteel.in", "dealer123", "10.0.0.1")
        driver_token = await get_auth_token(client, "driver.rajesh@loadlink.ai", "driver123", "10.0.0.2")
        admin_token = await get_auth_token(client, "admin@loadlink.ai", "admin123", "10.0.0.3")
        token_map = {"dealer": dealer_token, "driver": driver_token, "admin": admin_token}

        # Query baseline context (real truck, load, shipment)
        res_t = await client.get("/api/v1/trucks?limit=1", headers={"Authorization": f"Bearer {admin_token}"})
        truck_id = res_t.json()[0]["id"] if res_t.status_code == 200 and len(res_t.json()) > 0 else None

        res_l = await client.get("/api/v1/loads?limit=1", headers={"Authorization": f"Bearer {dealer_token}"})
        load_id = res_l.json()[0]["id"] if res_l.status_code == 200 and len(res_l.json()) > 0 else None

        res_s = await client.get("/api/v1/shipments?limit=1", headers={"Authorization": f"Bearer {admin_token}"})
        shipment_id = res_s.json()[0]["id"] if res_s.status_code == 200 and len(res_s.json()) > 0 else None
        driver_id = res_s.json()[0]["driver_id"] if res_s.status_code == 200 and len(res_s.json()) > 0 else None

        context = {
            "truck_id": truck_id,
            "load_id": load_id,
            "shipment_id": shipment_id,
            "driver_id": driver_id
        }

        # Work queue
        queue = asyncio.Queue()
        for i in range(total_requests):
            scenario = scenarios[i % len(scenarios)]
            await queue.put((i, scenario))

        async def worker(wid: int):
            while not queue.empty():
                try:
                    item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                req_idx, scen = item
                lat, code = await run_scenario(client, token_map, context, wid, scen)
                latencies.append(lat)
                status_codes[code] = status_codes.get(code, 0) + 1
                queue.task_done()

        workers = [asyncio.create_task(worker(i)) for i in range(concurrency)]
        await asyncio.gather(*workers)

    wall_duration = time.perf_counter() - wall_start
    cpu_duration = time.process_time() - cpu_start
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Latency percentiles
    latencies.sort()
    count = len(latencies)
    if count >= 100:
        quantiles = statistics.quantiles(latencies, n=100)
        p50 = round(quantiles[49], 2)
        p95 = round(quantiles[94], 2)
        p99 = round(quantiles[98], 2)
    elif count > 0:
        p50 = round(statistics.median(latencies), 2)
        p95 = round(latencies[int(count * 0.95)], 2)
        p99 = round(latencies[int(count * 0.99)], 2)
    else:
        p50 = p95 = p99 = 0.0

    rps = round(count / max(0.001, wall_duration), 1)
    err_count = sum(cnt for code, cnt in status_codes.items() if code >= 400)
    err_rate = round((err_count / max(1, count)) * 100.0, 2)
    cpu_pct = round((cpu_duration / max(0.001, wall_duration)) * 100.0, 1)
    mem_mb = round(peak_memory / (1024.0 * 1024.0), 2)

    result = {
        "concurrency": concurrency,
        "total_requests": count,
        "wall_time_sec": round(wall_duration, 2),
        "requests_per_second": rps,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "latency_p99_ms": p99,
        "error_count": err_count,
        "error_rate_pct": err_rate,
        "status_breakdown": status_codes,
        "cpu_utilization_pct": cpu_pct,
        "peak_memory_mb": mem_mb,
    }

    print(f"  Requests Per Second (RPS): {rps}")
    print(f"  p50 Latency: {p50} ms | p95: {p95} ms | p99: {p99} ms")
    print(f"  Error Rate: {err_rate}% ({err_count} errors)")
    print(f"  Status Codes: {status_codes}")
    print(f"  Peak Memory: {mem_mb} MB | CPU Utilization: {cpu_pct}%")
    return result

async def main():
    print("=" * 70)
    print("LOADLINK AI MASTER PROMPT 4: LOAD & PERFORMANCE BENCHMARK")
    print("=" * 70)

    # 1. 100 simulated concurrent users (300 requests)
    r100 = await run_concurrent_load_test(concurrency=100, total_requests=300)

    # 2. 500 simulated concurrent users (1000 requests)
    r500 = await run_concurrent_load_test(concurrency=500, total_requests=1000)

    # 3. 1,000 simulated concurrent users (2000 requests)
    r1000 = await run_concurrent_load_test(concurrency=1000, total_requests=2000)

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY TABLE:")
    print("=" * 70)
    print(f"{'Concurrency':<12} | {'RPS':<8} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'Error %':<8} | {'Peak RAM':<10}")
    print("-" * 75)
    for res in [r100, r500, r1000]:
        print(f"{res['concurrency']:<12} | {res['requests_per_second']:<8} | {res['latency_p50_ms']:<10} | {res['latency_p95_ms']:<10} | {res['latency_p99_ms']:<10} | {res['error_rate_pct']:<8} | {res['peak_memory_mb']} MB")

if __name__ == "__main__":
    asyncio.run(main())
