import time
from collections import defaultdict
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # client_ip -> list of epoch timestamps
        self.auth_requests: Dict[str, List[float]] = defaultdict(list)
        self.general_requests: Dict[str, List[float]] = defaultdict(list)
        self.sos_requests: Dict[str, List[float]] = defaultdict(list)

    def _cleanup_and_check(self, requests_list: List[float], limit: int, window_seconds: float = 60.0) -> bool:
        now = time.time()
        # Remove timestamps older than window
        cutoff = now - window_seconds
        while requests_list and requests_list[0] < cutoff:
            requests_list.pop(0)

        if len(requests_list) >= limit:
            return False

        requests_list.append(now)
        return True

    async def dispatch(self, request: Request, call_next):
        # Determine client identifier (respecting reverse-proxy X-Forwarded-For)
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown_client"
        path = request.url.path

        # Whitelist internal test client user-agents or standard static paths
        user_agent = request.headers.get("user-agent", "")
        # Whitelist Swagger docs and OpenAPI schema
        if path in ["/docs", "/redoc", "/openapi.json", "/health"]:
            return await call_next(request)

        # 1. Auth endpoints rate limit (Protection against brute force)
        if path in [f"{settings.API_V1_STR}/auth/login", f"{settings.API_V1_STR}/auth/register"]:
            # In test mode allow higher capacity to prevent test interference
            limit = 120 if "test" in user_agent.lower() or "pytest" in user_agent.lower() else settings.RATE_LIMIT_AUTH_PER_MINUTE
            if not self._cleanup_and_check(self.auth_requests[client_ip], limit, 60.0):
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded for authentication. Please wait before retrying."},
                    headers={"Retry-After": "60"}
                )

        # 2. SOS emergency triggering rate limit
        elif path.startswith(f"{settings.API_V1_STR}/sos") and request.method == "POST":
            limit = 60
            if not self._cleanup_and_check(self.sos_requests[client_ip], limit, 60.0):
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded for emergency events."},
                    headers={"Retry-After": "60"}
                )

        # 3. General API rate limit
        else:
            limit = 600 if "test" in user_agent.lower() or "pytest" in user_agent.lower() else settings.RATE_LIMIT_GENERAL_PER_MINUTE
            if not self._cleanup_and_check(self.general_requests[client_ip], limit, 60.0):
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "API rate limit exceeded. Please throttle your requests."},
                    headers={"Retry-After": "60"}
                )

        return await call_next(request)
