"""
Position tracker - tracks open positions, realized/unrealized PnL, position size.
"""
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger("nautilus_ext")


@dataclass
class Position:
    """Represents a position in a single symbol."""
    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trade_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def market_value(self) -> float:
        """Estimated market value of position."""
        return self.quantity * self.avg_entry_price
    
    @property
    def is_long(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        return self.quantity < 0
    
    @property
    def is_flat(self) -> bool:
        return self.quantity == 0.0
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "trade_count": self.trade_count,
            "last_updated": self.last_updated.isoformat(),
            "market_value": self.market_value,
            "is_long": self.is_long,
            "is_short": self.is_short,
            "is_flat": self.is_flat,
        }


@dataclass
class PortfolioSummary:
    """Summary of entire portfolio state."""
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_market_value: float = 0.0
    position_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def total_pnl(self) -> float:
        return self.total_realized_pnl + self.total_unrealized_pnl
    
    def to_dict(self) -> dict:
        return {
            "total_realized_pnl": self.total_realized_pnl,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_pnl": self.total_pnl,
            "total_market_value": self.total_market_value,
            "position_count": self.position_count,
            "timestamp": self.timestamp.isoformat(),
        }


class PositionTracker:
    """
    Tracks open positions, realized/unrealized PnL, and position sizes per symbol.
    
    Provides a simple in-memory position tracking system suitable for
    integration with NautilusTrader execution events.
    """

    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._closed_positions: list = []  # History of closed positions
        self._total_realized_pnl: float = 0.0
        logger.info("PositionTracker initialized")

    def update_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str,  # BUY or SELL (from order side, not position direction)
    ) -> Position:
        """
        Update position based on a trade execution.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity traded
            price: Execution price
            side: Order side ("BUY" or "SELL")
            
        Returns:
            Updated Position object
        """
        if symbol not in self._positions:
            self._positions[symbol] = Position(symbol=symbol)
        
        pos = self._positions[symbol]
        pos.last_updated = datetime.now(timezone.utc)
        
        # Calculate quantity change based on side
        # BUY increases long or decreases short
        # SELL decreases long or increases short
        signed_qty = quantity if side.upper() == "BUY" else -quantity
        new_qty = pos.quantity + signed_qty
        
        # Calculate realized PnL for closing trades
        if (pos.quantity > 0 and signed_qty < 0) or (pos.quantity < 0 and signed_qty > 0):
            # Closing trade - calculate realized PnL
            closing_qty = min(abs(pos.quantity), abs(signed_qty))
            if pos.quantity > 0:
                # Closing long
                pos.realized_pnl += closing_qty * (price - pos.avg_entry_price)
            else:
                # Closing short  
                pos.realized_pnl += closing_qty * (pos.avg_entry_price - price)
            self._total_realized_pnl += pos.realized_pnl
        
        # Update average entry price for opening trades
        if new_qty != 0:
            old_abs_qty = abs(pos.quantity)
            new_abs_qty = abs(new_qty)
            if old_abs_qty == 0:
                pos.avg_entry_price = price
            elif (pos.quantity > 0 and new_qty > 0) or (pos.quantity < 0 and new_qty < 0):
                # Adding to existing position
                total_cost = pos.avg_entry_price * old_abs_qty + price * abs(signed_qty)
                pos.avg_entry_price = total_cost / new_abs_qty
        
        pos.quantity = new_qty
        pos.trade_count += 1
        
        logger.info(
            f"Position updated: {symbol} qty={pos.quantity} avg={pos.avg_entry_price:.4f} "
            f"realized_pnl={pos.realized_pnl:.2f}"
        )
        
        # Handle fully closed positions
        if pos.is_flat and pos.trade_count > 0:
            self._closed_positions.append(pos.to_dict())
            logger.info(f"Position closed: {symbol}, total realized PnL: {pos.realized_pnl:.2f}")
        
        return pos

    def update_unrealized_pnl(self, symbol: str, current_price: float) -> Optional[float]:
        """
        Update unrealized PnL for a position based on current market price.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            Updated unrealized PnL or None if position not found
        """
        if symbol not in self._positions:
            return None
        
        pos = self._positions[symbol]
        if pos.is_flat:
            pos.unrealized_pnl = 0.0
        elif pos.is_long:
            pos.unrealized_pnl = pos.quantity * (current_price - pos.avg_entry_price)
        else:  # short
            pos.unrealized_pnl = abs(pos.quantity) * (pos.avg_entry_price - current_price)
        
        return pos.unrealized_pnl

    def update_all_unrealized(self, prices: Dict[str, float]) -> None:
        """
        Update unrealized PnL for all positions using provided prices.
        
        Args:
            prices: Dict mapping symbol -> current price
        """
        for symbol, price in prices.items():
            self.update_unrealized_pnl(symbol, price)

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all open positions."""
        return self._positions.copy()

    def get_open_positions(self) -> Dict[str, Position]:
        """Get only non-flat positions."""
        return {s: p for s, p in self._positions.items() if not p.is_flat}

    def get_position_size(self, symbol: str) -> float:
        """Get position size (absolute quantity) for a symbol."""
        pos = self._positions.get(symbol)
        return abs(pos.quantity) if pos else 0.0

    def get_position_pct(self, symbol: str, total_value: float) -> float:
        """
        Get position as percentage of total portfolio value.
        
        Args:
            symbol: Trading symbol
            total_value: Total portfolio value for normalization
            
        Returns:
            Position percentage (0.0 to 1.0+)
        """
        if total_value <= 0:
            return 0.0
        pos = self._positions.get(symbol)
        if not pos:
            return 0.0
        return abs(pos.market_value) / total_value

    def get_realized_pnl(self, symbol: Optional[str] = None) -> float:
        """
        Get realized PnL for symbol or total portfolio.
        
        Args:
            symbol: Optional symbol to filter by. If None, returns total.
            
        Returns:
            Realized PnL amount
        """
        if symbol:
            pos = self._positions.get(symbol)
            return pos.realized_pnl if pos else 0.0
        return self._total_realized_pnl

    def get_unrealized_pnl(self, symbol: Optional[str] = None) -> float:
        """
        Get unrealized PnL for symbol or total portfolio.
        
        Args:
            symbol: Optional symbol to filter by. If None, returns total.
            
        Returns:
            Unrealized PnL amount
        """
        if symbol:
            pos = self._positions.get(symbol)
            return pos.unrealized_pnl if pos else 0.0
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_total_pnl(self) -> float:
        """Get total PnL (realized + unrealized) for entire portfolio."""
        return self._total_realized_pnl + self.get_unrealized_pnl()

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get summary of entire portfolio state."""
        return PortfolioSummary(
            total_realized_pnl=self._total_realized_pnl,
            total_unrealized_pnl=self.get_unrealized_pnl(),
            total_market_value=sum(p.market_value for p in self._positions.values()),
            position_count=len(self.get_open_positions()),
        )

    def get_closed_position_count(self) -> int:
        """Get count of fully closed positions in history."""
        return len(self._closed_positions)

    def reset(self) -> None:
        """Clear all positions and history. Use with caution."""
        self._positions.clear()
        self._closed_positions.clear()
        self._total_realized_pnl = 0.0
        logger.info("PositionTracker reset")
