import sys
import asyncio
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.products import router as products_router
from app.api.orders import router as orders_router
from app.api.promo_codes import router as promo_codes_router
from app.api.auth import router as auth_router
from app.core.middleware import LoggingMiddleware
from app.core.db_init import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Windows-specific event loop policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(title="Marketplace API")

app.add_middleware(LoggingMiddleware)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Не прерываем запуск, так как база может быть уже инициализирована

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = {}
    for error in exc.errors():
        field = error['loc'][-1] if error['loc'] else 'unknown'
        details[str(field)] = error['msg']

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": details
        }
    )

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(promo_codes_router)

@app.get("/ping")
async def ping():
    return {"message": "pong"}
