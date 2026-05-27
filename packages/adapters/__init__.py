"""Adapters package - external system adapters."""
from adapters.base import DataSourceABC
from adapters.exchange import ExchangeAdapterABC
from adapters.social import SocialAdapterABC
from adapters.polymarket import PolymarketAdapterABC
from adapters.onchain import OnchainAdapterABC

__all__ = [
    "DataSourceABC",
    "ExchangeAdapterABC",
    "SocialAdapterABC",
    "PolymarketAdapterABC",
    "OnchainAdapterABC",
]
