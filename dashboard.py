import dash
import dash_daq

import backend

app = dash.Dash("BepiColombo Region Prediction")

probability_maps_layout = dash.html.Div(
    [
        dash.html.P("Choose a crossing list to construct region probability maps"),
        dash.dcc.Dropdown(
            ["Hollman+ 2025", "Philpott+ 2020"],
            "Hollman+ 2025",
            id="crossing_list_choice",
            clearable=False,
            style={"width": "250px"},
        ),
        # Smoothing
        dash.html.P("We can smooth these maps with interpolation"),
        dash.html.Div(
            dash.dcc.Slider(
                min=1,
                max=10,
                step=0.5,
                value=1,
                marks={i: str(i) for i in range(11)},
                id="smooth-density",
                tooltip={
                    "always_visible": False,
                    "template": "Grid Density Multiplier",
                },
            ),
            style={"width": "30pc"},
        ),
        dash.html.Div(
            [
                dash.html.H4("Region Probability Maps"),
                dash.dcc.Graph(id="probability_maps", mathjax=True),
            ]
        ),
    ]
)

app.layout = dash.html.Div(
    [
        dash.html.H1(
            children="BepiColombo Prediction Dashboard", style={"textAlign": "center"}
        ),
        probability_maps_layout,
        dash.html.P("Select a spacecraft to plot"),
        dash.dcc.Dropdown(
            ["MPO", "MMO"],
            "MPO",
            id="spacecraft_choice",
        ),
        dash.dcc.Input(
            id="start_time",
            type="text",  # user types freely
            value="2023-06-19 18:30:00",
            placeholder="Start: YYYY-MM-DD HH:MM:SS",
            style={"width": "250px"},
        ),
        dash.dcc.Input(
            id="end_time",
            type="text",  # user types freely
            value="2023-06-19 20:00:00",
            placeholder="End: YYYY-MM-DD HH:MM:SS",
            style={"width": "250px"},
        ),
        dash.html.Button("Predict", id="predict-button"),
        dash.html.Div(
            [
                dash.html.H4("Trajectory Overlay"),
                dash.dcc.Graph(id="trajectory_overlay", mathjax=True),
                dash.html.Button(
                    "Download Time Series", id="download-time-series-button"
                ),
                dash.dcc.Download(id="download-time-series-csv"),
            ]
        ),
    ]
)


@app.callback(
    dash.Output("probability_maps", "figure"),
    dash.Input("crossing_list_choice", "value"),
    dash.Input("smooth-density", "value"),
)
def load_probability_maps(dropdown_value, grid_density):
    return backend.load_probability_maps(dropdown_value, grid_density)


@app.callback(
    dash.Output("trajectory_overlay", "figure"),
    dash.Input("predict-button", "n_clicks"),
    dash.Input("crossing_list_choice", "value"),
    dash.Input("spacecraft_choice", "value"),
    dash.State("start_time", "value"),
    dash.State("end_time", "value"),
    dash.Input("smooth-density", "value"),
)
def overlay_trajectory(
    n_clicks,
    crossing_list_selection,
    spacecraft_choice,
    start_time,
    end_time,
    smooth_density,
):
    return backend.overlay_trajectory(
        n_clicks,
        crossing_list_selection,
        spacecraft_choice,
        start_time,
        end_time,
        smooth_density,
    )


# Every time the overlay trajectory function is called, a tmpfile is created
# with the plotted data
@app.callback(
    dash.Output("download-time-series-csv", "data"),
    dash.Input("download-time-series-button", "n_clicks"),
    dash.State("spacecraft_choice", "value"),
    dash.State("start_time", "value"),
    dash.State("end_time", "value"),
    prevent_initial_call=True,
)
def download_time_series(n_clicks, spacecraft, start_time, end_time):
    data, filename = backend.download_time_series(
        n_clicks, spacecraft, start_time, end_time
    )

    return dash.dcc.send_data_frame(
        data.to_csv,
        filename=filename,
        index=False,
    )


if __name__ == "__main__":
    app.run(debug=True)
