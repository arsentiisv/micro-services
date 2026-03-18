import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base

class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, nullable=False)
    flight_id = Column(Integer, nullable=False)
    passenger_name = Column(String, nullable=False)
    passenger_email = Column(String, nullable=False)
    seat_count = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="CONFIRMED") # CONFIRMED, CANCELLED