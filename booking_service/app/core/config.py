from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://booking_user:booking_password@localhost:5433/booking_db"
    FLIGHT_SERVICE_URL: str = "localhost:50051"
    API_KEY: str = "super_secret_key"
    
    # Circuit Breaker configs
    CB_FAILURE_THRESHOLD: int = 5
    CB_RECOVERY_TIMEOUT: int = 30
    
    # Retry configs
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BACKOFF_BASE: float = 0.1

    class Config:
        env_file = ".env"

settings = Settings()