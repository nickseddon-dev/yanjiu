
"""
NautilusTrader Signal Adapter
Fork of: https://github.com.nautechsystems/nautilus_trader
Custom adapters for signal consumption and order execution.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field
import uuid

logger = logging.getLogger("nautilus_ext")


@dataclass
class SignalOrder:
    """A signal-driven order for NautilusTrader."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    direction: str = ""  # LONG or SHORT
    order_type: str = "MARKET"
    size: float = 0.0
    price: Optional[float] = None
    metadata: dict = field(default_factory=dict)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Re-export from submodules for public API
from libs.nautilus_ext.adapters.order_adapter import (
    OrderExecutionAdapter,
    OrderResult,
    OrderStatus,
)
from libs.nautilus_ext.execution_serializer import (
    ExecutionSerializer,
    OrderSide,
    OrderType,
    NautilusOrderSpec,
)
from libs.nautilus_ext.position_tracker import (
    PositionTracker,
    Position,
    PortfolioSummary,
)
from libs.nautilus_ext.risk_checker import (
    RiskChecker,
    RiskCheckResponse,
)


class SignalConsumer:
    """
    Consumes signals from SignalBridge (research host) and executes via NautilusTrader.
    Acts as the LIVE HOST consumer counterpart to the research host SignalBridge.
    """

    def __init__(self, listen_url: str = "http://0.0.0.0:8090"):
        self.listen_url = listen_url
        self._running = False
        self._signal_cache: dict = {}  # signal_id -> signal

    def start(self) -> None:
        """Start the signal consumer."""
        self._running = True
        logger.info(f"SignalConsumer started, listening on {self.listen_url}")

    def stop(self) -> None:
        """Stop the signal consumer."""
        self._running = False
        logger.info("SignalConsumer stopped")

    def process_signal(self, signal_data: dict) -> SignalOrder:
        """
        Process a raw signal dict into a SignalOrder.
        Called when SignalBridge delivers a signal to the live host.
        """
        order = SignalOrder(
            signal_id=signal_data.get("signal_id", str(uuid.uuid4())),
            symbol=signal_data.get("symbol", ""),
            direction=signal_data.get("direction", ""),
            size=signal_data.get("size_usd", 0.0),
            price=signal_data.get("entry_price"),
            metadata=signal_data.get("metadata", {}),
        )
        self._signal_cache[order.signal_id] = order
        logger.info(f"Processed signal {order.signal_id}: {order.symbol} {order.direction}")
        return order

    def acknowledge_signal(self, signal_id: str, status: str, detail: str = "") -> dict:
        """Acknowledge receipt of a signal back to SignalBridge."""
        ack = {
            "signal_id": signal_id,
            "status": status,  # ACKNOWLEDGED, REJECTED, EXECUTED
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"ACK {signal_id}: {status}")
        return ack

    def get_cache_size(self) -> int:
        return len(self._signal_cache)
