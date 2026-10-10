from pathlib import Path

import requests


URL = (
    "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
    "blend.20260820/12/text/"
    "blend_nbstx.t12z"
)

OUT = Path(
    "data/raw/weather/v2_probe/"
    "blend.20260820.12Z.nbstx.txt"
)

OUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

STATIONS = [
    "KNYC",
    "KMDW",
    "KDEN",
]


def main():
    print(
        "\nDOWNLOADING RAW NOAA NBS PROBE"
    )
    print("=" * 80)

    with requests.get(
        URL,
        stream=True,
        timeout=60,
    ) as r:
        r.raise_for_status()

        with OUT.open("wb") as f:
            for chunk in r.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)

    print(
        f"Saved: {OUT}"
    )
    print(
        f"Size: {OUT.stat().st_size / 1024 / 1024:.1f} MB"
    )

    raw = OUT.read_bytes()

    text = raw.decode(
        "latin-1",
        errors="replace",
    )

    print()
    print(
        "FIRST 2000 CHARACTERS"
    )
    print("=" * 80)
    print(
        text[:2000]
    )

    for station in STATIONS:
        print()
        print("=" * 80)
        print(
            f"SEARCH: {station}"
        )
        print("=" * 80)

        positions = []

        start = 0

        while True:
            pos = text.find(
                station,
                start,
            )

            if pos < 0:
                break

            positions.append(pos)

            if len(positions) >= 5:
                break

            start = pos + len(
                station
            )

        print(
            "Occurrences found:",
            len(positions),
        )

        if not positions:
            continue

        for i, pos in enumerate(
            positions,
            start=1,
        ):
            lo = max(
                0,
                pos - 700,
            )

            hi = min(
                len(text),
                pos + 1800,
            )

            print()
            print(
                f"--- occurrence {i} "
                f"at byte/char ~{pos} ---"
            )

            print(
                text[lo:hi]
            )

    print()
    print("=" * 80)
    print(
        "RAW STRUCTURE PROBE COMPLETE"
    )


if __name__ == "__main__":
    main()
