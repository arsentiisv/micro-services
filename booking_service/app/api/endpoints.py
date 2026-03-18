import uuid
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.booking import BookingCreate, BookingResponse
from app.services.booking_service import BookingService
from app.grpc_client.client import FlightClient
import flight_pb2
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter()

def get_flight_client():
    return FlightClient()

def get_booking_service(db: AsyncSession = Depends(get_db), flight_client: FlightClient = Depends(get_flight_client)):
    return BookingService(db, flight_client)

@router.post("/bookings", response_model=BookingResponse)
async def create_booking(booking_in: BookingCreate, service: BookingService = Depends(get_booking_service)):
    return await service.create_booking(booking_in)

@router.get("/bookings/{id}", response_model=BookingResponse)
async def get_booking(id: uuid.UUID, service: BookingService = Depends(get_booking_service)):
    return await service.get_booking(id)

@router.post("/bookings/{id}/cancel", response_model=BookingResponse)
async def cancel_booking(id: uuid.UUID, service: BookingService = Depends(get_booking_service)):
    return await service.cancel_booking(id)

@router.get("/bookings", response_model=List[BookingResponse])
async def list_bookings(user_id: int = Query(...), service: BookingService = Depends(get_booking_service)):
    return await service.list_bookings(user_id)

def flight_status_to_string(status_enum):
    if status_enum == flight_pb2.FlightStatus.SCHEDULED: return "SCHEDULED"
    if status_enum == flight_pb2.FlightStatus.DEPARTED: return "DEPARTED"
    if status_enum == flight_pb2.FlightStatus.CANCELLED: return "CANCELLED"
    if status_enum == flight_pb2.FlightStatus.COMPLETED: return "COMPLETED"
    return "UNKNOWN_STATUS"

@router.get("/flights")
async def get_flights(origin: str = Query(...), destination: str = Query(...), date: str = Query(None), client: FlightClient = Depends(get_flight_client)):
    try:
        flights = await client.search_flights(origin, destination, date or "")
        return [{
            "id": f.id, 
            "flight_number": f.flight_number, 
            "airline": f.airline, 
            "origin": f.origin, 
            "destination": f.destination, 
            "departure_time": f.departure_time.ToDatetime().isoformat(), 
            "arrival_time": f.arrival_time.ToDatetime().isoformat(), 
            "total_seats": f.total_seats, 
            "available_seats": f.available_seats, 
            "price": f.price, 
            "status": flight_status_to_string(f.status)
        } for f in flights]
    except Exception as e:
        logger.error(f"Error in get_flights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/flights/{id}")
async def get_flight(id: int, client: FlightClient = Depends(get_flight_client)):
    try:
        f = await client.get_flight(id)
        return {
            "id": f.id, 
            "flight_number": f.flight_number, 
            "airline": f.airline, 
            "origin": f.origin, 
            "destination": f.destination, 
            "departure_time": f.departure_time.ToDatetime().isoformat(), 
            "arrival_time": f.arrival_time.ToDatetime().isoformat(), 
            "total_seats": f.total_seats, 
            "available_seats": f.available_seats, 
            "price": f.price, 
            "status": flight_status_to_string(f.status)
        }
    except Exception as e:
         logger.error(f"Error in get_flight: {e}")
         raise HTTPException(status_code=404, detail="Flight not found")