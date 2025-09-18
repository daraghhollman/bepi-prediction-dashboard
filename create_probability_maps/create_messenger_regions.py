"""
Creates a dataset of the magnetospheric region at a given position for each
observation (downsampled to 0.2 Hz) of the MESSENGER mission. A backend must be
input to determine which crossing list to use:
    - Hollman+ 2025 (in review) id=hollman
    - Philpott+ 2020 id=philpott
    - Sun+ 2023... (to be added in future, list has some issues)

Usage:

    python create_messenger_regions.py <crossing list>

    e.g.
    python create_messenger_regions.py hollman
"""

import os
import pathlib
import sys

import numpy as np
import pandas as pd
from hermpy import boundaries, mag, utils


def main():

    # Make output directory
    os.makedirs(pathlib.Path(os.path.dirname(__file__)) / "output", exist_ok=True)

    # Assign crossing list based on input
    chosen_crossing_list = sys.argv[1]

    assert chosen_crossing_list in ["hollman", "philpott"]

    # We want to first load the entire MESSENGER MISSION
    # It is most convenient to load the pre-saved mission file from hermpy
    # This is at one second resolution.
    messenger_ephemeris = mag.Load_Mission(
        utils.User.DATA_DIRECTORIES["FULL MISSION"]
    )  # THE ONLY REFERENCE TO HERMPY!! WE SHOULD REPLACE THIS WITH SOMETHING BUILTIN
    messenger_ephemeris["Time"] = pd.to_datetime(messenger_ephemeris["date"])

    # We want the option to downsample this to lower resolutions
    # This is once every 5 seconds, or 0.2 Hz
    downsample = 5  # seconds

    if downsample != 1:
        messenger_ephemeris = messenger_ephemeris.iloc[::downsample, :].reset_index(
            drop=True
        )

    # We can limit down to only the columns we want
    messenger_ephemeris = messenger_ephemeris[
        [
            "Time",
            "X MSM' (radii)",
            "Y MSM' (radii)",
            "Z MSM' (radii)",
        ]
    ]

    # For each of these data-points, we want to know which region MESSENGER was in.
    # To do this, we compare the times column to a list of crossings, and use the
    # most recent crossing to determine the current region.

    predicted_regions = (
        determine_regions_with_hollman(messenger_ephemeris)
        if chosen_crossing_list == "hollman"
        else determine_regions_with_philpott(messenger_ephemeris)
    )

    # Save this to file
    predicted_regions.to_csv(
        pathlib.Path(os.path.dirname(__file__))
        / f"output/messenger_region_observations_{chosen_crossing_list}.csv"
    )


def determine_regions_with_philpott(messenger_ephemeris):

    # Load Philpott crossing list
    crossings = boundaries.Load_Crossings(
        str(
            pathlib.Path(os.path.dirname(__file__)) / f"../resources/philpott_2020.xlsx"
        ),
        include_data_gaps=False,
    )

    # Shorten the columns down to just what we need
    crossings = crossings[["Start Time", "End Time", "Type"]]

    # We want to:
    #   - Remove any observations that are within the start and end time of any
    #   crossing interval.
    #   - Determine the region based on the closest previous interval, the
    #   closest following interval, and only accept observations where these
    #   two match.

    # Find the nearest interval start time before each
    # observation
    tmp = pd.merge_asof(
        messenger_ephemeris,
        crossings,
        left_on="Time",
        right_on="Start Time",
        direction="backward",
    )

    # If the end time of the same interval is after the observation time, then
    # this observation is within the interval
    mask_inside = tmp["Time"] <= tmp["End Time"]

    # Keep only rows outside as the region is unknown within.
    messenger_ephemeris = messenger_ephemeris.loc[~mask_inside].copy()

    # Next check the closest intervals before and after, merging their labels
    # onto the observation
    backward_merge = pd.merge_asof(
        messenger_ephemeris,
        crossings,
        left_on="Time",
        right_on="End Time",
        direction="backward",
    ).rename(columns={"Type": "Previous Interval Type"})

    forward_merge = pd.merge_asof(
        messenger_ephemeris,
        crossings,
        left_on="Time",
        right_on="Start Time",
        direction="forward",
    ).rename(columns={"Type": "Next Interval Type"})

    # We have nan values as there are some data points before the first crossing.
    # We could include these by basing them off of the next crossing, but I don't
    # think it matters too much for the average behaviour per bin.
    ephemeris_with_crossings = backward_merge.merge(
        forward_merge[["Time", "Next Interval Type"]], on="Time"
    ).dropna()

    # Write a look-up table: What region are we in based on the surrounding
    # crossings
    previous_crossing_table = {
        "BS_OUT": "Solar Wind",
        "BS_IN": "Magnetosheath",
        "MP_OUT": "Magnetosheath",
        "MP_IN": "Magnetosphere",
    }
    next_crossing_table = {
        "BS_OUT": "Magnetosheath",
        "BS_IN": "Solar Wind",
        "MP_OUT": "Magnetosphere",
        "MP_IN": "Magnetosheath",
    }

    # Add the region prediction and drop unneeded columns
    ephemeris_with_crossings["Predicted Region (prev. crossing)"] = [
        previous_crossing_table[previous_crossing]
        for previous_crossing in ephemeris_with_crossings["Previous Interval Type"]
    ]
    ephemeris_with_crossings["Predicted Region (next crossing)"] = [
        next_crossing_table[next_crossing]
        for next_crossing in ephemeris_with_crossings["Next Interval Type"]
    ]

    ephemeris_with_crossings = ephemeris_with_crossings.loc[
        ephemeris_with_crossings["Predicted Region (next crossing)"]
        == ephemeris_with_crossings["Predicted Region (prev. crossing)"]
    ]

    # Convert to cylindrical coordinates
    ephemeris_with_crossings["CYL MSM' (radii)"] = np.sqrt(
        ephemeris_with_crossings["Y MSM' (radii)"] ** 2
        + ephemeris_with_crossings["Z MSM' (radii)"] ** 2
    )

    ephemeris_with_crossings.rename(
        columns={"Predicted Region (prev. crossing)": "Predicted Region"}, inplace=True
    )

    # Reorded columns
    predicted_spatial_regions = (
        ephemeris_with_crossings[
            [
                "Predicted Region",
                "X MSM' (radii)",
                "CYL MSM' (radii)",
            ]
        ]
        .copy()
        .reset_index(drop=True)
    )

    return predicted_spatial_regions


def determine_regions_with_hollman(messenger_ephemeris):
    # Load Hollman et al. (in prep., 2025) crossing list
    crossings = pd.read_csv(
        pathlib.Path(os.path.dirname(__file__))
        / f"../resources/hollman_2025_crossing_list.csv"
    )
    crossings["Time"] = pd.to_datetime(crossings["Times"])

    # Shorten the columns down to just what we need
    crossings = crossings[["Time", "Label"]]

    # Merge the two, finding the closest past crossing to each data point
    backward_merge = pd.merge_asof(
        messenger_ephemeris, crossings, on="Time", direction="backward"
    ).rename(columns={"Label": "Previous Crossing Label"})
    # But it is not sufficient to check only which crossing was before. In the case
    # of intervals missing due to data gaps, or other anomalies, it is possible for
    # the current region according to the previous crossing and the current region
    # according to the next crossing to disagree. We should ignore these cases. We
    # need to do two merges with the crossing list, one looking forward and one
    # looking backwards.
    forward_merge = pd.merge_asof(
        messenger_ephemeris, crossings, on="Time", direction="forward"
    ).rename(columns={"Label": "Next Crossing Label"})

    # We have nan values as there are some data points before the first crossing.
    # We could include these by basing them off of the next crossing, but I don't
    # think it matters too much for the average behaviour per bin.
    ephemeris_with_crossings = backward_merge.merge(
        forward_merge[["Time", "Next Crossing Label"]], on="Time"
    ).dropna()

    # Write a look-up table: What region are we in based on the surrounding
    # crossings
    previous_crossing_table = {
        "BS_OUT": "Solar Wind",
        "BS_IN": "Magnetosheath",
        "MP_OUT": "Magnetosheath",
        "MP_IN": "Magnetosphere",
        "UNPHYSICAL (MSp -> SW)": "Solar Wind",
        "UNPHYSICAL (SW -> MSp)": "Magnetosphere",
    }
    next_crossing_table = {
        "BS_OUT": "Magnetosheath",
        "BS_IN": "Solar Wind",
        "MP_OUT": "Magnetosphere",
        "MP_IN": "Magnetosheath",
        "UNPHYSICAL (MSp -> SW)": "Magnteosphere",
        "UNPHYSICAL (SW -> MSp)": "Solar Wind",
    }

    # Add the region prediction and drop unneeded columns
    ephemeris_with_crossings["Predicted Region (prev. crossing)"] = [
        previous_crossing_table[previous_crossing]
        for previous_crossing in ephemeris_with_crossings["Previous Crossing Label"]
    ]
    ephemeris_with_crossings["Predicted Region (next crossing)"] = [
        next_crossing_table[next_crossing]
        for next_crossing in ephemeris_with_crossings["Next Crossing Label"]
    ]

    ephemeris_with_crossings = ephemeris_with_crossings.loc[
        ephemeris_with_crossings["Predicted Region (next crossing)"]
        == ephemeris_with_crossings["Predicted Region (prev. crossing)"]
    ]

    # Convert to cylindrical coordinates
    ephemeris_with_crossings["CYL MSM' (radii)"] = np.sqrt(
        ephemeris_with_crossings["Y MSM' (radii)"] ** 2
        + ephemeris_with_crossings["Z MSM' (radii)"] ** 2
    )

    ephemeris_with_crossings.rename(
        columns={"Predicted Region (prev. crossing)": "Predicted Region"}, inplace=True
    )

    # Reorded columns
    predicted_spatial_regions = (
        ephemeris_with_crossings[
            [
                "Predicted Region",
                "X MSM' (radii)",
                "CYL MSM' (radii)",
            ]
        ]
        .copy()
        .reset_index(drop=True)
    )

    return predicted_spatial_regions


if __name__ == "__main__":
    main()
