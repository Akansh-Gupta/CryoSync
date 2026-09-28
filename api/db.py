"""M9 — offline-first persistence.

SQLite is the zero-config local default. Set DATABASE_URL to PostgreSQL for a
station deployment.

Tables:
    - hourly_readings
    - equipment
    - forecasts
    - shedding_events
    - alerts
    - maintenance_flags
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_URL = "sqlite:///data/polaris.db"


# ============================================================
# DATABASE ENGINE
# ============================================================

def get_engine():
    """Return the configured database engine."""

    url = os.getenv("DATABASE_URL", DEFAULT_URL)

    # Ensure the local data directory exists for SQLite.
    if url.startswith("sqlite:///data"):
        (ROOT / "data").mkdir(parents=True, exist_ok=True)

        # Convert relative SQLite path into an absolute path so the
        # database location does not depend on the terminal's cwd.
        database_path = ROOT / "data" / "polaris.db"
        url = f"sqlite:///{database_path.as_posix()}"

    return create_engine(
        url,
        future=True,
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """Create all CRYOSYNC persistence tables if they do not exist."""

    engine = get_engine()

    with engine.begin() as conn:

        # ----------------------------------------------------
        # Hourly readings
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS hourly_readings (
                    timestamp TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
        )

        # ----------------------------------------------------
        # Equipment
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS equipment (
                    id TEXT PRIMARY KEY,
                    zone TEXT,
                    nominal_power_kw REAL,
                    priority TEXT,
                    behavior TEXT
                )
                """
            )
        )

        # ----------------------------------------------------
        # Forecasts
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS forecasts (
                    timestamp TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
        )

        # ----------------------------------------------------
        # Load-shedding events
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS shedding_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_hours INTEGER
                )
                """
            )
        )

        # ----------------------------------------------------
        # Alerts
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    type TEXT,
                    severity TEXT,
                    source_module TEXT,
                    message TEXT,
                    resolved INTEGER DEFAULT 0
                )
                """
            )
        )

        # ----------------------------------------------------
        # Maintenance flags
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS maintenance_flags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    equipment TEXT,
                    health_score REAL,
                    recommendation TEXT
                )
                """
            )
        )

    return engine


# ============================================================
# GENERIC JSON UPSERT
# ============================================================

def upsert_json(
    table: str,
    key: str,
    payload: dict,
):
    """Insert or replace JSON payloads for supported tables."""

    engine = init_db()

    with engine.begin() as conn:

        if table == "hourly_readings":

            conn.execute(
                text(
                    """
                    INSERT OR REPLACE INTO hourly_readings
                    (timestamp, payload)
                    VALUES (:k, :p)
                    """
                ),
                {
                    "k": key,
                    "p": json.dumps(
                        payload,
                        default=str,
                    ),
                },
            )

        elif table == "forecasts":

            conn.execute(
                text(
                    """
                    INSERT OR REPLACE INTO forecasts
                    (timestamp, payload)
                    VALUES (:k, :p)
                    """
                ),
                {
                    "k": key,
                    "p": json.dumps(
                        payload,
                        default=str,
                    ),
                },
            )

        else:
            raise ValueError(
                f"Unsupported JSON table: {table}"
            )


# ============================================================
# ALERT PERSISTENCE
# ============================================================

def save_alert(
    timestamp,
    alert_type: str,
    severity: str,
    source_module: str,
    message: str,
    resolved: bool = False,
):
    """Persist one operator alert."""

    engine = init_db()

    with engine.begin() as conn:

        conn.execute(
            text(
                """
                INSERT INTO alerts
                (
                    timestamp,
                    type,
                    severity,
                    source_module,
                    message,
                    resolved
                )
                VALUES
                (
                    :timestamp,
                    :type,
                    :severity,
                    :source_module,
                    :message,
                    :resolved
                )
                """
            ),
            {
                "timestamp": str(
                    pd.Timestamp(timestamp)
                ),
                "type": alert_type,
                "severity": severity,
                "source_module": source_module,
                "message": message,
                "resolved": int(resolved),
            },
        )


def save_alerts(alert_df: pd.DataFrame):
    """Persist a DataFrame of alerts."""

    if alert_df is None or alert_df.empty:
        return

    required_columns = {
        "timestamp",
        "type",
        "severity",
        "source_module",
        "message",
    }

    missing = required_columns - set(alert_df.columns)

    if missing:
        raise ValueError(
            f"Missing alert columns: {sorted(missing)}"
        )

    engine = init_db()

    with engine.begin() as conn:

        for _, row in alert_df.iterrows():

            resolved = row.get(
                "resolved",
                False,
            )

            if pd.isna(resolved):
                resolved = False

            conn.execute(
                text(
                    """
                    INSERT INTO alerts
                    (
                        timestamp,
                        type,
                        severity,
                        source_module,
                        message,
                        resolved
                    )
                    VALUES
                    (
                        :timestamp,
                        :type,
                        :severity,
                        :source_module,
                        :message,
                        :resolved
                    )
                    """
                ),
                {
                    "timestamp": str(
                        pd.Timestamp(
                            row["timestamp"]
                        )
                    ),
                    "type": str(row["type"]),
                    "severity": str(
                        row["severity"]
                    ),
                    "source_module": str(
                        row["source_module"]
                    ),
                    "message": str(
                        row["message"]
                    ),
                    "resolved": int(
                        bool(resolved)
                    ),
                },
            )


# ============================================================
# READ ALERTS
# ============================================================

def get_alerts(
    active_only: bool = False,
) -> pd.DataFrame:
    """Return persisted alerts."""

    engine = init_db()

    with engine.begin() as conn:

        if active_only:

            result = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        timestamp,
                        type,
                        severity,
                        source_module,
                        message,
                        resolved
                    FROM alerts
                    WHERE resolved = 0
                    ORDER BY timestamp DESC
                    """
                )
            )

        else:

            result = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        timestamp,
                        type,
                        severity,
                        source_module,
                        message,
                        resolved
                    FROM alerts
                    ORDER BY timestamp DESC
                    """
                )
            )

        rows = result.mappings().all()

    if not rows:

        return pd.DataFrame(
            columns=[
                "id",
                "timestamp",
                "type",
                "severity",
                "source_module",
                "message",
                "resolved",
            ]
        )

    alerts = pd.DataFrame(rows)

    alerts["timestamp"] = pd.to_datetime(
        alerts["timestamp"],
        errors="coerce",
    )

    alerts["resolved"] = (
        alerts["resolved"]
        .astype(bool)
    )

    return alerts


# ============================================================
# RESOLVE ALERT
# ============================================================

def resolve_alert(alert_id: int) -> bool:
    """Mark an alert as resolved."""

    engine = init_db()

    with engine.begin() as conn:

        result = conn.execute(
            text(
                """
                UPDATE alerts
                SET resolved = 1
                WHERE id = :alert_id
                """
            ),
            {
                "alert_id": int(alert_id),
            },
        )

        return result.rowcount > 0


# ============================================================
# RESOLVE ALERTS BY TYPE
# ============================================================

def resolve_alert_type(
    alert_type: str,
) -> int:
    """Resolve all active alerts of a specific type."""

    engine = init_db()

    with engine.begin() as conn:

        result = conn.execute(
            text(
                """
                UPDATE alerts
                SET resolved = 1
                WHERE type = :alert_type
                  AND resolved = 0
                """
            ),
            {
                "alert_type": alert_type,
            },
        )

        return result.rowcount


# ============================================================
# DATABASE STATUS
# ============================================================

def database_status() -> dict:
    """Return basic database status for diagnostics."""

    engine = init_db()

    with engine.begin() as conn:

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

    return {
        "database": "connected",
        "total_alerts": int(alert_count),
        "active_alerts": int(active_count),
    }