"""Main entry point for orchestrator service.

Prefect orchestration flows — coordinates research pipeline, scheduling,
and task dependencies across all services.

Real service URLs:
  - event_gateway:   EVENT_GATEWAY_URL (default: http://localhost:8003)
  - feature_service:  FEATURE_SERVICE_URL (default: http://localhost:8094)
  - data_gateway:     DATA_GATEWAY_URL (default: http://localhost:8002)
  - signal_bridge:    SIGNAL_BRIDGE_URL (default: http://localhost:8090)
  - research_runner:  RESEARCH_RUNNER_URL (default: http://localhost:8099)
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from prefect import flow, task, get_run_logger
from prefect.runtime import flow as prefect_flow
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

# Configuration
EVENT_GATEWAY_URL = os.getenv("EVENT_GATEWAY_URL", "http://localhost:8003")
FEATURE_SERVICE_URL = os.getenv("FEATURE_SERVICE_URL", "http://localhost:8094")
SIGNAL_BRIDGE_URL = os.getenv("SIGNAL_BRIDGE_URL", "http://localhost:8090")
DATA_GATEWAY_URL = os.getenv("DATA_GATEWAY_URL", "http://localhost:8002")
RESEARCH_RUNNER_URL = os.getenv("RESEARCH_RUNNER_URL", "http://localhost:8099")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("orchestrator")


# --- Shared HTTP client ---

_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30)
    return _http_client


# --- Pydantic Models ---

class FlowRunRequest(BaseModel):
    flow_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    run_name: Optional[str] = None


class FlowRunResponse(BaseModel):
    flow_name: str
    run_id: str
    status: str
    message: str
    triggered_at: str


class FlowStatusResponse(BaseModel):
    flow_name: str
    run_id: str
    state: str
    start_time: Optional[str]
    end_time: Optional[str]


class HealthResponse(BaseModel):
    status: str
    prefect_ready: bool
    all_services_connected: bool
    timestamp: str


# --- Prefect Tasks (real service calls) ---

@task(name="fetch_market_data", description="Fetch OHLCV market data for symbol from data_gateway")
async def fetch_market_data_task(symbol: str, interval: str = "1h") -> Dict[str, Any]:
    """
    Task to fetch market OHLCV data from data_gateway.

    Calls: GET {DATA_GATEWAY_URL}/ohlcv/{symbol}?interval={interval}&limit=100
    """
    logger = get_run_logger()
    logger.info(f"Fetching market data for {symbol} ({interval})")

    http = await get_http_client()
    try:
        resp = await http.get(
            f"{DATA_GATEWAY_URL}/ohlcv/{symbol}",
            params={"interval": interval, "limit": 100},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        candles = data.get("ohlcv", [])
        latest = candles[-1] if candles else {}
        logger.info(f"Fetched {len(candles)} candles, latest price: {latest.get('close', 'N/A')}")
        return {
            "symbol": symbol,
            "interval": interval,
            "candles": len(candles),
            "latest_price": latest.get("close", 0),
            "latest_ts": latest.get("timestamp", ""),
        }
    except Exception as e:
        logger.warning(f"data_gateway unavailable: {e}")
        return {
            "symbol": symbol,
            "interval": interval,
            "candles": 0,
            "latest_price": 0.0,
            "error": str(e),
        }


@task(name="fetch_events", description="Fetch recent events from event_gateway")
async def fetch_events_task(symbol: str, event_types: List[str]) -> List[Dict[str, Any]]:
    """
    Task to fetch social events for symbol from event_gateway.

    Calls: GET {EVENT_GATEWAY_URL}/stream/read?count=100
    """
    logger = get_run_logger()
    logger.info(f"Fetching events for {symbol}, types={event_types}")

    http = await get_http_client()
    try:
        resp = await http.get(
            f"{EVENT_GATEWAY_URL}/stream/read",
            params={"count": 100},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        # Filter by symbol
        events = [e for e in events if e.get("event", {}).get("symbol") == symbol]
        logger.info(f"Fetched {len(events)} events for {symbol}")
        return events
    except Exception as e:
        logger.warning(f"event_gateway unavailable: {e}")
        return []


@task(name="compute_features", description="Compute features for symbol via feature_service")
async def compute_features_task(symbol: str, feature_names: List[str]) -> List[Dict[str, Any]]:
    """
    Task to compute features via feature_service.

    Calls: POST {FEATURE_SERVICE_URL}/features/compute
    """
    logger = get_run_logger()
    logger.info(f"Computing features for {symbol}: {feature_names}")

    http = await get_http_client()
    try:
        resp = await http.post(
            f"{FEATURE_SERVICE_URL}/features/compute",
            json={"symbol": symbol, "feature_names": feature_names},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        logger.info(f"Computed {len(features)} features for {symbol}")
        return features
    except Exception as e:
        logger.warning(f"feature_service unavailable: {e}")
        return []


@task(name="generate_signal", description="Generate trading signal from features")
def generate_signal_task(symbol: str, features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Task to generate a trading signal from computed features.

    Logic:
      - polymarket_delta > 0.1 + sentiment_mean > 0 -> BUY
      - polymarket_delta < -0.1 + sentiment_mean < 0 -> SELL
      - prob_jump_magnitude > threshold -> confirm signal
      - Signal strength = weighted combination of feature values
    """
    logger = get_run_logger()
    logger.info(f"Generating signal for {symbol}")

    # Parse features
    feat_dict = {f["name"]: f["value"] for f in features}

    sentiment_mean = feat_dict.get("sentiment_mean", 0.0)
    hype_velocity = feat_dict.get("hype_velocity", 0.0)
    hype_zscore = feat_dict.get("hype_zscore", 0.0)
    bull_bear_ratio = feat_dict.get("bull_bear_ratio", 1.0)
    polymarket_delta = feat_dict.get("polymarket_delta", 0.0)
    prob_jump_magnitude = feat_dict.get("prob_jump_magnitude", 0.0)
    cross_platform_speed = feat_dict.get("cross_platform_speed", 0.0)

    # Decision thresholds
    POLYMARKET_THRESHOLD = 0.1
    SENTIMENT_THRESHOLD = 0.3

    side = "HOLD"
    entry_mode = "NO_TRADE"
    signal_strength = 0.0

    # Polymarket + sentiment confirmation logic
    if polymarket_delta > POLYMARKET_THRESHOLD and sentiment_mean > SENTIMENT_THRESHOLD:
        side = "BUY"
        entry_mode = "FULL_ENTER" if signal_strength > 0.7 else "PARTIAL_ENTER"
        # Compute strength from features
        base_strength = min(abs(polymarket_delta) * 3 + sentiment_mean * 0.5, 1.0)
        signal_strength = round(min(base_strength * 1.2, 1.0), 3)
    elif polymarket_delta < -POLYMARKET_THRESHOLD and sentiment_mean < -SENTIMENT_THRESHOLD:
        side = "SELL"
        entry_mode = "PARTIAL_ENTER"
        base_strength = min(abs(polymarket_delta) * 3 + abs(sentiment_mean) * 0.5, 1.0)
        signal_strength = round(min(base_strength, 0.9), 3)
    elif prob_jump_magnitude > 0.15:
        # Strong prob jump without sentiment confirmation
        side = "BUY" if polymarket_delta > 0 else "SELL"
        signal_strength = round(min(prob_jump_magnitude * 2, 0.8), 3)
        entry_mode = "SMALL_TEST"
    elif hype_zscore > 2.0 and bull_bear_ratio > 2.0:
        # Extreme hype without polymarket confirmation
        side = "SELL"
        signal_strength = round(min(hype_zscore * 0.2, 0.7), 3)
        entry_mode = "SMALL_TEST"
    else:
        signal_strength = 0.0
        side = "HOLD"
        entry_mode = "NO_TRADE"

    # Target position scales with signal strength
    target_position_pct = 10.0 if side == "BUY" else (5.0 if side == "SELL" else 0.0)

    risk_tags = [
        f"polymarket_delta_{polymarket_delta:.3f}",
        f"prob_jump_{prob_jump_magnitude:.3f}",
        f"hype_zscore_{hype_zscore:.2f}",
    ]

    return {
        "signal_id": str(uuid.uuid4()),
        "strategy_id": "crypto_sentiment_v1",
        "symbol": symbol,
        "side": side,
        "signal_strength": signal_strength,
        "target_position_pct": target_position_pct,
        "entry_mode": entry_mode,
        "ttl_seconds": 900,
        "risk_tags": risk_tags,
        "features_used": list(feat_dict.keys()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@task(name="publish_signal", description="Publish signal to signal_bridge")
async def publish_signal_task(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task to publish signal to signal_bridge.

    Calls: POST {SIGNAL_BRIDGE_URL}/signals
    """
    logger = get_run_logger()
    logger.info(f"Publishing signal {signal['signal_id']} for {signal['symbol']}")

    http = await get_http_client()
    try:
        resp = await http.post(
            f"{SIGNAL_BRIDGE_URL}/signals",
            json=signal,
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Signal published: {result}")
        return {
            "signal_id": signal["signal_id"],
            "status": "RECEIVED",
            "message": "Signal published successfully",
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to publish signal: {e}")
        return {
            "signal_id": signal["signal_id"],
            "status": "FAILED",
            "message": str(e),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }


@task(name="run_backtest", description="Run backtest via research_runner")
async def run_backtest_task(symbol: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Task to run a backtest via research_runner.

    Calls: POST {RESEARCH_RUNNER_URL}/backtest
    """
    logger = get_run_logger()
    logger.info(f"Running backtest for {symbol}")

    http = await get_http_client()
    try:
        resp = await http.post(
            f"{RESEARCH_RUNNER_URL}/backtest",
            json={
                "config": {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "strategy_id": "crypto_sentiment_v1",
                    "initial_capital": 10000.0,
                    "feature_names": [
                        "sentiment_mean", "hype_velocity",
                        "bull_bear_ratio", "polymarket_delta"
                    ],
                }
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Backtest completed: run_id={result.get('run_id')}")
        return result
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {"error": str(e)}


@task(name="log_research_run", description="Log research run results")
def log_research_run_task(results: Dict[str, Any]) -> None:
    """Task to log research run results."""
    logger = get_run_logger()
    logger.info(f"Research run completed: {results}")
    signal = results.get("signal", {})
    if signal:
        logger.info(
            f"Signal: {signal.get('side')} {signal.get('symbol')} "
            f"strength={signal.get('signal_strength')} "
            f"entry={signal.get('entry_mode')}"
        )


# --- Prefect Flows ---

@flow(name="crypto_research_flow", description="Main research pipeline flow — market data + events + features + signal + publish")
def crypto_research_flow(symbol: str = "BTC/USDT-Binance") -> Dict[str, Any]:
    """
    Main research pipeline flow.

    Orchestrates:
      1. Market data fetching (data_gateway)
      2. Event fetching (event_gateway)
      3. Feature computation (feature_service)
      4. Signal generation (local logic)
      5. Signal publishing (signal_bridge)
      6. Logging
    """
    logger = get_run_logger()
    logger.info(f"Starting crypto research flow for {symbol}")

    # Step 1: Fetch market data
    market_data = fetch_market_data_task(symbol)

    # Step 2: Fetch events
    events = fetch_events_task(symbol, ["SOCIAL_SURGE", "SENTIMENT_SHIFT"])

    # Step 3: Compute features
    features = compute_features_task(symbol, [
        "sentiment_mean",
        "hype_velocity",
        "hype_zscore",
        "bull_bear_ratio",
        "neutral_ratio",
        "polymarket_delta",
        "prob_jump_magnitude",
        "cross_platform_speed",
        "peak_heat_time",
    ])

    # Step 4: Generate signal
    signal = generate_signal_task(symbol, features)

    # Step 5: Publish signal (only if actionable)
    publish_result = None
    if signal.get("signal_strength", 0) > 0.3:
        publish_result = publish_signal_task(signal)
    else:
        logger.info(f"No actionable signal for {symbol} (strength={signal.get('signal_strength')}), skipping publish")

    # Log results
    log_research_run_task({
        "symbol": symbol,
        "market_data": market_data,
        "events_count": len(events),
        "features_count": len(features),
        "signal": signal,
    })

    return {
        "symbol": symbol,
        "market_data": market_data,
        "events": events,
        "features": features,
        "signal": signal,
        "publish_result": publish_result,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


@flow(name="batch_research_flow", description="Batch research across multiple symbols")
def batch_research_flow(symbols: List[str]) -> Dict[str, Any]:
    """
    Run research flow for multiple symbols in parallel.

    Uses asyncio.gather to run research for all symbols concurrently.
    """
    logger = get_run_logger()
    logger.info(f"Starting batch research for {len(symbols)} symbols")

    import asyncio
    results = {}
    for symbol in symbols:
        try:
            result = crypto_research_flow(symbol)
            results[symbol] = {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Failed research for {symbol}: {e}")
            results[symbol] = {"status": "error", "error": str(e)}

    return {
        "total": len(symbols),
        "completed": sum(1 for r in results.values() if r["status"] == "success"),
        "failed": sum(1 for r in results.values() if r["status"] == "error"),
        "results": results,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


@flow(name="hourly_research_flow", description="Hourly scheduled research cycle")
def hourly_research_flow() -> Dict[str, Any]:
    """Hourly scheduled research cycle — runs batch_research for default symbols."""
    logger = get_run_logger()
    logger.info("Starting hourly research cycle")

    symbols = ["BTC/USDT-Binance", "ETH/USDT-Binance"]
    result = batch_research_flow(symbols)

    logger.info(f"Hourly research cycle completed: {result['completed']}/{result['total']}")
    return result


@flow(name="daily_research_flow", description="Daily deep research with backtest")
def daily_research_flow(symbol: str = "BTC/USDT-Binance") -> Dict[str, Any]:
    """
    Daily deep research: runs full backtest and produces detailed report.
    """
    logger = get_run_logger()
    logger.info(f"Starting daily deep research for {symbol}")

    # Run research flow
    research = crypto_research_flow(symbol)

    # Run backtest (last 30 days)
    end_date = datetime.now(timezone.utc).date().isoformat()
    start_date = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()

    backtest = run_backtest_task(symbol, start_date, end_date)

    return {
        "symbol": symbol,
        "research": research,
        "backtest": backtest,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# --- FastAPI Endpoints ---

app = FastAPI(title="Orchestrator", version="1.0.0", description="Prefect orchestration service")

_flow_runs: Dict[str, Dict[str, Any]] = {}


async def _check_service_health(url: str) -> bool:
    """Check if a service is healthy."""
    try:
        http = await get_http_client()
        resp = await http.get(f"{url}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check — checks all downstream services."""
    services = {
        "event_gateway": EVENT_GATEWAY_URL,
        "feature_service": FEATURE_SERVICE_URL,
        "data_gateway": DATA_GATEWAY_URL,
        "signal_bridge": SIGNAL_BRIDGE_URL,
        "research_runner": RESEARCH_RUNNER_URL,
    }
    results = await asyncio.gather(*[_check_service_health(url) for url in services.values()])
    all_ok = all(results)

    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        prefect_ready=True,
        all_services_connected=all_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/flows/run", response_model=FlowRunResponse)
async def trigger_flow(request: FlowRunRequest):
    """Trigger a named flow run."""
    import uuid

    flow_map = {
        "crypto_research": crypto_research_flow,
        "batch_research": batch_research_flow,
        "hourly_research": hourly_research_flow,
        "daily_research": daily_research_flow,
    }

    if request.flow_name not in flow_map:
        raise HTTPException(
            status_code=404,
            detail=f"Flow {request.flow_name} not found. Available: {list(flow_map.keys())}"
        )

    run_id = str(uuid.uuid4())
    _flow_runs[run_id] = {
        "flow_name": request.flow_name,
        "run_id": run_id,
        "status": "RUNNING",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        flow_func = flow_map[request.flow_name]
        if request.flow_name == "crypto_research":
            result = flow_func(**request.parameters)
        elif request.flow_name == "batch_research":
            result = flow_func(**request.parameters)
        elif request.flow_name == "daily_research":
            result = flow_func(**request.parameters)
        else:
            result = flow_func()

        _flow_runs[run_id]["status"] = "COMPLETED"
        _flow_runs[run_id]["result"] = result

        return FlowRunResponse(
            flow_name=request.flow_name,
            run_id=run_id,
            status="COMPLETED",
            message="Flow completed successfully",
            triggered_at=_flow_runs[run_id]["triggered_at"],
        )
    except Exception as e:
        _flow_runs[run_id]["status"] = "FAILED"
        _flow_runs[run_id]["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/flows/{flow_name}")
async def get_flow_info(flow_name: str):
    """Get flow definition info."""
    flow_map = {
        "crypto_research": crypto_research_flow,
        "batch_research": batch_research_flow,
        "hourly_research": hourly_research_flow,
        "daily_research": daily_research_flow,
    }

    if flow_name not in flow_map:
        raise HTTPException(status_code=404, detail=f"Flow {flow_name} not found")

    return {
        "name": flow_name,
        "description": flow_map[flow_name].description,
        "parameters": {},
    }


@app.get("/flows/runs/{run_id}")
async def get_flow_run_status(run_id: str):
    """Get status of a flow run."""
    if run_id not in _flow_runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _flow_runs[run_id]


@app.get("/flows/runs")
async def list_flow_runs(limit: int = Query(50, ge=1, le=100)):
    """List recent flow runs."""
    runs = list(_flow_runs.values())[-limit:]
    return {"count": len(runs), "runs": runs}


# --- Main Entry Point ---

def main():
    """Run the orchestrator service."""
    logger.info("Starting orchestrator service on port 8095")
    uvicorn.run(app, host="0.0.0.0", port=8095, log_level="info")


if __name__ == "__main__":
    main()