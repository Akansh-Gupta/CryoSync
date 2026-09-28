"""Low-level readers and normalisers for CRYOSYNC pipeline artefacts.

Nothing here knows about Streamlit. Files are read once, timestamps are
normalised to a single convention, and the derived generation columns the
twin does not store (wind, renewables, net load) are reconstructed with the
exact same wind model the pipeline uses.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import core.paths as _paths  # noqa: F401  (patches sys.path for pipeline imports)

from core.paths import PipelineFile, pipeline_file
from twin.config import STATION_CONFIG
from twin.wind import simulate_wind

TIME_COLUMN = "timestamp"

# Battery flow values below this magnitude are treated as unrecorded rather
# than as a genuine zero.
FLOW_TOLERANCE_KW = 0.01

# The twin writes day-first timestamps ("03-09-2026 22:00") while the
# forecast, dispatch and alert writers emit ISO timestamps. Both conventions
# are parsed explicitly so neither can be silently mis-read.
ISO_TIMESTAMP_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
)

DAY_FIRST_TIMESTAMP_FORMATS: tuple[str, ...] = (
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
)

# Explicit numeric columns per artefact, taken from the pipeline writers.
NUMERIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "master": (
        "temperature",
        "wind_speed",
        "solar_irradiance",
        "occupancy",
        "activity_level",
        "critical_load",
        "residential_load",
        "research_load",
        "total_station_load",
        "solar_generation",
        "battery_soc",
        "battery_soc_pct",
        "battery_charge",
        "battery_discharge",
        "battery_power",
        "generator_output",
        "fuel_consumption",
        "fuel_level",
        "fuel_runway_days",
    ),
    "forecast": (
        "load_forecast_kw",
        "load_lower_kw",
        "load_upper_kw",
        "solar_forecast_kw",
        "solar_lower_kw",
        "solar_upper_kw",
        "wind_forecast_kw",
        "wind_lower_kw",
        "wind_upper_kw",
    ),
    "test_forecast": (
        "load_forecast_kw",
        "load_lower_kw",
        "load_upper_kw",
        "solar_forecast_kw",
        "solar_lower_kw",
        "solar_upper_kw",
        "wind_forecast_kw",
        "wind_lower_kw",
        "wind_upper_kw",
    ),
    "dispatch": (
        "load_forecast_kw",
        "solar_forecast_kw",
        "solar_to_load_kw",
        "solar_to_battery_kw",
        "battery_to_load_kw",
        "diesel_kw",
        "soc_kwh",
        "estimated_fuel_l",
        "fuel_remaining_l",
        "fuel_saving_vs_all_diesel_l",
    ),
    "alerts": (),
    "anomalies": ("anomaly_score",),
    "maintenance": ("battery_health_score", "generator_health_score"),
}

BOOLEAN_COLUMNS: dict[str, tuple[str, ...]] = {
    "master": (),
    "forecast": (),
    "test_forecast": (),
    "dispatch": (),
    "alerts": ("resolved",),
    "anomalies": ("is_anomaly", "ml_anomaly", "rule_anomaly"),
    "maintenance": (),
}


def read_table(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    """Read a CSV file, returning ``(frame, error)``."""

    if not path.exists():
        return None, f"{path.name} is missing"

    try:
        frame = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 - surfaced to the diagnostics page
        return None, f"{path.name} could not be read: {exc}"

    if frame.empty:
        return None, f"{path.name} contains no rows"

    return frame, None


def drop_unnamed(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop the padding column CSV writers leave behind."""

    unnamed = [column for column in frame.columns if str(column).startswith("Unnamed:")]

    if not unnamed:
        return frame

    return frame.drop(columns=unnamed)


def coerce_columns(
    frame: pd.DataFrame,
    numeric: tuple[str, ...] = (),
    boolean: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Coerce known measurement and flag columns to real types."""

    for column in numeric:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in boolean:
        if column in frame.columns:
            frame[column] = frame[column].astype("boolean").fillna(False).astype(bool)

    return frame


def parse_timestamps(series: pd.Series) -> pd.Series:
    """Parse the two timestamp conventions used by the pipeline.

    ISO is attempted first because it is unambiguous; only the values that
    fail are re-read day-first. This keeps the twin's ``03-09-2026 22:00``
    and the forecast writer's ``2026-09-04 00:00:00`` both correct.
    """

    text = series.astype("string")

    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    for fmt in ISO_TIMESTAMP_FORMATS + DAY_FIRST_TIMESTAMP_FORMATS:
        pending = parsed.isna()

        if not pending.any():
            break

        parsed.loc[pending] = pd.to_datetime(
            text[pending],
            format=fmt,
            errors="coerce",
        )

    pending = parsed.isna()

    if pending.any():
        parsed.loc[pending] = pd.to_datetime(text[pending], errors="coerce")

    return parsed


def normalise_time(
    frame: pd.DataFrame,
    column: str = TIME_COLUMN,
    ascending: bool = True,
) -> pd.DataFrame:
    """Parse, drop and order timestamps."""

    if column not in frame.columns:
        return frame

    frame[column] = parse_timestamps(frame[column])

    frame = frame.dropna(subset=[column])

    if ascending:
        frame = frame.sort_values(column)

    return frame.reset_index(drop=True)


def add_derived_generation(frame: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct wind, renewable and net-load columns from the twin state."""

    wind_config = STATION_CONFIG["wind_system"]

    if "wind_generation" not in frame.columns and "wind_speed" in frame.columns:
        speeds = (
            pd.to_numeric(frame["wind_speed"], errors="coerce").fillna(0.0).to_numpy()
        )
        frame["wind_generation"] = np.round(simulate_wind(speeds, wind_config), 3)

    if {"solar_generation", "wind_generation"} <= set(frame.columns):
        frame["renewable_generation"] = (
            frame["solar_generation"] + frame["wind_generation"]
        ).round(3)

    if {"total_station_load", "renewable_generation"} <= set(frame.columns):
        frame["net_load_kw"] = (
            frame["total_station_load"] - frame["renewable_generation"]
        ).round(3)

        load = frame["total_station_load"].replace(0, np.nan)
        frame["renewable_fraction"] = (
            frame["renewable_generation"] / load
        ).clip(lower=0.0, upper=1.5).round(4)

    frame = repair_battery_flows(frame)

    return frame


def repair_battery_flows(frame: pd.DataFrame) -> pd.DataFrame:
    """Rebuild battery flows from the SoC trajectory when they are degenerate.

    ``twin/power_balance.py`` previously exported charge and discharge through
    an inverted mutual-exclusivity filter, which zeroed every discharge value in
    datasets already generated. The state-of-charge trajectory itself is
    correct, so when both flow columns come back flat the flows are recovered
    from the hour-to-hour change in stored energy, and a flag records that the
    values were reconstructed rather than measured.
    """

    required = {"battery_soc", "battery_charge", "battery_discharge"}

    if not required <= set(frame.columns):
        return frame

    charge = pd.to_numeric(frame["battery_charge"], errors="coerce").fillna(0.0)
    discharge = pd.to_numeric(frame["battery_discharge"], errors="coerce").fillna(0.0)

    if max(charge.abs().max(), discharge.abs().max()) > FLOW_TOLERANCE_KW:
        return frame

    battery_config = STATION_CONFIG["battery_system"]

    single_trip_efficiency = float(battery_config["round_trip_efficiency"]) ** 0.5

    stored_kwh = pd.to_numeric(frame["battery_soc"], errors="coerce").fillna(0.0)

    delta_kwh = stored_kwh.diff().fillna(0.0)

    charging_kw = (delta_kwh.clip(lower=0.0) / single_trip_efficiency).clip(
        upper=float(battery_config["max_charge_kw"])
    )

    discharging_kw = (-delta_kwh.clip(upper=0.0) * single_trip_efficiency).clip(
        upper=float(battery_config["max_discharge_kw"])
    )

    frame["battery_charge"] = charging_kw.round(3)
    frame["battery_discharge"] = discharging_kw.round(3)
    frame["battery_power"] = (charging_kw - discharging_kw).round(3)
    frame["battery_flows_reconstructed"] = True

    return frame


def load_frame(artefact: PipelineFile) -> tuple[pd.DataFrame | None, str | None]:
    """Read one registered artefact and normalise it."""

    frame, error = read_table(artefact.path)

    if frame is None:
        return None, error

    frame = drop_unnamed(frame)

    frame = coerce_columns(
        frame,
        numeric=NUMERIC_COLUMNS.get(artefact.key, ()),
        boolean=BOOLEAN_COLUMNS.get(artefact.key, ()),
    )

    frame = normalise_time(frame)

    if artefact.key == "master":
        frame = add_derived_generation(frame)

    return frame, None


def load_by_key(key: str) -> tuple[pd.DataFrame | None, str | None]:
    """Convenience wrapper around :func:`load_frame`."""

    return load_frame(pipeline_file(key))
