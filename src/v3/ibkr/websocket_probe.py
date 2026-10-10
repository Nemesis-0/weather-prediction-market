"""Short read-only Client Portal Gateway websocket probes for V3.

No order topics are implemented. The probe subscribes only to streaming
market-data (`smd`) and immediately unsubscribes (`umd`) before closing.
"""

from __future__ import annotations

import json
import ssl
import time
from datetime import datetime, timezone
from statistics import median
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import websocket

from src.v3.ibkr.client import IBKRAPIError, IBKRClient


def websocket_url_from_base(base_url: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    path = parts.path.rstrip("/") + "/ws"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def _median_positive_delta(values: list[int]) -> float | None:
    if len(values) < 2:
        return None
    deltas = [b - a for a, b in zip(values, values[1:]) if b > a]
    return float(median(deltas)) if deltas else None


def probe_market_stream(
    client: IBKRClient,
    conid: int,
    *,
    fields: Iterable[str],
    duration_seconds: float = 5.0,
) -> dict[str, Any]:
    """Collect a short, safe summary of one top-of-book websocket stream."""

    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    token = client.session_token()  # kept in memory only
    url = websocket_url_from_base(client.base_url)
    sslopt = {} if client.verify_tls else {"cert_reqs": ssl.CERT_NONE}

    local_wall: list[str] = []
    local_mono_ns: list[int] = []
    broker_updated_ms: list[int] = []
    availability_values: set[str] = set()
    observed_fields: set[str] = set()
    matching_messages = 0
    total_messages = 0

    ws = None
    try:
        ws = websocket.create_connection(
            url,
            cookie=f"api={token}",
            timeout=1.0,
            sslopt=sslopt,
            http_proxy_host=None,
        )
        request_fields = [str(x) for x in fields]
        ws.send(f"smd+{conid}+" + json.dumps({"fields": request_fields}, separators=(",", ":")))

        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            remaining = max(0.05, min(1.0, deadline - time.monotonic()))
            ws.settimeout(remaining)
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not raw:
                continue
            total_messages += 1
            try:
                payload = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            topic = str(payload.get("topic", ""))
            payload_conid = payload.get("conid")
            if topic != f"smd+{conid}" and payload_conid != conid:
                continue

            matching_messages += 1
            local_wall.append(datetime.now(timezone.utc).isoformat())
            local_mono_ns.append(time.monotonic_ns())
            updated = payload.get("_updated")
            if isinstance(updated, int):
                broker_updated_ms.append(updated)
            availability = payload.get("6509")
            if availability is not None:
                availability_values.add(str(availability))
            observed_fields.update(k for k in payload if k in request_fields)

        try:
            ws.send(f"umd+{conid}+{{}}")
        except Exception:
            pass
    except Exception as exc:
        raise IBKRAPIError(f"websocket market-data probe failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    local_ms = [int(x / 1_000_000) for x in local_mono_ns]
    return {
        "conid": conid,
        "duration_seconds": duration_seconds,
        "total_messages": total_messages,
        "matching_market_messages": matching_messages,
        "first_local_receive_utc": local_wall[0] if local_wall else None,
        "last_local_receive_utc": local_wall[-1] if local_wall else None,
        "broker_updated_first_ms": broker_updated_ms[0] if broker_updated_ms else None,
        "broker_updated_last_ms": broker_updated_ms[-1] if broker_updated_ms else None,
        "median_positive_local_interarrival_ms": _median_positive_delta(local_ms),
        "median_positive_broker_update_delta_ms": _median_positive_delta(broker_updated_ms),
        "market_data_availability_values": sorted(availability_values),
        "observed_requested_fields": sorted(observed_fields),
        "broker_updated_is_exchange_timestamp": False,
        "session_token_persisted": False,
    }
