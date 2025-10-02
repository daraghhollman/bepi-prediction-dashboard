"""
It is useful to filter these region observations by TAA, or Heliocentric
Distance, or other parameters. For this reason, we write this script to aid in
that.
"""

import os
import pathlib
import sys

import hermpy.trajectory
import pandas as pd


def main():
    # Filter values should either be None, or a tuple length = 2 for bounds.
    filters = {
        "Heliocentric Distance": None,
        "True Anomaly Angle": (90, 270),  # Negative values are allowed
    }

    # Assign crossing list based on input
    chosen_crossing_list = sys.argv[1]

    assert chosen_crossing_list in ["hollman", "philpott"]

    # Load messenger observations data
    region_observations = pd.read_csv(
        pathlib.Path(os.path.dirname(__file__))
        / "output"
        / f"messenger_region_observations_{chosen_crossing_list}.csv",
        index_col=0,
    )
    region_observations["Time"] = pd.to_datetime(region_observations["Time"])

    # Next we loop though the filters and calculate / filter based on the
    # parameters.
    filtered_by = []
    for key in filters.keys():
        bounds = filters[key]

        if bounds is None:
            continue

        filtered_by.append(key)
        region_observations = apply_filter(region_observations, key, bounds)

    region_observations.to_csv(
        pathlib.Path(os.path.dirname(__file__))
        / "output"
        / (
            "messenger_region_observations_filtered_by_"
            + ("_".join(filtered_by)).lower().replace(" ", "_")
            + ".csv"
        ),
        index=False,
    )


def apply_filter(observations, key, bounds):
    match key:
        case "True Anomaly Angle":
            return filter_by_taa(observations, bounds)

        case _:
            raise ValueError(f"Unknown case for key: {key}")


def filter_by_taa(observations, bounds):
    min_taa = min(bounds)
    max_taa = max(bounds)

    observations["TAA"] = hermpy.trajectory.get_true_anomaly_angle(observations["Time"])

    if min_taa > 0:
        return observations.loc[
            (observations["TAA"] > min_taa) & (observations["TAA"] < max_taa)
        ].copy()

    else:
        return observations.loc[
            (observations["TAA"] > 360 + min_taa) | (observations["TAA"] < max_taa)
        ].copy()


if __name__ == "__main__":
    main()
