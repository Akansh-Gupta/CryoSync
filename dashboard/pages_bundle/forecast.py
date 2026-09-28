"""Forecast page - the next 24 hours of load, solar and wind."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.formatting import kilowatts, metres_per_second
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def _peak(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return float("nan")

    values = pd.to_numeric(frame[column], errors="coerce")

    return float(values.max()) if not values.dropna().empty else float("nan")


def render() -> None:
    data = _shared.data()

    forecast = data.forecast

    ui.page_header(
        "24-hour forecast",
        "Predicted load and renewable generation for the hours ahead.",
        eyebrow="Decision",
    )

    if forecast is None or forecast.empty:
        ui.empty_state(
            "No forecast artefact is available.",
            "Run `python run_pipeline.py` to generate the forecast.",
        )
        return

    horizon = forecast.head(24).copy()

    for column in (
        "load_forecast_kw",
        "solar_forecast_kw",
        "wind_forecast_kw",
    ):
        if column in horizon.columns:
            horizon[column] = pd.to_numeric(horizon[column], errors="coerce").clip(
                lower=0
            )

    ui.metric_grid(
        [
            ("Peak load", kilowatts(_peak(horizon, "load_forecast_kw")), None),
            ("Peak solar", kilowatts(_peak(horizon, "solar_forecast_kw")), None),
            ("Peak wind", kilowatts(_peak(horizon, "wind_forecast_kw")), None),
            ("Horizon", f"{len(horizon)} h", None),
        ],
        columns=4,
    )

    st.write("")

    with st.container(border=True):
        ui.card_title("Forecast power mix")

        _shared.line_chart(
            horizon,
            ["load_forecast_kw", "solar_forecast_kw", "wind_forecast_kw"],
            height=380,
            caption=(
                "Expected demand against expected renewable supply. Gaps between "
                "the two are covered by storage and, if needed, diesel."
            ),
        )

    # Confidence bands are only meaningful when the model exported them.
    band_pairs = [
        ("load_forecast_kw", "load_lower_kw", "load_upper_kw", "Load forecast"),
        ("solar_forecast_kw", "solar_lower_kw", "solar_upper_kw", "Solar forecast"),
        ("wind_forecast_kw", "wind_lower_kw", "wind_upper_kw", "Wind forecast"),
    ]

    available_bands = [
        (value, lower, upper, title)
        for value, lower, upper, title in band_pairs
        if value in horizon.columns and lower in horizon.columns and upper in horizon.columns
    ]

    if available_bands:
        st.write("")

        left, right = st.columns(2)

        for index, (value, lower, upper, title) in enumerate(available_bands):
            holder = left if index % 2 == 0 else right

            with holder:
                with st.container(border=True):
                    ui.card_title(title)

                    _shared.forecast_band_chart(
                        horizon,
                        value,
                        lower,
                        upper,
                        height=280,
                    )

                    st.caption("Shaded band is the model's confidence interval.")

    if "wind_speed_forecast_ms" in horizon.columns:
        st.write("")

        with st.container(border=True):
            ui.card_title("Antarctic wind speed")

            _shared.line_chart(
                horizon,
                ["wind_speed_forecast_ms"],
                height=280,
                y_title="m/s",
                zero_floor=False,
                caption=(
                    "Turbine output stays flat above rated speed, so a rising "
                    "wind forecast does not always mean more power."
                ),
            )

    # -------------------------------------------------------- models ---
    model_columns = [
        column
        for column in ("load_model", "solar_model", "wind_model")
        if column in forecast.columns
    ]

    if model_columns:
        st.write("")

        with st.container(border=True):
            ui.card_title("Forecast models in use")

            ui.rows(
                (
                    column.replace("_model", "").replace("_", " ").title(),
                    str(forecast[column].dropna().astype(str).unique()[0])
                    if not forecast[column].dropna().empty
                    else "Unknown",
                )
                for column in model_columns
            )
