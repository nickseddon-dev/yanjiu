
"""Signal publisher service - publishes signals to SignalBridge."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
import pydantic

logger = logging.getLogger("signal_publisher")


class Signal(pydantic.BaseModel):
    """Signal to be published."""
    signal_id: str = pydantic.Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    direction: str
    signal_type: str = "ALPHA"
    narrative: str = ""
    confidence: float = 0.5
    entry_price: Optional[float] = None
    size_usd: float = 0.0
    metadata: dict = pydantic.Field(default_factory=dict)
    timestamp: datetime = pydantic.Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"


class SignalPublisher:
    """Publishes signals to SignalBridge via queue and HTTP."""

    def __init__(self, bridge_url: str = "http://localhost:8090", api_key: str = ""):
        self.bridge_url = bridge_url.rstrip("/")
        self.api_key = api_key
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("SignalPublisher started")
        asyncio.create_task(self._publish_loop())

    async def stop(self) -> None:
        self._running = False
        logger.info("SignalPublisher stopped")

    async def publish(self, signal: Signal) -> bool:
        await self._queue.put(signal)
        logger.info(f"Signal queued: {signal.signal_id}")
        return True

    async def publish_direct(self, signal: Signal) -> dict:
        headers = {"X-API-Key": self.api_key} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.bridge_url}/signals",
                    json=signal.model_dump(mode="json"),
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Failed: {e}")
            return {"error": str(e)}

    async def _publish_loop(self) -> None:
        while self._running:
            try:
                signal = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                await self.publish_direct(signal)
            except Exception as e:
                logger.error(f"Error: {e}")
                await self._queue.put(signal)
            await asyncio.sleep(0.1)

    def get_queue_size(self) -> int:
        return self._queue.qsize()


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="signal_publisher", version="0.1.0")
_publisher: Optional[SignalPublisher] = None
SIGNAL_STORE: dict = {}


class PublishRequest(BaseModel):
    symbol: str
    direction: str
    signal_type: str = "ALPHA"
    narrative: str = ""
    confidence: float = 0.5
    entry_price: Optional[float] = None
    size_usd: float = 0.0
    metadata: dict = {}


class PublishResponse(BaseModel):
    signal_id: str
    status: str
    queued: bool


@app.on_event("startup")
async def startup():
    global _publisher
    _publisher = SignalPublisher()
    await _publisher.start()


@app.on_event("shutdown")
async def shutdown():
    if _publisher:
        await _publisher.stop()


@app.post("/signals", response_model=PublishResponse)
async def publish_signal(req: PublishRequest):
    signal = Signal(**req.model_dump())
    SIGNAL_STORE[signal.signal_id] = signal
    queued = await _publisher.publish(signal)
    return PublishResponse(signal_id=signal.signal_id, status="queued", queued=queued)


@app.get("/signals/{signal_id}")
async def get_signal(signal_id: str):
    if signal_id not in SIGNAL_STORE:
        raise HTTPException(status_code=404, detail="Not found")
    return SIGNAL_STORE[signal_id].model_dump(mode="json")


@app.get("/health")
async def health():
    return {"status": "ok", "queue_size": _publisher.get_queue_size() if _publisher else 0}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8093, log_level="info")


if __name__ == "__main__":
    main()
