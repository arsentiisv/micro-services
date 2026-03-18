import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flight_pb2
import flight_pb2_grpc
from app.db.models import Flight, SeatReservation
import grpc
from redis.asyncio.sentinel import Sentinel
from app.core.config import settings

logger = logging.getLogger(__name__)

class FlightBusinessService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Настройка подключения к Redis Sentinel
        self.sentinel = Sentinel(
            [(settings.REDIS_SENTINEL_HOST, settings.REDIS_SENTINEL_PORT)],
            socket_timeout=0.1
        )
        self.redis = self.sentinel.master_for(settings.REDIS_MASTER_NAME, decode_responses=True)

    def _serialize_flight(self, f: Flight):
        return {
            "id": f.id,
            "flight_number": f.flight_number,
            "airline": f.airline,
            "origin": f.origin,
            "destination": f.destination,
            "departure_time": f.departure_time.isoformat(),
            "arrival_time": f.arrival_time.isoformat(),
            "total_seats": f.total_seats,
            "available_seats": f.available_seats,
            "price": f.price,
            "status": f.status
        }
        
    def _deserialize_flight(self, data: dict):
        f = Flight()
        for k, v in data.items():
            if k in ['departure_time', 'arrival_time']:
                setattr(f, k, datetime.fromisoformat(v))
            else:
                setattr(f, k, v)
        return f

    async def get_flight(self, flight_id: int):
        cache_key = f"flight:{flight_id}"
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {cache_key}")
                return self._deserialize_flight(json.loads(cached))
        except Exception as e:
            logger.warning(f"Redis error: {e}")
            
        logger.info(f"Cache miss for {cache_key}")
        result = await self.db.execute(select(Flight).filter(Flight.id == flight_id))
        flight = result.scalar_one_or_none()
        
        if flight:
            try:
                await self.redis.setex(cache_key, 300, json.dumps(self._serialize_flight(flight)))
            except Exception as e:
                logger.warning(f"Redis error: {e}")
            
        return flight

    async def search_flights(self, origin: str, destination: str, date: str):
        cache_key = f"search:{origin}:{destination}:{date}"
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {cache_key}")
                return [self._deserialize_flight(f) for f in json.loads(cached)]
        except Exception as e:
             logger.warning(f"Redis error: {e}")
            
        logger.info(f"Cache miss for {cache_key}")
        query = select(Flight).filter(
            Flight.origin == origin,
            Flight.destination == destination,
            Flight.status == "SCHEDULED"
        )
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                query = query.filter(
                    Flight.departure_time >= datetime.combine(date_obj, datetime.min.time()),
                    Flight.departure_time <= datetime.combine(date_obj, datetime.max.time())
                )
            except ValueError:
                pass

        result = await self.db.execute(query)
        flights = result.scalars().all()
        
        try:
            await self.redis.setex(cache_key, 300, json.dumps([self._serialize_flight(f) for f in flights]))
        except Exception as e:
             logger.warning(f"Redis error: {e}")
        return flights

    async def _invalidate_flight_cache(self, flight_id: int):
        try:
            await self.redis.delete(f"flight:{flight_id}")
        except Exception as e:
             logger.warning(f"Redis error: {e}")

    async def reserve_seats(self, flight_id: int, seat_count: int, booking_id: str):
        try:
            result = await self.db.execute(
                select(Flight).filter(Flight.id == flight_id).with_for_update()
            )
            flight = result.scalar_one_or_none()

            if not flight:
                raise ValueError("Flight not found")

            if flight.available_seats < seat_count:
                raise ValueError("Not enough seats available")

            existing_res = await self.db.execute(
                select(SeatReservation).filter(SeatReservation.booking_id == booking_id)
            )
            if existing_res.scalar_one_or_none():
                await self.db.rollback()
                return True

            reservation = SeatReservation(
                flight_id=flight_id,
                booking_id=booking_id,
                seat_count=seat_count,
                status="ACTIVE"
            )
            self.db.add(reservation)

            flight.available_seats -= seat_count
            
            await self.db.commit()
            await self._invalidate_flight_cache(flight_id)
            return True
        except ValueError as e:
            await self.db.rollback()
            raise e
        except Exception as e:
            await self.db.rollback()
            raise e

    async def release_reservation(self, booking_id: str):
        try:
            result = await self.db.execute(
                select(SeatReservation).filter(
                    SeatReservation.booking_id == booking_id,
                    SeatReservation.status == "ACTIVE"
                ).with_for_update()
            )
            reservation = result.scalar_one_or_none()

            if not reservation:
                return True

            result_flight = await self.db.execute(
                select(Flight).filter(Flight.id == reservation.flight_id).with_for_update()
            )
            flight = result_flight.scalar_one_or_none()

            if not flight:
                raise ValueError("Flight not found")

            reservation.status = "RELEASED"
            flight.available_seats += reservation.seat_count
            
            await self.db.commit()
            await self._invalidate_flight_cache(flight.id)
            return True
        except Exception as e:
            await self.db.rollback()
            raise e