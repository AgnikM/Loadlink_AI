import json
import logging
import time
from typing import Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("loadlink.access")
logging.basicConfig(level=logging.INFO, format="%(message)s")

class MetricsStore:
    def __init__(self):
        self.requests_total: int = 0
        self.status_2xx: int = 0
        self.status_4xx: int = 0
        self.status_5xx: int = 0
        self.total_duration_ms: float = 0.0
        self.gps_ingested_count: int = 0
        self.sos_event_count: int = 0

    def record_request(self, status_code: int, duration_ms: float, path: str):
        self.requests_total += 1
        self.total_duration_ms += duration_ms
        if 200 <= status_code < 300:
            self.status_2xx += 1
        elif 400 <= status_code < 500:
            self.status_4xx += 1
        elif status_code >= 500:
            self.status_5xx += 1

        if "/tracking/batch" in path and 200 <= status_code < 300:
            self.gps_ingested_count += 1
        elif "/sos" in path and 200 <= status_code < 300:
            self.sos_event_count += 1

    def get_summary(self) -> Dict[str, Any]:
        avg_ms = round(self.total_duration_ms / max(1, self.requests_total), 2)
        return {
            "requests_total": self.requests_total,
            "status_2xx": self.status_2xx,
            "status_4xx": self.status_4xx,
            "status_5xx": self.status_5xx,
            "average_latency_ms": avg_ms,
            "gps_batches_ingested": self.gps_ingested_count,
            "sos_events_processed": self.sos_event_count,
        }

metrics = MetricsStore()

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            duration_ms = round((time.time() - start_time) * 1000, 2)
            metrics.record_request(status_code, duration_ms, path)
            log_record = {
                "timestamp": time.time(),
                "level": "ERROR",
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
                "error": str(e),
            }
            logger.error(json.dumps(log_record))
            raise e

        duration_ms = round((time.time() - start_time) * 1000, 2)
        metrics.record_request(status_code, duration_ms, path)

        # Do not log health checks to keep logs clean
        if path not in ["/health", "/docs", "/openapi.json", "/redoc"]:
            log_record = {
                "timestamp": time.time(),
                "level": "INFO" if status_code < 400 else ("WARNING" if status_code < 500 else "ERROR"),
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            }
            logger.info(json.dumps(log_record))

        return response
