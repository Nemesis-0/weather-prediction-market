from __future__ import annotations

import requests


URL = "https://mesonet.agron.iastate.edu/api/1/mos.json"

RUNTIME = "2026-09-28 12:00Z"

STATIONS = {
    "NYC": "KNYC",
    "Chicago": "KMDW",
    "Denver": "KDEN",
}


def main():
    print("\nIEM historical NBM/NBS probe")
    print("=" * 78)
    print("runtime:", RUNTIME)

    all_ok = True

    for city, station in STATIONS.items():
        print("\n" + "=" * 78)
        print(f"{city} — {station}")

        response = requests.get(
            URL,
            params={
                "station": station,
                "model": "NBS",
                "runtime": RUNTIME,
            },
            timeout=30,
        )

        print("HTTP status:", response.status_code)
        print("resolved URL:", response.url)

        response.raise_for_status()

        payload = response.json()

        print("top-level keys:", list(payload.keys()))

        rows = payload.get("data", [])

        print("forecast rows:", len(rows))

        if not rows:
            print("NO DATA")
            all_ok = False
            continue

        print("available fields:")
        print(sorted(rows[0].keys()))

        txn_rows = [
            row
            for row in rows
            if row.get("txn") is not None
            or row.get("xnd") is not None
        ]

        print("rows with TXN/XND:", len(txn_rows))

        for row in txn_rows[:10]:
            keep = {
                key: row.get(key)
                for key in (
                    "station",
                    "runtime",
                    "ftime",
                    "ftime_utc",
                    "txn",
                    "xnd",
                    "tmp",
                    "tsd",
                )
                if key in row
            }
            print(keep)

        if not txn_rows:
            all_ok = False

    print("\n" + "=" * 78)

    if all_ok:
        print("PASS: all three stations returned historical NBS TXN/XND data.")
    else:
        print("FAIL: at least one station is missing usable TXN/XND data.")


if __name__ == "__main__":
    main()
