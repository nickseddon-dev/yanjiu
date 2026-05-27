"""Real Polymarket CLOB API adapter.

Implements DataSourceABC for Polymarket prediction markets.
Uses the public CLOB REST API: https://clob.polymarket.com

Ratelimits:
  - Public endpoints: 200 req/min per IP
  - Authenticated (with API key): 600 req/min

Public endpoints used:
  GET /markets                     — list markets
  GET /markets/{market_id}        — market details + slug
  GET /orderbook/{slug}           — orderbook
  GET /candles/{market_hash}      — OHLCV candles
  GET /prices                     — current prices

For writing (placing orders), an API key is required. Set POLYMARKET_API_KEY.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
import pandas as pd

from adapters.base import DataSourceABC

logger = logging.getLogger("polymarket")


# Market slugification (matches Polymarket's rule)
import re


def _slugify(question: str) -> str:
    """Convert a market question to a Polymarket slug."""
    slug = question.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:113]  # Max 113 chars


class PolymarketAdapter(DataSourceABC):
    """Polymarket prediction market data adapter using CLOB API."""

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        affiliate_api_key: str = "",
        timeout: int = 15,
    ):
        """
        Initialize Polymarket adapter.

        Args:
            api_key: CLOB API key for authenticated endpoints (optional for reads).
            api_secret: CLOB API secret (optional).
            affiliate_api_key: Affiliate API key (optional).
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.affiliate_api_key = affiliate_api_key
        self.timeout = timeout
        self.base_url = "https://clob.polymarket.com"
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_headers: Dict[str, Any] = {}

    # --- Session management ---

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["CLOB-API-KEY"] = self.api_key
            if self.affiliate_api_key:
                headers["CLOB-AFFILIATE-API-KEY"] = self.affiliate_api_key
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout), headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request to the CLOB API."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        async with session.get(url, params=params) as resp:
            self._rate_limit_headers = {
                "remaining": resp.headers.get("X-RateLimit-Remaining", "N/A"),
                "limit": resp.headers.get("X-RateLimit-Limit", "N/A"),
            }
            if resp.status == 429:
                raise RuntimeError("Polymarket API rate limit hit")
            if resp.status == 404:
                raise RuntimeError(f"Polymarket endpoint not found: {path}")
            resp.raise_for_status()
            return await resp.json()

    async def _post(self, path: str, json: Dict) -> Dict:
        """Make a POST request to the CLOB API (requires auth)."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        async with session.post(url, json=json) as resp:
            resp.raise_for_status()
            return await resp.json()

    # --- DataSourceABC implementation ---

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str = "1h",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV candles (sync wrapper). Use async fetch_candles_async()."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            self.fetch_candles_async(symbol, interval, start, end)
        )

    async def fetch_candles_async(
        self, market_id: str, interval: str = "1h", start: Optional[str] = None, end: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles for a market by ID.

        Args:
            market_id: Polymarket market ID (hash).
            interval: Candle interval — 1m, 5m, 15m, 1h, 4h, 1d.
            start: ISO timestamp start.
            end: ISO timestamp end.
        """
        interval_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "1440"}
        period = interval_map.get(interval, "60")

        params: Dict[str, str] = {"period": period}
        if start:
            params["from"] = start
        if end:
            params["to"] = end

        try:
            data = await self._get(f"/candles/{market_id}", params)
        except Exception as e:
            logger.warning(f"fetch_candles_async failed for {market_id}: {e}")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        candles = data.get("candles", [])
        if not candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        rows = [
            {
                "timestamp": c.get("t", ""),
                "open": float(c.get("o", 0)),
                "high": float(c.get("h", 0)),
                "low": float(c.get("l", 0)),
                "close": float(c.get("c", 0)),
                "volume": float(c.get("v", 0)),
            }
            for c in candles
        ]
        df = pd.DataFrame(rows)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    def fetch_markets(self, filter_active: bool = True) -> pd.DataFrame:
        """Fetch all markets (sync wrapper). Use async fetch_markets_async()."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.fetch_markets_async(filter_active))

    async def fetch_markets_async(self, filter_active: bool = True) -> pd.DataFrame:
        """
        Fetch all markets from Polymarket.

        Args:
            filter_active: If True, only return active markets with non-zero volume.
        """
        # Pagination: fetch up to 1000 markets
        all_markets: List[Dict] = []
        cursor: Optional[str] = None

        for _ in range(10):  # max 10 pages
            params: Dict[str, Any] = {"limit": 100}
            if filter_active:
                params["active"] = "true"
            if cursor:
                params["cursor"] = cursor

            try:
                data = await self._get("/markets", params)
            except Exception as e:
                logger.warning(f"fetch_markets_async failed: {e}")
                break

            markets = data.get("markets", [])
            all_markets.extend(markets)

            cursor = data.get("nextCursor")
            if not cursor or cursor == data.get("nextCursor") == "":
                break

        if not all_markets:
            return pd.DataFrame(columns=["id", "question", "outcome", "probability", "volume", "slug"])

        rows = []
        for m in all_markets:
            outcomes = m.get("outcomes", []) or []
            probabilities = m.get("outcomePrices", []) or []
            prob = float(probabilities[0]) if probabilities else 0.5
            rows.append(
                {
                    "id": m.get("id", ""),
                    "question": m.get("question", ""),
                    "outcome": outcomes[0] if outcomes else "YES",
                    "probability": prob,
                    "volume": float(m.get("volume", 0) or 0),
                    "slug": m.get("slug", ""),
                    "active": m.get("active", True),
                    "closed": m.get("closed", False),
                    "end_date": m.get("endDate", ""),
                    "created_at": m.get("createdAt", ""),
                }
            )
        return pd.DataFrame(rows)

    def fetch_events(self, symbol: str = "") -> pd.DataFrame:
        """Fetch events/markets (sync wrapper)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.fetch_markets_async(filter_active=True))

    async def fetch_market_by_id(self, market_id: str) -> Optional[Dict]:
        """Fetch a single market by its ID."""
        try:
            return await self._get(f"/markets/{market_id}")
        except Exception as e:
            logger.warning(f"fetch_market_by_id {market_id}: {e}")
            return None

    async def fetch_market_by_slug(self, slug: str) -> Optional[Dict]:
        """Fetch a market by its slug."""
        try:
            return await self._get(f"/orderbook/{slug}")
        except Exception:
            pass

        # Fall back to searching markets
        try:
            df = await self.fetch_markets_async(filter_active=False)
            matches = df[df["slug"] == slug]
            if not matches.empty:
                row = matches.iloc[0]
                return await self.fetch_market_by_id(row["id"])
        except Exception as e:
            logger.warning(f"fetch_market_by_slug {slug}: {e}")

        return None

    def fetch_probability(self, market_id: str) -> dict:
        """Fetch current probability for a market (sync wrapper)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.fetch_probability_async(market_id))

    async def fetch_probability_async(self, market_id: str) -> Dict[str, Any]:
        """
        Fetch current probability/price for a market.

        Returns dict with market_id, probability, yes_price, no_price, timestamp.
        """
        try:
            market = await self._get(f"/markets/{market_id}")
        except Exception as e:
            logger.warning(f"fetch_probability_async {market_id}: {e}")
            return {"market_id": market_id, "probability": 0.5, "timestamp": None}

        outcome_prices = market.get("outcomePrices", []) or []
        yes_price = float(outcome_prices[0]) if outcome_prices else 0.5
        no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else (1 - yes_price)

        return {
            "market_id": market_id,
            "probability": yes_price,
            "yes_price": yes_price,
            "no_price": no_price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Fetch order book snapshot (sync wrapper)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.fetch_orderbook_async(symbol, depth))

    async def fetch_orderbook_async(self, slug: str, depth: int = 20) -> Dict[str, Any]:
        """
        Fetch order book for a market by slug.

        Args:
            slug: Market slug (e.g. "will-ethereum-reach-5000-by-dec-31-2024").
            depth: Number of price levels per side (default 20).
        """
        try:
            data = await self._get(f"/orderbook/{slug}")
        except Exception as e:
            logger.warning(f"fetch_orderbook_async {slug}: {e}")
            return {"symbol": slug, "bids": [], "asks": [], "timestamp": None}

        bids_raw = data.get("bids", []) or []
        asks_raw = data.get("asks", []) or []

        bids = [
            {"price": float(b["price"]), "size": float(b.get("size", b.get("qty", 0)))}
            for b in bids_raw[:depth]
        ]
        asks = [
            {"price": float(a["price"]), "size": float(a.get("size", a.get("qty", 0)))}
            for a in asks_raw[:depth]
        ]

        return {
            "symbol": slug,
            "bids": bids,
            "asks": asks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def fetch_funding_rate(self, symbol: str) -> pd.DataFrame:
        """
        Polymarket is a prediction market — no funding rate concept.
        Returns empty DataFrame.
        """
        return pd.DataFrame(columns=["timestamp", "rate"])

    async def health_check_async(self) -> bool:
        """Async health check — verify API responds."""
        try:
            data = await self._get("/markets", {"limit": 1})
            return "markets" in data or isinstance(data, list)
        except Exception:
            return False

    def health_check(self) -> bool:
        """Health check (sync)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.health_check_async())

    # --- Utility methods ---

    async def get_market_id_for_question(self, question: str) -> Optional[str]:
        """
        Find the market ID for a question string (partial match).
        Useful when you only have the question text from event_schema.
        """
        try:
            df = await self.fetch_markets_async(filter_active=True)
            matches = df[df["question"].str.contains(question, case=False, na=False)]
            if not matches.empty:
                return matches.iloc[0]["id"]
        except Exception as e:
            logger.warning(f"get_market_id_for_question '{question}': {e}")
        return None

    async def get_top_markets(self, limit: int = 10) -> pd.DataFrame:
        """Return top markets by volume."""
        try:
            df = await self.fetch_markets_async(filter_active=True)
            if df.empty:
                return df
            return df.sort_values("volume", ascending=False).head(limit)
        except Exception as e:
            logger.warning(f"get_top_markets: {e}")
            return pd.DataFrame(columns=["id", "question", "outcome", "probability", "volume"])