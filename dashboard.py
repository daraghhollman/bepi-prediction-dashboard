import datetime as dt
import os
import pathlib

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.subplots
import xarray as xr

app = dash.Dash("BepiColombo Region Prediction")

app.layout = dash.html.Div(
    [
        dash.html.H1(
            children="BepiColombo Prediction Dashboard", style={"textAlign": "center"}
        ),
        dash.dcc.Dropdown(
            ["Hollman+ 2025", "Philpott+ 2020"],
            "Hollman+ 2025",
            id="crossing_list_choice",
        ),
        dash.dcc.Input(
            id="start_time",
            type="text",  # user types freely
            placeholder="Start: YYYY-MM-DD HH:MM:SS",
            style={"width": "250px"},
        ),
        dash.dcc.Input(
            id="end_time",
            type="text",  # user types freely
            placeholder="End: YYYY-MM-DD HH:MM:SS",
            style={"width": "250px"},
        ),
        dash.html.Button("Predict", id="predict-button"),
        dash.html.Div(
            [
                dash.html.H4("Region Probability Maps"),
                dash.dcc.Graph(id="probability_maps", mathjax=True),
            ]
        ),
    ]
)


@app.callback(
    dash.Output("probability_maps", "figure"),
    dash.Input("crossing_list_choice", "value"),
)
def load_probability_maps(dropdown_value):
    # Load probability maps into memory
    hollman_map = xr.load_dataset(
        pathlib.Path(os.path.dirname(__file__))
        / "create_probability_maps"
        / "output"
        / f"region_maps_hollman.nc"
    )
    philpott_map = xr.load_dataset(
        pathlib.Path(os.path.dirname(__file__))
        / "create_probability_maps"
        / "output"
        / f"region_maps_philpott.nc"
    )

    match dropdown_value:
        case "Hollman+ 2025":
            selected_probability_map = hollman_map
        case "Philpott+ 2020":
            selected_probability_map = philpott_map

        case _:
            raise ValueError("Invalid dropdown selection")

    regions = ["Solar Wind", "Magnetosheath", "Magnetosphere"]

    fig = plotly.subplots.make_subplots(rows=1, cols=3, subplot_titles=regions)

    for i, region_name in enumerate(regions):

        data = selected_probability_map[
            f"{region_name.replace(' ', "_").lower()}_mean"
        ].T

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
        fig.update_xaxes(title_text=r"$X_{\rm MSM'}$ [$R_M$]", row=1, col=i + 1)
        fig.update_yaxes(
            title_text=r"$\left( Y_{\text{MSM'}}^2 + Z_{\text{MSM'}}^2 \right)^{0.5} \quad \left[ \text{R}_\text{M} \right]$",
            row=1,
            col=i + 1,
        )

        fig.update_layout(template="simple_white")
        fig.update_layout(plot_bgcolor="lightgrey")

    return fig


"""
@app.callback(
    dash.Output("output-div", "children"),
    dash.Input("predict-button", "n_clicks"),
    dash.State("crossing_list_choice", "value"),
    dash.State("start_time", "value"),
    dash.State("end_time", "value"),
)
def overlay_trajectory(n_clicks, dropdown_value, start_time, end_time):

    try:
        start_time = dt.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return f"Invalid datetime format: {start_time}"

    try:
        end_time = dt.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return f"Invalid datetime format: {end_time}"

    return f"{dropdown_value}"
"""


if __name__ == "__main__":
    app.run(debug=True)
