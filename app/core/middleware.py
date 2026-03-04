import time
import uuid
import json
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("api_logger")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Add request_id to request state for later use
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": getattr(request.state, "user_id", None),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S%z')
        }
        
        logger.info(json.dumps(log_data))
        
        response.headers["X-Request-Id"] = request_id
        return response
