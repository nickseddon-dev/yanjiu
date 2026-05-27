"""Executor service - live host signal consumer and order executor.

Consumes signals from Redis streams (placed there by signal_bridge),
runs pre-trade risk checks via RiskChecker, and executes orders via
OrderExecutionAdapter. Supports paper-trading and live modes.
"""
from .main import app

__all__ = ["app"]