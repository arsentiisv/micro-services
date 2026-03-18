from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://flight_user:flight_password@localhost:5432/flight_db"
    REDIS_SENTINEL_HOST: str = "localhost"
    REDIS_SENTINEL_PORT: int = 26379
    REDIS_MASTER_NAME: str = "mymaster"
    API_KEY: str = "super_secret_key"
    
    class Config:
        env_file = ".env"

settings = Settings()