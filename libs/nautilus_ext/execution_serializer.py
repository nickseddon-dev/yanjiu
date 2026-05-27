"""
Execution serializer - converts common_schema Signal to Nautilus order specs.
"""
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from common_schema.signal import Signal, EntryDecision

logger = logging.getLogger("nautilus_ext")


class OrderSide(Enum):
    """Order side enum compatible with NautilusTrader."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type enum compatible with NautilusTrader."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass
class NautilusOrderSpec:
    """A ready-to-submit order specification for NautilusTrader."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    client_order_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "client_order_id": self.client_order_id,
        }


class ExecutionSerializer:
    """
    Serializes Signal objects into NautilusTrader order specifications.
    
    Converts from common_schema.signal.Signal to Nautilus order specs
    (OrderSide, OrderType, Quantity, Price).
    """

    def __init__(self, default_market_order: bool = True):
        """
        Initialize the serializer.
        
        Args:
            default_market_order: If True, use MARKET orders by default.
                                  If False, prefer LIMIT orders when price available.
        """
        self._default_market_order = default_market_order
        logger.info(f"ExecutionSerializer initialized (market_order_default={default_market_order})")

    def signal_to_order_spec(
        self,
        signal: Signal,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
    ) -> Optional[NautilusOrderSpec]:
        """
        Convert a Signal to a NautilusOrderSpec.
        
        Args:
            signal: The Signal to convert
            quantity: Override quantity (uses signal target_position_pct if None)
            price: Override price (uses signal-based calculation if None)
            
        Returns:
            NautilusOrderSpec or None if signal should not be executed
        """
        # Check if signal should be executed based on entry_mode
        if signal.entry_mode == EntryDecision.NO_TRADE:
            logger.debug(f"Signal {signal.signal_id}: NO_TRADE, skipping")
            return None
        
        # Convert side
        try:
            order_side = OrderSide.BUY if signal.side.upper() == "BUY" else OrderSide.SELL
        except ValueError:
            logger.error(f"Invalid side in signal {signal.signal_id}: {signal.side}")
            return None
        
        # Determine order type
        order_type = self._determine_order_type(signal, price)
        
        # Determine quantity
        final_quantity = quantity if quantity is not None else signal.target_position_pct
        if final_quantity <= 0:
            logger.warning(f"Invalid quantity {final_quantity} for signal {signal.signal_id}")
            return None
        
        # Determine price (required for LIMIT orders)
        final_price = price
        if order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and final_price is None:
            logger.warning(f"Limit order requires price, signal {signal.signal_id}")
            # Fall back to market order
            order_type = OrderType.MARKET
        
        spec = NautilusOrderSpec(
            symbol=signal.symbol,
            side=order_side,
            order_type=order_type,
            quantity=final_quantity,
            price=final_price,
            client_order_id=signal.signal_id,
        )
        
        logger.info(
            f"Serialized signal {signal.signal_id} -> "
            f"{order_side.value} {final_quantity} {signal.symbol} {order_type.value}"
            + (f" @ {final_price}" if final_price else "")
        )
        return spec

    def _determine_order_type(
        self,
        signal: Signal,
        price: Optional[float],
    ) -> OrderType:
        """
        Determine the appropriate order type based on signal and price.
        
        Args:
            signal: The signal being processed
            price: Explicit price override if provided
            
        Returns:
            OrderType to use
        """
        # If price is explicitly provided and non-None, use LIMIT
        if price is not None:
            return OrderType.LIMIT
        
        # If signal has entry_price metadata, use LIMIT
        entry_price = signal.risk_tags  # Could check metadata for price
        # For now, check if any tag looks like a price constraint
        
        # Default based on serializer configuration
        if self._default_market_order:
            return OrderType.MARKET
        
        # If not defaulting to market, require price for limit
        return OrderType.MARKET

    def serialize_order(
        self,
        signal: Signal,
        quantity: float,
        price: Optional[float] = None,
    ) -> Tuple[Optional[str], Optional[dict]]:
        """
        Serialize a Signal to order submission dict for NautilusTrader.
        
        Returns tuple of (order_type_str, order_params_dict) or (None, None).
        
        Args:
            signal: The Signal to serialize
            quantity: Order quantity
            price: Limit price (optional)
            
        Returns:
            Tuple of (order_type, params_dict) ready for Nautilus submission
        """
        spec = self.signal_to_order_spec(signal, quantity, price)
        if spec is None:
            return None, None
        
        params = {
            "symbol": spec.symbol,
            "side": spec.side.value,
            "quantity": spec.quantity,
            "client_order_id": spec.client_order_id,
        }
        
        if spec.order_type == OrderType.MARKET:
            return "MARKET", params
        elif spec.order_type == OrderType.LIMIT:
            params["price"] = spec.price
            return "LIMIT", params
        elif spec.order_type == OrderType.STOP_MARKET:
            params["trigger_price"] = spec.price
            return "STOP_MARKET", params
        elif spec.order_type == OrderType.STOP_LIMIT:
            params["price"] = spec.price
            params["trigger_price"] = spec.price
            return "STOP_LIMIT", params
        
        return None, None

    def get_order_side(self, side_str: str) -> Optional[OrderSide]:
        """
        Convert string side to OrderSide enum.
        
        Args:
            side_str: Side string ("BUY", "SELL", etc.)
            
        Returns:
            OrderSide or None if invalid
        """
        try:
            return OrderSide(side_str.upper())
        except ValueError:
            logger.error(f"Invalid side string: {side_str}")
            return None

    def get_order_type(self, type_str: str) -> Optional[OrderType]:
        """
        Convert string order type to OrderType enum.
        
        Args:
            type_str: Order type string ("MARKET", "LIMIT", etc.)
            
        Returns:
            OrderType or None if invalid
        """
        try:
            return OrderType(type_str.upper())
        except ValueError:
            logger.error(f"Invalid order type string: {type_str}")
            return None
