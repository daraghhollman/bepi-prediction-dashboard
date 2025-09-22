import dash

import backend

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
        dash.dcc.Dropdown(
            ["MPO", "MMO"],
            "MPO",
            id="spacecraft_choice",
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
        dash.html.Div(
            [
                dash.html.H4("Trajectory Overlay"),
                dash.dcc.Graph(id="trajectory_overlay", mathjax=True),
            ]
        ),
    ]
)


@app.callback(
    dash.Output("probability_maps", "figure"),
    dash.Input("crossing_list_choice", "value"),
)
def load_probability_maps(dropdown_value):
    return backend.load_probability_maps(dropdown_value)


@app.callback(
    dash.Output("trajectory_overlay", "figure"),
    dash.Input("predict-button", "n_clicks"),
    dash.State("crossing_list_choice", "value"),
    dash.State("spacecraft_choice", "value"),
    dash.State("start_time", "value"),
    dash.State("end_time", "value"),
)
def overlay_trajectory(
    n_clicks, crossing_list_selection, spacecraft_choice, start_time, end_time
):
    return backend.overlay_trajectory(
        n_clicks, crossing_list_selection, spacecraft_choice, start_time, end_time
    )


if __name__ == "__main__":
    app.run(debug=True)
