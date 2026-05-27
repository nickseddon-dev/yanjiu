"""On-chain blockchain features for crypto assets."""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class OnChainFeatures:
    """On-chain features for a crypto asset.

    Attributes:
        gas_price_gwei: Current gas price in Gwei.
        active_addresses_24h: Number of active addresses in 24h.
        tvl_usd: Total value locked in USD.
        nft_volume: NFT trading volume in USD.
        defi_protocol_tvl: DeFi protocol TVL in USD.
        timestamp: Feature extraction timestamp.
    """
    gas_price_gwei: float
    active_addresses_24h: int
    tvl_usd: float
    nft_volume: float
    defi_protocol_tvl: float
    timestamp: Optional[str] = None


def compute_gas_price_gwei(avg_gas: float, base_fee: float) -> float:
    """Compute effective gas price in Gwei.

    Args:
        avg_gas: Average gas price.
        base_fee: Base fee.

    Returns:
        Gas price in Gwei.
    """
    return round((avg_gas + base_fee), 4)


def compute_active_addresses_24h(new_addresses: int, returning_addresses: int) -> int:
    """Compute active addresses count.

    Args:
        new_addresses: New addresses in period.
        returning_addresses: Returning addresses in period.

    Returns:
        Total active addresses.
    """
    return new_addresses + returning_addresses


def compute_defi_protocol_tvl(tvl_by_protocol: dict) -> float:
    """Aggregate DeFi protocol TVL.

    Args:
        tvl_by_protocol: Dict mapping protocol name to TVL.

    Returns:
        Total TVL in USD.
    """
    return round(sum(tvl_by_protocol.values()), 4)


def compute_nft_volume(volume_by_marketplace: dict) -> float:
    """Aggregate NFT volume across marketplaces.

    Args:
        volume_by_marketplace: Dict mapping marketplace to volume.

    Returns:
        Total NFT volume in USD.
    """
    return round(sum(volume_by_marketplace.values()), 4)