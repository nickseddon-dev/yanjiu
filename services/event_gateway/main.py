"""Main entry point for event_gateway service.

Event stream processing with Redis Streams - handles event ingestion,
deduplication, enrichment, and routing to downstream consumers.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel, Field
import uvicorn

from event_schema.base import EventSnapshot, EventType

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
EVENT_STREAM_KEY = os.getenv("EVENT_STREAM_KEY", "events:stream")
EVENT_DEDUP_WINDOW = int(os.getenv("EVENT_DEDUP_WINDOW", "300"))  # 5 minutes
EVENT_TTL = int(os.getenv("EVENT_TTL", "86400"))  # 24 hours
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "event_processors")
CONSUMER_NAME = os.getenv("CONSUMER_NAME", f"consumer-{uuid.uuid4().hex[:8]}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("event_gateway")

app = FastAPI(title="Event Gateway", version="1.0.0", description="Event stream processing service")


# --- Pydantic Models ---

class EventRequest(BaseModel):
    """Incoming event request."""
    event_type: str
    source: str
    symbol: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    intensity: float = Field(default=0.0, ge=0.0, le=1.0)
    decay_window_h: int = Field(default=24, ge=1, le=168)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    """Event processing response."""
    event_id: str
    status: str
    message: str
    processed_at: str


class EventBatchRequest(BaseModel):
    """Batch event ingestion."""
    events: List[EventRequest]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis_connected: bool
    stream_length: int
    timestamp: str


# --- Redis Client Management ---

class RedisClient:
    """Async Redis client manager."""
    
    def __init__(self, url: str):
        self.url = url
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Establish Redis connection."""
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
            logger.info(f"Connected to Redis at {self.url}")
        return self._client
    
    async def disconnect(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Redis")
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    async def is_connected(self) -> bool:
        try:
            if self._client is None:
                return False
            await self._client.ping()
            return True
        except Exception:
            return False


# Global Redis client
redis_client = RedisClient(REDIS_URL)


# --- Event Gateway Logic ---

class EventGateway:
    """Event stream processing and routing."""
    
    def __init__(self, redis_cli: RedisClient):
        self.redis = redis_cli
        self.dedup_window = EVENT_DEDUP_WINDOW
        self.ttl = EVENT_TTL
    
    def _dedup_key(self, event_type: str, source: str, symbol: str) -> str:
        """Generate deduplication key for similar events."""
        return f"dedup:{event_type}:{source}:{symbol}"
    
    async def _is_duplicate(self, dedup_key: str) -> bool:
        """Check if event is duplicate within dedup window."""
        exists = await self.redis.client.exists(dedup_key)
        return bool(exists)
    
    async def _mark_processed(self, dedup_key: str) -> None:
        """Mark event as processed for deduplication."""
        await self.redis.client.setex(dedup_key, self.dedup_window, "1")
    
    async def _store_event(self, event: EventSnapshot) -> None:
        """Store event in Redis with TTL."""
        import json
        key = f"event:{event.event_id}"
        await self.redis.client.setex(key, self.ttl, json.dumps(event.to_dict()))
    
    async def _add_to_stream(self, event: EventSnapshot) -> str:
        """Add event to Redis stream for consumers."""
        import json
        msg_id = await self.redis.client.xadd(
            EVENT_STREAM_KEY,
            {"event": json.dumps(event.to_dict())},
            maxlen=10000
        )
        return msg_id
    
    async def ingest_event(self, request: EventRequest) -> EventResponse:
        """Ingest and process a single event."""
        # Create event snapshot
        event = EventSnapshot(
            event_id=str(uuid.uuid4()),
            event_type=EventType(request.event_type),
            source=request.source,
            symbol=request.symbol,
            timestamp=datetime.now(timezone.utc),
            confidence=request.confidence,
            intensity=request.intensity,
            decay_window_h=request.decay_window_h,
            raw_payload=tuple(request.raw_payload.items())
        )
        
        # Deduplication check
        dedup_key = self._dedup_key(request.event_type, request.source, request.symbol)
        if await self._is_duplicate(dedup_key):
            logger.info(f"Duplicate event filtered: {event.event_id}")
            return EventResponse(
                event_id=event.event_id,
                status="DUPLICATE",
                message="Event filtered as duplicate",
                processed_at=datetime.now(timezone.utc).isoformat()
            )
        
        # Mark as processed (dedup)
        await self._mark_processed(dedup_key)
        
        # Store event
        await self._store_event(event)
        
        # Add to stream
        msg_id = await self._add_to_stream(event)
        
        logger.info(f"Event ingested: {event.event_id} (msg_id={msg_id})")
        
        return EventResponse(
            event_id=event.event_id,
            status="INGESTED",
            message=f"Event added to stream: {msg_id}",
            processed_at=datetime.now(timezone.utc).isoformat()
        )
    
    async def ingest_batch(self, batch: EventBatchRequest) -> List[EventResponse]:
        """Ingest multiple events in batch."""
        responses = []
        for req in batch.events:
            resp = await self.ingest_event(req)
            responses.append(resp)
        return responses
    
    async def get_event(self, event_id: str) -> Optional[EventSnapshot]:
        """Retrieve event by ID."""
        import json
        key = f"event:{event_id}"
        data = await self.redis.client.get(key)
        if data:
            return EventSnapshot.from_dict(json.loads(data))
        return None
    
    async def get_stream_info(self) -> Dict[str, Any]:
        """Get stream statistics."""
        try:
            info = await self.redis.client.xinfo_stream(EVENT_STREAM_KEY)
            return {
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry", None),
                "last_entry": info.get("last-entry", None),
                "groups": info.get("groups", 0),
            }
        except Exception as e:
            logger.warning(f"Could not get stream info: {e}")
            return {"length": 0, "error": str(e)}
    
    async def setup_consumer_group(self) -> None:
        """Set up consumer group for stream processing."""
        try:
            await self.redis.client.xgroup_create(
                EVENT_STREAM_KEY,
                CONSUMER_GROUP,
                id="0",
                mkstream=True
            )
            logger.info(f"Created consumer group: {CONSUMER_GROUP}")
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.debug(f"Consumer group {CONSUMER_GROUP} already exists")
    
    async def read_from_stream(self, count: int = 10, block: int = 5000) -> List[Dict]:
        """Read events from stream using consumer group."""
        try:
            results = await self.redis.client.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {EVENT_STREAM_KEY: ">"},
                count=count,
                block=block
            )
            
            events = []
            if results:
                for stream_name, messages in results:
                    for msg_id, msg_data in messages:
                        import json
                        event_data = json.loads(msg_data.get("event", "{}"))
                        events.append({
                            "msg_id": msg_id,
                            "event": event_data
                        })
                        # Acknowledge after processing
                        await self.redis.client.xack(EVENT_STREAM_KEY, CONSUMER_GROUP, msg_id)
            
            return events
        except Exception as e:
            logger.error(f"Error reading from stream: {e}")
            return []


# Global gateway instance
gateway: Optional[EventGateway] = None


# --- FastAPI Endpoints ---

@app.on_event("startup")
async def startup():
    """Initialize connections on startup."""
    global gateway
    await redis_client.connect()
    gateway = EventGateway(redis_client)
    await gateway.setup_consumer_group()
    logger.info("Event gateway service started")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    await redis_client.disconnect()
    logger.info("Event gateway service stopped")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    connected = await redis_client.is_connected()
    stream_info = await gateway.get_stream_info() if gateway else {"length": 0}
    return HealthResponse(
        status="healthy" if connected else "degraded",
        redis_connected=connected,
        stream_length=stream_info.get("length", 0),
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/events", response_model=EventResponse)
async def ingest_event(request: EventRequest):
    """Ingest a single event.
    
    Events are deduplicated, stored, and added to the event stream
    for downstream consumers (feature_service, signal_publisher, etc.)
    """
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.ingest_event(request)


@app.post("/events/batch", response_model=List[EventResponse])
async def ingest_batch(batch: EventBatchRequest):
    """Ingest multiple events in a single batch request."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.ingest_batch(batch)


@app.get("/events/{event_id}")
async def get_event(event_id: str):
    """Get event details by ID."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    event = await gateway.get_event(event_id)
    if event:
        return event.to_dict()
    raise HTTPException(status_code=404, detail="Event not found")


@app.get("/stream/info")
async def get_stream_info():
    """Get event stream statistics."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.get_stream_info()


@app.get("/stream/read")
async def read_events(count: int = 10):
    """Read events from stream (for testing/debugging).
    
    Note: This is for monitoring/debugging. In production,
    use proper consumer group reads.
    """
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    events = await gateway.read_from_stream(count=count)
    return {"count": len(events), "events": events}


# --- Main Entry Point ---

def main():
    """Run the event gateway service."""
    logger.info("Starting event_gateway service on port 8003")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")


if __name__ == "__main__":
    main()