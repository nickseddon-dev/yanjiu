"""
Order execution adapter for NautilusTrader.
Wraps NautilusTrader order methods for signal-driven execution.
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger("nautilus_ext")


@dataclass
class OrderResult:
    """Result of an order submission attempt."""
    order_id: str
    success: bool
    message: str = ""
    submitted_price: Optional[float] = None
    submitted_quantity: Optional[float] = None


@dataclass
class OrderStatus:
    """Current status of an order."""
    order_id: str
    status: str  # PENDING, SUBMITTED, FILLED, PARTIALLY_FILLED, CANCELLED, REJECTED
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    leaves_qty: float = 0.0


class OrderExecutionAdapter:
    """
    Adapter providing NautilusTrader order execution methods.
    
    This adapter wraps the core NautilusTrader execution interface:
    - submit_market_order
    - submit_limit_order
    - cancel_order
    - get_order_status
    
    In production, these delegate to the NautilusTrader ExecutionGateway.
    For testing/development, they can use mock clients.
    """

    def __init__(self, client: Optional[Any] = None):
        """
        Initialize the adapter.
        
        Args:
            client: NautilusTrader client instance. If None, uses internal mock.
        """
        self._client = client
        self._orders: Dict[str, Dict[str, Any]] = {}
        logger.info("OrderExecutionAdapter initialized")

    def submit_market_order(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        quantity: float,
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit a market order to NautilusTrader.
        
        Args:
            symbol: Trading symbol (e.g., "BTC-USDT")
            side: Order side ("BUY" or "SELL")
            quantity: Order quantity
            client_order_id: Optional client-provided order ID
            
        Returns:
            OrderResult with order_id and success status
        """
        order_id = client_order_id or self._generate_order_id()
        logger.info(
            f"Submitting MARKET order: {side} {quantity} {symbol} [id={order_id}]"
        )
        
        if self._client is not None:
            try:
                # Delegate to real NautilusTrader client
                result = self._client.submit_market_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    client_order_id=order_id,
                )
                self._orders[order_id] = {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "order_type": "MARKET",
                    "status": "SUBMITTED",
                }
                return OrderResult(order_id=order_id, success=True, message="Submitted")
            except Exception as e:
                logger.error(f"Market order failed: {e}")
                return OrderResult(order_id=order_id, success=False, message=str(e))
        
        # Mock mode for testing
        self._orders[order_id] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "MARKET",
            "status": "SUBMITTED",
        }
        return OrderResult(order_id=order_id, success=True, message="Mock: Submitted")

    def submit_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit a limit order to NautilusTrader.
        
        Args:
            symbol: Trading symbol
            side: Order side ("BUY" or "SELL")
            quantity: Order quantity
            price: Limit price
            client_order_id: Optional client-provided order ID
            
        Returns:
            OrderResult with order_id and success status
        """
        order_id = client_order_id or self._generate_order_id()
        logger.info(
            f"Submitting LIMIT order: {side} {quantity} {symbol} @ {price} [id={order_id}]"
        )
        
        if self._client is not None:
            try:
                result = self._client.submit_limit_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    client_order_id=order_id,
                )
                self._orders[order_id] = {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                    "order_type": "LIMIT",
                    "status": "SUBMITTED",
                }
                return OrderResult(
                    order_id=order_id,
                    success=True,
                    message="Submitted",
                    submitted_price=price,
                    submitted_quantity=quantity,
                )
            except Exception as e:
                logger.error(f"Limit order failed: {e}")
                return OrderResult(order_id=order_id, success=False, message=str(e))
        
        # Mock mode
        self._orders[order_id] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "order_type": "LIMIT",
            "status": "SUBMITTED",
        }
        return OrderResult(
            order_id=order_id,
            success=True,
            message="Mock: Submitted",
            submitted_price=price,
            submitted_quantity=quantity,
        )

    def cancel_order(self, order_id: str) -> OrderResult:
        """
        Cancel an existing order.
        
        Args:
            order_id: The order ID to cancel
            
        Returns:
            OrderResult indicating success/failure
        """
        logger.info(f"Canceling order: {order_id}")
        
        if order_id not in self._orders:
            return OrderResult(
                order_id=order_id,
                success=False,
                message=f"Order {order_id} not found",
            )
        
        if self._client is not None:
            try:
                self._client.cancel_order(order_id)
                self._orders[order_id]["status"] = "CANCELLED"
                return OrderResult(order_id=order_id, success=True, message="Cancelled")
            except Exception as e:
                logger.error(f"Cancel order failed: {e}")
                return OrderResult(order_id=order_id, success=False, message=str(e))
        
        # Mock mode
        self._orders[order_id]["status"] = "CANCELLED"
        return OrderResult(order_id=order_id, success=True, message="Mock: Cancelled")

    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        Get the current status of an order.
        
        Args:
            order_id: The order ID to query
            
        Returns:
            OrderStatus object or None if not found
        """
        if order_id not in self._orders:
            logger.warning(f"Order not found: {order_id}")
            return None
        
        order_data = self._orders[order_id]
        
        if self._client is not None:
            try:
                status_data = self._client.get_order_status(order_id)
                return OrderStatus(
                    order_id=order_id,
                    status=status_data.get("status", "UNKNOWN"),
                    filled_qty=status_data.get("filled_qty", 0.0),
                    avg_fill_price=status_data.get("avg_fill_price", 0.0),
                    leaves_qty=status_data.get("leaves_qty", 0.0),
                )
            except Exception as e:
                logger.error(f"Get order status failed: {e}")
                return None
        
        # Mock mode
        return OrderStatus(
            order_id=order_id,
            status=order_data.get("status", "UNKNOWN"),
            filled_qty=order_data.get("filled_qty", 0.0),
            avg_fill_price=order_data.get("avg_fill_price", 0.0),
            leaves_qty=order_data.get("leaves_qty", order_data.get("quantity", 0.0)),
        )

    def _generate_order_id(self) -> str:
        """Generate a unique order ID."""
        import uuid
        return f"ord_{uuid.uuid4().hex[:12]}"

    def get_open_orders(self) -> Dict[str, Dict[str, Any]]:
        """Return all open (non-terminal) orders."""
        terminal_statuses = {"FILLED", "CANCELLED", "REJECTED", "EXPIRED"}
        return {
            oid: data
            for oid, data in self._orders.items()
            if data.get("status") not in terminal_statuses
        }

    def get_order_count(self) -> int:
        """Return total number of tracked orders."""
        return len(self._orders)
