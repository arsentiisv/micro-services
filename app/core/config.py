from pydantic import BaseSettings

class Settings(BaseSettings):
    # ИЗМЕНЕНО: Порт 5455
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5455/marketplace"
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    class Config:
        env_file = ".env"

settings = Settings()
