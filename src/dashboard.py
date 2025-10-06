import sys

import dash
import dash_iconify as dicons
import waitress

import backend

if len(sys.argv) == 2:
    num_threads = int(sys.argv[1])
else:
    num_threads = 4  # waitress.serve default

app = dash.Dash(
    "DIAS BepiColombo Region Prediction",
)

about_layout = dash.html.Div(
    [
        dash.html.H1("About"),
        dash.html.P(
            "BepiColombo is a two-spacecraft mission due to arrive at Mercury in December 2026. When planning for spacecraft operations (e.g. instrument modes and/or pointing), it can be important for many science goals to determine within which magnetospheric region each of the spacecraft will be in. Previously, Mercury was orbited by the MESSENGER spacecraft between 2011 and 2015. Automated and manual methods have been applied to magnetometer data to determine where MESSENGER crossed the bow shock and magnetopause. Based on these crossing detections, we can determine whether MESSENGER was in the solar wind, the magnetosheath, or the magnetosphere. From these region determinations over the whole mission, we can construct probability maps to determine statistically how likely it is for a spacecraft to be in each region for a given location."
        ),
        dash.html.Div(
            [
                dash.dcc.Link(
                    children=dicons.DashIconify(icon="ion:logo-github"),
                    href="https://github.com/daraghhollman/bepi-prediction-dashboard",
                    className="icon",
                ),
                dash.dcc.Link(
                    children=dicons.DashIconify(icon="fluent:mail"),
                    href="https://github.com/daraghhollman/bepi-prediction-dashboard",
                    className="icon",
                ),
            ],
            className="icon-container",
        ),
    ]
)

probability_maps_layout = dash.html.Div(
    [
        dash.html.H1("Region Probability Maps"),
        dash.html.H2("Select a probability map"),
        dash.dcc.Dropdown(
            ["Hollman+ 2025", "Philpott+ 2020"],
            "Hollman+ 2025",
            id="crossing_list_choice",
            clearable=False,
            style={"width": "250px"},
            className="dropdown",
        ),
        dash.dcc.Upload(
            id="upload-probability-map",
            children=dash.html.Div(
                ["or ", dash.html.A("upload file", className="url")]
            ),
        ),
        dash.html.P(
            "Choose a crossing list to construct region probability maps. These probability maps have been previously computed based on region predictions during the entire MESSENGER mission (sampled every 5 seconds). Two crossing lists are implimented, the Hollman et al. (submitted, 2025) crossing list, and the Philpott et al. (2020) crossing intervals list. Probability maps may also be loaded from file provided they follow the correct format."
        ),
        # Smoothing
        dash.html.P("We can smooth these maps with simple linear interpolation."),
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
                    "template": "Bin Size: 0.25 / {value} radii",
                },
            ),
            style={"width": "30pc"},
        ),
        dash.html.Div(
            [
                dash.dcc.Loading(
                    dash.dcc.Graph(id="probability_maps", mathjax=True),
                ),
            ]
        ),
    ]
)

probability_time_series_layout = dash.html.Div(
    [
        dash.html.H1("Prediction"),
        dash.dcc.Dropdown(
            ["MPO", "MMO"],
            "MPO",
            id="spacecraft_choice",
            clearable=False,
            style={"width": "250px"},
            className="dropdown",
        ),
        dash.html.P(
            "Select a BepiColombo spacecraft to query for. For times prior to planned orbital insersion (December 2026), MPO and MMO will both yeild the same result. Select a start time and end time (format: YYYY-MM-DD HH:MM:SS) and a time cadence to sample the trajectory (default: every 60 seconds). Please be patient for large queries with a small time cadence."
        ),
        dash.dcc.Input(
            id="start_time",
            type="text",  # user types freely
            value="2023-06-19 18:30:00",
            placeholder="Start: YYYY-MM-DD HH:MM:SS",
            style={"width": "20pc"},
        ),
        dash.dcc.Input(
            id="end_time",
            type="text",  # user types freely
            value="2023-06-19 20:00:00",
            placeholder="End: YYYY-MM-DD HH:MM:SS",
            style={"width": "20pc"},
        ),
        dash.dcc.Input(
            id="time-cadence",
            type="text",
            value="60",
            placeholder="Time Cadence (seconds)",
            style={"width": "10pc"},
        ),
        dash.html.Button("Predict", id="predict-button", className="button"),
        dash.html.Div(
            [
                dash.html.H2("Trajectory Overlay"),
                dash.dcc.Loading(
                    dash.html.Div(
                        [
                            dash.dcc.Graph(id="bepi_trajectory", mathjax=True),
                        ]
                    ),
                ),
                dash.html.H2("Extracted Time Series"),
                dash.dcc.Loading(
                    dash.html.Div(
                        [
                            dash.dcc.Graph(id="bepi_time_series", mathjax=True),
                        ]
                    ),
                ),
                dash.html.Button(
                    "Download Time Series",
                    id="download-time-series-button",
                    className="button",
                ),
                dash.dcc.Download(id="download-time-series-csv"),
            ]
        ),
    ]
)

app.layout = dash.html.Div(
    [
        dash.html.H1(
            children="BepiColombo Prediction Dashboard",
            style={"textAlign": "center"},
            className="title",
        ),
        dash.html.Div(about_layout, className="card"),
        dash.html.Div(probability_maps_layout, className="card"),
        dash.html.Div(probability_time_series_layout, className="card"),
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
    [
        dash.Output("bepi_time_series", "figure"),
        dash.Output("bepi_trajectory", "figure"),
    ],
    dash.Input("predict-button", "n_clicks"),
    dash.Input("crossing_list_choice", "value"),
    dash.Input("spacecraft_choice", "value"),
    dash.State("start_time", "value"),
    dash.State("end_time", "value"),
    dash.State("time-cadence", "value"),
    dash.Input("smooth-density", "value"),
)
def bepi_probabilities(
    n_clicks,
    crossing_list_selection,
    spacecraft_choice,
    start_time,
    end_time,
    time_cadence,
    smooth_density,
):
    return backend.bepi_probabilities(
        n_clicks,
        crossing_list_selection,
        spacecraft_choice,
        start_time,
        end_time,
        time_cadence,
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
    # waitress.serve(app.server, host="0.0.0.0", port=8050, threads=num_threads)
    app.run(debug=True)
