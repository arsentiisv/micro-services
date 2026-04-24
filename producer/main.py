import asyncio
import logging
import os
import random
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

import requests
from confluent_kafka import SerializingProducer
from confluent_kafka.error import KafkaException
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
logger = logging.getLogger("producer")
logging.basicConfig(level=logging.INFO)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
SCHEMA_REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081")
GENERATOR_MODE = os.environ.get("GENERATOR_MODE", "false").lower() == "true"
TOPIC_NAME = "movie-events"
PRODUCE_MAX_ATTEMPTS = int(os.environ.get("PRODUCE_MAX_ATTEMPTS", "5"))
PRODUCE_BACKOFF_BASE_SECONDS = float(os.environ.get("PRODUCE_BACKOFF_BASE_SECONDS", "0.25"))


class EventType(str, Enum):
    VIEW_STARTED = "VIEW_STARTED"
    VIEW_FINISHED = "VIEW_FINISHED"
    VIEW_PAUSED = "VIEW_PAUSED"
    VIEW_RESUMED = "VIEW_RESUMED"
    LIKED = "LIKED"
    SEARCHED = "SEARCHED"


class DeviceType(str, Enum):
    MOBILE = "MOBILE"
    DESKTOP = "DESKTOP"
    TV = "TV"
    TABLET = "TABLET"


class MovieEvent(BaseModel):
    event_id: Optional[UUID] = Field(default_factory=uuid.uuid4)
    user_id: str
    movie_id: str
    event_type: EventType
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    device_type: DeviceType
    session_id: str
    progress_seconds: int

    def to_payload(self) -> dict:
        payload = self.model_dump(mode="json")
        if self.timestamp is not None:
            payload["timestamp"] = int(self.timestamp.astimezone(timezone.utc).timestamp() * 1000)
        return payload


with open("/schemas/movie_event.avsc", "r", encoding="utf-8") as f:
    schema_str = f.read()

schema_registry_conf = {"url": SCHEMA_REGISTRY_URL}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)
avro_serializer = AvroSerializer(schema_registry_client, schema_str)

producer_conf = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "value.serializer": avro_serializer,
    "acks": "all",
    "retries": 5,
    "retry.backoff.ms": 500,
}

producer = None


def _build_delivery_callback(state: dict, event_meta: dict):
    def _callback(err, msg):
        state["error"] = err
        state["done"].set()
        if err is not None:
            logger.error(
                "Delivery failed event_id=%s event_type=%s timestamp=%s error=%s",
                event_meta["event_id"],
                event_meta["event_type"],
                event_meta["timestamp"],
                err,
            )
        else:
            logger.info(
                "Delivered event_id=%s event_type=%s timestamp=%s topic=%s partition=%s offset=%s",
                event_meta["event_id"],
                event_meta["event_type"],
                event_meta["timestamp"],
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )

    return _callback


def _produce_with_ack(payload: dict, key: str):
    last_error = None
    for attempt in range(1, PRODUCE_MAX_ATTEMPTS + 1):
        state = {"done": threading.Event(), "error": None}
        callback = _build_delivery_callback(
            state,
            {
                "event_id": payload["event_id"],
                "event_type": payload["event_type"],
                "timestamp": payload["timestamp"],
            },
        )
        try:
            producer.produce(topic=TOPIC_NAME, key=key, value=payload, on_delivery=callback)
            while not state["done"].wait(timeout=0.1):
                producer.poll(0.1)
            producer.poll(0)
            if state["error"] is not None:
                raise KafkaException(state["error"])
            return
        except Exception as exc:
            last_error = exc
            backoff = PRODUCE_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "Produce attempt %s/%s failed for event_id=%s error=%s, retry in %.2fs",
                attempt,
                PRODUCE_MAX_ATTEMPTS,
                payload["event_id"],
                exc,
                backoff,
            )
            if attempt < PRODUCE_MAX_ATTEMPTS:
                awaiter = threading.Event()
                awaiter.wait(timeout=backoff)

    raise RuntimeError(f"Failed to deliver event after {PRODUCE_MAX_ATTEMPTS} attempts: {last_error}")


async def _wait_schema_registry():
    retries = 20
    backoff = 0.5
    while retries > 0:
        try:
            requests.get(SCHEMA_REGISTRY_URL, timeout=2)
            return
        except Exception:
            logger.info("Waiting for schema registry...")
            retries -= 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5)

    raise RuntimeError("Schema Registry is unavailable")


@app.on_event("startup")
async def startup_event():
    global producer
    await _wait_schema_registry()
    producer = SerializingProducer(producer_conf)

    if GENERATOR_MODE:
        asyncio.create_task(run_generator())


@app.post("/events")
async def send_event(event: MovieEvent):
    try:
        payload = event.to_payload()
        _produce_with_ack(payload, key=event.user_id)
        return {"event_id": payload["event_id"], "status": "success"}
    except Exception as exc:
        logger.exception("Error sending event")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


def _emit_generated_event(payload: dict):
    _produce_with_ack(payload=payload, key=payload["user_id"])


async def run_generator():
    logger.info("Starting generator mode...")
    users = [str(uuid.uuid4()) for _ in range(10)]
    movies = [str(uuid.uuid4()) for _ in range(5)]
    devices = [device.value for device in DeviceType]

    while True:
        user_id = random.choice(users)
        movie_id = random.choice(movies)
        session_id = str(uuid.uuid4())
        device = random.choice(devices)

        # Realistic sequence inside one session.
        progress = 0
        _emit_generated_event(
            {
                "event_id": str(uuid.uuid4()),
                "user_id": user_id,
                "movie_id": movie_id,
                "event_type": EventType.VIEW_STARTED.value,
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "device_type": device,
                "session_id": session_id,
                "progress_seconds": progress,
            }
        )

        await asyncio.sleep(random.uniform(0.5, 2.0))

        if random.random() > 0.4:
            progress += random.randint(15, 180)
            _emit_generated_event(
                {
                    "event_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "movie_id": movie_id,
                    "event_type": EventType.VIEW_PAUSED.value,
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "device_type": device,
                    "session_id": session_id,
                    "progress_seconds": progress,
                }
            )
            await asyncio.sleep(random.uniform(0.3, 1.0))
            progress += random.randint(10, 120)
            _emit_generated_event(
                {
                    "event_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "movie_id": movie_id,
                    "event_type": EventType.VIEW_RESUMED.value,
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "device_type": device,
                    "session_id": session_id,
                    "progress_seconds": progress,
                }
            )

        if random.random() > 0.5:
            _emit_generated_event(
                {
                    "event_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "movie_id": movie_id,
                    "event_type": EventType.LIKED.value,
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "device_type": device,
                    "session_id": session_id,
                    "progress_seconds": progress,
                }
            )

        progress += random.randint(120, 3600)
        _emit_generated_event(
            {
                "event_id": str(uuid.uuid4()),
                "user_id": user_id,
                "movie_id": movie_id,
                "event_type": EventType.VIEW_FINISHED.value,
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "device_type": device,
                "session_id": session_id,
                "progress_seconds": progress,
            }
        )

        await asyncio.sleep(1)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
