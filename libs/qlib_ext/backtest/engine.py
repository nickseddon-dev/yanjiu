"""Backtest engine orchestrating historical data and backtest execution."""

from dataclasses import dataclass
from typing import Optional, Protocol, Callable
import logging

logger = logging.getLogger(__name__)


class DataFetcher(Protocol):
    """Protocol for fetching historical price data."""

    def fetch(self, symbol: str, start: str, end: str) -> list[float]:
        """Fetch historical prices for a symbol.

        Args:
            symbol: Trading pair symbol.
            start: Start date (ISO format).
            end: End date (ISO format).

        Returns:
            List of historical prices.
        """
        ...


@dataclass
class BacktestConfig:
    """Configuration for a backtest run.

    Attributes:
        symbol: Trading pair symbol.
        start_date: Start date (ISO format).
        end_date: End date (ISO format).
        initial_capital: Starting capital in USD.
        commission_rate: Commission rate per trade.
        data_fetcher: Optional data fetcher to use.
    """
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 10_000.0
    commission_rate: float = 0.001
    data_fetcher: Optional[DataFetcher] = None


@dataclass
class BacktestResult:
    """Result from a backtest engine run.

    Attributes:
        symbol: Trading pair symbol.
        equity_curve: Portfolio value over time.
        final_value: Final portfolio value.
        backtest_metrics: Computed backtest metrics.
    """
    symbol: str
    equity_curve: list[float]
    final_value: float
    metrics: "BacktestMetrics"


class BacktestEngine:
    """Orchestrates historical data fetching and backtest execution.

    The BacktestEngine ties together a data fetcher (e.g., exchange adapter)
    with the SignalDrivenBacktest to run full backtests from configuration.

    Attributes:
        config: Backtest configuration.
    """

    def __init__(self, config: BacktestConfig) -> None:
        """Initialize engine with configuration.

        Args:
            config: Backtest configuration.
        """
        self.config = config
        logger.info(
            "BacktestEngine initialized for %s (%s to %s)",
            config.symbol, config.start_date, config.end_date,
        )

    def run(
        self,
        signals: list[int],
        prices: Optional[list[float]] = None,
    ) -> BacktestResult:
        """Run backtest with signals and optional prices.

        Args:
            signals: Trading signals (-1 sell, 0 hold, 1 buy).
            prices: Optional price list. If None, fetches using config data_fetcher.

        Returns:
            BacktestResult with equity curve and metrics.
        """
        # Fetch prices if not provided
        if prices is None:
            if self.config.data_fetcher is None:
                raise ValueError("prices or data_fetcher must be provided")
            logger.info("Fetching data for %s", self.config.symbol)
            prices = self.config.data_fetcher.fetch(
                self.config.symbol,
                self.config.start_date,
                self.config.end_date,
            )
            logger.info("Fetched %d price points", len(prices))

        if len(prices) != len(signals):
            raise ValueError("prices and signals must have same length")

        # Import here to avoid circular dependency
        from libs.qlib_ext.backtest.signal_backtest import SignalDrivenBacktest

        backtester = SignalDrivenBacktest(
            prices=prices,
            signals=signals,
            initial_capital=self.config.initial_capital,
            commission_rate=self.config.commission_rate,
        )

        equity_curve = backtester.run()
        metrics = backtester.compute_metrics()

        final_value = equity_curve[-1]
        logger.info(
            "Backtest complete for %s: final=%.2f, Sharpe=%.4f",
            self.config.symbol, final_value, metrics.sharpe,
        )

        return BacktestResult(
            symbol=self.config.symbol,
            equity_curve=equity_curve,
            final_value=final_value,
            metrics=metrics,
        )