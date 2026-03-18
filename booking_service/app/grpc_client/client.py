import grpc
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import flight_pb2
import flight_pb2_grpc
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pybreaker
from app.grpc_client.circuit_breaker import flight_service_breaker, is_retryable_grpc_error
from app.core.config import settings

logger = logging.getLogger(__name__)

class FlightClient:
    def __init__(self):
        self.target = settings.FLIGHT_SERVICE_URL
        self.api_key = settings.API_KEY
        self._channel = None
        self._stub = None

    @property
    def stub(self):
        if self._channel is None:
            self._channel = grpc.aio.insecure_channel(self.target)
            self._stub = flight_pb2_grpc.FlightServiceStub(self._channel)
        return self._stub

    def _get_metadata(self):
        return (('authorization', f'Bearer {self.api_key}'),)

    @retry(
        stop=stop_after_attempt(settings.RETRY_MAX_ATTEMPTS), 
        wait=wait_exponential(multiplier=settings.RETRY_BACKOFF_BASE, max=10), 
        retry=retry_if_exception_type(grpc.aio.AioRpcError)
    )
    async def get_flight(self, flight_id: int):
        request = flight_pb2.GetFlightRequest(id=flight_id)
        try:
            response = await flight_service_breaker.call(self.stub.GetFlight, request, metadata=self._get_metadata())
            return response
        except pybreaker.CircuitBreakerError as e:
            logger.error("Circuit breaker OPEN")
            raise grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, None, None, None, "Circuit breaker OPEN")
        except grpc.aio.AioRpcError as e:
            if is_retryable_grpc_error(e):
                logger.warning(f"Retrying GetFlight due to {e.code()}")
                raise e
            logger.error(f"gRPC error on GetFlight: {e.code()} - {e.details()}")
            raise e

    @retry(
        stop=stop_after_attempt(settings.RETRY_MAX_ATTEMPTS), 
        wait=wait_exponential(multiplier=settings.RETRY_BACKOFF_BASE, max=10), 
        retry=retry_if_exception_type(grpc.aio.AioRpcError)
    )
    async def search_flights(self, origin: str, destination: str, date: str = ""):
        request = flight_pb2.SearchFlightsRequest(origin=origin, destination=destination, date=date)
        try:
            response = await flight_service_breaker.call(self.stub.SearchFlights, request, metadata=self._get_metadata())
            return response.flights
        except pybreaker.CircuitBreakerError as e:
            logger.error("Circuit breaker OPEN")
            raise grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, None, None, None, "Circuit breaker OPEN")
        except grpc.aio.AioRpcError as e:
            if is_retryable_grpc_error(e):
                logger.warning(f"Retrying SearchFlights due to {e.code()}")
                raise e
            logger.error(f"gRPC error on SearchFlights: {e.code()} - {e.details()}")
            raise e

    @retry(
        stop=stop_after_attempt(settings.RETRY_MAX_ATTEMPTS), 
        wait=wait_exponential(multiplier=settings.RETRY_BACKOFF_BASE, max=10), 
        retry=retry_if_exception_type(grpc.aio.AioRpcError)
    )
    async def reserve_seats(self, flight_id: int, seat_count: int, booking_id: str):
        request = flight_pb2.ReserveSeatsRequest(
            flight_id=flight_id,
            seat_count=seat_count,
            booking_id=booking_id
        )
        try:
            response = await flight_service_breaker.call(self.stub.ReserveSeats, request, metadata=self._get_metadata())
            return response.success
        except pybreaker.CircuitBreakerError as e:
            logger.error("Circuit breaker OPEN")
            raise grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, None, None, None, "Circuit breaker OPEN")
        except grpc.aio.AioRpcError as e:
            if is_retryable_grpc_error(e):
                logger.warning(f"Retrying ReserveSeats due to {e.code()}")
                raise e
            logger.error(f"gRPC error on ReserveSeats: {e.code()} - {e.details()}")
            raise e

    @retry(
        stop=stop_after_attempt(settings.RETRY_MAX_ATTEMPTS), 
        wait=wait_exponential(multiplier=settings.RETRY_BACKOFF_BASE, max=10), 
        retry=retry_if_exception_type(grpc.aio.AioRpcError)
    )
    async def release_reservation(self, booking_id: str):
        request = flight_pb2.ReleaseReservationRequest(booking_id=booking_id)
        try:
            response = await flight_service_breaker.call(self.stub.ReleaseReservation, request, metadata=self._get_metadata())
            return response.success
        except pybreaker.CircuitBreakerError as e:
            logger.error("Circuit breaker OPEN")
            raise grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, None, None, None, "Circuit breaker OPEN")
        except grpc.aio.AioRpcError as e:
            if is_retryable_grpc_error(e):
                logger.warning(f"Retrying ReleaseReservation due to {e.code()}")
                raise e
            logger.error(f"gRPC error on ReleaseReservation: {e.code()} - {e.details()}")
            raise e