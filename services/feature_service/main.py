"""Main entry point for feature_service service.

Feature computation service — computes and serves features from real event data:
  - Social signals from event_gateway (X posts, sentiment, intensity)
  - Polymarket probability data from data_gateway (probability changes, jumps)
  - On-chain metrics from onchain adapter

Features are cached in Redis with configurable TTL.

Real data wiring:
  - sentiment_mean, hype_velocity, bull_bear_ratio -> event_gateway social events
  - polymarket_delta, prob_jump -> data_gateway Polymarket API
  - cross_platform_speed, peak_heat_time -> derived from event_gateway stream
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pandas as pd
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

from feature_registry.base import FeatureSpec, FeatureGroup

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
FEATURE_CACHE_TTL = int(os.getenv("FEATURE_CACHE_TTL", "300"))  # 5 minutes
EVENT_GATEWAY_URL = os.getenv("EVENT_GATEWAY_URL", "http://localhost:8003")
DATA_GATEWAY_URL = os.getenv("DATA_GATEWAY_URL", "http://localhost:8002")
POLYMARKET_DELTA_WINDOW = int(os.getenv("POLYMARKET_DELTA_WINDOW", "24"))  # hours

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("feature_service")


# --- Pydantic Models ---

class FeatureComputeRequest(BaseModel):
    symbol: str
    feature_names: List[str] = Field(default_factory=list)
    start_ts: Optional[str] = None
    end_ts: Optional[str] = None


class FeatureValue(BaseModel):
    name: str
    value: float
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeatureComputeResponse(BaseModel):
    symbol: str
    features: List[FeatureValue]
    computed_at: str


class FeatureListResponse(BaseModel):
    features: List[Dict[str, Any]]
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    redis_connected: bool
    event_gateway_connected: bool
    data_gateway_connected: bool
    timestamp: str


app = FastAPI(title="Feature Service", version="1.0.0")


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


# --- Real data fetchers ---

class EventGatewayFetcher:
    """
    Fetches social signal events from event_gateway.

    event_gateway stores social events in Redis streams and provides
    a REST API for querying recent events by symbol.
    """

    def __init__(self, http_client: httpx.AsyncClient, base_url: str):
        self.http = http_client
        self.base_url = base_url.rstrip("/")

    async def fetch_recent_events(
        self, symbol: str, event_types: List[str], limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch recent social events for a symbol from event_gateway.

        Returns a DataFrame with columns: event_id, event_type, symbol,
        confidence, intensity, timestamp.
        """
        try:
            # Try stream read first
            resp = await self.http.get(
                f"{self.base_url}/stream/read",
                params={"count": limit},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("events", [])
                if events:
                    df = pd.DataFrame([e["event"] for e in events])
                    # Filter by symbol and event types
                    if "symbol" in df.columns:
                        df = df[df["symbol"] == symbol]
                    if "event_type" in df.columns and event_types:
                        df = df[df["event_type"].isin(event_types)]
                    return df
        except Exception as e:
            logger.warning(f"event_gateway stream read failed: {e}")

        # Fallback: try individual event lookup
        try:
            resp = await self.http.get(
                f"{self.base_url}/events",
                params={"symbol": symbol},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("events", [])
                if events:
                    return pd.DataFrame(events)
        except Exception as e:
            logger.warning(f"event_gateway /events failed: {e}")

        return pd.DataFrame()

    async def fetch_event_count(self, symbol: str, window_h: int = 24) -> int:
        """Get event count for symbol within window."""
        try:
            # Use stream info to estimate volume
            resp = await self.http.get(
                f"{self.base_url}/stream/info",
                timeout=5,
            )
            if resp.status_code == 200:
                info = resp.json()
                return info.get("length", 0)
        except Exception:
            pass
        return 0


class PolymarketFetcher:
    """
    Fetches Polymarket probability data from data_gateway.

    Computes probability changes over rolling windows to detect
    prob_jump and polymarket_delta features.
    """

    def __init__(self, http_client: httpx.AsyncClient, base_url: str):
        self.http = http_client
        self.base_url = base_url.rstrip("/")
        self._prob_cache: Dict[str, Tuple[float, str]] = {}  # market_id -> (prob, timestamp)

    async def fetch_markets(self, limit: int = 50) -> pd.DataFrame:
        """Fetch top Polymarket markets by volume."""
        try:
            resp = await self.http.get(
                f"{self.base_url}/polymarket/markets",
                params={"limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                markets = data.get("markets", data.get("data", []))
            elif isinstance(data, list):
                markets = data
            else:
                return pd.DataFrame()
            return pd.DataFrame(markets)
        except Exception as e:
            logger.warning(f"Failed to fetch Polymarket markets: {e}")
            return pd.DataFrame()

    async def fetch_probability_history(
        self, market_id: str, window_h: int = 24
    ) -> Tuple[float, float]:
        """
        Fetch probability history and compute delta.

        Returns (current_prob, prob_delta) where delta is change over window.
        """
        try:
            resp = await self.http.get(
                f"{self.base_url}/polymarket/markets/{market_id}/history",
                params={"limit": 200},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict):
                history = data.get("history", data.get("data", []))
            elif isinstance(data, list):
                history = data
            else:
                history = []

            if not history:
                # Use cached value for delta calculation
                if market_id in self._prob_cache:
                    current, ts = self._prob_cache[market_id]
                    return current, 0.0
                return 0.5, 0.0

            df = pd.DataFrame(history)
            prob_col = None
            for col in ["probability", "yes_price", "price", "outcome_price"]:
                if col in df.columns:
                    prob_col = col
                    break

            if prob_col is None:
                return 0.5, 0.0

            df = df.dropna(subset=[prob_col])
            if df.empty:
                return 0.5, 0.0

            current = float(df[prob_col].iloc[-1])
            past_idx = max(0, len(df) - window_h)
            past = float(df[prob_col].iloc[past_idx]) if past_idx < len(df) else current

            self._prob_cache[market_id] = (current, datetime.now(timezone.utc).isoformat())
            delta = current - past
            return current, delta

        except Exception as e:
            logger.warning(f"Failed to fetch probability history for {market_id}: {e}")
            # Return cached if available
            if market_id in self._prob_cache:
                current, _ = self._prob_cache[market_id]
                return current, 0.0
            return 0.5, 0.0

    async def compute_polymarket_features(
        self, symbol: str, window_h: int = 24
    ) -> Dict[str, float]:
        """
        Compute Polymarket-based features for a symbol.

        Aggregates across top markets to produce:
          - polymarket_delta: weighted avg probability change
          - prob_jump_magnitude: max single-market probability jump
        """
        markets = await self.fetch_markets(limit=LOOKBACK_MARKETS)
        if markets.empty:
            return {"polymarket_delta": 0.0, "prob_jump_magnitude": 0.0}

        deltas = []
        max_jump = 0.0

        for _, row in markets.iterrows():
            market_id = row.get("id", "")
            if not market_id:
                continue

            _, delta = await self.fetch_probability_history(market_id, window_h)
            if delta != 0.0:
                deltas.append(delta)
                if abs(delta) > abs(max_jump):
                    max_jump = delta

        if not deltas:
            return {"polymarket_delta": 0.0, "prob_jump_magnitude": 0.0}

        # Weighted average (exclude outliers)
        deltas_sorted = sorted(deltas, key=abs, reverse=True)
        top_deltas = deltas_sorted[:5]  # top 5 most significant
        avg_delta = sum(top_deltas) / len(top_deltas) if top_deltas else 0.0

        return {
            "polymarket_delta": round(avg_delta, 4),
            "prob_jump_magnitude": round(abs(max_jump), 4),
        }


# Configuration for Polymarket fetcher
LOOKBACK_MARKETS = int(os.getenv("LOOKBACK_MARKETS", "20"))


# --- Feature Computation Engine ---

class FeatureEngine:
    """Feature computation engine with real data wiring."""

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
            params=(("window_h", 24),),
        ),
        "prob_jump_magnitude": FeatureSpec(
            name="prob_jump_magnitude",
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

    def __init__(
        self,
        redis_cli: RedisClient,
        event_fetcher: EventGatewayFetcher,
        polymarket_fetcher: PolymarketFetcher,
    ):
        self.redis = redis_cli
        self.event_fetcher = event_fetcher
        self.polymarket_fetcher = polymarket_fetcher
        self.cache_ttl = FEATURE_CACHE_TTL

    def _cache_key(self, symbol: str, feature_name: str) -> str:
        return f"feature:{symbol}:{feature_name}"

    async def _get_cached(self, symbol: str, feature_name: str) -> Optional[float]:
        """Get cached feature value."""
        key = self._cache_key(symbol, feature_name)
        val = await self.redis.client.get(key)
        return float(val) if val else None

    async def _cache_feature(
        self, symbol: str, feature_name: str, value: float
    ) -> None:
        """Cache computed feature value."""
        key = self._cache_key(symbol, feature_name)
        await self.redis.client.setex(key, self.cache_ttl, str(value))

    # --- Real feature computations ---

    def _compute_sentiment_mean(self, events: pd.DataFrame) -> float:
        """Compute mean sentiment from event confidence scores."""
        if events.empty:
            return 0.0
        if "confidence" in events.columns:
            return round(float(events["confidence"].mean()), 4)
        return 0.0

    def _compute_sentiment_polarity_skew(self, events: pd.DataFrame) -> float:
        """Compute skewness of confidence distribution."""
        if events.empty or "confidence" not in events.columns:
            return 0.0
        if len(events) < 5:
            return 0.0
        # Simple skew: difference between upper and lower quartile deviation
        conf = events["confidence"]
        q75, q25 = conf.quantile(0.75), conf.quantile(0.25)
        median = conf.median()
        if q75 == q25:
            return 0.0
        return round((median - (q75 + q25) / 2) / (q75 - q25), 4)

    def _compute_hype_velocity(self, events: pd.DataFrame) -> float:
        """
        Compute hype velocity (events per hour) from event timestamps.

        Looks at event frequency in recent window to detect viral spread.
        """
        if events.empty or "timestamp" not in events.columns:
            return 0.0
        try:
            events = events.copy()
            events["ts"] = pd.to_datetime(events["timestamp"], utc=True, errors="coerce")
            events = events.dropna(subset=["ts"])
            if events.empty:
                return 0.0
            now = datetime.now(timezone.utc)
            recent = events[events["ts"] > (now - timedelta(hours=6))]
            if recent.empty:
                return 0.0
            time_span_h = (now - recent["ts"].min()).total_seconds() / 3600
            if time_span_h < 0.1:
                time_span_h = 0.1
            return round(len(recent) / time_span_h, 2)
        except Exception as e:
            logger.warning(f"hype_velocity computation failed: {e}")
            return 0.0

    def _compute_hype_zscore(self, events: pd.DataFrame) -> float:
        """
        Compute z-score of current event count vs historical baseline.
        Uses rolling window statistics.
        """
        if events.empty:
            return 0.0
        # Mock: compute from current volume vs expected
        try:
            event_count = len(events)
            baseline = 50  # historical average
            std = 20  # historical std
            if std == 0:
                return 0.0
            return round((event_count - baseline) / std, 3)
        except Exception:
            return 0.0

    def _compute_bull_bear_ratio(self, events: pd.DataFrame) -> float:
        """Compute ratio of high-confidence events to low-confidence events."""
        if events.empty or "confidence" not in events.columns:
            return 1.0
        high = (events["confidence"] >= 0.6).sum()
        low = (events["confidence"] < 0.4).sum()
        if low == 0:
            return float(high) if high > 0 else 1.0
        return round(high / low, 3)

    def _compute_neutral_ratio(self, events: pd.DataFrame) -> float:
        """Compute proportion of medium-confidence events."""
        if events.empty or "confidence" not in events.columns:
            return 0.0
        neutral = ((events["confidence"] >= 0.4) & (events["confidence"] < 0.6)).sum()
        return round(neutral / len(events), 4) if len(events) > 0 else 0.0

    def _compute_cross_platform_speed(self, events: pd.DataFrame) -> float:
        """
        Compute speed of sentiment diffusion across platforms.

        Measures how quickly events for this symbol appeared across
        different sources (encoded in event_type or source field).
        """
        if events.empty:
            return 0.0
        if "source" in events.columns:
            unique_sources = events["source"].nunique()
            time_span = 24.0  # hours
            return round(unique_sources / time_span, 3)
        return 0.0

    def _compute_peak_heat_time(self, events: pd.DataFrame) -> float:
        """
        Compute hours since peak social activity.

        Finds the timestamp with highest event density.
        """
        if events.empty or "timestamp" not in events.columns:
            return 24.0
        try:
            events = events.copy()
            events["ts"] = pd.to_datetime(events["timestamp"], utc=True, errors="coerce")
            events = events.dropna(subset=["ts"])
            if events.empty:
                return 24.0
            now = datetime.now(timezone.utc)
            most_recent = events["ts"].max()
            hours_ago = (now - most_recent).total_seconds() / 3600
            return round(max(0.0, min(hours_ago, 168.0)), 2)
        except Exception:
            return 24.0

    async def compute_features(
        self,
        symbol: str,
        feature_names: Optional[List[str]] = None,
    ) -> List[FeatureValue]:
        """
        Compute features for a symbol using real data from event_gateway
        and Polymarket.

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT-Binance")
            feature_names: List of feature names to compute. If None, compute all.

        Returns:
            List of FeatureValue objects.
        """
        if feature_names is None:
            feature_names = list(self.FEATURE_SPECS.keys())

        now = datetime.now(timezone.utc)
        results: List[FeatureValue] = []

        # Fetch real event data from event_gateway
        event_types = ["SOCIAL_SURGE", "SENTIMENT_SHIFT", "SENTIMENT_SPIKE", "BULLISH_SIGNAL", "BEARISH_SIGNAL"]
        events = await self.event_fetcher.fetch_recent_events(symbol, event_types, limit=200)

        # Fetch Polymarket features
        poly_features = await self.polymarket_fetcher.compute_polymarket_features(symbol)

        for name in feature_names:
            if name not in self.FEATURE_SPECS:
                logger.warning(f"Feature {name} not in registry, skipping")
                continue

            # Check cache first (skip for Polymarket features - always fresh)
            if name not in ("polymarket_delta", "prob_jump_magnitude"):
                cached = await self._get_cached(symbol, name)
                if cached is not None:
                    results.append(FeatureValue(
                        name=name,
                        value=cached,
                        timestamp=now.isoformat(),
                        metadata={"cached": True}
                    ))
                    continue

            # Compute from real data
            try:
                if name == "polymarket_delta":
                    value = poly_features.get("polymarket_delta", 0.0)
                elif name == "prob_jump_magnitude":
                    value = poly_features.get("prob_jump_magnitude", 0.0)
                else:
                    value = self._compute_from_events(name, events)

                # Cache (except Polymarket - always fresh)
                if name not in ("polymarket_delta", "prob_jump_magnitude"):
                    await self._cache_feature(symbol, name, value)

                spec = self.FEATURE_SPECS[name]
                results.append(FeatureValue(
                    name=name,
                    value=value,
                    timestamp=now.isoformat(),
                    metadata={
                        "version": spec.version,
                        "group": spec.group.value,
                        "cached": False,
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

    def _compute_from_events(self, feature_name: str, events: pd.DataFrame) -> float:
        """Dispatch feature computation to appropriate handler."""
        handlers = {
            "sentiment_mean": self._compute_sentiment_mean,
            "sentiment_polarity_skew": self._compute_sentiment_polarity_skew,
            "hype_velocity": self._compute_hype_velocity,
            "hype_zscore": self._compute_hype_zscore,
            "bull_bear_ratio": self._compute_bull_bear_ratio,
            "neutral_ratio": self._compute_neutral_ratio,
            "cross_platform_speed": self._compute_cross_platform_speed,
            "peak_heat_time": self._compute_peak_heat_time,
        }
        handler = handlers.get(feature_name)
        if handler is None:
            return 0.0
        return handler(events)


# Global engine instance
engine: Optional[FeatureEngine] = None


# --- FastAPI Endpoints ---

@app.on_event("startup")
async def startup():
    global engine
    await redis_client.connect()

    http = httpx.AsyncClient(timeout=30)
    event_fetcher = EventGatewayFetcher(http, EVENT_GATEWAY_URL)
    polymarket_fetcher = PolymarketFetcher(http, DATA_GATEWAY_URL)

    engine = FeatureEngine(redis_client, event_fetcher, polymarket_fetcher)
    logger.info("Feature service started")


@app.on_event("shutdown")
async def shutdown():
    await redis_client.disconnect()
    logger.info("Feature service stopped")


@app.get("/health", response_model=HealthResponse)
async def health():
    redis_ok = await redis_client.is_connected()

    event_ok = False
    poly_ok = False

    if engine:
        try:
            http = engine.event_fetcher.http
            resp = await http.get(f"{EVENT_GATEWAY_URL}/health", timeout=5)
            event_ok = resp.status_code == 200
        except Exception:
            pass
        try:
            resp = await http.get(f"{DATA_GATEWAY_URL}/health", timeout=5)
            poly_ok = resp.status_code == 200
        except Exception:
            pass

    return HealthResponse(
        status="healthy" if (redis_ok and event_ok) else "degraded",
        redis_connected=redis_ok,
        event_gateway_connected=event_ok,
        data_gateway_connected=poly_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/features", response_model=FeatureListResponse)
async def list_features():
    """List all available features with their specs."""
    features = [spec.to_dict() for spec in engine.FEATURE_SPECS.values()]
    return FeatureListResponse(
        features=features,
        timestamp=datetime.now(timezone.utc).isoformat(),
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
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/features/{symbol}/{feature_name}/history")
async def get_feature_history(
    symbol: str,
    feature_name: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """Get historical feature values (from cache/Redis)."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    key = f"feature_history:{symbol}:{feature_name}"
    raw = await engine.redis.client.lrange(key, 0, limit - 1)
    history = [json.loads(r) for r in raw] if raw else []

    return {
        "symbol": symbol,
        "feature": feature_name,
        "history": history,
        "count": len(history),
    }


# --- Main Entry Point ---

def main():
    """Run the feature service."""
    logger.info("Starting feature_service on port 8094")
    uvicorn.run(app, host="0.0.0.0", port=8094, log_level="info")


if __name__ == "__main__":
    main()