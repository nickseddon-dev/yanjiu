"""Main entry point for orchestrator service.

Prefect orchestration flows - coordinates research pipeline, scheduling,
and task dependencies across all services.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from prefect import flow, task, get_run_logger
from prefect.runtime import flow as prefect_flow
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

# Configuration
EVENT_GATEWAY_URL = os.getenv("EVENT_GATEWAY_URL", "http://localhost:8003")
FEATURE_SERVICE_URL = os.getenv("FEATURE_SERVICE_URL", "http://localhost:8004")
SIGNAL_BRIDGE_URL = os.getenv("SIGNAL_BRIDGE_URL", "http://localhost:8001")
DATA_GATEWAY_URL = os.getenv("DATA_GATEWAY_URL", "http://localhost:8002")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("orchestrator")

app = FastAPI(title="Orchestrator", version="1.0.0", description="Prefect orchestration service")


# --- Pydantic Models ---

class FlowRunRequest(BaseModel):
    """Request to trigger a flow run."""
    flow_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    run_name: Optional[str] = None


class FlowRunResponse(BaseModel):
    """Response after triggering a flow."""
    flow_name: str
    run_id: str
    status: str
    message: str
    triggered_at: str


class FlowStatusResponse(BaseModel):
    """Flow run status."""
    flow_name: str
    run_id: str
    state: str
    start_time: Optional[str]
    end_time: Optional[str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    prefect_ready: bool
    timestamp: str


# --- Prefect Tasks ---

@task(name="fetch_market_data", description="Fetch latest market data for symbol")
def fetch_market_data_task(symbol: str, interval: str = "1h") -> Dict[str, Any]:
    """Task to fetch market OHLCV data."""
    logger = get_run_logger()
    logger.info(f"Fetching market data for {symbol} ({interval})")
    
    # Mock implementation - in production, call data_gateway
    return {
        "symbol": symbol,
        "interval": interval,
        "candles": 100,
        "latest_price": 65000.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@task(name="fetch_events", description="Fetch recent events from event gateway")
def fetch_events_task(symbol: str, event_types: List[str]) -> List[Dict[str, Any]]:
    """Task to fetch events for symbol."""
    logger = get_run_logger()
    logger.info(f"Fetching events for {symbol}, types={event_types}")
    
    # Mock implementation - in production, call event_gateway
    return [
        {
            "event_id": "evt-001",
            "event_type": "SOCIAL_SURGE",
            "symbol": symbol,
            "confidence": 0.8,
            "intensity": 0.7,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    ]


@task(name="compute_features", description="Compute features for symbol")
def compute_features_task(symbol: str, feature_names: List[str]) -> List[Dict[str, Any]]:
    """Task to compute features."""
    logger = get_run_logger()
    logger.info(f"Computing features for {symbol}: {feature_names}")
    
    # Mock implementation - in production, call feature_service
    return [
        {
            "name": "sentiment_mean",
            "value": 0.65,
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        {
            "name": "hype_velocity",
            "value": 150.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    ]


@task(name="generate_signal", description="Generate trading signal from features")
def generate_signal_task(symbol: str, features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Task to generate a trading signal."""
    logger = get_run_logger()
    logger.info(f"Generating signal for {symbol}")
    
    # Simple signal logic based on features
    sentiment = 0.0
    hype = 0.0
    
    for f in features:
        if f["name"] == "sentiment_mean":
            sentiment = f["value"]
        elif f["name"] == "hype_velocity":
            hype = f["value"]
    
    # Decision logic
    if sentiment > 0.6 and hype > 100:
        signal_strength = min((sentiment + hype / 500) / 2, 1.0)
        side = "BUY"
        entry_mode = "FULL_ENTER"
    elif sentiment < -0.4:
        signal_strength = min(abs(sentiment), 1.0)
        side = "SELL"
        entry_mode = "PARTIAL_ENTER"
    else:
        signal_strength = 0.0
        side = "HOLD"
        entry_mode = "NO_TRADE"
    
    import uuid
    return {
        "signal_id": str(uuid.uuid4()),
        "strategy_id": "crypto_sentiment_v1",
        "symbol": symbol,
        "side": side,
        "signal_strength": signal_strength,
        "target_position_pct": 10.0 if side == "BUY" else (5.0 if side == "SELL" else 0.0),
        "entry_mode": entry_mode,
        "ttl_seconds": 900,
        "risk_tags": ["automated"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }


@task(name="publish_signal", description="Publish signal to signal bridge")
def publish_signal_task(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Task to publish signal to signal bridge."""
    logger = get_run_logger()
    logger.info(f"Publishing signal {signal['signal_id']} for {signal['symbol']}")
    
    # Mock - in production, call signal_bridge
    return {
        "signal_id": signal["signal_id"],
        "status": "RECEIVED",
        "message": "Signal published successfully",
        "received_at": datetime.now(timezone.utc).isoformat()
    }


@task(name="log_research_run", description="Log research run results")
def log_research_run_task(results: Dict[str, Any]) -> None:
    """Task to log research run results."""
    logger = get_run_logger()
    logger.info(f"Research run completed: {results}")
    logger.info(f"Signal generated: {results.get('signal', {}).get('signal_id', 'N/A')}")


# --- Prefect Flows ---

@flow(name="crypto_research_flow", description="Main research pipeline flow")
def crypto_research_flow(symbol: str = "BTC/USDT-Binance") -> Dict[str, Any]:
    """Main research pipeline flow.
    
    Orchestrates:
    1. Market data fetching
    2. Event fetching
    3. Feature computation
    4. Signal generation
    5. Signal publishing
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
        "polymarket_delta"
    ])
    
    # Step 4: Generate signal
    signal = generate_signal_task(symbol, features)
    
    # Step 5: Publish signal (only if actionable)
    if signal.get("signal_strength", 0) > 0:
        publish_signal_task(signal)
    else:
        logger.info(f"No actionable signal for {symbol}, skipping publish")
    
    # Log results
    log_research_run_task({
        "symbol": symbol,
        "market_data": market_data,
        "events_count": len(events),
        "features_count": len(features),
        "signal": signal
    })
    
    return {
        "symbol": symbol,
        "market_data": market_data,
        "events": events,
        "features": features,
        "signal": signal,
        "completed_at": datetime.now(timezone.utc).isoformat()
    }


@flow(name="batch_research_flow", description="Batch research across multiple symbols")
def batch_research_flow(symbols: List[str]) -> Dict[str, Any]:
    """Run research flow for multiple symbols."""
    logger = get_run_logger()
    logger.info(f"Starting batch research for {len(symbols)} symbols")
    
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
        "completed_at": datetime.now(timezone.utc).isoformat()
    }


@flow(name="hourly_research_flow", description="Hourly research cycle")
def hourly_research_flow() -> Dict[str, Any]:
    """Hourly scheduled research cycle."""
    logger = get_run_logger()
    logger.info("Starting hourly research cycle")
    
    # Default symbols for hourly cycle
    symbols = ["BTC/USDT-Binance", "ETH/USDT-Binance"]
    result = batch_research_flow(symbols)
    
    logger.info(f"Hourly research cycle completed: {result['completed']}/{result['total']}")
    return result


# --- FastAPI Endpoints ---

_flow_runs: Dict[str, Dict[str, Any]] = {}


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        prefect_ready=True,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/flows/run", response_model=FlowRunResponse)
async def trigger_flow(request: FlowRunRequest):
    """Trigger a named flow run."""
    import uuid
    
    flow_map = {
        "crypto_research": crypto_research_flow,
        "batch_research": batch_research_flow,
        "hourly_research": hourly_research_flow,
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
        "triggered_at": datetime.now(timezone.utc).isoformat()
    }
    
    # In production, use Prefect API to submit flow run
    # For now, run synchronously as a preview
    try:
        flow_func = flow_map[request.flow_name]
        if request.flow_name == "crypto_research":
            result = flow_func(**request.parameters)
        elif request.flow_name == "batch_research":
            result = flow_func(**request.parameters)
        elif request.flow_name == "hourly_research":
            result = flow_func()
        
        _flow_runs[run_id]["status"] = "COMPLETED"
        _flow_runs[run_id]["result"] = result
        
        return FlowRunResponse(
            flow_name=request.flow_name,
            run_id=run_id,
            status="COMPLETED",
            message="Flow completed successfully",
            triggered_at=_flow_runs[run_id]["triggered_at"]
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
    }
    
    if flow_name not in flow_map:
        raise HTTPException(status_code=404, detail=f"Flow {flow_name} not found")
    
    return {
        "name": flow_name,
        "description": flow_map[flow_name].description,
        "parameters": {}
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
    logger.info("Starting orchestrator service on port 8005")
    uvicorn.run(app, host="0.0.0.0", port=8005, log_level="info")


if __name__ == "__main__":
    main()