"""Main entry point for data_gateway service.

Unified market data entry point - aggregates data from multiple sources
(Binance, Polymarket, social feeds) via the adapter layer.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

from common_schema.market import OHLCV, OrderBookSnapshot, FundingRate, Ticker

# Configuration
BINANCE_ENABLED = os.getenv("BINANCE_ENABLED", "true").lower() == "true"
POLYMARKET_ENABLED = os.getenv("POLYMARKET_ENABLED", "true").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("data_gateway")

app = FastAPI(title="Data Gateway", version="1.0.0", description="Unified market data entry point")


# --- Pydantic Models ---

class OHLCVResponse(BaseModel):
    """OHLCV data response."""
    symbol: str
    interval: str
    data: List[Dict[str, Any]]
    timestamp: str


class OrderBookResponse(BaseModel):
    """Order book response."""
    symbol: str
    bids: List[List[float]]
    asks: List[List[float]]
    timestamp: str


class TickerResponse(BaseModel):
    """Ticker response."""
    symbol: str
    last_price: float
    volume_24h: float
    change_24h: float
    high_24h: float
    low_24h: float
    timestamp: str


class FundingRateResponse(BaseModel):
    """Funding rate response."""
    symbol: str
    funding_rate: float
    next_funding_time: str
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    binance_connected: bool
    polymarket_connected: bool
    timestamp: str


# --- Mock Data Source Adapters (replace with real adapters) ---

class BinanceAdapter:
    """Mock Binance adapter - replace with adapters.exchange.binance.BinanceAdapter."""
    
    async def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV candlestick data."""
        # Mock data - replace with real API call
        import numpy as np
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=limit, freq='1h')
        return pd.DataFrame({
            'timestamp': dates,
            'open': np.random.uniform(50000, 70000, limit),
            'high': np.random.uniform(50000, 70000, limit),
            'low': np.random.uniform(50000, 70000, limit),
            'close': np.random.uniform(50000, 70000, limit),
            'volume': np.random.uniform(100, 1000, limit),
        })
    
    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """Fetch order book snapshot."""
        import numpy as np
        mid = 65000
        return {
            'symbol': symbol,
            'bids': [[mid - i * 10, np.random.uniform(1, 10)] for i in range(depth)],
            'asks': [[mid + i * 10, np.random.uniform(1, 10)] for i in range(depth)],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch 24h ticker."""
        import numpy as np
        price = np.random.uniform(50000, 70000)
        return {
            'symbol': symbol,
            'last_price': price,
            'volume_24h': np.random.uniform(10000, 100000),
            'change_24h': np.random.uniform(-5, 5),
            'high_24h': price * 1.02,
            'low_24h': price * 0.98,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def fetch_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Fetch funding rate."""
        import numpy as np
        return {
            'symbol': symbol,
            'funding_rate': np.random.uniform(0.0001, 0.001),
            'next_funding_time': '2026-05-28T08:00:00Z',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def health_check(self) -> bool:
        """Check if Binance API is accessible."""
        return True  # Mock always healthy


class PolymarketAdapter:
    """Mock Polymarket adapter - replace with adapters.polymarket.client.PolymarketClient."""
    
    async def fetch_markets(self, filter_opts: Optional[Dict] = None) -> List[Dict]:
        """Fetch prediction markets."""
        return [
            {
                'id': 'crypto-price-may-2026',
                'question': 'Will BTC exceed $80k by end of May 2026?',
                'outcome': 'Yes',
                'probability': 0.65,
                'volume': 1000000,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        ]
    
    async def fetch_market_history(self, market_id: str, limit: int = 100) -> List[Dict]:
        """Fetch market price history."""
        import numpy as np
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=limit, freq='1h')
        return [
            {
                'timestamp': d.isoformat(),
                'probability': np.clip(0.3 + i * 0.005 + np.random.uniform(-0.1, 0.1), 0, 1)
            }
            for i, d in enumerate(dates)
        ]
    
    async def health_check(self) -> bool:
        """Check if Polymarket API is accessible."""
        return True  # Mock always healthy


# Global adapters
binance = BinanceAdapter()
polymarket = PolymarketAdapter()


# --- Data Gateway Logic ---

class DataGateway:
    """Unified data gateway - aggregates and normalizes market data."""
    
    def __init__(self, binance_adapter, polymarket_adapter):
        self.binance = binance_adapter
        self.polymarket = polymarket_adapter
    
    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> OHLCVResponse:
        """Get OHLCV data for symbol."""
        try:
            df = await self.binance.fetch_ohlcv(symbol, interval, limit)
            return OHLCVResponse(
                symbol=symbol,
                interval=interval,
                data=df.to_dict(orient='records'),
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch OHLCV: {str(e)}")
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBookResponse:
        """Get order book for symbol."""
        try:
            data = await self.binance.fetch_orderbook(symbol, depth)
            return OrderBookResponse(
                symbol=data['symbol'],
                bids=data['bids'],
                asks=data['asks'],
                timestamp=data['timestamp']
            )
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch orderbook: {str(e)}")
    
    async def get_ticker(self, symbol: str) -> TickerResponse:
        """Get 24h ticker for symbol."""
        try:
            data = await self.binance.fetch_ticker(symbol)
            return TickerResponse(
                symbol=data['symbol'],
                last_price=data['last_price'],
                volume_24h=data['volume_24h'],
                change_24h=data['change_24h'],
                high_24h=data['high_24h'],
                low_24h=data['low_24h'],
                timestamp=data['timestamp']
            )
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch ticker: {str(e)}")
    
    async def get_funding_rate(self, symbol: str) -> FundingRateResponse:
        """Get funding rate for symbol."""
        try:
            data = await self.binance.fetch_funding_rate(symbol)
            return FundingRateResponse(
                symbol=data['symbol'],
                funding_rate=data['funding_rate'],
                next_funding_time=data['next_funding_time'],
                timestamp=data['timestamp']
            )
        except Exception as e:
            logger.error(f"Failed to fetch funding rate for {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch funding rate: {str(e)}")
    
    async def get_polymarket_markets(self, filter_opts: Optional[Dict] = None) -> List[Dict]:
        """Get Polymarket prediction markets."""
        try:
            return await self.polymarket.fetch_markets(filter_opts)
        except Exception as e:
            logger.error(f"Failed to fetch Polymarket markets: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch markets: {str(e)}")
    
    async def get_polymarket_history(self, market_id: str, limit: int = 100) -> List[Dict]:
        """Get Polymarket market price history."""
        try:
            return await self.polymarket.fetch_market_history(market_id, limit)
        except Exception as e:
            logger.error(f"Failed to fetch Polymarket history for {market_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")


# Global gateway instance
gateway: Optional[DataGateway] = None


# --- FastAPI Endpoints ---

@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    global gateway
    gateway = DataGateway(binance, polymarket)
    logger.info("Data gateway service started")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    binance_ok = await binance.health_check() if BINANCE_ENABLED else False
    polymarket_ok = await polymarket.health_check() if POLYMARKET_ENABLED else False
    all_ok = binance_ok and polymarket_ok
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        binance_connected=binance_ok,
        polymarket_connected=polymarket_ok,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/ohlcv/{symbol}", response_model=OHLCVResponse)
async def get_ohlcv(
    symbol: str,
    interval: str = Query("1h", description="Candlestick interval (1m, 5m, 15m, 1h, 4h, 1d)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of candles")
):
    """Get OHLCV candlestick data for a symbol."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.get_ohlcv(symbol, interval, limit)


@app.get("/orderbook/{symbol}", response_model=OrderBookResponse)
async def get_orderbook(
    symbol: str,
    depth: int = Query(20, ge=5, le=100, description="Order book depth")
):
    """Get order book snapshot for a symbol."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.get_orderbook(symbol, depth)


@app.get("/ticker/{symbol}", response_model=TickerResponse)
async def get_ticker(symbol: str):
    """Get 24h ticker data for a symbol."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.get_ticker(symbol)


@app.get("/funding/{symbol}", response_model=FundingRateResponse)
async def get_funding_rate(symbol: str):
    """Get funding rate for a perpetual futures symbol."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.get_funding_rate(symbol)


@app.get("/polymarket/markets")
async def get_polymarket_markets(
    filter_tag: Optional[str] = Query(None, description="Filter by tag")
):
    """Get Polymarket prediction markets."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    filter_opts = {"tag": filter_tag} if filter_tag else None
    return await gateway.get_polymarket_markets(filter_opts)


@app.get("/polymarket/markets/{market_id}/history")
async def get_polymarket_market_history(
    market_id: str,
    limit: int = Query(100, ge=1, le=1000)
):
    """Get price history for a Polymarket market."""
    if gateway is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await gateway.get_polymarket_history(market_id, limit)


# --- Main Entry Point ---

def main():
    """Run the data gateway service."""
    logger.info("Starting data_gateway service on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")


if __name__ == "__main__":
    main()