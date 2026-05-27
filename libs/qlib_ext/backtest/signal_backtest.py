"""Signal-driven backtesting engine for crypto trading strategies."""

from dataclasses import dataclass, field
from typing import Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BacktestMetrics:
    """Results from a backtest run.

    Attributes:
        sharpe: Annualized Sharpe ratio.
        max_drawdown: Maximum drawdown (0-1).
        win_rate: Win rate (0-1).
        total_pnl: Total profit/loss.
        total_return: Total return percentage.
        num_trades: Total number of trades.
    """
    sharpe: float
    max_drawdown: float
    win_rate: float
    total_pnl: float
    total_return: float
    num_trades: int


@dataclass
class SignalDrivenBacktest:
    """Signal-driven backtester for crypto trading strategies.

    Runs a backtest given historical price data and trading signals,
    computing performance metrics including Sharpe ratio, max drawdown,
    win rate, and total PnL.

    Attributes:
        prices: List of historical prices.
        signals: List of trading signals (-1, 0, 1 for sell/hold/buy).
        initial_capital: Starting capital in USD.
        commission_rate: Commission rate per trade (e.g., 0.001 for 0.1%).
    """
    prices: list[float]
    signals: list[int]
    initial_capital: float = 10_000.0
    commission_rate: float = 0.001
    _equity_curve: list[float] = field(default_factory=list, init=False, repr=False)
    _trades: list[tuple[int, float, float, float]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate inputs."""
        if len(self.prices) != len(self.signals):
            raise ValueError("prices and signals must have same length")
        if not self.prices:
            raise ValueError("prices cannot be empty")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not all(s in (-1, 0, 1) for s in self.signals):
            raise ValueError("signals must be -1 (sell), 0 (hold), or 1 (buy)")

    def run(self) -> list[float]:
        """Run the backtest simulation.

        Returns:
            Equity curve as list of portfolio values.
        """
        logger.info("Starting backtest with %d bars", len(self.prices))
        self._equity_curve = [self.initial_capital]
        self._trades = []

        position = 0
        entry_price = 0.0
        capital = self.initial_capital

        for i in range(len(self.prices)):
            price = self.prices[i]
            signal = self.signals[i]

            # Entry logic
            if signal == 1 and position == 0:
                shares = capital / price
                cost = capital * self.commission_rate
                position = shares
                entry_price = price
                capital = capital - cost - (shares * price)
                self._trades.append((i, price, 1, shares))
                logger.debug("Entry: bar=%d price=%.4f shares=%.4f", i, price, shares)

            # Exit logic
            elif signal == -1 and position > 0:
                proceeds = position * price
                cost = proceeds * self.commission_rate
                capital = capital + proceeds - cost
                pnl = proceeds - (position * entry_price) - cost
                self._trades.append((i, price, -1, position))
                logger.debug("Exit: bar=%d price=%.4f pnl=%.4f", i, price, pnl)
                position = 0
                entry_price = 0.0

            # Track equity
            portfolio_value = capital + (position * price)
            self._equity_curve.append(portfolio_value)

        # Close any remaining position at final price
        if position > 0:
            final_price = self.prices[-1]
            proceeds = position * final_price
            cost = proceeds * self.commission_rate
            capital = capital + proceeds - cost
            self._trades.append((len(self.prices) - 1, final_price, -1, position))
            position = 0
            logger.info("Closed remaining position at final price %.4f", final_price)

        self._equity_curve[-1] = capital
        logger.info("Backtest complete. Final equity: %.2f", self._equity_curve[-1])
        return self._equity_curve

    def compute_metrics(self) -> BacktestMetrics:
        """Compute performance metrics from the backtest.

        Returns:
            BacktestMetrics with Sharpe, max drawdown, win rate, PnL, and return.
        """
        if len(self._equity_curve) < 2:
            raise RuntimeError("Run backtest first by calling run()")

        equity = np.array(self._equity_curve)
        returns = np.diff(equity) / equity[:-1]

        # Sharpe ratio (annualized, assuming 365 periods/day-like sampling)
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(365)
        else:
            sharpe = 0.0

        # Max drawdown
        cummax = np.maximum.accumulate(equity)
        drawdowns = (equity - cummax) / cummax
        max_drawdown = abs(np.min(drawdowns))

        # Win rate
        winning_trades = sum(1 for t in self._trades if len(t) >= 3 and t[2] == -1 and (t[1] - t[1]) > 0)
        total_closed_trades = sum(1 for t in self._trades if t[2] == -1)
        win_rate = winning_trades / total_closed_trades if total_closed_trades > 0 else 0.0

        # Total PnL and return
        total_pnl = equity[-1] - self.initial_capital
        total_return = (total_pnl / self.initial_capital) * 100

        logger.info(
            "Metrics: sharpe=%.4f max_dd=%.4f win_rate=%.4f pnl=%.2f return=%.2f%%",
            sharpe, max_drawdown, win_rate, total_pnl, total_return,
        )

        return BacktestMetrics(
            sharpe=round(float(sharpe), 4),
            max_drawdown=round(float(max_drawdown), 4),
            win_rate=round(float(win_rate), 4),
            total_pnl=round(float(total_pnl), 4),
            total_return=round(float(total_return), 4),
            num_trades=len([t for t in self._trades if t[2] == 1]),
        )