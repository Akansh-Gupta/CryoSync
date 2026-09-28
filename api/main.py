"""CRYOSYNC API — offline-first energy intelligence API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sys
import json
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.db import get_engine, init_db, upsert_json


# -------------------------------------------------------------------
# DATABASE
# -------------------------------------------------------------------

def ensure_integration_tables() -> None:
    """Create M10 integration tables if they do not already exist."""

    engine = init_db()

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS operator_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT
                )
                """
            )
        )


def sync_pipeline_data() -> None:
    """
    Persist pipeline-generated readings and forecasts into the local DB.

    CSV files remain the pipeline source.
    SQLite becomes the local persistence layer.
    """

    sync_table(
        ROOT / "data" / "master_dataset.csv",
        "hourly_readings",
        "readings",
    )

    sync_table(
        ROOT / "data" / "forecast.csv",
        "forecasts",
        "forecasts",
    )


# -------------------------------------------------------------------
# APP LIFECYCLE
# -------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize the local database and synchronize pipeline outputs
    whenever the API starts.
    """

    init_db()
    ensure_integration_tables()
    sync_pipeline_data()

    print("[M10] CRYOSYNC database integration ready.")

    yield


app = FastAPI(
    title="CRYOSYNC API",
    version="1.0.0",
    description="Offline-first polar station energy intelligence API",
    lifespan=lifespan,
)


# -------------------------------------------------------------------
# DATA LOADERS
# -------------------------------------------------------------------

def load_master_dataset() -> pd.DataFrame:
    path = ROOT / "data" / "master_dataset.csv"

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(
        path,
        parse_dates=["timestamp"],
    )


def load_forecast() -> pd.DataFrame:
    path = ROOT / "data" / "forecast.csv"

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(
        path,
        parse_dates=["timestamp"],
    )


def load_alerts_from_pipeline() -> pd.DataFrame:
    path = ROOT / "data" / "alerts.csv"

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def dataframe_to_records(
    df: pd.DataFrame,
) -> list[dict[str, Any]]:

    if df.empty:
        return []

    records = df.copy()

    for column in records.columns:
        if pd.api.types.is_datetime64_any_dtype(records[column]):
            records[column] = records[column].astype(str)

    records = records.where(pd.notnull(records), None)

    return records.to_dict(orient="records")


def load_first_available_csv(
    paths: list[Path],
) -> list[dict[str, Any]]:
    """Return records from the first readable CSV in paths, or [] if none."""

    for path in paths:

        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
            return dataframe_to_records(df)

        except Exception as exc:
            print(f"[M10] Could not read {path.name}: {exc}")
            continue
    return []


def sync_table(path: Path, table_name: str, label: str) -> None:
    """Load a pipeline CSV (if present) and upsert each row into table_name."""

    if not path.exists():
        return
    try:
        df = pd.read_csv(
            path,
            parse_dates=["timestamp"],
        )

        for record in dataframe_to_records(df):
            timestamp = str(record.get("timestamp"))

            if timestamp and timestamp != "None":
                upsert_json(
                    table_name,
                    timestamp,
                    record,
                )

    except Exception as exc:
        print(f"[M10] Could not sync {label}: {exc}")


def json_safe(value: Any) -> Any:
    """Convert pandas / numpy values into JSON-safe Python values."""


    if value is None:
        return None

    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value
# -------------------------------------------------------------------
# STATUS
# -------------------------------------------------------------------

@app.get("/status")
def get_status():

    df = load_master_dataset()

    if df.empty:
        return {
            "status": "no_data",
            "message": "CRYOSYNC dataset not found or empty.",
        }

    latest = df.iloc[-1]

    return {
        "status": "ok",
        "timestamp": json_safe(latest.get("timestamp")),
        "station_load_kw": json_safe(
            latest.get("total_station_load")
        ),
        "solar_generation_kw": json_safe(
            latest.get("solar_generation")
        ),
        "battery_soc_pct": json_safe(
            latest.get("battery_soc_pct")
        ),
        "fuel_level_l": json_safe(
            latest.get("fuel_level")
        ),
    }


# -------------------------------------------------------------------
# FORECAST
# -------------------------------------------------------------------

@app.get("/forecast")
def get_forecast():

    df = load_forecast()

    if df.empty:
        return []

    return dataframe_to_records(df)


# -------------------------------------------------------------------
# DISPATCH PLAN
# -------------------------------------------------------------------

@app.get("/dispatch-plan")
def get_dispatch_plan():

    return load_first_available_csv(
        [
            ROOT / "data" / "dispatch_plan.csv",
            ROOT / "data" / "dispatch.csv",
        ]
    )


# -------------------------------------------------------------------
# ALERTS
# -------------------------------------------------------------------

@app.get("/alerts")
def get_alerts():

    df = load_alerts_from_pipeline()

    if df.empty:
        return []

    return dataframe_to_records(df)


# -------------------------------------------------------------------
# SHEDDING EVENTS
# -------------------------------------------------------------------

@app.get("/shedding-events")
def get_shedding_events():

    return load_first_available_csv(
        [
            ROOT / "data" / "shedding_events.csv",
            ROOT / "data" / "shedding-events.csv",
        ]
    )


# -------------------------------------------------------------------
# MAINTENANCE
# -------------------------------------------------------------------

@app.get("/maintenance")
def get_maintenance():

    return load_first_available_csv(
        [
            ROOT / "data" / "maintenance.csv",
            ROOT / "data" / "maintenance_flags.csv",
        ]
    )


# -------------------------------------------------------------------
# OPERATOR OVERRIDE
# -------------------------------------------------------------------

class OverrideRequest(BaseModel):
    decision: str
    reason: str = ""


@app.post("/override")
def create_override(request: OverrideRequest):

    decision = request.decision.strip()
    reason = request.reason.strip()

    if not decision:
        raise HTTPException(
            status_code=400,
            detail="Decision cannot be empty.",
        )

    timestamp = pd.Timestamp.utcnow().isoformat()

    try:

        engine = get_engine()

        with engine.begin() as conn:

            conn.execute(
                text(
                    """
                    INSERT INTO operator_overrides
                    (timestamp, decision, reason)
                    VALUES (:timestamp, :decision, :reason)
                    """
                ),
                {
                    "timestamp": timestamp,
                    "decision": decision,
                    "reason": reason,
                },
            )

        return {
            "status": "recorded",
            "timestamp": timestamp,
            "decision": decision,
            "reason": reason,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not record override: {exc}",
        )


# -------------------------------------------------------------------
# OPERATOR OVERRIDES
# -------------------------------------------------------------------

@app.get("/overrides")
def get_overrides():

    try:

        engine = get_engine()

        with engine.connect() as conn:

            result = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        timestamp,
                        decision,
                        reason
                    FROM operator_overrides
                    ORDER BY timestamp DESC
                    """
                )
            )

            return [
                dict(row._mapping)
                for row in result
            ]

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not load overrides: {exc}",
        )


# -------------------------------------------------------------------
# DATABASE STATUS
# -------------------------------------------------------------------

@app.get("/database-status")
def database_status():

    try:

        engine = get_engine()

        with engine.connect() as conn:

            alert_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM alerts"
                )
            ).scalar_one()

            active_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM alerts
                    WHERE resolved = 0
                    """
                )
            ).scalar_one()

            reading_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM hourly_readings"
                )
            ).scalar_one()

            forecast_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM forecasts"
                )
            ).scalar_one()

            override_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM operator_overrides"
                )
            ).scalar_one()

        return {
            "database": "connected",
            "hourly_readings": int(reading_count),
            "forecasts": int(forecast_count),
            "alerts": int(alert_count),
            "active_alerts": int(active_count),
            "operator_overrides": int(override_count),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Database unavailable: {exc}",
        )


# -------------------------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------------------------

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "CRYOSYNC API",
        "mode": "offline-first",
    }