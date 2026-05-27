"""Main entry point for research_runner service.

Automated research pipeline - runs backtests, computes features,
evaluates strategies, and publishes results.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

from common_schema.signal import Signal, SignalStatus

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SIGNAL_BRIDGE_URL = os.getenv("SIGNAL_BRIDGE_URL", "http://localhost:8001")
FEATURE_SERVICE_URL = os.getenv("FEATURE_SERVICE_URL", "http://localhost:8004")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("research_runner")

app = FastAPI(title="Research Runner", version="1.0.0", description="Automated research pipeline service")


# --- Pydantic Models ---

class ResearchConfig(BaseModel):
    """Configuration for a research run."""
    symbol: str = "BTC/USDT-Binance"
    start_date: str = "2026-01-01"
    end_date: str = "2026-05-27"
    strategy_id: str = "crypto_sentiment_v1"
    initial_capital: float = 10000.0
    feature_names: List[str] = Field(default_factory=lambda: [
        "sentiment_mean", "hype_velocity", "bull_bear_ratio", "polymarket_delta"
    ])


class BacktestRequest(BaseModel):
    """Request to run a backtest."""
    config: ResearchConfig
    run_name: Optional[str] = None


class BacktestResult(BaseModel):
    """Backtest result summary."""
    run_id: str
    symbol: str
    strategy_id: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    final_capital: float
    completed_at: str


class SignalEvaluationRequest(BaseModel):
    """Request to evaluate signals."""
    symbol: str
    lookback_days: int = 30


class SignalEvaluationResult(BaseModel):
    """Signal evaluation result."""
    signal_id: str
    symbol: str
    predicted_strength: float
    actual_outcome: Optional[float] = None
    score: float
    evaluated_at: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis_connected: bool
    timestamp: str


# --- Redis Client ---

class RedisClient:
    def __init__(self, url: str):
        self.url = url
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client
    
    async def disconnect(self):
        if self._client:
            await self._client.close()
            self._client = None
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected")
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


# --- Research Runner Logic ---

class ResearchRunner:
    """Automated research pipeline runner."""
    
    def __init__(self, redis_cli: RedisClient):
        self.redis = redis_cli
    
    def _generate_mock_ohlcv(self, symbol: str, days: int) -> List[Dict]:
        """Generate mock OHLCV data for backtesting."""
        import numpy as np
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=days * 24, freq='1h')
        base_price = 60000 if "BTC" in symbol else 3000
        return [
            {
                "timestamp": d.isoformat(),
                "open": base_price * np.random.uniform(0.98, 1.02),
                "high": base_price * np.random.uniform(1.0, 1.05),
                "low": base_price * np.random.uniform(0.95, 1.0),
                "close": base_price * np.random.uniform(0.98, 1.02),
                "volume": np.random.uniform(100, 1000)
            }
            for d in dates
        ]
    
    def _simulate_strategy(self, config: ResearchConfig) -> Dict[str, Any]:
        """Simulate strategy backtest (mock implementation)."""
        import numpy as np
        
        # Calculate mock metrics
        num_days = (datetime.now(timezone.utc) - datetime.fromisoformat(config.start_date)).days
        num_trades = int(np.random.randint(10, 50))
        
        # Random walk returns
        daily_returns = np.random.normal(0.001, 0.02, num_days)
        cumulative_return = (1 + daily_returns).prod() - 1
        
        # Sharpe ratio (mock)
        sharpe = np.random.uniform(0.5, 2.5) * (1 if cumulative_return > 0 else -1)
        
        # Max drawdown (mock)
        max_dd = np.random.uniform(0.05, 0.25)
        
        # Win rate (mock)
        win_rate = np.random.uniform(0.4, 0.7)
        
        # Final capital
        final_capital = config.initial_capital * (1 + cumulative_return)
        
        return {
            "total_return": cumulative_return * 100,  # percentage
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd * 100,  # percentage
            "win_rate": win_rate * 100,  # percentage
            "num_trades": num_trades,
            "final_capital": final_capital,
        }
    
    def _generate_signals_from_features(self, config: ResearchConfig) -> List[Signal]:
        """Generate signals based on feature computation (mock)."""
        import numpy as np
        
        signals = []
        num_signals = np.random.randint(5, 20)
        
        for i in range(num_signals):
            signal_strength = np.random.uniform(0.3, 0.9)
            side = "BUY" if signal_strength > 0.5 else "SELL"
            entry_mode = "FULL_ENTER" if signal_strength > 0.7 else (
                "PARTIAL_ENTER" if signal_strength > 0.5 else "SMALL_TEST"
            )
            
            signal = Signal(
                signal_id=str(uuid.uuid4()),
                strategy_id=config.strategy_id,
                symbol=config.symbol,
                side=side,
                signal_strength=signal_strength,
                target_position_pct=10.0 if side == "BUY" else 5.0,
                entry_mode=entry_mode,
                ttl_seconds=900,
                risk_tags=("backtest",),
            )
            signals.append(signal)
        
        return signals
    
    async def run_backtest(self, config: ResearchConfig) -> BacktestResult:
        """Run strategy backtest."""
        logger.info(f"Running backtest for {config.symbol} ({config.start_date} to {config.end_date})")
        
        # Simulate backtest
        metrics = self._simulate_strategy(config)
        
        run_id = str(uuid.uuid4())
        
        # Store result
        import json
        key = f"backtest:{run_id}"
        await self.redis.client.setex(key, 86400, json.dumps({
            "run_id": run_id,
            "config": config.model_dump(),
            "metrics": metrics,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }))
        
        logger.info(f"Backtest completed: run_id={run_id}")
        
        return BacktestResult(
            run_id=run_id,
            symbol=config.symbol,
            strategy_id=config.strategy_id,
            total_return=metrics["total_return"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_drawdown=metrics["max_drawdown"],
            win_rate=metrics["win_rate"],
            num_trades=metrics["num_trades"],
            final_capital=metrics["final_capital"],
            completed_at=datetime.now(timezone.utc).isoformat()
        )
    
    async def evaluate_signal(self, symbol: str, lookback_days: int) -> List[SignalEvaluationResult]:
        """Evaluate historical signals for a symbol."""
        logger.info(f"Evaluating signals for {symbol} (lookback={lookback_days}d)")
        
        results = []
        import numpy as np
        
        for i in range(np.random.randint(5, 15)):
            predicted = np.random.uniform(0.3, 0.95)
            actual = np.random.uniform(-0.1, 0.3) if np.random.random() > 0.3 else None
            
            # Score based on prediction accuracy
            if actual is not None:
                score = 1 - abs(predicted - actual) / 0.5 if abs(predicted - actual) < 0.5 else 0
            else:
                score = predicted  # No outcome yet
            
            results.append(SignalEvaluationResult(
                signal_id=str(uuid.uuid4()),
                symbol=symbol,
                predicted_strength=predicted,
                actual_outcome=actual,
                score=score,
                evaluated_at=datetime.now(timezone.utc).isoformat()
            ))
        
        return results
    
    async def store_backtest_result(self, result: BacktestResult) -> None:
        """Store backtest result in Redis."""
        import json
        key = f"backtest_result:{result.run_id}"
        await self.redis.client.setex(key, 86400 * 7, json.dumps(result.model_dump()))


# Global runner instance
runner: Optional[ResearchRunner] = None


# --- FastAPI Endpoints ---

import pandas as pd

@app.on_event("startup")
async def startup():
    global runner
    await redis_client.connect()
    runner = ResearchRunner(redis_client)
    logger.info("Research runner service started")


@app.on_event("shutdown")
async def shutdown():
    await redis_client.disconnect()
    logger.info("Research runner service stopped")


@app.get("/health", response_model=HealthResponse)
async def health():
    redis_ok = await redis_client.is_connected()
    return HealthResponse(
        status="healthy" if redis_ok else "degraded",
        redis_connected=redis_ok,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/backtest", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    """Run a strategy backtest."""
    if runner is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await runner.run_backtest(request.config)


@app.post("/signals/evaluate", response_model=List[SignalEvaluationResult])
async def evaluate_signals(request: SignalEvaluationRequest):
    """Evaluate historical signals."""
    if runner is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await runner.evaluate_signal(request.symbol, request.lookback_days)


@app.get("/backtest/{run_id}")
async def get_backtest_result(run_id: str):
    """Get backtest result by ID."""
    if runner is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    import json
    key = f"backtest:{run_id}"
    data = await runner.redis.client.get(key)
    if data:
        return json.loads(data)
    raise HTTPException(status_code=404, detail="Backtest not found")


@app.get("/backtest/history")
async def get_backtest_history(limit: int = Query(50, ge=1, le=100)):
    """Get backtest history."""
    if runner is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    import json
    keys = await runner.redis.client.keys("backtest:*")
    results = []
    for key in keys[-limit:]:
        data = await runner.redis.client.get(key)
        if data:
            results.append(json.loads(data))
    
    return {"count": len(results), "backtests": results}


# --- Main Entry Point ---

def main():
    logger.info("Starting research_runner service on port 8006")
    uvicorn.run(app, host="0.0.0.0", port=8006, log_level="info")


if __name__ == "__main__":
    main()