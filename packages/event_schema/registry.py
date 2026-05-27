"""Event registry - maps event types to schema classes."""
from event_schema.base import EventType, EventSnapshot, EventABC
from typing import Type, Dict


class EventRegistry:
    """Maps event_type strings to concrete event classes."""

    _registry: Dict[EventType, Type[EventABC]] = {}

    @classmethod
    def register(cls, event_type: EventType, cls_: Type[EventABC]) -> None:
        """Register an event class for an event type."""
        cls._registry[event_type] = cls_

    @classmethod
    def resolve(cls, event_type: EventType) -> Type[EventABC]:
        """Resolve event type to class. Raises KeyError if unknown."""
        if event_type not in cls._registry:
            raise KeyError(f"No event class registered for {event_type.value}")
        return cls._registry[event_type]

    @classmethod
    def list_registered(cls) -> Dict[EventType, Type[EventABC]]:
        """List all registered event types."""
        return dict(cls._registry)


from event_schema.social import SocialSurgeEvent, SentimentShiftEvent
from event_schema.prediction_market import PolymarketJumpEvent, PolymarketResolutionEvent
from event_schema.onchain import OnchainInflowEvent, WhaleAlertEvent

EventRegistry.register(EventType.SOCIAL_SURGE, SocialSurgeEvent)
EventRegistry.register(EventType.SENTIMENT_SHIFT, SentimentShiftEvent)
EventRegistry.register(EventType.POLYMARKET_JUMP, PolymarketJumpEvent)
EventRegistry.register(EventType.POLYMARKET_RESOLUTION, PolymarketResolutionEvent)
EventRegistry.register(EventType.ONCHAIN_INFLOW, OnchainInflowEvent)
EventRegistry.register(EventType.WHALE_ALERT, WhaleAlertEvent)
