from fastapi import FastAPI
from app.api.endpoints import router
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Booking Service")

app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "ok"}