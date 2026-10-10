from pathlib import Path
import pandas as pd
import numpy as np


EVENT_PATH = Path(
    "results/v2_feasibility/v2_market_alignment_events.csv"
)

MARKET_PATH = Path(
    "data/processed/market_panel_all.csv"
)

OUTDIR = Path(
    "results/v2_residual_assimilation"
)

OUTDIR.mkdir(
    parents=True,
    exist_ok=True
)


OUTFILE = (
    OUTDIR /
    "v2_residual_events.csv"
)


def load_market_snapshot(
    market,
    city,
    event_ticker,
    timestamp,
):
    """
    Extract six-bucket probability vector
    at one synchronized candle timestamp.
    """

    x = market[
        (market["city"] == city)
        &
        (market["event_ticker"] == event_ticker)
        &
        (market["timestamp_utc"] == timestamp)
    ].copy()

    if len(x) != 6:
        return None

    x = x.sort_values(
        "market_ticker"
    )

    return x["midpoint_close"].to_numpy(
        dtype=float
    )


def directional_response(
    weather_vec,
    market_change,
):
    """
    Dot product:
    positive = market moved in weather direction
    """

    return float(
        np.dot(
            weather_vec,
            market_change,
        )
    )


def main():

    events = pd.read_csv(
        EVENT_PATH
    )

    market = pd.read_csv(
        MARKET_PATH
    )


    print(
        "Input revision events:",
        len(events)
    )


    # only actual weather revisions
    events = events[
        events["any_weather_change"]
        &
        events["clean_pre_post1h"]
        &
        events["clean_pre_post2h"]
    ].copy()


    print(
        "Eligible H2.2 events:",
        len(events)
    )


    rows = []


    for r in events.itertuples():

        pre = load_market_snapshot(
            market,
            r.city,
            r.event_ticker,
            r.pre_snapshot_utc,
        )

        post1 = load_market_snapshot(
            market,
            r.city,
            r.event_ticker,
            r.post1_snapshot_utc,
        )

        post2 = load_market_snapshot(
            market,
            r.city,
            r.event_ticker,
            r.post2_snapshot_utc,
        )


        if (
            pre is None
            or post1 is None
            or post2 is None
        ):
            continue


        market_change_1h = (
            post1 - pre
        )

        market_change_2h = (
            post2 - post1
        )


        # Weather direction proxy:
        # positive TXN/XND revision mapped
        # through bucket probability movement.
        #
        # For now store raw revision;
        # directional mapping will be frozen
        # after inspection.

        rows.append(
            {
                "event_date_local":
                    r.event_date_local,

                "city":
                    r.city,

                "transition":
                    r.transition,

                "delta_txn":
                    r.delta_txn,

                "delta_xnd":
                    r.delta_xnd,

                "pre_snapshot_utc":
                    r.pre_snapshot_utc,

                "post1_snapshot_utc":
                    r.post1_snapshot_utc,

                "post2_snapshot_utc":
                    r.post2_snapshot_utc,

                "initial_market_l1":
                    float(
                        np.abs(
                            market_change_1h
                        ).sum()
                    ),

                "residual_market_l1":
                    float(
                        np.abs(
                            market_change_2h
                        ).sum()
                    ),

                "pre_distribution":
                    pre.tolist(),

                "post1_distribution":
                    post1.tolist(),

                "post2_distribution":
                    post2.tolist(),

            }
        )


    out = pd.DataFrame(
        rows
    )


    out.to_csv(
        OUTFILE,
        index=False,
    )


    print()
    print(
        "="*80
    )
    print(
        "H2.2 RESIDUAL DATASET"
    )
    print(
        "="*80
    )

    print(
        "Rows:",
        len(out)
    )

    print(
        "Cities:"
    )

    print(
        out["city"]
        .value_counts()
        .to_string()
    )


    print()
    print(
        "Saved:"
    )

    print(
        OUTFILE
    )


if __name__ == "__main__":
    main()
