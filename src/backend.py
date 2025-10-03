import datetime as dt
import itertools
import os
import pathlib
from typing import Iterable

import hermpy.utils
import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import planetary_coverage as pc
import plotly.express as px
import plotly.graph_objects as go
import plotly.subplots
import spiceypy as spice
import xarray as xr


def plot_magnetospheric_boundaries(
    fig,
    row,
    col,
    sub_solar_magnetopause: float = 1.45,
    alpha: float = 0.5,
    psi: float = 1.04,
    p: float = 2.75,
    initial_x: float = 0.5,
) -> None:
    # Plotting magnetopause
    phi = np.linspace(0, 2 * np.pi, 1000)
    rho = sub_solar_magnetopause * (2 / (1 + np.cos(phi))) ** alpha

    magnetopause_x_coords = rho * np.cos(phi)
    magnetopause_y_coords = rho * np.sin(phi)

    L = psi * p

    rho = L / (1 + psi * np.cos(phi))

    bow_shock_x_coords = initial_x + rho * np.cos(phi)
    bow_shock_y_coords = rho * np.sin(phi)

    # Bow shock functional form creates non-physical points far sunward of Mercury.
    # These are incorrect and must be removed.
    bow_shock_y_coords = bow_shock_y_coords[bow_shock_x_coords < 2]
    bow_shock_x_coords = bow_shock_x_coords[bow_shock_x_coords < 2]

    fig.add_trace(
        go.Scatter(
            x=magnetopause_x_coords,
            y=magnetopause_y_coords,
            mode="lines",
            line=dict(
                color="black",
                dash="dot",
            ),
            showlegend=False,
        ),
        row=row,
        col=col,
    )
    fig.add_trace(
        go.Scatter(
            x=bow_shock_x_coords,
            y=bow_shock_y_coords,
            mode="lines",
            line=dict(
                color="black",
            ),
            showlegend=False,
        ),
        row=row,
        col=col,
    )


def get_heliocentric_distance(date: dt.datetime | dt.date | list[dt.datetime]) -> float:
    if isinstance(date, (dt.datetime, dt.date)):
        et = spice.str2et(date.strftime("%Y-%m-%d %H:%M:%S"))

        position, _ = spice.spkpos("MERCURY", et, "J2000", "NONE", "SUN")

        distance = np.sqrt(np.sum(position**2))

        return distance

    elif isinstance(date, Iterable):
        et = spice.datetime2et(date)

        positions, _ = spice.spkpos("MERCURY", et, "J2000", "NONE", "SUN")

        distances = np.sqrt(np.sum(positions**2, axis=1))

        return distances

    else:
        raise ValueError("Input date of incorrect type!")


def get_aberration_angle(date: dt.datetime | dt.date) -> float:
    if isinstance(date, dt.datetime):
        mercury_distance = (
            get_heliocentric_distance(date.date()) * 1000
        )  # convert to meters

    elif isinstance(date, dt.date):
        mercury_distance = get_heliocentric_distance(date) * 1000  # convert to meters

    # determine mercury velocity
    a = hermpy.utils.Constants.MERCURY_SEMI_MAJOR_AXIS
    M = hermpy.utils.Constants.SOLAR_MASS
    G = hermpy.utils.Constants.G

    orbital_velocity = np.sqrt(G * M * ((2 / mercury_distance) - (1 / a)))

    # Aberration angle is related to the orbital velocity and the solar wind speed
    # Solar wind speed is assumed to be 400 km/s
    # Angle is minus as y in the coordinate system points away from the orbital velocity
    aberration_angle = np.arctan(
        orbital_velocity / hermpy.utils.Constants.SOLAR_WIND_SPEED_AVG
    )

    return aberration_angle


def aberrate_position(position: list[float], date: dt.datetime | dt.date):
    aberration_angle = get_aberration_angle(date)

    rotation_matrix = np.array(
        [
            [np.cos(aberration_angle), -np.sin(aberration_angle), 0],
            [np.sin(aberration_angle), np.cos(aberration_angle), 0],
            [0, 0, 1],
        ]
    )

    rotated_position = np.matmul(rotation_matrix, position)

    return rotated_position


def bepi_probabilities(
    n_clicks,
    crossing_list_selection,
    spacecraft_selection,
    start_time,
    end_time,
    time_cadence,
    grid_density,
):
    if n_clicks == 0:
        return

    constants = {
        "DIPOLE_OFFSET_KM": 479,
        "MERCURY_RADIUS_KM": 2439.7,
    }

    # Make sure times are formatted correctly
    try:
        start_time = dt.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return

    try:
        end_time = dt.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return

    # Load Bepi trajectory between these times
    kernels_dir = (
        pathlib.Path(os.path.dirname(__file__)) / "resources" / "spice" / "kernels"
    )
    metakernel_path = kernels_dir / "mk" / "bc_plan.tm"

    mk = pc.MetaKernel(metakernel_path, kernels=kernels_dir)
    with spice.KernelPool(mk):
        resolution = dt.timedelta(seconds=int(time_cadence))
        times = [
            start_time + i * resolution
            for i in range(round((end_time - start_time) / resolution))
        ]
        spice_times = spice.datetime2et(times)

        positions, _ = spice.spkpos(
            spacecraft_selection,
            spice_times,
            "BC_MSO",  # We do aberration ourselves as spice is bad at it
            "NONE",
            "MERCURY",
        )

        # We want the positions in MSM' coordinates, not MSO', and must add
        # 479 km to Z.
        positions[:, 2] += constants["DIPOLE_OFFSET_KM"]

        # Convert to radii
        positions /= constants["MERCURY_RADIUS_KM"]

        trajectory = pd.DataFrame(
            {
                "Time": times,
                "X MSM'": positions[:, 0],
                "Y MSM'": positions[:, 1],
                "Z MSM'": positions[:, 2],
                "CYL MSM'": np.sqrt(positions[:, 1] ** 2 + positions[:, 2] ** 2),
            }
        )

        # We want to aberrate these positions on each unique day
        # Split up trajectory by date
        trajectory_groups = {
            day: group for day, group in trajectory.groupby(trajectory["Time"].dt.date)
        }

        for day in trajectory_groups.keys():
            trajectory_group = trajectory_groups[day]

            aberrated_positions = np.array(
                [
                    aberrate_position(
                        [position["X MSM'"], position["Y MSM'"], position["Z MSM'"]],
                        day,
                    )
                    for _, position in trajectory_group[
                        ["X MSM'", "Y MSM'", "Z MSM'"]
                    ].iterrows()
                ]
            )
            trajectory_group["X MSM'"] = aberrated_positions[:, 0]
            trajectory_group["Y MSM'"] = aberrated_positions[:, 1]
            trajectory_group["Z MSM'"] = aberrated_positions[:, 2]

        trajectory = pd.concat(trajectory_groups.values(), axis=0)
        trajectory = trajectory.sort_values("Time")

    match crossing_list_selection:
        case "Hollman+ 2025":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_hollman.nc"
            )
        case "Philpott+ 2020":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_philpott.nc"
            )

        case "90 < TAA < 270":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_from_direct_input_taa_90_270.nc"
            )

        case "270 < TAA < 90":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_from_direct_input_taa_n90_90.nc"
            )

        case _:
            raise ValueError("Invalid dropdown selection")

    x_data = trajectory["X MSM'"]
    cyl_data = trajectory["CYL MSM'"]

    regions = ["Solar Wind", "Magnetosheath", "Magnetosphere"]

    trajectory_probabilities = {
        region: np.zeros_like(x_data, dtype=float) for region in regions
    }
    # trajectory_probabilities_uncertainty = {
    #     region: np.zeros_like(x_data, dtype=float) for region in regions
    # }

    # Interpolate if grid_density is not one
    bin_size = (
        selected_probability_map.coords["X"][1]
        - selected_probability_map.coords["X"][0]
    )

    new_x_coords = np.arange(
        selected_probability_map.coords["X"][0],
        selected_probability_map.coords["X"][-1] + bin_size / grid_density,
        bin_size / grid_density,
    )
    new_cyl_coords = np.arange(
        selected_probability_map.coords["CYL"][0],
        selected_probability_map.coords["CYL"][-1] + bin_size / grid_density,
        bin_size / grid_density,
    )

    selected_probability_map = selected_probability_map.interp(
        coords={"X": new_x_coords, "CYL": new_cyl_coords}
    )

    # Recalculate binsize
    bin_size = (
        selected_probability_map.coords["X"][1]
        - selected_probability_map.coords["X"][0]
    )

    x_coords = selected_probability_map.coords["X"].values
    cyl_coords = selected_probability_map.coords["CYL"].values

    # Create bin edges (add one extra edge at the end for np.digitize)
    # Resolves floating point precision issues
    x_bins = np.concatenate([x_coords, [x_coords[-1] + bin_size]])
    cyl_bins = np.concatenate([cyl_coords, [cyl_coords[-1] + bin_size]])

    # Digitize the trajectory data into bin indices
    x_indices = np.digitize(x_data, x_bins) - 1
    cyl_indices = np.digitize(cyl_data, cyl_bins) - 1

    # Iterate over trajectory points and assign probabilities
    for i in range(len(x_data)):
        x_index = x_indices[i]
        cyl_index = cyl_indices[i]

        # Ensure the index is within the valid histogram range
        if 0 <= x_index < len(x_bins) - 1 and 0 <= cyl_index < len(cyl_bins) - 1:
            for region in regions:
                trajectory_probabilities[region][i] = selected_probability_map[
                    f"{region.replace(' ', '_').lower()}_mean"
                ][x_index, cyl_index]

        else:
            for region in regions:
                trajectory_probabilities[region][
                    i
                ] = np.nan  # Assign NaN if out of bounds

    probabilities = pd.DataFrame(trajectory_probabilities)
    probabilities["Time"] = trajectory["Time"]

    # Reorder columns
    probabilities = probabilities[
        ["Time", "Solar Wind", "Magnetosheath", "Magnetosphere"]
    ]

    # Plotting
    colours = ["#F0E442", "#E69F00", "#56B4E9"]
    time_series_fig = px.line(
        probabilities, x="Time", y=regions, color_discrete_sequence=colours
    )

    time_series_fig.update_layout(template="simple_white")

    time_series_fig.update_yaxes(title_text="Region Probability")

    # We want to save these time series to a tmp filepath
    start_time = dt.datetime.strftime(start_time, "%Y%m%d_%H%M%S")
    end_time = dt.datetime.strftime(end_time, "%Y%m%d_%H%M%S")

    download_path = (
        pathlib.Path(os.path.dirname(__file__))
        / "tmp"
        / f"{spacecraft_selection}_region_probabilities_{start_time}_{end_time}.csv"
    )

    probabilities.to_csv(download_path, index=False)

    # Trajectory panels
    trajectory_fig = plotly.subplots.make_subplots(
        rows=1, cols=3, subplot_titles=regions
    )

    cmap = plt.cm.get_cmap("viridis")
    norm = matplotlib.colors.Normalize(vmin=0, vmax=1)

    for i, region_name in enumerate(regions):
        x_pairs = itertools.pairwise(trajectory["X MSM'"])
        cyl_pairs = itertools.pairwise(trajectory["CYL MSM'"])

        colours = [
            matplotlib.colors.to_hex(cmap(norm(p))) if not np.isnan(p) else None
            for p in probabilities[region_name]
        ]

        # Add light trajectory in grey
        trajectory_fig.add_trace(
            go.Scatter(
                x=trajectory["X MSM'"],
                y=trajectory["CYL MSM'"],
                mode="lines",
                line=dict(color="lightgrey", width=3),
                showlegend=False,
            ),
            row=1,
            col=i + 1,
        )

        # Overlay with colour based on region prediction
        for x, cyl, colour in zip(x_pairs, cyl_pairs, colours):
            if colour is None:
                continue

            trajectory_fig.add_trace(
                go.Scatter(
                    x=x,
                    y=cyl,
                    mode="lines",
                    line=dict(color=colour, width=6),
                    showlegend=False,
                ),
                row=1,
                col=i + 1,
            )

        # Add Mercury
        circle_params = dict(
            fillcolor="rgba(0,0,0,0)",
            opacity=1,
            line=dict(color="rgba(0,0,0,1)", width=3),
            row=1,
            col=i + 1,
        )
        trajectory_fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=-1,
            y0=-1 - hermpy.utils.Constants.DIPOLE_OFFSET_RADII,
            x1=1,
            y1=1 - hermpy.utils.Constants.DIPOLE_OFFSET_RADII,
            **circle_params,
        )
        trajectory_fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=-1,
            y0=-1 + hermpy.utils.Constants.DIPOLE_OFFSET_RADII,
            x1=1,
            y1=1 + hermpy.utils.Constants.DIPOLE_OFFSET_RADII,
            **circle_params,
        )

        # Add axis labels for each subplot
        trajectory_fig.update_xaxes(
            title_text=r"$X_{\rm MSM'} \quad \left[ \text{R}_\text{M} \right]$",
            row=1,
            col=i + 1,
        )
        trajectory_fig.update_yaxes(
            title_text=r"$\left( Y_{\text{MSM'}}^2 + Z_{\text{MSM'}}^2 \right)^{0.5} \quad \left[ \text{R}_\text{M} \right]$",
            row=1,
            col=i + 1,
        )

        trajectory_fig.update_xaxes(range=[-5, 5])
        trajectory_fig.update_yaxes(range=[0, 8])

        trajectory_fig.update_layout(template="simple_white")

        # Force equal aspect
        trajectory_fig.update_yaxes(
            scaleanchor=f"x{i + 1}",
            scaleratio=1,
            row=1,
            col=i + 1,
        )

        # Remove margins
        trajectory_fig.update_xaxes(constrain="domain")
        trajectory_fig.update_yaxes(constrain="domain")

        # Add magnetospheric boundaries
        plot_magnetospheric_boundaries(trajectory_fig, 1, i + 1)

    # A fake scatter to add a colourbar
    trajectory_fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(
                colorscale="Viridis",
                cmin=0,
                cmax=1,
                color=[0, 1],
                colorbar=dict(title=""),
            ),
            showlegend=False,
        )
    )

    return time_series_fig, trajectory_fig


def load_probability_maps(dropdown_value, grid_density):
    match dropdown_value:
        case "Hollman+ 2025":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_hollman.nc"
            )
        case "Philpott+ 2020":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_philpott.nc"
            )

        case "90 < TAA < 270":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_from_direct_input_taa_90_270.nc"
            )

        case "270 < TAA < 90":
            selected_probability_map = xr.load_dataset(
                pathlib.Path(os.path.dirname(__file__))
                / "create_probability_maps"
                / "output"
                / "region_maps_from_direct_input_taa_n90_90.nc"
            )

        case _:
            raise ValueError("Invalid dropdown selection")

    regions = ["Solar Wind", "Magnetosheath", "Magnetosphere"]

    fig = plotly.subplots.make_subplots(rows=1, cols=3, subplot_titles=regions)

    for i, region_name in enumerate(regions):
        data = selected_probability_map[
            f"{region_name.replace(' ', '_').lower()}_mean"
        ].T

        data.values[np.where(data.values == 0)] = np.nan

        # Interpolate if grid_density is not one
        bin_size = data.coords["X"][1] - data.coords["X"][0]

        new_x_coords = np.arange(
            data.coords["X"][0],
            data.coords["X"][-1] + bin_size / grid_density,
            bin_size / grid_density,
        )
        new_cyl_coords = np.arange(
            data.coords["CYL"][0],
            data.coords["CYL"][-1] + bin_size / grid_density,
            bin_size / grid_density,
        )

        data = data.interp(coords={"X": new_x_coords, "CYL": new_cyl_coords})

        fig.add_trace(
            go.Heatmap(
                z=data.values,
                x=data.coords["X"],
                y=data.coords["CYL"],
                colorscale="greys_r",
            ),
            row=1,
            col=i + 1,
        )

        # Add axis labels for each subplot
        fig.update_xaxes(
            title_text=r"$X_{\rm MSM'} \quad \left[ \text{R}_\text{M} \right]$",
            row=1,
            col=i + 1,
        )
        fig.update_yaxes(
            title_text=r"$\left( Y_{\text{MSM'}}^2 + Z_{\text{MSM'}}^2 \right)^{0.5} \quad \left[ \text{R}_\text{M} \right]$",
            row=1,
            col=i + 1,
        )

        fig.update_layout(template="simple_white")
        fig.update_layout(plot_bgcolor="lightgrey")

        # Force equal aspect
        fig.update_yaxes(
            scaleanchor=f"x{i + 1}",
            scaleratio=1,
            row=1,
            col=i + 1,
        )

        # Remove margins
        fig.update_xaxes(constrain="domain")
        fig.update_yaxes(constrain="domain")

    return fig


def download_time_series(n_clicks, spacecraft, start_time, end_time):
    # Make sure times are formatted correctly
    try:
        start_time = dt.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return

    try:
        end_time = dt.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return

    start_time = dt.datetime.strftime(start_time, "%Y%m%d_%H%M%S")
    end_time = dt.datetime.strftime(end_time, "%Y%m%d_%H%M%S")

    download_path = (
        pathlib.Path(os.path.dirname(__file__))
        / "tmp"
        / f"{spacecraft}_region_probabilities_{start_time}_{end_time}.csv"
    )

    data = pd.read_csv(download_path)

    return data, f"{spacecraft}_region_probabilities_{start_time}_{end_time}.csv"
