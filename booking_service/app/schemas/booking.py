from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID

class BookingCreate(BaseModel):
    user_id: int
    flight_id: int
    passenger_name: str
    passenger_email: EmailStr
    seat_count: int

class BookingResponse(BaseModel):
    id: UUID
    user_id: int
    flight_id: int
    passenger_name: str
    passenger_email: EmailStr
    seat_count: int
    total_price: float
    status: str

    model_config = ConfigDict(from_attributes=True)