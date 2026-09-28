"""Cached, normalised access to every CRYOSYNC pipeline artefact.

The dashboard never reads a CSV directly: pages ask this module for a frame
and get a normalised one back. Loading is cached so switching pages stays
instant, and every failure is recorded rather than raised, so a missing
artefact degrades one card instead of breaking the app.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from core.io import load_by_key

ARTEFACT_KEYS: tuple[str, ...] = (
    "master",
    "forecast",
    "dispatch",
    "alerts",
    "anomalies",
    "maintenance",
    "test_forecast",
)

TIME_COLUMN = "timestamp"


@dataclass(frozen=True)
class StationData:
    """Every loaded artefact plus the errors that stopped the others."""

    frames: dict[str, pd.DataFrame]
    errors: dict[str, str]
    loaded_at: pd.Timestamp

    def frame(self, key: str) -> pd.DataFrame | None:
        return self.frames.get(key)

    def has(self, key: str) -> bool:
        return key in self.frames

    @property
    def missing_keys(self) -> tuple[str, ...]:
        return tuple(key for key in ARTEFACT_KEYS if key not in self.frames)

    @property
    def master(self) -> pd.DataFrame | None:
        return self.frames.get("master")

    @property
    def forecast(self) -> pd.DataFrame | None:
        return self.frames.get("forecast")

    @property
    def dispatch(self) -> pd.DataFrame | None:
        return self.frames.get("dispatch")

    @property
    def alerts(self) -> pd.DataFrame | None:
        return self.frames.get("alerts")

    @property
    def anomalies(self) -> pd.DataFrame | None:
        return self.frames.get("anomalies")

    @property
    def maintenance(self) -> pd.DataFrame | None:
        return self.frames.get("maintenance")

    @property
    def latest(self) -> pd.Series | None:
        master = self.master

        if master is None or master.empty:
            return None

        return master.iloc[-1]

    @property
    def latest_timestamp(self) -> pd.Timestamp | None:
        latest = self.latest

        if latest is None:
            return None

        return pd.Timestamp(latest[TIME_COLUMN])

    def window(self, hours: int) -> pd.DataFrame:
        """Trailing master window of ``hours`` rows."""

        master = self.master

        if master is None or master.empty:
            return pd.DataFrame()

        return master.tail(hours).copy()

    def seasonal_window(self, days: int) -> pd.DataFrame:
        """Trailing window used as the seasonal-conditions sample."""

        return self.window(days * 24)

    def active_alerts(self, limit: int | None = None) -> pd.DataFrame:
        """Unresolved alerts, newest first."""

        alerts = self.alerts

        if alerts is None or alerts.empty:
            return pd.DataFrame()

        active = alerts[~alerts["resolved"]].copy()

        active = active.sort_values(TIME_COLUMN, ascending=False)

        if limit is not None:
            active = active.head(limit)

        return active.reset_index(drop=True)

    def flagged_anomalies(self) -> pd.DataFrame:
        """Detections flagged by the model or by a physical sanity rule."""

        anomalies = self.anomalies

        if anomalies is None or anomalies.empty:
            return pd.DataFrame()

        if "is_anomaly" not in anomalies.columns:
            return pd.DataFrame()

        flagged = anomalies[anomalies["is_anomaly"]].copy()

        return flagged.sort_values(TIME_COLUMN, ascending=False).reset_index(drop=True)

    def latest_health(self) -> pd.Series | None:
        """Most recent battery and generator health scores."""

        maintenance = self.maintenance

        if maintenance is None or maintenance.empty:
            return None

        return maintenance.iloc[-1]


@st.cache_data(ttl="2m", show_spinner=False)
def load_station_data() -> StationData:
    """Load every artefact once and cache the result."""

    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}

    for key in ARTEFACT_KEYS:
        frame, error = load_by_key(key)

        if frame is not None:
            frames[key] = frame

        if error is not None:
            errors[key] = error

    return StationData(
        frames=frames,
        errors=errors,
        loaded_at=pd.Timestamp.now(),
    )
