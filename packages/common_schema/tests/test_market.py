"""Tests for market schemas."""
from datetime import datetime, timezone
from common_schema.market import OHLCV, OrderBookSnapshot, FundingRate, Ticker


def test_ohlcv_serialization():
    ohlcv = OHLCV(
        symbol="BTCUSDT",
        timestamp=datetime(2026, 5, 27, 12, 0, 0, tzinfo=timezone.utc),
        open=70000.0,
        high=71000.0,
        low=69000.0,
        close=70500.0,
        volume=100.0,
        turnover=7050000.0,
    )
    d = ohlcv.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["close"] == 70500.0
    restored = OHLCV.from_dict(d)
    assert restored.symbol == ohlcv.symbol
    assert restored.close == ohlcv.close


def test_orderbook_snapshot():
    ob = OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        bids=((70000.0, 1.0), (69900.0, 2.0)),
        asks=((70100.0, 1.5), (70200.0, 0.5)),
        spread=100.0,
    )
    d = ob.to_dict()
    restored = OrderBookSnapshot.from_dict(d)
    assert len(restored.bids) == 2
    assert restored.spread == 100.0


def test_funding_rate():
    fr = FundingRate(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        rate=0.0001,
        next_funding_time=datetime(2026, 5, 28, 8, 0, 0, tzinfo=timezone.utc),
    )
    d = fr.to_dict()
    restored = FundingRate.from_dict(d)
    assert restored.rate == 0.0001


def test_ticker():
    ticker = Ticker(
        symbol="ETHUSDT",
        timestamp=datetime.now(timezone.utc),
        last_price=3500.0,
        bid=3499.0,
        ask=3501.0,
        volume_24h=50000.0,
    )
    d = ticker.to_dict()
    restored = Ticker.from_dict(d)
    assert restored.last_price == 3500.0
