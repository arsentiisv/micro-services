import logging
import grpc
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import flight_pb2
import flight_pb2_grpc
from app.db.database import get_db
from app.services.flight_service import FlightBusinessService
from app.core.config import settings

logger = logging.getLogger(__name__)

class FlightServiceServicer(flight_pb2_grpc.FlightServiceServicer):
    def _check_auth(self, context):
        metadata = dict(context.invocation_metadata())
        auth_header = metadata.get('authorization', '')
        if not auth_header.startswith('Bearer '):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Missing or invalid authentication token')
        token = auth_header.split('Bearer ')[1]
        if token != settings.API_KEY:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Invalid API Key')

    async def SearchFlights(self, request, context):
        self._check_auth(context)
        logger.info(f"SearchFlights called with origin={request.origin}, dest={request.destination}")
        async for session in get_db():
            service = FlightBusinessService(session)
            flights = await service.search_flights(request.origin, request.destination, request.date)
            
            response = flight_pb2.SearchFlightsResponse()
            for f in flights:
                flight_pb = response.flights.add()
                flight_pb.id = f.id
                flight_pb.flight_number = f.flight_number
                flight_pb.airline = f.airline
                flight_pb.origin = f.origin
                flight_pb.destination = f.destination
                flight_pb.departure_time.FromDatetime(f.departure_time)
                flight_pb.arrival_time.FromDatetime(f.arrival_time)
                flight_pb.total_seats = f.total_seats
                flight_pb.available_seats = f.available_seats
                flight_pb.price = f.price
                flight_pb.status = getattr(flight_pb2.FlightStatus, f.status)
            return response

    async def GetFlight(self, request, context):
        self._check_auth(context)
        logger.info(f"GetFlight called for id={request.id}")
        async for session in get_db():
            service = FlightBusinessService(session)
            f = await service.get_flight(request.id)
            if not f:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")

            flight_pb = flight_pb2.Flight()
            flight_pb.id = f.id
            flight_pb.flight_number = f.flight_number
            flight_pb.airline = f.airline
            flight_pb.origin = f.origin
            flight_pb.destination = f.destination
            flight_pb.departure_time.FromDatetime(f.departure_time)
            flight_pb.arrival_time.FromDatetime(f.arrival_time)
            flight_pb.total_seats = f.total_seats
            flight_pb.available_seats = f.available_seats
            flight_pb.price = f.price
            flight_pb.status = getattr(flight_pb2.FlightStatus, f.status)
            return flight_pb

    async def ReserveSeats(self, request, context):
        self._check_auth(context)
        logger.info(f"ReserveSeats called for flight_id={request.flight_id}, seats={request.seat_count}")
        async for session in get_db():
            service = FlightBusinessService(session)
            try:
                success = await service.reserve_seats(request.flight_id, request.seat_count, request.booking_id)
                return flight_pb2.ReserveSeatsResponse(success=success)
            except ValueError as e:
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, str(e))
            except Exception as e:
                context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def ReleaseReservation(self, request, context):
        self._check_auth(context)
        logger.info(f"ReleaseReservation called for booking_id={request.booking_id}")
        async for session in get_db():
            service = FlightBusinessService(session)
            try:
                success = await service.release_reservation(request.booking_id)
                return flight_pb2.ReleaseReservationResponse(success=success)
            except Exception as e:
                context.abort(grpc.StatusCode.INTERNAL, str(e))