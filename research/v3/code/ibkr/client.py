"""Read-only IBKR Client Portal Web API client for V3 capability audits.

This module deliberately excludes order submission. It exists only to establish
what market-data, contract metadata, historical bars, and streaming top-of-book
capabilities are actually accessible before any V3 strategy is frozen or
prospective PnL is inspected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import requests


DEFAULT_BASE_URL = "https://localhost:5000/v1/api"


class IBKRAPIError(RuntimeError):
    """Raised when an IBKR endpoint returns an unsuccessful response."""


@dataclass
class IBKRClient:
    base_url: str = DEFAULT_BASE_URL
    verify_tls: bool = False
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                timeout=self.timeout_seconds,
                verify=self.verify_tls,
            )
        except requests.RequestException as exc:
            raise IBKRAPIError(f"request failed for {method} {url}: {exc}") from exc

        if not response.ok:
            # Do not persist broker response bodies in audit errors. Even a
            # read-only endpoint may return session/account context.
            raise IBKRAPIError(
                f"IBKR returned HTTP {response.status_code} for {method} {url}"
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise IBKRAPIError(f"non-JSON response from {method} {url}") from exc

    # Session / readiness -------------------------------------------------
    def auth_status(self) -> Any:
        return self._request("POST", "/iserver/auth/status")

    def tickle(self) -> Any:
        return self._request("POST", "/tickle")

    def session_token(self) -> str:
        """Return the current CPGW websocket session token in memory only.

        The token must never be written to V3 research artifacts.
        """
        payload = self.tickle()
        token = None
        if isinstance(payload, dict):
            token = payload.get("session")
            if token is None and isinstance(payload.get("success"), dict):
                value = payload["success"].get("value")
                if isinstance(value, dict):
                    token = value.get("session")
        if not token:
            raise IBKRAPIError("tickle response did not contain a websocket session token")
        return str(token)

    def accounts(self) -> Any:
        # IBKR documents this as a required pre-flight before market data.
        return self._request("GET", "/iserver/accounts")

    # Event-contract discovery -------------------------------------------
    def category_tree(self) -> Any:
        return self._request("GET", "/forecast/category/tree")

    def forecast_market(
        self,
        underlying_conid: int,
        *,
        exchange: str = "FORECASTX",
    ) -> Any:
        return self._request(
            "GET",
            "/forecast/contract/market",
            params={"underlyingConid": underlying_conid, "exchange": exchange},
        )

    def search_symbol(self, symbol: str) -> Any:
        return self._request("GET", "/iserver/secdef/search", params={"symbol": symbol})

    def strikes(
        self,
        *,
        underlying_conid: int,
        month: str,
        exchange: str = "FORECASTX",
        sectype: str = "OPT",
    ) -> Any:
        return self._request(
            "GET",
            "/iserver/secdef/strikes",
            params={
                "conid": underlying_conid,
                "exchange": exchange,
                "sectype": sectype,
                "month": month,
            },
        )

    def secdef_info(
        self,
        *,
        underlying_conid: int,
        month: str,
        strike: float,
        exchange: str = "FORECASTX",
        sectype: str = "OPT",
    ) -> Any:
        return self._request(
            "GET",
            "/iserver/secdef/info",
            params={
                "conid": underlying_conid,
                "exchange": exchange,
                "sectype": sectype,
                "month": month,
                "strike": strike,
            },
        )

    def contract_details(self, conid: int) -> Any:
        return self._request("GET", "/forecast/contract/details", params={"conid": conid})

    def contract_rules(self, conid: int) -> Any:
        return self._request("GET", "/forecast/contract/rules", params={"conid": conid})

    def contract_schedules(self, conid: int) -> Any:
        return self._request("GET", "/forecast/contract/schedules", params={"conid": conid})

    # Market data ---------------------------------------------------------
    def marketdata_snapshot(
        self,
        conids: Iterable[int],
        *,
        fields: Iterable[str] | None = None,
    ) -> Any:
        params: dict[str, Any] = {"conids": ",".join(str(c) for c in conids)}
        if fields is not None:
            params["fields"] = ",".join(str(f) for f in fields)
        return self._request("GET", "/iserver/marketdata/snapshot", params=params)

    def historical_marketdata(
        self,
        conid: int,
        *,
        period: str = "1d",
        bar: str = "1min",
        exchange: str | None = "FORECASTX",
        outside_rth: bool = True,
    ) -> Any:
        params: dict[str, Any] = {
            "conid": conid,
            "period": period,
            "bar": bar,
            "outsideRth": str(bool(outside_rth)).lower(),
        }
        if exchange:
            params["exchange"] = exchange
        return self._request("GET", "/iserver/marketdata/history", params=params)
