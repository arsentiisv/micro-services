import uuid
import grpc
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Booking
from app.schemas.booking import BookingCreate, BookingResponse
from app.grpc_client.client import FlightClient

class BookingService:
    def __init__(self, db: AsyncSession, flight_client: FlightClient):
        self.db = db
        self.flight_client = flight_client

    async def create_booking(self, booking_data: BookingCreate):
        flight_id = booking_data.flight_id
        try:
            flight = await self.flight_client.get_flight(flight_id)
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise HTTPException(status_code=404, detail="Flight not found")
            raise HTTPException(status_code=500, detail="Error fetching flight info")

        booking_id = uuid.uuid4()
        total_price = booking_data.seat_count * flight.price

        try:
            success = await self.flight_client.reserve_seats(
                flight_id, booking_data.seat_count, str(booking_id)
            )
            if not success:
                 raise HTTPException(status_code=400, detail="Could not reserve seats")
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
                raise HTTPException(status_code=400, detail="Not enough available seats")
            raise HTTPException(status_code=500, detail=f"Error reserving seats: {e.details()}")

        db_booking = Booking(
            id=booking_id,
            user_id=booking_data.user_id,
            flight_id=flight_id,
            passenger_name=booking_data.passenger_name,
            passenger_email=booking_data.passenger_email,
            seat_count=booking_data.seat_count,
            total_price=total_price,
            status="CONFIRMED"
        )
        self.db.add(db_booking)
        await self.db.commit()
        await self.db.refresh(db_booking)
        return db_booking

    async def get_booking(self, booking_id: uuid.UUID):
        result = await self.db.execute(select(Booking).filter(Booking.id == booking_id))
        booking = result.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return booking

    async def cancel_booking(self, booking_id: uuid.UUID):
        booking = await self.get_booking(booking_id)
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail="Booking is not in CONFIRMED status")
            
        try:
            success = await self.flight_client.release_reservation(str(booking_id))
            if not success:
                raise HTTPException(status_code=500, detail="Error releasing reservation in Flight Service")
        except grpc.aio.AioRpcError as e:
            raise HTTPException(status_code=500, detail=f"Error releasing reservation: {e.details()}")

        booking.status = "CANCELLED"
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def list_bookings(self, user_id: int):
        result = await self.db.execute(select(Booking).filter(Booking.user_id == user_id))
        return result.scalars().all()