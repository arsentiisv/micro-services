from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base
from datetime import datetime

class Flight(Base):
    __tablename__ = "flights"
    
    id = Column(Integer, primary_key=True)
    flight_number = Column(String, nullable=False)
    airline = Column(String, nullable=False)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="SCHEDULED") # SCHEDULED, DEPARTED, CANCELLED, COMPLETED
    
    __table_args__ = (
        CheckConstraint('available_seats >= 0', name='check_available_seats_positive'),
        CheckConstraint('price > 0', name='check_price_positive'),
        UniqueConstraint('flight_number', 'departure_time', name='uix_flight_number_departure_time'),
    )

class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    
    id = Column(Integer, primary_key=True)
    flight_id = Column(Integer, ForeignKey('flights.id'), nullable=False)
    booking_id = Column(String, unique=True, nullable=False) # UUID string
    seat_count = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE") # ACTIVE, RELEASED, EXPIRED