"""Tests for adapter base."""
from adapters.base import DataSourceABC
from adapters.exchange.binance import BinanceAdapter
from adapters.social.x_adapter import XAdapter
from adapters.polymarket.client import PolymarketAdapter
from adapters.onchain.client import OnchainAdapter


def test_binance_adapter_creation():
    adapter = BinanceAdapter()
    assert adapter.health_check() is True
    df = adapter.fetch_ohlcv("BTCUSDT", "1h")
    assert df.empty


def test_x_adapter():
    adapter = XAdapter()
    assert adapter.health_check() is True
    mentions = adapter.fetch_mentions("BTC")
    assert mentions["symbol"] == "BTC"


def test_polymarket_adapter():
    adapter = PolymarketAdapter()
    assert adapter.health_check() is True
    prob = adapter.fetch_probability("test-market")
    assert "probability" in prob


def test_onchain_adapter():
    adapter = OnchainAdapter()
    assert adapter.health_check() is True
    df = adapter.fetch_whale_activity("BTC")
    assert df.empty
