"""Main entry point for feature_service service.

Feature computation service - computes and serves features from event data.
Features include sentiment scores, hype metrics, divergence indicators, etc.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import numpy as np
import uvicorn

from feature_registry.base import FeatureSpec, FeatureGroup

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
FEATURE_CACHE_TTL = int(os.getenv("FEATURE_CACHE_TTL", "300"))  # 5 minutes
EVENT_GATEWAY_URL = os.getenv("EVENT_GATEWAY_URL", "http://localhost:8003")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("feature_service")

app = FastAPI(title="Feature Service", version="1.0.0", description="Feature computation service")


# --- Pydantic Models ---

class FeatureComputeRequest(BaseModel):
    """Request to compute features for a symbol."""
    symbol: str
    feature_names: List[str] = Field(default_factory=list)
    start_ts: Optional[str] = None
    end_ts: Optional[str] = None


class FeatureValue(BaseModel):
    """Single feature value."""
    name: str
    value: float
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeatureComputeResponse(BaseModel):
    """Feature computation response."""
    symbol: str
    features: List[FeatureValue]
    computed_at: str


class FeatureListResponse(BaseModel):
    """List available features."""
    features: List[Dict[str, Any]]
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis_connected: bool
    event_gateway_connected: bool
    timestamp: str


# --- Redis Client ---

class RedisClient:
    """Async Redis client manager."""
    
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


# --- Feature Computation ---

class FeatureEngine:
    """Feature computation engine."""
    
    # Pre-defined feature specs
    FEATURE_SPECS = {
        "sentiment_mean": FeatureSpec(
            name="sentiment_mean",
            version="v1",
            group=FeatureGroup.SENTIMENT,
            description="Mean sentiment score across sources",
            params=(("window_h", 24), ("min_samples", 10)),
        ),
        "sentiment_polarity_skew": FeatureSpec(
            name="sentiment_polarity_skew",
            version="v1",
            group=FeatureGroup.SENTIMENT,
            description="Skewness of sentiment polarity distribution",
            params=(("window_h", 24),),
        ),
        "hype_velocity": FeatureSpec(
            name="hype_velocity",
            version="v1",
            group=FeatureGroup.HYPE,
            description="Rate of change in social mentions",
            params=(("window_h", 6), ("threshold", 100)),
        ),
        "hype_zscore": FeatureSpec(
            name="hype_zscore",
            version="v1",
            group=FeatureGroup.HYPE,
            description="Z-score of current hype vs historical baseline",
            params=(("window_h", 168), ("lookback", 720)),
        ),
        "bull_bear_ratio": FeatureSpec(
            name="bull_bear_ratio",
            version="v1",
            group=FeatureGroup.DIVERGENCE,
            description="Ratio of bullish to bearish mentions",
            params=(("window_h", 24),),
        ),
        "neutral_ratio": FeatureSpec(
            name="neutral_ratio",
            version="v1",
            group=FeatureGroup.DIVERGENCE,
            description="Proportion of neutral mentions",
            params=(("window_h", 24),),
        ),
        "polymarket_delta": FeatureSpec(
            name="polymarket_delta",
            version="v1",
            group=FeatureGroup.EXPECTATION,
            description="Change in Polymarket probability",
            params=(("market_id", ""),),
        ),
        "prob_jump": FeatureSpec(
            name="prob_jump",
            version="v1",
            group=FeatureGroup.EXPECTATION,
            description="Significant probability change detection",
            params=(("threshold", 0.1), ("window_h", 24)),
        ),
        "cross_platform_speed": FeatureSpec(
            name="cross_platform_speed",
            version="v1",
            group=FeatureGroup.DIFFUSION,
            description="Speed of sentiment diffusion across platforms",
            params=(("window_h", 6),),
        ),
        "peak_heat_time": FeatureSpec(
            name="peak_heat_time",
            version="v1",
            group=FeatureGroup.DIFFUSION,
            description="Hours since peak social activity",
            params=(("window_h", 24),),
        ),
    }
    
    def __init__(self, redis_cli: RedisClient):
        self.redis = redis_cli
        self.cache_ttl = FEATURE_CACHE_TTL
    
    def _cache_key(self, symbol: str, feature_name: str) -> str:
        return f"feature:{symbol}:{feature_name}"
    
    async def _get_cached(self, symbol: str, feature_name: str) -> Optional[float]:
        """Get cached feature value."""
        key = self._cache_key(symbol, feature_name)
        val = await self.redis.client.get(key)
        return float(val) if val else None
    
    async def _cache_feature(self, symbol: str, feature_name: str, value: float) -> None:
        """Cache computed feature value."""
        key = self._cache_key(symbol, feature_name)
        await self.redis.client.setex(key, self.cache_ttl, str(value))
    
    def _compute_sentiment_mean(self, signals: pd.DataFrame) -> float:
        """Compute mean sentiment from raw signals."""
        if len(signals) == 0:
            return 0.0
        # Mock: generate random sentiment
        return np.random.uniform(-1, 1)
    
    def _compute_sentiment_polarity_skew(self, signals: pd.DataFrame) -> float:
        """Compute sentiment polarity skew."""
        if len(signals) < 10:
            return 0.0
        # Mock: generate random skew
        return np.random.uniform(-2, 2)
    
    def _compute_hype_velocity(self, signals: pd.DataFrame) -> float:
        """Compute hype velocity (mentions per hour change)."""
        if len(signals) == 0:
            return 0.0
        # Mock: generate random velocity
        return np.random.uniform(0, 500)
    
    def _compute_hype_zscore(self, signals: pd.DataFrame) -> float:
        """Compute hype z-score vs historical baseline."""
        if len(signals) == 0:
            return 0.0
        # Mock: generate random z-score
        return np.random.uniform(-3, 3)
    
    def _compute_bull_bear_ratio(self, signals: pd.DataFrame) -> float:
        """Compute bull/bear ratio."""
        if len(signals) == 0:
            return 1.0
        # Mock: generate random ratio
        return np.random.uniform(0.5, 3.0)
    
    def _compute_neutral_ratio(self, signals: pd.DataFrame) -> float:
        """Compute neutral ratio."""
        if len(signals) == 0:
            return 0.0
        # Mock: generate random ratio
        return np.random.uniform(0, 0.5)
    
    def _compute_polymarket_delta(self, market_id: str) -> float:
        """Compute Polymarket probability change."""
        # Mock: generate random delta
        return np.random.uniform(-0.2, 0.2)
    
    def _compute_prob_jump(self, signals: pd.DataFrame) -> float:
        """Detect probability jump."""
        # Mock: generate random boolean-ish value
        return 1.0 if np.random.random() > 0.7 else 0.0
    
    def _compute_cross_platform_speed(self, signals: pd.DataFrame) -> float:
        """Compute cross-platform diffusion speed."""
        if len(signals) == 0:
            return 0.0
        # Mock: generate random speed
        return np.random.uniform(0, 10)
    
    def _compute_peak_heat_time(self, signals: pd.DataFrame) -> float:
        """Compute hours since peak heat."""
        if len(signals) == 0:
            return 24.0
        # Mock: generate random hours
        return np.random.uniform(0, 24)
    
    def compute_feature(self, feature_name: str, symbol: str, signals: pd.DataFrame) -> float:
        """Compute a single feature."""
        handlers = {
            "sentiment_mean": self._compute_sentiment_mean,
            "sentiment_polarity_skew": self._compute_sentiment_polarity_skew,
            "hype_velocity": self._compute_hype_velocity,
            "hype_zscore": self._compute_hype_zscore,
            "bull_bear_ratio": self._compute_bull_bear_ratio,
            "neutral_ratio": self._compute_neutral_ratio,
            "polymarket_delta": self._compute_polymarket_delta,
            "prob_jump": self._compute_prob_jump,
            "cross_platform_speed": self._compute_cross_platform_speed,
            "peak_heat_time": self._compute_peak_heat_time,
        }
        
        if feature_name not in handlers:
            raise ValueError(f"Unknown feature: {feature_name}")
        
        if feature_name == "polymarket_delta":
            params = dict(self.FEATURE_SPECS[feature_name].params)
            market_id = params.get("market_id", "")
            return handlers[feature_name](market_id)
        
        return handlers[feature_name](signals)
    
    async def compute_features(
        self,
        symbol: str,
        feature_names: Optional[List[str]] = None
    ) -> List[FeatureValue]:
        """Compute multiple features for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USDT-Binance")
            feature_names: List of feature names to compute. If None, compute all.
        
        Returns:
            List of FeatureValue objects.
        """
        if feature_names is None:
            feature_names = list(self.FEATURE_SPECS.keys())
        
        results = []
        now = datetime.now(timezone.utc)
        
        # Mock: empty signals DataFrame for feature computation
        signals = pd.DataFrame()
        
        for name in feature_names:
            if name not in self.FEATURE_SPECS:
                logger.warning(f"Feature {name} not in registry, skipping")
                continue
            
            # Check cache first
            cached = await self._get_cached(symbol, name)
            if cached is not None:
                results.append(FeatureValue(
                    name=name,
                    value=cached,
                    timestamp=now.isoformat(),
                    metadata={"cached": True}
                ))
                continue
            
            # Compute feature
            try:
                value = self.compute_feature(name, symbol, signals)
                
                # Cache result
                await self._cache_feature(symbol, name, value)
                
                spec = self.FEATURE_SPECS[name]
                results.append(FeatureValue(
                    name=name,
                    value=value,
                    timestamp=now.isoformat(),
                    metadata={
                        "version": spec.version,
                        "group": spec.group.value,
                        "cached": False
                    }
                ))
            except Exception as e:
                logger.error(f"Failed to compute feature {name}: {e}")
                results.append(FeatureValue(
                    name=name,
                    value=0.0,
                    timestamp=now.isoformat(),
                    metadata={"error": str(e)}
                ))
        
        return results


# Global engine instance
engine: Optional[FeatureEngine] = None


# --- FastAPI Endpoints ---

@app.on_event("startup")
async def startup():
    global engine
    await redis_client.connect()
    engine = FeatureEngine(redis_client)
    logger.info("Feature service started")


@app.on_event("shutdown")
async def shutdown():
    await redis_client.disconnect()
    logger.info("Feature service stopped")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    redis_ok = await redis_client.is_connected()
    return HealthResponse(
        status="healthy" if redis_ok else "degraded",
        redis_connected=redis_ok,
        event_gateway_connected=True,  # Mock for now
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/features", response_model=FeatureListResponse)
async def list_features():
    """List all available features with their specs."""
    features = [spec.to_dict() for spec in engine.FEATURE_SPECS.values()]
    return FeatureListResponse(
        features=features,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/features/{feature_name}", response_model=FeatureValue)
async def get_feature(
    feature_name: str,
    symbol: str = Query(..., description="Trading symbol"),
):
    """Get a single feature value for a symbol."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if feature_name not in engine.FEATURE_SPECS:
        raise HTTPException(status_code=404, detail=f"Feature {feature_name} not found")
    
    results = await engine.compute_features(symbol, [feature_name])
    return results[0]


@app.post("/features/compute", response_model=FeatureComputeResponse)
async def compute_features(request: FeatureComputeRequest):
    """Compute multiple features for a symbol."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    features = await engine.compute_features(request.symbol, request.feature_names)
    
    return FeatureComputeResponse(
        symbol=request.symbol,
        features=features,
        computed_at=datetime.now(timezone.utc).isoformat()
    )


@app.get("/features/{symbol}/{feature_name}/history")
async def get_feature_history(
    symbol: str,
    feature_name: str,
    limit: int = Query(100, ge=1, le=1000)
):
    """Get historical feature values (from cache/Redis)."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    key = f"feature_history:{symbol}:{feature_name}"
    import json
    raw = await engine.redis.client.lrange(key, 0, limit - 1)
    history = [json.loads(r) for r in raw] if raw else []
    
    return {
        "symbol": symbol,
        "feature": feature_name,
        "history": history,
        "count": len(history)
    }


# --- Main Entry Point ---

def main():
    """Run the feature service."""
    logger.info("Starting feature_service on port 8004")
    uvicorn.run(app, host="0.0.0.0", port=8004, log_level="info")


if __name__ == "__main__":
    main()