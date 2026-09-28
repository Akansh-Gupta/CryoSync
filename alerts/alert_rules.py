"""M7 — deterministic operator alert rules."""

from __future__ import annotations

import pandas as pd


# =========================================================
# DEFAULT CONFIGURATION
# =========================================================

DEFAULT_CONFIG = {
    "low_fuel_runway_days": 14,
    "battery_warning_pct": 50,
    "low_battery_pct": 25,
    "storm_wind_speed": 25,
    "forecast_uncertainty_kw": 10,
}


# =========================================================
# OUTPUT SCHEMA
# =========================================================

ALERT_COLUMNS = [
    "timestamp",
    "type",
    "severity",
    "source_module",
    "message",
    "resolved",
]


# =========================================================
# HELPERS
# =========================================================

def _condition_start_indices(
    df: pd.DataFrame,
    condition: pd.Series,
) -> list:
    """
    Return indices where a condition changes from False to True.

    This converts repeated hourly conditions into event-based alerts.

    Example:
        False False True True True False True True

    becomes:
        alert at first True
        alert at second separate True event
    """

    if df is None or df.empty:
        return []

    condition = (
        condition
        .fillna(False)
        .astype(bool)
        .reset_index(drop=True)
    )

    starts = condition & ~condition.shift(
        1,
        fill_value=False,
    )

    return list(condition.index[starts])


def _prepare_time_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Return a clean time-sorted copy of a dataframe."""

    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(
            out["timestamp"],
            errors="coerce",
        )

        out = out.sort_values(
            "timestamp"
        )

    return out.reset_index(drop=True)


# =========================================================
# MAIN ALERT BUILDER
# =========================================================

def build_alerts(
    df: pd.DataFrame,
    forecast_df=None,
    anomaly_df=None,
    health_df=None,
    cfg=None,
) -> pd.DataFrame:
    """
    Build deterministic operator alerts from CRYOSYNC data.

    Alert sources:
        - M7: Fuel, battery and storm conditions
        - M6: Anomaly and equipment health conditions
        - M3: Forecast uncertainty

    Alerts are EVENT-BASED rather than HOURLY.

    Therefore, when a condition remains true for several
    consecutive hours, only one alert is generated for that event.

    Example:
        Battery SoC < 25% for 20 hours
        -> one LOW_BATTERY alert

        Battery recovers
        -> event resets

        Battery later drops below 25%
        -> a new LOW_BATTERY alert is generated

    Returns:
        pandas.DataFrame with a consistent alert schema.
    """

    # =====================================================
    # CONFIGURATION
    # =====================================================

    config = DEFAULT_CONFIG.copy()

    if cfg:
        config.update(cfg)

    rows = []

    # =====================================================
    # ALERT CREATOR
    # =====================================================

    def add_alert(
        timestamp,
        alert_type,
        severity,
        source,
        message,
    ):
        """Add one normalized alert record."""

        if pd.isna(timestamp):
            return

        rows.append(
            {
                "timestamp": pd.Timestamp(timestamp),
                "type": str(alert_type),
                "severity": str(severity).lower(),
                "source_module": str(source),
                "message": str(message),
                "resolved": False,
            }
        )

    # =====================================================
    # BASIC VALIDATION
    # =====================================================

    if df is None or df.empty:
        return pd.DataFrame(
            columns=ALERT_COLUMNS
        )

    df = _prepare_time_dataframe(df)

    # =====================================================
    # M7 — LOW FUEL
    # =====================================================

    if "fuel_runway_days" in df.columns:

        fuel_runway = pd.to_numeric(
            df["fuel_runway_days"],
            errors="coerce",
        )

        low_fuel_condition = (
            fuel_runway
            < config["low_fuel_runway_days"]
        )

        for index in _condition_start_indices(
            df,
            low_fuel_condition,
        ):

            value = fuel_runway.iloc[index]

            add_alert(
                df.iloc[index]["timestamp"],
                "LOW_FUEL",
                "high",
                "M7",
                f"Fuel runway is {value:.1f} days.",
            )

    # =====================================================
    # M7 — LOW BATTERY
    # =====================================================

    if "battery_soc_pct" in df.columns:

        battery_soc = pd.to_numeric(
            df["battery_soc_pct"],
            errors="coerce",
        )

        battery_warning_condition = (
            (battery_soc < config["battery_warning_pct"])
            & (battery_soc >= config["low_battery_pct"])
        )

        for index in _condition_start_indices(
            df,
            battery_warning_condition,
        ):

            value = battery_soc.iloc[index]

            add_alert(
                df.iloc[index]["timestamp"],
                "BATTERY_LEVEL_WARNING",
                "medium",
                "M7",
                f"Battery level is {value:.1f}%, below the 50% warning level.",
            )

        low_battery_condition = (
            battery_soc
            < config["low_battery_pct"]
        )

        for index in _condition_start_indices(
            df,
            low_battery_condition,
        ):

            value = battery_soc.iloc[index]

            add_alert(
                df.iloc[index]["timestamp"],
                "LOW_BATTERY",
                "high",
                "M7",
                f"Battery SoC is {value:.1f}%.",
            )

    # =====================================================
    # M7 — STORM RISK
    # =====================================================

    if "wind_speed" in df.columns:

        wind_speed = pd.to_numeric(
            df["wind_speed"],
            errors="coerce",
        )

        storm_condition = (
            wind_speed
            >= config["storm_wind_speed"]
        )

        for index in _condition_start_indices(
            df,
            storm_condition,
        ):

            value = wind_speed.iloc[index]

            add_alert(
                df.iloc[index]["timestamp"],
                "STORM_RISK",
                "high",
                "M5/M7",
                f"Storm alert: wind speed reached {value:.1f} m/s.",
            )

    # =====================================================
    # M6 — ANOMALY ALERTS
    # =====================================================

    if (
        anomaly_df is not None
        and not anomaly_df.empty
        and "is_anomaly" in anomaly_df.columns
    ):

        anomaly_df = _prepare_time_dataframe(
            anomaly_df
        )

        anomalous_condition = (
            anomaly_df["is_anomaly"]
            .fillna(False)
            .astype(bool)
        )

        anomaly_start_indices = (
            _condition_start_indices(
                anomaly_df,
                anomalous_condition,
            )
        )

        for index in anomaly_start_indices:

            row = anomaly_df.iloc[index]

            score = pd.to_numeric(
                row.get(
                    "anomaly_score",
                    0,
                ),
                errors="coerce",
            )

            if pd.isna(score):
                score = 0.0

            severity = str(
                row.get(
                    "severity",
                    "medium",
                )
            )

            add_alert(
                row.get("timestamp"),
                "ANOMALY",
                severity,
                "M6",
                "Abnormal operating pattern "
                f"detected (score {score:.2f}).",
            )

    # =====================================================
    # M6 — EQUIPMENT HEALTH
    # =====================================================

    if health_df is not None and not health_df.empty:

        health_df = _prepare_time_dataframe(
            health_df
        )

        # -------------------------------------------------
        # BATTERY HEALTH
        # -------------------------------------------------

        if "battery_health_score" in health_df.columns:

            battery_health = pd.to_numeric(
                health_df["battery_health_score"],
                errors="coerce",
            )

            low_battery_health = (
                battery_health < 70
            )

            for index in _condition_start_indices(
                health_df,
                low_battery_health,
            ):

                row = health_df.iloc[index]

                recommendation = row.get(
                    "battery_recommendation",
                    "Battery health requires inspection.",
                )

                if pd.isna(recommendation):
                    recommendation = (
                        "Battery health requires inspection."
                    )

                add_alert(
                    row.get("timestamp"),
                    "BATTERY_MAINTENANCE",
                    "medium",
                    "M6",
                    recommendation,
                )

        # -------------------------------------------------
        # GENERATOR HEALTH
        # -------------------------------------------------

        if "generator_health_score" in health_df.columns:

            generator_health = pd.to_numeric(
                health_df["generator_health_score"],
                errors="coerce",
            )

            low_generator_health = (
                generator_health < 70
            )

            for index in _condition_start_indices(
                health_df,
                low_generator_health,
            ):

                row = health_df.iloc[index]

                recommendation = row.get(
                    "generator_recommendation",
                    "Generator health requires inspection.",
                )

                if pd.isna(recommendation):
                    recommendation = (
                        "Generator health requires inspection."
                    )

                add_alert(
                    row.get("timestamp"),
                    "GENERATOR_MAINTENANCE",
                    "medium",
                    "M6",
                    recommendation,
                )

    # =====================================================
    # M3 — FORECAST UNCERTAINTY
    # =====================================================

    if (
        forecast_df is not None
        and not forecast_df.empty
        and {
            "load_forecast_kw",
            "load_upper_kw",
        }.issubset(
            forecast_df.columns
        )
    ):

        forecast_df = _prepare_time_dataframe(
            forecast_df
        )

        forecast_value = pd.to_numeric(
            forecast_df["load_forecast_kw"],
            errors="coerce",
        )

        upper_value = pd.to_numeric(
            forecast_df["load_upper_kw"],
            errors="coerce",
        )

        uncertainty = (
            upper_value
            - forecast_value
        )

        high_uncertainty_condition = (
            uncertainty
            > config["forecast_uncertainty_kw"]
        )

        for index in _condition_start_indices(
            forecast_df,
            high_uncertainty_condition,
        ):

            value = uncertainty.iloc[index]

            add_alert(
                forecast_df.iloc[index]["timestamp"],
                "FORECAST_UNCERTAINTY",
                "medium",
                "M3",
                f"Load forecast uncertainty is "
                f"{value:.1f} kW.",
            )

    # =====================================================
    # BUILD FINAL DATAFRAME
    # =====================================================

    alerts = pd.DataFrame(
        rows,
        columns=ALERT_COLUMNS,
    )

    if alerts.empty:
        return pd.DataFrame(
            columns=ALERT_COLUMNS
        )

    # =====================================================
    # TIMESTAMP NORMALIZATION
    # =====================================================

    alerts["timestamp"] = pd.to_datetime(
        alerts["timestamp"],
        errors="coerce",
    )

    # =====================================================
    # REMOVE EXACT DUPLICATES
    # =====================================================

    alerts = alerts.drop_duplicates(
        subset=[
            "timestamp",
            "type",
            "severity",
            "source_module",
            "message",
        ],
        keep="first",
    )

    # =====================================================
    # SORT LATEST FIRST
    # =====================================================

    alerts = alerts.sort_values(
        "timestamp",
        ascending=False,
    ).reset_index(
        drop=True
    )

    return alerts[
        ALERT_COLUMNS
    ]