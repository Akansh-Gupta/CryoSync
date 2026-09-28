# CRYOSYNC

CRYOSYNC is an offline-first energy intelligence prototype for a polar research
station. It contains a digital twin, forecasting, dispatch optimization,
anomaly detection, health scoring, alerts, a FastAPI service, and a Streamlit
dashboard.

## 1. Prerequisites

- Windows 10/11
- Python 3.11 or newer
- PowerShell
- Git, if you are downloading the repository with Git

The supplied `Dockerfile` uses Python 3.11. Python 3.13 also works with the
current dependency set when running locally.

## 2. Open the project directory

Open PowerShell and run:

```powershell
cd "path\to\cryosync"
```

## 3. Create and activate a virtual environment

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

After activation, the terminal prompt should show `(.venv)`.

## 4. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
```

The main packages are:

- Prophet and XGBoost for forecasting
- PuLP and SciPy for optimization
- scikit-learn for anomaly detection
- FastAPI/Uvicorn for the API
- Streamlit and Plotly for the dashboard

## 5. Choose the data workflow

### Option A: Generate the digital-twin dataset

Use this for a clean synthetic simulation:

```powershell
python run_twin.py
```

This generates `data/master_dataset.csv` from the weather, occupancy, load,
solar, wind, battery, and diesel models.

To use a real weather CSV instead of the built-in synthetic weather source,
pass its path as the first argument:

```powershell
python run_twin.py path\to\weather.csv
```

### Option B: Keep an edited master dataset

If `data/master_dataset.csv` has been edited manually, do **not** run
`run_twin.py`, because it regenerates and overwrites that file. Run only:

```powershell
python run_pipeline.py
```

The pipeline reads the existing master dataset and retrains/regenerates:

- `data/forecast.csv`
- `data/dispatch_plan.csv`
- `data/anomalies.csv`
- `data/maintenance.csv`
- `data/alerts.csv`

## 6. Run tests

```powershell
python -m pytest -q
```

## 7. Run the dashboard

Open a second PowerShell window:

```powershell
cd "path\to\cryosync"
.\.venv\Scripts\Activate.ps1
streamlit run dashboard/app.py
```

Open the displayed URL, normally:

```text
http://localhost:8501
```

The dashboard includes live replay, power-mix graphs, forecasts, anomaly
calendar filtering, categorized anomalies, alert read/unread controls, and
dispatch information.

## 8. Run the API (optional)

Open another PowerShell window:

```powershell
cd "path\to\cryosync"
.\.venv\Scripts\Activate.ps1
uvicorn api.main:app --reload
```

API URLs:

- API: <http://localhost:8000>
- Interactive API documentation: <http://localhost:8000/docs>
- Status endpoint: <http://localhost:8000/status>
- Forecast endpoint: <http://localhost:8000/forecast>
- Dispatch endpoint: <http://localhost:8000/dispatch-plan>

The API synchronizes pipeline data into SQLite by default. Set
`DATABASE_URL` to a PostgreSQL connection string when PostgreSQL is required.

## 9. Run with Docker

Build and start the API container from the project root:

```powershell
docker build -t cryosync .
docker run --rm -p 8000:8000 cryosync
```

The container exposes the FastAPI service at <http://localhost:8000>. The
Streamlit dashboard is intended to run locally with the command above.

## 10. Stop the services

In the terminal running Streamlit or Uvicorn, press:

```text
Ctrl+C
```

If a detached dashboard is still using port `8501`, run:

```powershell
$listeners = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
$listeners | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
	Stop-Process -Id $_ -Force
}
```

## 11. Architecture diagrams

- [Overall architecture diagram](docs/cryosync-architecture.svg)
- [Runtime sequence diagram](docs/cryosync-runtime-sequence.svg)

## Project flow

```text
Weather + occupancy
		-> digital twin loads and generation
		-> master_dataset.csv
		-> forecasting and dispatch optimization
		-> anomaly detection, health scoring, and alerts
		-> Streamlit dashboard and FastAPI service
```
