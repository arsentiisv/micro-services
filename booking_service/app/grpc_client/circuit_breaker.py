import pybreaker
import logging
import grpc
from app.core.config import settings

logger = logging.getLogger(__name__)

class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        logger.warning(f"Circuit Breaker state changed from {old_state.name} to {new_state.name}")

# Create circuit breaker instance using settings
flight_service_breaker = pybreaker.CircuitBreaker(
    fail_max=settings.CB_FAILURE_THRESHOLD,
    reset_timeout=settings.CB_RECOVERY_TIMEOUT,
    listeners=[CircuitBreakerListener()]
)

def is_retryable_grpc_error(exception):
    if isinstance(exception, grpc.aio.AioRpcError):
        return exception.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED)
    return False