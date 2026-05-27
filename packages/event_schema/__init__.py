"""Event schema package - event types and snapshots."""
from event_schema.base import EventType, EventSnapshot, EventABC
from event_schema.social import SocialSurgeEvent, SentimentShiftEvent
from event_schema.prediction_market import PolymarketJumpEvent, PolymarketResolutionEvent
from event_schema.onchain import OnchainInflowEvent, WhaleAlertEvent
from event_schema.registry import EventRegistry

__all__ = [
    "EventType", "EventSnapshot", "EventABC",
    "SocialSurgeEvent", "SentimentShiftEvent",
    "PolymarketJumpEvent", "PolymarketResolutionEvent",
    "OnchainInflowEvent", "WhaleAlertEvent",
    "EventRegistry",
]
