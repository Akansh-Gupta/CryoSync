"""Filesystem layout for the CRYOSYNC dashboard.

The dashboard reads the artefacts produced by the digital twin and the
downstream pipeline. This module is the single place that knows where those
files live, and it makes the pipeline packages importable no matter which
directory the Streamlit server was started from.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
ROOT = DASHBOARD_DIR.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "polaris.db"
ASSUMPTIONS_PATH = DATA_DIR / "operator_assumptions.json"

# twin/, forecasting/, optimization/, anomaly/, alerts/, control/, validation/
# and api/ all live at the project root, one level above this package.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class PipelineFile:
    """One artefact written by run_twin.py or run_pipeline.py."""

    key: str
    filename: str
    label: str
    description: str
    producer: str
    cadence: str

    @property
    def path(self) -> Path:
        return DATA_DIR / self.filename

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def size_kb(self) -> float:
        if not self.exists:
            return 0.0
        return round(self.path.stat().st_size / 1024, 1)


PIPELINE_FILES: tuple[PipelineFile, ...] = (
    PipelineFile(
        key="master",
        filename="master_dataset.csv",
        label="Master dataset",
        description="Hour-by-hour digital twin state for one simulated year.",
        producer="run_twin.py",
        cadence="hourly",
    ),
    PipelineFile(
        key="forecast",
        filename="forecast.csv",
        label="Forecast",
        description="Next 24 hours of load, solar and wind with confidence bounds.",
        producer="forecasting/forecast_engine.py",
        cadence="24 h horizon",
    ),
    PipelineFile(
        key="dispatch",
        filename="dispatch_plan.csv",
        label="Dispatch plan",
        description="Fuel-minimising battery, solar and diesel schedule.",
        producer="optimization/optimizer.py",
        cadence="24 h horizon",
    ),
    PipelineFile(
        key="alerts",
        filename="alerts.csv",
        label="Alerts",
        description="Deterministic operator alerts raised by the rule engine.",
        producer="alerts/alert_rules.py",
        cadence="event driven",
    ),
    PipelineFile(
        key="anomalies",
        filename="anomalies.csv",
        label="Anomalies",
        description="IsolationForest plus physical sanity rule detections.",
        producer="anomaly/anomaly_detector.py",
        cadence="trailing 168 h",
    ),
    PipelineFile(
        key="maintenance",
        filename="maintenance.csv",
        label="Maintenance",
        description="Battery and generator health scores with recommendations.",
        producer="anomaly/health_scoring.py",
        cadence="trailing 168 h",
    ),
    PipelineFile(
        key="test_forecast",
        filename="test_forecast.csv",
        label="Backtest forecast",
        description="Held-out XGBoost forecast used by the test suite.",
        producer="tests/test_modules.py",
        cadence="24 h horizon",
    ),
)


def pipeline_file(key: str) -> PipelineFile:
    """Return the pipeline artefact registered under ``key``."""

    for artefact in PIPELINE_FILES:
        if artefact.key == key:
            return artefact

    raise KeyError(f"Unknown pipeline artefact: {key}")
