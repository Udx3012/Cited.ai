import time
import logging
from typing import Dict, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class RateLimitingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int = 60):
        super().__init__(app)
        self.limit = limit_per_minute
        # Dictionary storing client IP: (request_count, window_start_time)
        self.clients: Dict[str, Tuple[int, float]] = {}

    async def dispatch(self, request: Request, call_next):
        # Exclude health check endpoints from rate limiting
        if request.url.path in ["/health", "/ready"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown_ip"
        current_time = time.time()
        
        # Check window
        if client_ip not in self.clients:
            self.clients[client_ip] = (1, current_time)
        else:
            count, window_start = self.clients[client_ip]
            if current_time - window_start > 60.0:
                # Reset window
                self.clients[client_ip] = (1, current_time)
            else:
                if count >= self.limit:
                    logger.warning(f"Rate limit exceeded for IP: {client_ip} on path {request.url.path}")
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests. Rate limit exceeded."}
                    )
                else:
                    self.clients[client_ip] = (count + 1, window_start)

        return await call_next(request)
