"""Main entry point for executor service.

Live-host signal consumer — consumes from Redis streams published by
signal_bridge, runs pre-trade risk checks, executes orders, and sends ACKs
back via signal_bridge /ack endpoint.

Supports three modes:
  PAPER  — simulate fills, no real exchange. Default in development.
  LIVE   — submit real orders via OrderExecutionAdapter (requires exchange creds).
  SHADOW — log signal receipt and routing decisions without executing anything.
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger("executor")

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SIGNAL_BRIDGE_URL = os.getenv("SIGNAL_BRIDGE_URL", "http://signal_bridge:8090")
EXECUTION_MODE = os.getenv("EXECUTION_MODE", "PAPER").upper()  # PAPER | LIVE | SHADOW
TRADING_SYMBOLS = os.getenv("TRADING_SYMBOLS", "BTC/USDT,ETH/USDT").split(",")

INSTRUMENT_MAP = {
    "BTC/USDT": "BTC-USDT",
    "ETH/USDT": "ETH-USDT",
    "BTC/USDT-Binance": "BTC-USDT",
    "ETH/USDT-Binance": "ETH-USDT",
}


# --- Pydantic models ---

class HealthResponse(BaseModel):
    status: str
    redis_connected: bool
    execution_mode: str
    timestamp: str


class ExecutionResult(BaseModel):
    signal_id: str
    order_id: str
    success: bool
    mode: str
    message: str
    symbol: str
    side: str
    quantity: float
    executed_price: float = 0.0
    executed_quantity: float = 0.0
    executed_at: str = ""


class SignalStreamMessage(BaseModel):
    signal_id: str
    symbol: str
    side: str
    signal_strength: float
    target_position_pct: float
    entry_mode: str
    ttl_seconds: int
    created_at: str


# --- Redis client wrapper ---

class RedisClient:
    def __init__(self, url: str):
        self.url = url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        self._client = redis.from_url(self.url, decode_responses=True)
        await self._client.ping()
        logger.info(f"Redis connected: {self.url}")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Redis disconnected")

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


redis_client = RedisClient(REDIS_URL)


# --- Paper trade fill simulator ---

class PaperFillSimulator:
    """Simulates realistic fill prices for paper trading mode."""

    def simulate_fill(
        self, symbol: str, side: str, quantity: float, signal_strength: float
    ) -> Dict[str, Any]:
        """Return a simulated fill result."""
        import random

        base_prices = {
            "BTC-USDT": 60000 + random.uniform(-500, 500),
            "ETH-USDT": 3000 + random.uniform(-50, 50),
        }
        price = base_prices.get(symbol, 100.0)
        # Slippage: stronger signals get tighter fills
        slippage_bps = random.uniform(2, 8) * (1 - signal_strength)
        fill_price = price * (1 + slippage_bps / 10000) if side == "BUY" else price * (1 - slippage_bps / 10000)
        return {
            "executed_price": round(fill_price, 2),
            "executed_quantity": round(quantity, 6),
            "slippage_bps": round(slippage_bps, 2),
        }


paper_sim = PaperFillSimulator()


# --- Executor core ---

class Executor:
    """Core executor: consume signals, check risk, execute, ACK."""

    def __init__(self, redis_cli: RedisClient):
        self.redis = redis_cli
        self.mode = EXECUTION_MODE
        self._running = False
        self._order_count = 0
        self._exec_log: list = []

        # Lazy-import libs to avoid hard dependency on nautilus_trader in dev
        try:
            from nautilus_ext.risk_checker import RiskChecker
            from nautilus_ext.order_adapter import OrderExecutionAdapter
            self._risk_checker = RiskChecker()
            self._order_adapter = OrderExecutionAdapter()
            logger.info("Nautilus libs loaded — LIVE mode available")
        except ImportError as e:
            logger.warning(f"Nautilus libs not available ({e}), running in degraded mode")
            self._risk_checker = None
            self._order_adapter = None

    def _stream_key(self, symbol: str) -> str:
        base = symbol.split("/")[0]
        return f"executor:signals:{base}"

    def _all_stream_keys(self) -> list:
        return [self._stream_key(s.strip()) for s in TRADING_SYMBOLS]

    async def _fetch_signal_from_stream(self, symbol: str) -> Optional[Dict]:
        """Fetch one signal from the Redis stream."""
        key = self._stream_key(symbol)
        try:
            msgs = await self.redis.client.xread({key: "0"}, count=1, block=1000)
        except Exception:
            return None

        if not msgs:
            return None

        # msgs = [(stream_key, [(msg_id, fields)])]
        _, entries = msgs[0]
        if not entries:
            return None

        msg_id, fields = entries[0]
        # fields = {"signal": "<json>"}
        raw = fields.get("signal", "{}")
        data = json.loads(raw)

        # Acknowledge the message to remove it from the stream
        await self.redis.client.xdel(key, msg_id)

        return data

    async def _check_risk(self, signal: Dict) -> tuple[bool, str]:
        """Run pre-trade risk check. Returns (approved, reason)."""
        if self._risk_checker is None:
            return True, "risk_checker_unavailable"

        # Build minimal portfolio state for risk checker
        portfolio_state = {
            "total_value": 100000.0,
            "positions": {},
            "narrative_exposure": {},
            "venue_exposure": {},
            "portfolio_var_pct": 0.01,
            "current_drawdown_pct": 0.01,
        }

        from common_schema.signal import Signal
        sig = Signal.from_dict(signal)
        result = self._risk_checker.pre_trade_check(sig, portfolio_state)
        return result.approved, result.message

    def _compute_quantity(self, symbol: str, target_pct: float, current_price: float) -> float:
        """Compute quantity from target position percentage."""
        portfolio_value = 100000.0  # Mock portfolio value
        target_value = portfolio_value * (target_pct / 100)
        return target_value / current_price

    async def _execute_order(self, signal: Dict, mode: str) -> ExecutionResult:
        """Execute an order in the given mode."""
        self._order_count += 1
        order_id = f"ord_{uuid.uuid4().hex[:12]}"
        symbol_raw = signal.get("symbol", "BTC/USDT")
        symbol = INSTRUMENT_MAP.get(symbol_raw, symbol_raw.replace("/", "-"))
        side = signal.get("side", "BUY")
        strength = signal.get("signal_strength", 0.5)
        target_pct = signal.get("target_position_pct", 10.0)
        signal_id = signal.get("signal_id", "unknown")

        current_prices = {"BTC-USDT": 60000.0, "ETH-USDT": 3000.0}
        current_price = current_prices.get(symbol, 100.0)
        quantity = self._compute_quantity(symbol, target_pct, current_price)

        if mode == "SHADOW":
            return ExecutionResult(
                signal_id=signal_id,
                order_id=order_id,
                success=True,
                mode=mode,
                message=f"SHADOW: would {side} {quantity:.4f} {symbol} @ market",
                symbol=symbol,
                side=side,
                quantity=quantity,
            )

        if mode == "PAPER":
            fill = paper_sim.simulate_fill(symbol, side, quantity, strength)
            return ExecutionResult(
                signal_id=signal_id,
                order_id=order_id,
                success=True,
                mode=mode,
                message=f"PAPER: simulated fill",
                symbol=symbol,
                side=side,
                quantity=quantity,
                executed_price=fill["executed_price"],
                executed_quantity=fill["executed_quantity"],
                executed_at=datetime.now(timezone.utc).isoformat(),
            )

        # LIVE mode — delegate to Nautilus adapter
        if self._order_adapter is None:
            return ExecutionResult(
                signal_id=signal_id,
                order_id=order_id,
                success=False,
                mode=mode,
                message="order_adapter_unavailable",
                symbol=symbol,
                side=side,
                quantity=quantity,
            )

        result = self._order_adapter.submit_market_order(symbol, side, quantity, order_id)
        return ExecutionResult(
            signal_id=signal_id,
            order_id=result.order_id,
            success=result.success,
            mode=mode,
            message=result.message,
            symbol=symbol,
            side=side,
            quantity=quantity,
            executed_price=result.submitted_price or current_price,
            executed_quantity=result.submitted_quantity or quantity,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _send_ack(self, signal_id: str, status: str, message: str,
                        executed_price: float = 0.0,
                        executed_quantity: float = 0.0,
                        rejected_reason: str = "") -> None:
        """Send ACK back to signal_bridge via HTTP POST."""
        import httpx

        payload = {
            "signal_id": signal_id,
            "status": status,
            "message": message,
            "executed_price": executed_price,
            "executed_quantity": executed_quantity,
            "rejected_reason": rejected_reason,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"{SIGNAL_BRIDGE_URL}/signals/ack", json=payload)
                resp.raise_for_status()
                logger.info(f"ACK sent for {signal_id}: {status}")
        except Exception as e:
            logger.warning(f"Failed to send ACK for {signal_id}: {e}")

    async def _process_signal(self, signal: Dict) -> ExecutionResult:
        """Process a single signal end-to-end."""
        signal_id = signal.get("signal_id", "unknown")
        symbol_raw = signal.get("symbol", "BTC/USDT")
        logger.info(f"Processing signal {signal_id}: {symbol_raw} {signal.get('side')}")

        # 1. Risk check
        approved, reason = await self._check_risk(signal)
        if not approved:
            result = ExecutionResult(
                signal_id=signal_id,
                order_id="",
                success=False,
                mode=self.mode,
                message=f"REJECTED by risk check: {reason}",
                symbol=symbol_raw,
                side=signal.get("side", ""),
                quantity=0.0,
            )
            await self._send_ack(signal_id, "REJECTED", result.message,
                                 rejected_reason=reason)
            return result

        # 2. Execute
        result = await self._execute_order(signal, self.mode)

        # 3. Send ACK
        status = "EXECUTED" if result.success else "REJECTED"
        await self._send_ack(signal_id, status, result.message,
                             executed_price=result.executed_price,
                             executed_quantity=result.executed_quantity,
                             rejected_reason="" if result.success else result.message)

        self._exec_log.append(result)
        return result

    async def run_loop(self) -> None:
        """Main consumer loop — polls all symbol streams."""
        self._running = True
        logger.info(f"Executor loop started in {self.mode} mode")

        while self._running:
            try:
                for symbol in TRADING_SYMBOLS:
                    signal = await self._fetch_signal_from_stream(symbol.strip())
                    if signal:
                        await self._process_signal(signal)
            except Exception as e:
                logger.error(f"Executor loop error: {e}")
                await asyncio.sleep(5)

    def stop_loop(self) -> None:
        self._running = False
        logger.info("Executor loop stopped")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "order_count": self._order_count,
            "exec_log_size": len(self._exec_log),
            "recent": [r.model_dump() for r in self._exec_log[-10:]],
        }


# Global executor instance
executor: Optional[Executor] = None
_executor_task: Optional[asyncio.Task] = None


# --- FastAPI Endpoints ---

app = FastAPI(title="executor", version="0.1.0")


@app.on_event("startup")
async def startup():
    global executor, _executor_task
    await redis_client.connect()
    executor = Executor(redis_client)

    # Start the consumer loop in background
    _executor_task = asyncio.create_task(executor.run_loop())
    logger.info("Executor service started")


@app.on_event("shutdown")
async def shutdown():
    global executor, _executor_task
    if executor:
        executor.stop_loop()
    if _executor_task:
        _executor_task.cancel()
        try:
            await _executor_task
        except asyncio.CancelledError:
            pass
    await redis_client.disconnect()
    logger.info("Executor service stopped")


@app.get("/health", response_model=HealthResponse)
async def health():
    redis_ok = await redis_client.is_connected()
    return HealthResponse(
        status="healthy" if redis_ok else "degraded",
        redis_connected=redis_ok,
        execution_mode=EXECUTION_MODE,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/stats")
async def stats():
    if executor is None:
        raise HTTPException(503, "not initialized")
    return executor.get_stats()


@app.post("/mode/{new_mode}")
async def set_mode(new_mode: str):
    global EXECUTION_MODE
    valid = ("PAPER", "LIVE", "SHADOW")
    new_mode = new_mode.upper()
    if new_mode not in valid:
        raise HTTPException(400, f"Mode must be one of {valid}")
    if executor:
        executor.mode = new_mode
    return {"mode": new_mode, "previous": EXECUTION_MODE}


@app.post("/signals/test")
async def inject_test_signal():
    """Inject a test signal directly for testing (bypasses Redis stream)."""
    if executor is None:
        raise HTTPException(503, "not initialized")

    from common_schema.signal import Signal, EntryDecision
    import uuid

    test_signal = Signal(
        signal_id=str(uuid.uuid4()),
        strategy_id="test_strategy",
        symbol="BTC/USDT",
        side="BUY",
        signal_strength=0.75,
        target_position_pct=5.0,
        entry_mode=EntryDecision.FULL_ENTER,
        ttl_seconds=300,
        risk_tags=("test",),
    )
    return await executor._process_signal(test_signal.to_dict())


# --- Main Entry Point ---

def main():
    logger.info("Starting executor service on port 8100")
    uvicorn.run(app, host="0.0.0.0", port=8100, log_level="info")


if __name__ == "__main__":
    main()