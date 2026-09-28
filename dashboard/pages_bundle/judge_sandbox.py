"""Judge sandbox - hold candidate plans and the forecast model up to scrutiny."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import settings
from core.autonomy import outlook
from core.formatting import EM_DASH, kilowatts, percent
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def _accuracy(frame: pd.DataFrame, actual: str, predicted: str) -> dict[str, float]:
    """Simple error statistics for a forecast against its realised values."""

    if frame is None or frame.empty or actual not in frame.columns:
        return {}

    if predicted not in frame.columns:
        return {}

    observed = pd.to_numeric(frame[actual], errors="coerce")
    modelled = pd.to_numeric(frame[predicted], errors="coerce")

    paired = pd.DataFrame({"actual": observed, "pred": modelled}).dropna()

    if paired.empty:
        return {}

    error = paired["pred"] - paired["actual"]

    mean_actual = paired["actual"].mean()

    mae = float(error.abs().mean())

    rmse = float((error**2).mean() ** 0.5)

    return {
        "MAE (kW)": round(mae, 2),
        "RMSE (kW)": round(rmse, 2),
        "Bias (kW)": round(float(error.mean()), 2),
        "Points": int(len(paired)),
        "MAE % of mean": round(mae / mean_actual * 100, 1) if mean_actual else 0.0,
    }


def render() -> None:
    data = _shared.data()

    ui.page_header(
        "Judge sandbox",
        "Stress the models and hold candidate plans against measured performance.",
        eyebrow="Experiment",
    )

    assumptions = settings.current()

    # ------------------------------------------------------- backtest ---
    with st.container(border=True):
        ui.card_title(
            "Forecast backtest",
            "held-out model output"
            if data.has("test_forecast")
            else "no held-out artefact",
        )

        held_out = data.frame("test_forecast")

        if held_out is None or held_out.empty:
            ui.empty_state(
                "No held-out forecast is available to score.",
                "The test suite writes this artefact when it runs.",
            )
        else:
            master = data.master

            pairs = [
                ("load_forecast_kw", "total_station_load", "Load"),
                ("solar_forecast_kw", "solar_generation", "Solar"),
                ("wind_forecast_kw", "wind_generation", "Wind"),
            ]

            scored = False

            for predicted, actual, title in pairs:
                stats = _accuracy(held_out, actual, predicted)

                if not stats:
                    continue

                scored = True

                ui.card_title(f"{title} forecast accuracy")

                ui.metric_grid(
                    [
                        ("MAE (kW)", str(stats["MAE (kW)"]), None),
                        ("RMSE (kW)", str(stats["RMSE (kW)"]), None),
                        ("Bias (kW)", str(stats["Bias (kW)"]), None),
                        ("Error %", f"{stats['MAE % of mean']}%", None),
                    ],
                    columns=4,
                )

                st.caption(f"Scored over {stats['Points']:,} paired observations.")

            if not scored:
                st.caption(
                    "The held-out file does not carry matched actual and predicted "
                    "columns, so it cannot be scored here."
                )

    st.write("")

    # ---------------------------------------------------- model export ---
    forecast = data.forecast

    if forecast is not None and not forecast.empty:
        with st.container(border=True):
            ui.card_title("Model registry")

            models = [
                column
                for column in ("load_model", "solar_model", "wind_model")
                if column in forecast.columns
            ]

            if models:
                ui.rows(
                    (
                        column.replace("_model", "").replace("_", chr(32)).title(),
                        str(forecast[column].dropna().astype(str).unique()[0])
                        if not forecast[column].dropna().empty
                        else EM_DASH,
                    )
                    for column in models
                )
            else:
                st.caption("The forecast artefact does not record which models ran.")

    # --------------------------------------------------- plan judging ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Candidate plan judge")

        master = data.master

        if master is None or master.empty or data.latest is None:
            ui.empty_state("The master dataset is not available.")
            return

        reserve_floor = st.slider(
            "Test reserve floor (%)",
            min_value=5,
            max_value=60,
            value=int(assumptions.battery_reserve_floor_pct),
            help="Re-simulate the autonomy envelope with a stricter battery floor.",
        )

        candidate = settings.derive(
            assumptions, battery_reserve_floor_pct=float(reserve_floor)
        )

        baseline = outlook(master, data.latest, assumptions, cap_days=120)
        stressed = outlook(master, data.latest, candidate, cap_days=120)

        delta = stressed.headline_days - baseline.headline_days

        level = Level.SAFE if delta >= 0 else (
            Level.ATTENTION if delta > -2 else Level.CRITICAL
        )

        ui.accent_card(
            f"Adverse horizon moves {delta:+,.1f} d",
            (
                f"Baseline floor {assumptions.battery_reserve_floor_pct:,.0f}% gives "
                f"{baseline.headline_days:,.1f} d; a {reserve_floor:,.0f}% floor gives "
                f"{stressed.headline_days:,.1f} d."
            ),
            level,
            icon_name="gavel",
        )

        st.write("")

        ui.metric_grid(
            [
                ("Baseline horizon", f"{baseline.headline_days:,.1f} d", None),
                ("Stressed horizon", f"{stressed.headline_days:,.1f} d", None),
                ("Baseline margin", f"{baseline.cqrm.margin_days:+,.1f} d", None),
                ("Stressed margin", f"{stressed.cqrm.margin_days:+,.1f} d", None),
            ],
            columns=4,
        )

        st.caption(
            "Both cases are simulated with a shorter horizon cap so the comparison "
            "returns quickly; relative ranking is what matters here."
        )
