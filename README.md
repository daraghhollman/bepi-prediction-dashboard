# BepiColombo Prediction Dashboard

write a decription here

## Installation

### Clone this repository:

**HTTPS**
```shell
git clone --recurse-submodules --shallow-submodules https://github.com/daraghhollman/bepi-prediction-dashboard.git
cd bepi-prediction-dashboard
```

**SSH**
```shell
git clone --recurse-submodules --shallow-submodules git@github.com:daraghhollman/bepi-prediction-dashboard.git
cd bepi-prediction-dashboard
```

This will download the repository code along with the ESA Bitbucket repository
for required BepiColombo SPICE kernels (~3 GiB).

### Download required crossing lists

Crossing lists implemented include the Hollman et al. (submitted, 2025) list
and the Philpott et al. (2020) intervals list.

```shell
curl 'https://zenodo.org/records/15797283/files/hollman_2025_crossing_list.csv?download=1' > ./src/resources/hollman_2025_crossing_list.csv
```

Unfortunately, the Philpott crossing list is not available for automatic
download. It must be manually downloaded from supporting information at:
<https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2019JA027544>

Download 'Table S1' and move to `./src/resources/philpott_2020.xlsx`

## Running

Deploy locally with:

```shell
uv run python src/dashboard.py
```

to automatically manage the environment, or, create a virtual environment and
install the dependencies as listed in `pyproject.toml`.

Access via: <localhost:8050>
