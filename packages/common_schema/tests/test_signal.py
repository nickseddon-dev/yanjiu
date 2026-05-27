"""Tests for signal schemas."""
from datetime import datetime, timezone
from common_schema.signal import (
    Signal, SignalAck, SignalStatus, EntryDecision, SignalStrength
)


def test_signal_creation():
    sig = Signal(
        signal_id="test-123",
        strategy_id="social_event_v1",
        symbol="BTCUSDT",
        side="BUY",
        signal_strength=0.87,
        target_position_pct=0.15,
        entry_mode=EntryDecision.SMALL_TEST,
        max_slippage_bps=8,
        ttl_seconds=900,
    )
    assert sig.signal_id == "test-123"
    assert sig.signal_strength == 0.87
    d = sig.to_dict()
    assert d["side"] == "BUY"
    assert d["entry_mode"] == "SMALL_TEST"


def test_signal_round_trip():
    sig = Signal(
        strategy_id="test_strategy",
        symbol="ETHUSDT",
        side="SELL",
        signal_strength=0.5,
    )
    d = sig.to_dict()
    restored = Signal.from_dict(d)
    assert restored.symbol == sig.symbol
    assert restored.side == sig.side


def test_signal_ack():
    ack = SignalAck(
        signal_id="sig-456",
        status=SignalStatus.EXECUTED,
        executed_price=70500.0,
        executed_quantity=0.1,
    )
    d = ack.to_dict()
    restored = SignalAck.from_dict(d)
    assert restored.status == SignalStatus.EXECUTED
    assert restored.executed_price == 70500.0


def test_signal_status_enum():
    assert SignalStatus.PENDING.value == "PENDING"
    assert SignalStatus.EXECUTED.value == "EXECUTED"


def test_entry_decision_enum():
    assert EntryDecision.NO_TRADE.value == "NO_TRADE"
    assert EntryDecision.FULL_ENTER.value == "FULL_ENTER"
