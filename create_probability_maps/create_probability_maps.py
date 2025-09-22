"""
Takes inputs from create_messenger_regions.py and outputs 2d array files for
the solar wind, magnetosheath, and magnetosphere based on an input crossing
list identifier

Usage:

    python create_probability_maps.py <crossing list>

    e.g.
    python create_probability_maps.py hollman
"""

import datetime as dt
import os
import pathlib
import sys

import numpy as np
import pandas as pd
import xarray as xr
from tqdm import tqdm


def main():

    bootstrap = False

    # Assign crossing list based on input
    chosen_crossing_list = sys.argv[1]

    assert chosen_crossing_list in ["hollman", "philpott"]

    # Load messenger observations data
    region_observations = pd.read_csv(
        pathlib.Path(os.path.dirname(__file__))
        / "output"
        / f"messenger_region_observations_{chosen_crossing_list}.csv"
    )

    # Create bins
    bin_size = 0.25
    x_bins = np.arange(-5, 5 + bin_size, bin_size)  # Radii
    cyl_bins = np.arange(0, 8 + bin_size, bin_size)  # Radii

    if bootstrap:
        bootstrap_count = 1000
        bootstrap_fraction = 0.01
    else:
        bootstrap_count = 1
        bootstrap_fraction = 1

    region_maps = {}

    # Make histograms for each region type
    for region_name, region_id in zip(
        ["Solar Wind", "Magnetosheath", "Magnetosphere"],
        ["solar_wind", "magnetosheath", "magnetosphere"],
    ):

        region_probability_maps = []

        for _ in tqdm(
            range(bootstrap_count),
            desc=f"Bootstrapping {region_name} Observations to Determine Uncertainties",
            disable=not bootstrap,
        ):

            if bootstrap:
                observation_subset = region_observations.sample(
                    frac=bootstrap_fraction, replace=True
                )
            else:
                observation_subset = region_observations

            filtered_predictions = observation_subset.loc[
                observation_subset["Predicted Region"] == region_name
            ][["X MSM' (radii)", "CYL MSM' (radii)"]]

            region_probability_map, _, _ = np.histogram2d(
                filtered_predictions["X MSM' (radii)"],
                filtered_predictions["CYL MSM' (radii)"],
                bins=[x_bins, cyl_bins],
            )

            region_probability_maps.append(region_probability_map)

        mean_region_probabilities = np.mean(region_probability_maps, axis=0)
        std_region_probabilities = np.std(region_probability_maps, axis=0)

        region_maps.update(
            {
                region_name: {
                    "Mean": mean_region_probabilities,
                    "Uncertainty": std_region_probabilities,
                }
            }
        )

    # Noramlise these maps so that they actually represent probabilities
    map_totals = np.sum(
        [
            region_maps[region]["Mean"]
            for region in ["Solar Wind", "Magnetosheath", "Magnetosphere"]
        ],
        axis=0,
    )

    for region in ["Solar Wind", "Magnetosheath", "Magnetosphere"]:
        region_maps[region]["Mean"] /= map_totals
        region_maps[region]["Uncertainty"] /= map_totals

        # We also don't want 0 values as they obscure the low value data
        region_maps[region]["Mean"][np.where(region_maps[region]["Mean"] == 0)] = np.nan

    # The cleanest way to save these data is as a netcdf file.

    probability_map = xr.Dataset()

    # Save dimensions (bin centres)
    probability_map.coords["X"] = (x_bins[:-1] + x_bins[1:]) / 2
    probability_map.coords["CYL"] = (cyl_bins[:-1] + cyl_bins[1:]) / 2

    for region_name, data in region_maps.items():
        region_id = region_name.replace(" ", "_").lower()

        probability_map[f"{region_id}_mean"] = (("X", "CYL"), data["Mean"])

        if bootstrap:
            probability_map[f"{region_id}_uncertainty"] = (
                ("X", "CYL"),
                data["Uncertainty"],
            )

    # Add other metadata
    probability_map.attrs["Referenced crossing list"] = chosen_crossing_list
    probability_map.attrs["Date created"] = dt.datetime.today().__str__()
    probability_map.attrs["Bootstrapped"] = "True" if bootstrap else "False"

    # Save to NetCDF
    output_file = (
        pathlib.Path(os.path.dirname(__file__))
        / "output"
        / f"region_maps_{chosen_crossing_list}.nc"
    )
    probability_map.to_netcdf(output_file)

    loaded = xr.load_dataset(output_file)
    print(loaded)


if __name__ == "__main__":
    main()
