"""
Risk checker - pre-trade checks using risk_rules engine.

Provides pre-trade risk validation including:
- Position limits
- Exposure limits
- Drawdown checks
"""
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from common_schema.signal import Signal
from packages.risk_rules.base import RiskCheckResult, RiskVerdict, RiskDimension
from packages.risk_rules.engine import RiskEngine
from packages.risk_rules.position import SingleSymbolLimit, SingleNarrativeLimit
from packages.risk_rules.portfolio import PortfolioVaRLimit, MaxDrawdownLimit

logger = logging.getLogger("nautilus_ext")


@dataclass
class RiskCheckResponse:
    """Response from a pre-trade risk check."""
    approved: bool
    signal_id: str
    violations: List[RiskCheckResult] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "signal_id": self.signal_id,
            "message": self.message,
            "violations": [v.to_dict() for v in self.violations],
        }


class RiskChecker:
    """
    Pre-trade risk checker using the risk_rules engine.
    
    Validates signals against portfolio state before order execution.
    Uses RiskEngine to run configured risk rules.
    """

    def __init__(
        self,
        max_position_pct: float = 0.2,
        max_narrative_pct: float = 0.3,
        max_venue_pct: float = 0.4,
        max_var_pct: float = 0.02,
        max_drawdown_pct: float = 0.05,
    ):
        """
        Initialize RiskChecker with default limits.
        
        Args:
            max_position_pct: Max position size as % of portfolio (default 20%)
            max_narrative_pct: Max narrative exposure % (default 30%)
            max_venue_pct: Max venue exposure % (default 40%)
            max_var_pct: Max portfolio VaR % (default 2%)
            max_drawdown_pct: Max drawdown % (default 5%)
        """
        self._max_position_pct = max_position_pct
        self._max_narrative_pct = max_narrative_pct
        self._max_venue_pct = max_venue_pct
        self._max_var_pct = max_var_pct
        self._max_drawdown_pct = max_drawdown_pct
        
        # Initialize risk engine with rules
        self._engine = RiskEngine()
        self._setup_rules()
        
        logger.info(
            f"RiskChecker initialized: position<{max_position_pct:.0%}, "
            f"narrative<{max_narrative_pct:.0%}, var<{max_var_pct:.0%}, "
            f"drawdown<{max_drawdown_pct:.0%}"
        )

    def _setup_rules(self) -> None:
        """Configure risk rules in the engine."""
        self._engine.add_rule(SingleSymbolLimit(max_position_pct=self._max_position_pct))
        self._engine.add_rule(SingleNarrativeLimit(max_narrative_pct=self._max_narrative_pct))
        self._engine.add_rule(PortfolioVaRLimit(max_var_pct=self._max_var_pct))
        self._engine.add_rule(MaxDrawdownLimit(max_drawdown_pct=self._max_drawdown_pct))

    def pre_trade_check(
        self,
        signal: Signal,
        portfolio_state: Dict[str, Any],
    ) -> RiskCheckResponse:
        """
        Run pre-trade risk checks for a signal.
        
        Args:
            signal: The Signal to validate
            portfolio_state: Current portfolio state dict containing:
                - total_value: float
                - positions: dict (symbol -> {market_value, quantity})
                - narrative_exposure: dict (narrative -> value)
                - venue_exposure: dict (venue -> value)
                - portfolio_var_pct: float
                - current_drawdown_pct: float
                
        Returns:
            RiskCheckResponse with approval status and any violations
        """
        # Build state dict for risk engine
        state = self._build_state(signal, portfolio_state)
        
        # Evaluate all rules
        results = self._engine.evaluate(state)
        
        # Separate violations
        violations = [r for r in results if r.verdict == RiskVerdict.VIOLATION]
        
        if violations:
            violation_msgs = [v.detail for v in violations]
            logger.warning(
                f"Signal {signal.signal_id} REJECTED: {len(violations)} violations - "
                f"{violation_msgs}"
            )
            return RiskCheckResponse(
                approved=False,
                signal_id=signal.signal_id,
                violations=violations,
                message=f"Rejected: {'; '.join(violation_msgs)}",
            )
        
        logger.info(f"Signal {signal.signal_id} approved by risk checks")
        return RiskCheckResponse(
            approved=True,
            signal_id=signal.signal_id,
            violations=[],
            message="Approved",
        )

    def check_position_limit(
        self,
        symbol: str,
        proposed_quantity: float,
        current_positions: Dict[str, Dict[str, float]],
        total_value: float,
    ) -> bool:
        """
        Check if a proposed position would exceed position limits.
        
        Args:
            symbol: Trading symbol
            proposed_quantity: Proposed new quantity
            current_positions: Current positions dict
            total_value: Total portfolio value
            
        Returns:
            True if within limits, False otherwise
        """
        state = {
            "positions": current_positions.copy(),
            "total_value": total_value,
        }
        
        # Temporarily update state with proposed position
        proposed_value = proposed_quantity * current_positions.get(symbol, {}).get("price", 0)
        if symbol in state["positions"]:
            state["positions"][symbol]["quantity"] = proposed_quantity
        else:
            state["positions"][symbol] = {
                "quantity": proposed_quantity,
                "market_value": proposed_value,
            }
        
        rule = SingleSymbolLimit(max_position_pct=self._max_position_pct)
        result = rule.check(state)
        
        return result.verdict != RiskVerdict.VIOLATION

    def check_exposure_limit(
        self,
        exposure_type: str,
        proposed_exposure: float,
        total_value: float,
    ) -> bool:
        """
        Check if proposed exposure would exceed exposure limits.
        
        Args:
            exposure_type: Type of exposure ("narrative" or "venue")
            proposed_exposure: Proposed exposure value
            total_value: Total portfolio value
            
        Returns:
            True if within limits, False otherwise
        """
        if total_value <= 0:
            return True
        
        pct = abs(proposed_exposure) / total_value
        limit = self._max_narrative_pct if exposure_type == "narrative" else self._max_venue_pct
        
        return pct <= limit

    def check_drawdown(self, current_drawdown_pct: float) -> bool:
        """
        Check if current drawdown is within allowed limits.
        
        Args:
            current_drawdown_pct: Current drawdown as decimal (e.g., 0.03 for 3%)
            
        Returns:
            True if within limits, False otherwise
        """
        return current_drawdown_pct <= self._max_drawdown_pct

    def get_available_position_capacity(
        self,
        symbol: str,
        current_positions: Dict[str, Dict[str, float]],
        total_value: float,
    ) -> float:
        """
        Calculate available position capacity for a symbol.
        
        Args:
            symbol: Trading symbol
            current_positions: Current positions dict
            total_value: Total portfolio value
            
        Returns:
            Maximum quantity that can be traded while staying within limits
        """
        current_pos = current_positions.get(symbol, {})
        current_qty = current_pos.get("quantity", 0.0)
        current_mkt_val = current_pos.get("market_value", 0.0)
        
        max_position_value = total_value * self._max_position_pct
        available = max_position_value - abs(current_mkt_val)
        
        return max(0.0, available)

    def evaluate_portfolio_state(self, state: Dict[str, Any]) -> List[RiskCheckResult]:
        """
        Evaluate all risk rules against a portfolio state.
        
        Args:
            state: Portfolio state dict
            
        Returns:
            List of RiskCheckResult for all rules
        """
        return self._engine.evaluate(state)

    def _build_state(
        self,
        signal: Signal,
        portfolio_state: Dict[str, Any],
    ) -> dict:
        """
        Build state dict for risk engine from signal and portfolio state.
        
        Args:
            signal: The signal being evaluated
            portfolio_state: Current portfolio state
            
        Returns:
            Combined state dict for risk engine
        """
        # Start with provided portfolio state
        state = portfolio_state.copy()
        
        # Add signal metadata to state
        state["signal_id"] = signal.signal_id
        state["signal_symbol"] = signal.symbol
        state["signal_side"] = signal.side
        state["signal_strength"] = signal.signal_strength
        
        return state

    def get_limits(self) -> Dict[str, float]:
        """Get current risk limits."""
        return {
            "max_position_pct": self._max_position_pct,
            "max_narrative_pct": self._max_narrative_pct,
            "max_venue_pct": self._max_venue_pct,
            "max_var_pct": self._max_var_pct,
            "max_drawdown_pct": self._max_drawdown_pct,
        }

    def set_limits(
        self,
        max_position_pct: Optional[float] = None,
        max_narrative_pct: Optional[float] = None,
        max_venue_pct: Optional[float] = None,
        max_var_pct: Optional[float] = None,
        max_drawdown_pct: Optional[float] = None,
    ) -> None:
        """Update risk limits and reconfigure rules."""
        if max_position_pct is not None:
            self._max_position_pct = max_position_pct
        if max_narrative_pct is not None:
            self._max_narrative_pct = max_narrative_pct
        if max_venue_pct is not None:
            self._max_venue_pct = max_venue_pct
        if max_var_pct is not None:
            self._max_var_pct = max_var_pct
        if max_drawdown_pct is not None:
            self._max_drawdown_pct = max_drawdown_pct
        
        # Rebuild rules with new limits
        self._engine = RiskEngine()
        self._setup_rules()
        
        logger.info(f"RiskChecker limits updated: {self.get_limits()}")
