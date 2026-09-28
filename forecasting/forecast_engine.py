"""M3 — AI Forecasting Engine.

Provides a small, production-friendly forecasting API for CRYOSYNC.

Forecast targets:
    1. total_station_load
    2. solar_generation
    3. wind_generation

Prophet is used when installed; otherwise XGBoost is used so the
offline prototype can still run in a clean environment.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from twin.config import STATION_CONFIG
from twin.wind import simulate_wind

try:
    from prophet import Prophet  # type: ignore
except ImportError:
    Prophet = None

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None


logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)


# =========================================================
# FORECAST TARGETS
# =========================================================

TARGETS = (
    "total_station_load",
    "solar_generation",
    "wind_generation",
)


# =========================================================
# DATA LOADING
# =========================================================

def load_dataset(
    path: str | Path = "data/master_dataset.csv"
) -> pd.DataFrame:

    df = pd.read_csv(
        path,
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )
    df = df.dropna(subset=["timestamp"]).sort_values(
        "timestamp"
    ).reset_index(drop=True)

    unnamed_columns = [
        column
        for column in df.columns
        if str(column).startswith("Unnamed:")
    ]
    if unnamed_columns:
        df = df.drop(columns=unnamed_columns)

    if "wind_generation" not in df.columns and "wind_speed" in df.columns:
        df["wind_generation"] = simulate_wind(
            pd.to_numeric(df["wind_speed"], errors="coerce").fillna(0).to_numpy(),
            STATION_CONFIG["wind_system"],
        )

    required_columns = [
        "timestamp",
        "total_station_load",
        "solar_generation",
        "wind_generation",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Dataset is missing required columns: "
            + ", ".join(missing)
        )

    return df


# =========================================================
# PROPHET DATA
# =========================================================

def _to_prophet_frame(
    df: pd.DataFrame,
    timestamp_col: str,
    value_col: str
) -> pd.DataFrame:

    out = df[
        [
            timestamp_col,
            value_col
        ]
    ].rename(
        columns={
            timestamp_col: "ds",
            value_col: "y"
        }
    ).copy()

    out["y"] = pd.to_numeric(
        out["y"],
        errors="coerce"
    ).interpolate().bfill().ffill()

    return out.dropna()


# =========================================================
# FEATURE ENGINEERING
# =========================================================

def _feature_frame(
    df: pd.DataFrame,
    target_col: str
) -> pd.DataFrame:

    d = df[
        [
            "timestamp",
            target_col
        ]
    ].copy().sort_values(
        "timestamp"
    )

    d["y"] = pd.to_numeric(
        d[target_col],
        errors="coerce"
    )

    ts = d["timestamp"]

    d["hour"] = ts.dt.hour
    d["dayofyear"] = ts.dt.dayofyear
    d["dayofweek"] = ts.dt.dayofweek

    d["hour_sin"] = np.sin(
        2 * np.pi * d["hour"] / 24
    )

    d["hour_cos"] = np.cos(
        2 * np.pi * d["hour"] / 24
    )

    d["doy_sin"] = np.sin(
        2 * np.pi * d["dayofyear"] / 365.25
    )

    d["doy_cos"] = np.cos(
        2 * np.pi * d["dayofyear"] / 365.25
    )

    # Historical lag features.
    for lag in (
        1,
        2,
        3,
        24,
        48,
        72,
        168
    ):
        d[f"lag_{lag}"] = d["y"].shift(lag)

    d = d.dropna().reset_index(
        drop=True
    )

    return d[
        [
            "timestamp",
            "y",
            "hour",
            "dayofyear",
            "dayofweek",
            "hour_sin",
            "hour_cos",
            "doy_sin",
            "doy_cos",
            "lag_1",
            "lag_2",
            "lag_3",
            "lag_24",
            "lag_48",
            "lag_72",
            "lag_168",
        ]
    ]


# =========================================================
# MODEL TRAINING
# =========================================================

def train_forecast_model(
    history_df: pd.DataFrame,
    target_col: str,
    timestamp_col: str = "timestamp",
    yearly_seasonality: bool = False,
    model_type: str = "auto"
):

    if target_col not in history_df.columns:
        raise ValueError(
            f"Missing target column: {target_col}"
        )

    if model_type == "auto":

        model_type = (
            "prophet"
            if Prophet is not None
            else "xgboost"
        )

    # -----------------------------------------------------
    # PROPHET
    # -----------------------------------------------------

    if model_type == "prophet":

        if Prophet is None:
            raise ImportError(
                "Prophet is not installed. "
                "Install prophet or use model_type='xgboost'."
            )

        model = Prophet(
            daily_seasonality=True,
            yearly_seasonality=yearly_seasonality,
            weekly_seasonality=False,
            changepoint_prior_scale=0.05
        )

        model.fit(
            _to_prophet_frame(
                history_df,
                timestamp_col,
                target_col
            )
        )

        return model

    # -----------------------------------------------------
    # XGBOOST
    # -----------------------------------------------------

    if (
        model_type != "xgboost"
        or XGBRegressor is None
    ):

        raise ImportError(
            "XGBoost is required for the "
            "fallback forecasting engine."
        )

    frame = _feature_frame(
        history_df,
        target_col
    )

    X = frame.drop(
        columns=[
            "y",
            "timestamp"
        ]
    )

    y = frame["y"]

    model = XGBRegressor(
        n_estimators=350,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=2,
    )

    model.fit(
        X,
        y
    )

    # Store information required for recursive forecasting.
    model._cryosync_target = target_col

    model._cryosync_history = history_df[
        [
            "timestamp",
            target_col
        ]
    ].copy()

    return model


# =========================================================
# 24-HOUR FORECAST
# =========================================================

def forecast_next_24h(
    model,
    last_timestamp,
    freq: str = "h"
) -> pd.DataFrame:

    """Forecast the 24 hours immediately after last_timestamp."""

    # -----------------------------------------------------
    # PROPHET
    # -----------------------------------------------------

    if (
        Prophet is not None
        and model.__class__.__name__ == "Prophet"
    ):

        future = pd.DataFrame(
            {
                "ds": pd.date_range(
                    last_timestamp,
                    periods=25,
                    freq=freq
                )[1:]
            }
        )

        f = model.predict(
            future
        )

        return (
            f[
                [
                    "ds",
                    "yhat",
                    "yhat_lower",
                    "yhat_upper"
                ]
            ]
            .rename(
                columns={
                    "ds": "timestamp",
                    "yhat": "forecast",
                    "yhat_lower": "lower",
                    "yhat_upper": "upper",
                }
            )
        )

    # -----------------------------------------------------
    # XGBOOST
    # -----------------------------------------------------

    history = model._cryosync_history.copy()

    target = model._cryosync_target

    values = history[
        target
    ].astype(float).tolist()

    timestamps = history[
        "timestamp"
    ].tolist()

    rows = []

    future_ts = pd.date_range(
        pd.Timestamp(last_timestamp),
        periods=25,
        freq=freq
    )[1:]

    for ts in future_ts:

        hour = ts.hour
        doy = ts.dayofyear

        row = {
            "hour": hour,
            "dayofyear": doy,
            "dayofweek": ts.dayofweek,

            "hour_sin": np.sin(
                2 * np.pi * hour / 24
            ),

            "hour_cos": np.cos(
                2 * np.pi * hour / 24
            ),

            "doy_sin": np.sin(
                2 * np.pi * doy / 365.25
            ),

            "doy_cos": np.cos(
                2 * np.pi * doy / 365.25
            ),

            "lag_1": values[-1],
            "lag_2": values[-2],
            "lag_3": values[-3],
            "lag_24": values[-24],
            "lag_48": values[-48],
            "lag_72": values[-72],
            "lag_168": values[-168],
        }

        pred = float(
            model.predict(
                pd.DataFrame([row])
            )[0]
        )

        # Generation/load cannot be negative.
        pred = max(
            0.0,
            pred
        )

        values.append(pred)
        timestamps.append(ts)

        rows.append(
            (
                ts,
                pred
            )
        )

    out = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "forecast"
        ]
    )

    # XGBoost does not produce probabilistic bounds.
    residual_scale = (
        max(
            float(
                np.std(
                    np.diff(
                        values[-168:]
                    )
                )
            ),
            0.01
        )
        * 2.0
    )

    out["lower"] = np.maximum(
        0,
        out["forecast"] - residual_scale
    )

    out["upper"] = (
        out["forecast"]
        + residual_scale
    )

    return out


# =========================================================
# FORECAST ALL TARGETS
# =========================================================

def forecast_24h(
    df: pd.DataFrame,
    model_type: str = "auto"
) -> Dict[str, pd.DataFrame]:

    results: Dict[str, pd.DataFrame] = {}

    for target in TARGETS:

        model = train_forecast_model(
            df,
            target,
            model_type=model_type
        )

        results[target] = forecast_next_24h(
            model,
            df["timestamp"].iloc[-1]
        )

        results[target]["target"] = target

        results[target]["model"] = (
            model.__class__.__name__
        )

    return results


# =========================================================
# BACKTEST
# =========================================================

def backtest_24h(
    history_df: pd.DataFrame,
    target_col: str,
    cutoff_index: int,
    timestamp_col: str = "timestamp",
    model_type: str = "auto"
) -> Tuple[
    pd.DataFrame,
    float,
    float,
    int
]:

    train_slice = history_df.iloc[
        :cutoff_index
    ]

    actual_slice = history_df.iloc[
        cutoff_index:
        cutoff_index + 24
    ]

    model = train_forecast_model(
        train_slice,
        target_col,
        timestamp_col,
        model_type=model_type
    )

    forecast = forecast_next_24h(
        model,
        train_slice[
            timestamp_col
        ].iloc[-1]
    )

    merged = forecast.merge(
        actual_slice[
            [
                timestamp_col,
                target_col
            ]
        ].rename(
            columns={
                timestamp_col: "timestamp"
            }
        ),
        on="timestamp",
        how="inner"
    )

    merged["error"] = (
        merged[target_col]
        - merged["forecast"]
    )

    mae = (
        float(
            merged["error"]
            .abs()
            .mean()
        )
        if len(merged)
        else float("nan")
    )

    threshold = (
        history_df[target_col].max()
        * 0.05
    )

    meaningful = merged[
        merged[target_col].abs()
        >= threshold
    ]

    mape = (
        float(
            (
                meaningful["error"].abs()
                /
                meaningful[target_col].abs()
            ).mean()
            * 100
        )
        if len(meaningful)
        else float("nan")
    )

    return (
        merged,
        mae,
        mape,
        len(merged) - len(meaningful)
    )


# =========================================================
# FORECAST PIPELINE
# =========================================================

def run_forecast_pipeline(
    data_path="data/master_dataset.csv",
    output_path="data/forecast.csv",
    model_type="auto"
):

    df = load_dataset(
        data_path
    )

    results = forecast_24h(
        df,
        model_type=model_type
    )

    load_f = results[
        "total_station_load"
    ]

    solar_f = results[
        "solar_generation"
    ]

    wind_f = results[
        "wind_generation"
    ]

    # -----------------------------------------------------
    # LOAD FORECAST
    # -----------------------------------------------------

    out = load_f[
        [
            "timestamp",
            "forecast",
            "lower",
            "upper",
            "model"
        ]
    ].rename(
        columns={
            "forecast": "load_forecast_kw",
            "lower": "load_lower_kw",
            "upper": "load_upper_kw",
            "model": "load_model",
        }
    )

    # -----------------------------------------------------
    # SOLAR FORECAST
    # -----------------------------------------------------

    out = out.merge(
        solar_f[
            [
                "timestamp",
                "forecast",
                "lower",
                "upper",
                "model"
            ]
        ],
        on="timestamp"
    )

    out = out.rename(
        columns={
            "forecast": "solar_forecast_kw",
            "lower": "solar_lower_kw",
            "upper": "solar_upper_kw",
            "model": "solar_model",
        }
    )

    # -----------------------------------------------------
    # WIND FORECAST
    # -----------------------------------------------------

    out = out.merge(
        wind_f[
            [
                "timestamp",
                "forecast",
                "lower",
                "upper",
                "model"
            ]
        ],
        on="timestamp"
    )

    out = out.rename(
        columns={
            "forecast": "wind_forecast_kw",
            "lower": "wind_lower_kw",
            "upper": "wind_upper_kw",
            "model": "wind_model",
        }
    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    Path(
        output_path
    ).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    out.to_csv(
        output_path,
        index=False
    )

    return out


# =========================================================
# COMMAND-LINE ENTRY POINT
# =========================================================

if __name__ == "__main__":

    df = load_dataset()

    cutoff = max(
        168 + 24,
        min(
            6000,
            len(df) - 24
        )
    )

    for target in TARGETS:

        _, mae, mape, excluded = backtest_24h(
            df,
            target,
            cutoff
        )

        print(
            f"{target}: "
            f"MAE={mae:.2f} kW, "
            f"MAPE={mape:.1f}% "
            f"({excluded} near-zero hours excluded)"
        )

    out = run_forecast_pipeline()

    print(
        f"Saved 24-hour forecast -> "
        f"data/forecast.csv "
        f"({len(out)} rows)"
    )

    print(
        "\nForecast columns:"
    )

    print(
        list(out.columns)
    )