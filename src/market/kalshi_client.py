from __future__ import annotations

from typing import Any

import requests


BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


class KalshiPublicClient:
    """Unauthenticated client for Kalshi public market data."""

    def __init__(self, base_url: str = BASE_URL, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _get(
        self,
        path: str,
        params: Any = None,
    ) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_series(self, series_ticker: str) -> dict[str, Any]:
        return self._get(f"/series/{series_ticker}")

    def get_markets(
        self,
        series_ticker: str,
        status: str = "open",
    ) -> list[dict[str, Any]]:
        markets: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {
                "series_ticker": series_ticker,
                "status": status,
                "limit": 1000,
            }

            if cursor:
                params["cursor"] = cursor

            payload = self._get("/markets", params=params)
            markets.extend(payload.get("markets", []))

            cursor = payload.get("cursor")
            if not cursor:
                break

        return markets

    def get_orderbooks(
        self,
        tickers: list[str],
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch multiple order books in batch.

        Kalshi currently supports up to 100 market tickers per request.
        """
        result: dict[str, dict[str, Any]] = {}

        for i in range(0, len(tickers), 100):
            chunk = tickers[i:i + 100]

            payload = self._get(
                "/markets/orderbooks",
                params={"tickers": chunk},
            )

            for record in payload.get("orderbooks", []):
                result[record["ticker"]] = record["orderbook_fp"]

        return result
