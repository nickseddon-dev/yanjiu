"""Main entry point for signal_bridge service.

CRITICAL: Cross-host signal delivery from research host to live execution host.
Handles signal routing, HMAC authentication, ACK/retry/TTL/dead-letter patterns.
"""
import asyncio
import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from pydantic import BaseModel, Field
import uvicorn

from common_schema.signal import Signal, SignalAck, SignalStatus, EntryDecision

# Configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SIGNAL_KEY_PREFIX = os.getenv("SIGNAL_KEY_PREFIX", "signal_bridge:")
ACK_KEY_PREFIX = os.getenv("ACK_KEY_PREFIX", "signal_ack:")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me-in-production")
DEAD_LETTER_QUEUE = os.getenv("DEAD_LETTER_QUEUE", "dead_letter_signals")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
SIGNAL_TTL = int(os.getenv("SIGNAL_TTL", "900"))  # 15 minutes default

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("signal_bridge")

app = FastAPI(title="Signal Bridge", version="1.0.0", description="Cross-host signal delivery service")


# --- Pydantic Models ---

class SignalRequest(BaseModel):
    """Incoming signal from research host."""
    signal: dict  # Signal.to_dict() format

    class Config:
        json_schema_extra = {
            "example": {
                "signal_id": "550e8400-e29b-41d4-a716-446655440000",
                "strategy_id": "crypto_sentiment_v1",
                "symbol": "BTC/USDT-Binance",
                "side": "BUY",
                "signal_strength": 0.85,
                "target_position_pct": 10.0,
                "entry_mode": "FULL_ENTER",
                "max_slippage_bps": 8,
                "ttl_seconds": 900,
                "created_at": "2026-05-27T12:00:00Z",
                "risk_tags": ["momentum", "social_surge"],
                "signature": ""
            }
        }


class SignalResponse(BaseModel):
    """Response after signal received."""
    signal_id: str
    status: str
    message: str
    received_at: str


class AckRequest(BaseModel):
    """ACK from execution host."""
    signal_id: str
    status: str
    message: str = ""
    executed_price: float = 0.0
    executed_quantity: float = 0.0
    rejected_reason: str = ""


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis_connected: bool
    timestamp: str


# --- Utility Functions ---

def compute_hmac(payload: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for payload."""
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_signature(signal_dict: dict, signature: str, secret: str) -> bool:
    """Verify HMAC signature of signal payload."""
    if not signature:
        return False
    # Reconstruct payload without signature field
    payload_for_signing = {k: v for k, v in signal_dict.items() if k != "signature"}
    import json
    payload_str = json.dumps(payload_for_signing, sort_keys=True)
    expected = compute_hmac(payload_str, secret)
    return hmac.compare_digest(expected, signature)


def sign_signal(signal_dict: dict, secret: str) -> str:
    """Generate HMAC signature for signal."""
    payload_for_signing = {k: v for k, v in signal_dict.items() if k != "signature"}
    import json
    payload_str = json.dumps(payload_for_signing, sort_keys=True)
    return compute_hmac(payload_str, secret)


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


# Global Redis client instance
redis_client = RedisClient(REDIS_URL)


# --- Signal Bridge Logic ---

class SignalBridge:
    """Core signal bridge logic."""
    
    def __init__(self, redis_cli: RedisClient):
        self.redis = redis_cli
        self.secret = WEBHOOK_SECRET
        self.max_retries = MAX_RETRIES
        self.ttl = SIGNAL_TTL
    
    def _signal_key(self, signal_id: str) -> str:
        return f"{SIGNAL_KEY_PREFIX}{signal_id}"
    
    def _ack_key(self, signal_id: str) -> str:
        return f"{ACK_KEY_PREFIX}{signal_id}"
    
    async def store_signal(self, signal: Signal) -> None:
        """Store signal in Redis with TTL."""
        key = self._signal_key(signal.signal_id)
        import json
        data = json.dumps(signal.to_dict())
        await self.redis.client.setex(key, self.ttl, data)
        logger.info(f"Stored signal {signal.signal_id} with TTL {self.ttl}s")
    
    async def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Retrieve signal from Redis."""
        key = self._signal_key(signal_id)
        data = await self.redis.client.get(key)
        if data:
            import json
            return Signal.from_dict(json.loads(data))
        return None
    
    async def delete_signal(self, signal_id: str) -> None:
        """Delete signal from Redis."""
        key = self._signal_key(signal_id)
        await self.redis.client.delete(key)
        logger.info(f"Deleted signal {signal_id}")
    
    async def store_ack(self, ack: SignalAck) -> None:
        """Store ACK for research host to pick up."""
        key = self._ack_key(ack.signal_id)
        import json
        data = json.dumps(ack.to_dict())
        # ACK TTL is longer - research host may poll later
        await self.redis.client.setex(key, self.ttl * 2, data)
        logger.info(f"Stored ACK for signal {ack.signal_id}")
    
    async def get_ack(self, signal_id: str) -> Optional[SignalAck]:
        """Retrieve ACK from Redis."""
        key = self._ack_key(signal_id)
        data = await self.redis.client.get(key)
        if data:
            import json
            return SignalAck.from_dict(json.loads(data))
        return None
    
    async def publish_to_dead_letter(self, signal: Signal, reason: str) -> None:
        """Move failed signal to dead letter queue."""
        import json
        payload = {
            "signal": signal.to_dict(),
            "reason": reason,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "retries": self.max_retries
        }
        await self.redis.client.lpush(DEAD_LETTER_QUEUE, json.dumps(payload))
        logger.warning(f"Signal {signal.signal_id} moved to dead letter queue: {reason}")
    
    async def increment_retry(self, signal_id: str) -> int:
        """Track retry count for signal."""
        key = f"{SIGNAL_KEY_PREFIX}retry:{signal_id}"
        count = await self.redis.client.incr(key)
        await self.redis.client.expire(key, self.ttl)
        return count
    
    async def get_retry_count(self, signal_id: str) -> int:
        """Get retry count for signal."""
        key = f"{SIGNAL_KEY_PREFIX}retry:{signal_id}"
        count = await self.redis.client.get(key)
        return int(count) if count else 0
    
    async def route_signal_to_executor(self, signal: Signal) -> bool:
        """Route signal to executor's Redis stream for processing."""
        stream_key = f"executor:signals:{signal.symbol.split('/')[0]}"
        import json
        payload = json.dumps(signal.to_dict())
        msg_id = await self.redis.client.xadd(stream_key, {"signal": payload}, maxlen=1000)
        logger.info(f"Routed signal {signal.signal_id} to stream {stream_key}, msg_id={msg_id}")
        return True
    
    async def bridge_signal(self, signal_request: SignalRequest) -> SignalResponse:
        """Main entry point: receive, validate, store, and route signal."""
        signal_dict = signal_request.signal
        
        # Parse signal
        signal = Signal.from_dict(signal_dict)
        
        # Verify signature if provided
        if signal.signature:
            if not verify_signature(signal_dict, signal.signature, self.secret):
                logger.warning(f"Invalid signature for signal {signal.signal_id}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        else:
            # Auto-sign if no signature provided (for testing/development)
            signal_dict["signature"] = sign_signal(signal_dict, self.secret)
            signal = Signal.from_dict(signal_dict)
        
        # Check TTL expiration
        age = (datetime.now(timezone.utc) - signal.created_at).total_seconds()
        if age > signal.ttl_seconds:
            logger.warning(f"Signal {signal.signal_id} expired (age={age}s > ttl={signal.ttl_seconds}s)")
            await self.publish_to_dead_letter(signal, "TTL_EXPIRED")
            raise HTTPException(status_code=410, detail="Signal expired")
        
        # Store signal
        await self.store_signal(signal)
        
        # Route to executor
        try:
            await self.route_signal_to_executor(signal)
        except Exception as e:
            logger.error(f"Failed to route signal {signal.signal_id}: {e}")
            # Retry logic
            retries = await self.increment_retry(signal.signal_id)
            if retries >= self.max_retries:
                await self.publish_to_dead_letter(signal, f"ROUTE_FAILED after {retries} retries")
                raise HTTPException(status_code=503, detail="Failed to route signal")
            raise HTTPException(status_code=503, detail=f"Retry {retries}/{self.max_retries}")
        
        return SignalResponse(
            signal_id=signal.signal_id,
            status=SignalStatus.RECEIVED.value,
            message="Signal received and routed to executor",
            received_at=datetime.now(timezone.utc).isoformat()
        )
    
    async def process_ack(self, ack_request: AckRequest) -> SignalResponse:
        """Process ACK from execution host."""
        # Update ACK store
        ack = SignalAck(
            signal_id=ack_request.signal_id,
            status=SignalStatus(ack_request.status),
            message=ack_request.message,
            executed_price=ack_request.executed_price,
            executed_quantity=ack_request.executed_quantity,
            rejected_reason=ack_request.rejected_reason
        )
        await self.store_ack(ack)
        
        # Clean up signal from active queue
        await self.delete_signal(ack_request.signal_id)
        
        logger.info(f"Processed ACK for signal {ack_request.signal_id}: {ack_request.status}")
        
        return SignalResponse(
            signal_id=ack_request.signal_id,
            status=ack_request.status,
            message=ack_request.message or "ACK processed",
            received_at=datetime.now(timezone.utc).isoformat()
        )


# Global bridge instance
bridge: Optional[SignalBridge] = None


# --- FastAPI Endpoints ---

@app.on_event("startup")
async def startup():
    """Initialize connections on startup."""
    global bridge
    await redis_client.connect()
    bridge = SignalBridge(redis_client)
    logger.info("Signal bridge service started")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    await redis_client.disconnect()
    logger.info("Signal bridge service stopped")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    connected = await redis_client.is_connected()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        redis_connected=connected,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/signals", response_model=SignalResponse)
async def receive_signal(request: SignalRequest):
    """Receive signal from research host (webhook endpoint).
    
    This is the primary entry point for signals from the research host.
    Signals are validated, stored, and routed to the executor.
    """
    if bridge is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await bridge.bridge_signal(request)


@app.post("/signals/ack", response_model=SignalResponse)
async def receive_ack(ack: AckRequest):
    """Receive ACK from execution host.
    
    Execution host calls this to report execution results back
    to the research host via the bridge.
    """
    if bridge is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await bridge.process_ack(ack)


@app.get("/signals/{signal_id}/ack")
async def get_signal_ack(signal_id: str):
    """Poll ACK status for a signal (for research host)."""
    if bridge is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    ack = await bridge.get_ack(signal_id)
    if ack:
        return ack.to_dict()
    return {"signal_id": signal_id, "status": "PENDING", "message": "ACK not yet available"}


@app.get("/signals/{signal_id}")
async def get_signal(signal_id: str):
    """Get signal details by ID."""
    if bridge is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    signal = await bridge.get_signal(signal_id)
    if signal:
        return signal.to_dict()
    raise HTTPException(status_code=404, detail="Signal not found")


@app.delete("/signals/{signal_id}")
async def cancel_signal(signal_id: str):
    """Cancel a pending signal."""
    if bridge is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    await bridge.delete_signal(signal_id)
    return {"signal_id": signal_id, "status": "CANCELLED"}


@app.get("/dead-letter")
async def list_dead_letter():
    """List dead letter signals (for monitoring/debugging)."""
    if bridge is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    items = await redis_client.client.lrange(DEAD_LETTER_QUEUE, 0, -1)
    import json
    return {"count": len(items), "items": [json.loads(i) for i in items]}


@app.post("/signals/test", response_model=SignalResponse)
async def create_test_signal():
    """Create a test signal for testing purposes."""
    if bridge is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    test_signal = Signal(
        strategy_id="test_strategy",
        symbol="BTC/USDT-Binance",
        side="BUY",
        signal_strength=0.75,
        target_position_pct=5.0,
        entry_mode=EntryDecision.FULL_ENTER,
        ttl_seconds=300,
        risk_tags=("test",)
    )
    
    # Sign the signal
    signal_dict = test_signal.to_dict()
    signal_dict["signature"] = sign_signal(signal_dict, WEBHOOK_SECRET)
    test_signal = Signal.from_dict(signal_dict)
    
    request = SignalRequest(signal=signal_dict)
    return await bridge.bridge_signal(request)


# --- Main Entry Point ---

def main():
    """Run the signal bridge service."""
    logger.info("Starting signal_bridge service on port 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")


if __name__ == "__main__":
    main()