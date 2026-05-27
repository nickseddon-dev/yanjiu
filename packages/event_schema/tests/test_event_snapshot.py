"""Tests for event schemas."""
from datetime import datetime, timezone
from event_schema.base import EventType, EventSnapshot
from event_schema.social import SocialSurgeEvent, SentimentShiftEvent
from event_schema.prediction_market import PolymarketJumpEvent
from event_schema.onchain import OnchainInflowEvent, WhaleAlertEvent


def test_event_snapshot_creation():
    evt = EventSnapshot(
        event_type=EventType.SOCIAL_SURGE,
        source="X",
        symbol="BTC",
        timestamp=datetime.now(timezone.utc),
        confidence=0.85,
        intensity=0.72,
        decay_window_h=6,
    )
    d = evt.to_dict()
    assert d["event_type"] == "SOCIAL_SURGE"
    assert d["confidence"] == 0.85
    restored = EventSnapshot.from_dict(d)
    assert restored.event_type == EventType.SOCIAL_SURGE


def test_social_surge_round_trip():
    evt = SocialSurgeEvent(
        symbol="BTC",
        source="X",
        mention_count=5000,
        mention_velocity=120.0,
        z_score=3.2,
        top_keywords=("bitcoin", "etf", "approval"),
        confidence=0.85,
        intensity=0.72,
    )
    snap = evt.to_snapshot()
    restored = SocialSurgeEvent.from_snapshot(snap)
    assert restored.mention_count == 5000
    assert restored.z_score == 3.2


def test_polymarket_jump_round_trip():
    evt = PolymarketJumpEvent(
        symbol="BTC",
        market_question="Will BTC reach 100k by end of 2026?",
        prior_probability=0.3,
        current_probability=0.65,
        probability_delta=0.35,
        volume=50000.0,
        confidence=0.9,
        intensity=0.8,
    )
    snap = evt.to_snapshot()
    restored = PolymarketJumpEvent.from_snapshot(snap)
    assert restored.probability_delta == 0.35
    assert restored.current_probability == 0.65


def test_onchain_inflow_round_trip():
    evt = OnchainInflowEvent(
        symbol="ETH",
        inflow_amount=10000.0,
        inflow_usd=35000000.0,
        inflow_velocity=500.0,
        source_chain="Ethereum",
        wallet_count=150,
        confidence=0.8,
        intensity=0.65,
    )
    snap = evt.to_snapshot()
    restored = OnchainInflowEvent.from_snapshot(snap)
    assert restored.inflow_usd == 35000000.0
    assert restored.wallet_count == 150


def test_whale_alert_round_trip():
    evt = WhaleAlertEvent(
        symbol="BTC",
        transaction_hash="0xabc123",
        from_address="0xwallet1",
        to_address="0xexchange",
        amount=2000.0,
        amount_usd=140000000.0,
        transaction_type="EXCHANGE",
        confidence=0.95,
        intensity=0.9,
    )
    snap = evt.to_snapshot()
    restored = WhaleAlertEvent.from_snapshot(snap)
    assert restored.amount_usd == 140000000.0
    assert restored.transaction_type == "EXCHANGE"
