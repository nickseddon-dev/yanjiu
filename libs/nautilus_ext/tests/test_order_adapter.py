"""
Tests for order_adapter module.
"""
import pytest
from libs.nautilus_ext.adapters.order_adapter import (
    OrderExecutionAdapter,
    OrderResult,
    OrderStatus,
)


class TestOrderExecutionAdapter:
    """Test cases for OrderExecutionAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = OrderExecutionAdapter()

    def test_initialization(self):
        """Test adapter initializes correctly."""
        assert self.adapter is not None
        assert self.adapter._client is None
        assert self.adapter.get_order_count() == 0

    def test_submit_market_order_buy(self):
        """Test submitting a BUY market order."""
        result = self.adapter.submit_market_order(
            symbol="BTC-USDT",
            side="BUY",
            quantity=0.1,
        )
        
        assert result.success is True
        assert result.order_id.startswith("ord_")
        assert result.message == "Mock: Submitted"

    def test_submit_market_order_sell(self):
        """Test submitting a SELL market order."""
        result = self.adapter.submit_market_order(
            symbol="ETH-USDT",
            side="SELL",
            quantity=1.0,
        )
        
        assert result.success is True
        assert result.order_id in self.adapter._orders

    def test_submit_limit_order(self):
        """Test submitting a LIMIT order."""
        result = self.adapter.submit_limit_order(
            symbol="BTC-USDT",
            side="BUY",
            quantity=0.05,
            price=50000.0,
        )
        
        assert result.success is True
        assert result.submitted_price == 50000.0
        assert result.submitted_quantity == 0.05
        assert self.adapter._orders[result.order_id]["order_type"] == "LIMIT"

    def test_submit_limit_order_with_client_id(self):
        """Test submitting a limit order with client order ID."""
        client_id = "my_custom_order_123"
        result = self.adapter.submit_limit_order(
            symbol="ETH-USDT",
            side="SELL",
            quantity=2.0,
            price=3000.0,
            client_order_id=client_id,
        )
        
        assert result.success is True
        assert result.order_id == client_id

    def test_cancel_order_success(self):
        """Test successfully cancelling an order."""
        # First submit an order
        submit_result = self.adapter.submit_market_order(
            symbol="BTC-USDT",
            side="BUY",
            quantity=0.1,
        )
        
        # Then cancel it
        cancel_result = self.adapter.cancel_order(submit_result.order_id)
        
        assert cancel_result.success is True
        assert self.adapter._orders[submit_result.order_id]["status"] == "CANCELLED"

    def test_cancel_order_not_found(self):
        """Test cancelling a non-existent order."""
        result = self.adapter.cancel_order("non_existent_order_id")
        
        assert result.success is False
        assert "not found" in result.message

    def test_get_order_status(self):
        """Test getting order status."""
        # Submit an order
        submit_result = self.adapter.submit_market_order(
            symbol="BTC-USDT",
            side="BUY",
            quantity=0.1,
        )
        
        # Get status
        status = self.adapter.get_order_status(submit_result.order_id)
        
        assert status is not None
        assert status.order_id == submit_result.order_id
        assert status.status == "SUBMITTED"

    def test_get_order_status_not_found(self):
        """Test getting status for non-existent order."""
        status = self.adapter.get_order_status("non_existent_id")
        assert status is None

    def test_get_open_orders(self):
        """Test getting open orders."""
        # Submit multiple orders
        self.adapter.submit_market_order("BTC-USDT", "BUY", 0.1)
        self.adapter.submit_market_order("ETH-USDT", "BUY", 1.0)
        
        open_orders = self.adapter.get_open_orders()
        
        assert len(open_orders) == 2

    def test_get_open_orders_after_cancel(self):
        """Test open orders excludes cancelled."""
        # Submit two orders
        order1 = self.adapter.submit_market_order("BTC-USDT", "BUY", 0.1)
        self.adapter.submit_market_order("ETH-USDT", "BUY", 1.0)
        
        # Cancel one
        self.adapter.cancel_order(order1.order_id)
        
        open_orders = self.adapter.get_open_orders()
        
        assert len(open_orders) == 1
        assert order1.order_id not in open_orders

    def test_order_result_dataclass(self):
        """Test OrderResult dataclass fields."""
        result = OrderResult(
            order_id="test_123",
            success=True,
            message="Test message",
            submitted_price=100.0,
            submitted_quantity=1.0,
        )
        
        assert result.order_id == "test_123"
        assert result.success is True
        assert result.message == "Test message"
        assert result.submitted_price == 100.0
        assert result.submitted_quantity == 1.0

    def test_order_status_dataclass(self):
        """Test OrderStatus dataclass fields."""
        status = OrderStatus(
            order_id="test_456",
            status="FILLED",
            filled_qty=1.0,
            avg_fill_price=100.0,
            leaves_qty=0.0,
        )
        
        assert status.order_id == "test_456"
        assert status.status == "FILLED"
        assert status.filled_qty == 1.0
        assert status.avg_fill_price == 100.0
        assert status.leaves_qty == 0.0


class TestOrderExecutionAdapterMockClient:
    """Test OrderExecutionAdapter with a mock client."""

    def test_adapter_with_mock_client_set_to_none(self):
        """Test adapter behavior when client is explicitly None."""
        adapter = OrderExecutionAdapter(client=None)
        
        result = adapter.submit_market_order("BTC-USDT", "BUY", 0.1)
        
        assert result.success is True
        assert "Mock" in result.message
