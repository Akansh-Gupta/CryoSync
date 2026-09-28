"""System health page - are the engines behind the numbers actually well?"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.formatting import EM_DASH, datetime_label, relative_age
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def _level_from_score(score: float, attention: float, critical: float) -> Level:
    """Map a health score onto a status level (higher score is healthier)."""

    if score <= critical:
        return Level.CRITICAL

    if score <= attention:
        return Level.ATTENTION

    return Level.SAFE


def render() -> None:
    data = _shared.data()

    ui.page_header(
        "System health",
        "Health of the station assets and of the prediction engines themselves.",
        eyebrow="System",
    )

    # ------------------------------------------------------ asset health ---
    health = data.latest_health()

    with st.container(border=True):
        ui.card_title("Asset health")

        if health is None:
            ui.empty_state(
                "No maintenance artefact is available.",
                "Run `python run_pipeline.py` to score asset health.",
            )
        else:
            battery_score = _shared.numeric(health, "battery_health_score", 100.0)
            generator_score = _shared.numeric(health, "generator_health_score", 100.0)

            left, right = st.columns(2)

            with left:
                level = _level_from_score(battery_score, 60.0, 40.0)

                ui.accent_card(
                    f"Battery health {battery_score:,.1f}",
                    str(
                        health.get("battery_recommendation")
                        or health.get("recommendation")
                        or "No recommendation recorded."
                    ),
                    level,
                    icon_name="battery_charging_full",
                )

            with right:
                level = _level_from_score(generator_score, 60.0, 40.0)

                ui.accent_card(
                    f"Generator health {generator_score:,.1f}",
                    str(
                        health.get("generator_recommendation")
                        or health.get("recommendation")
                        or "No recommendation recorded."
                    ),
                    level,
                    icon_name="build",
                )

            st.write("")

            ui.metric_grid(
                [
                    ("Battery score", f"{battery_score:,.1f}", None),
                    ("Generator score", f"{generator_score:,.1f}", None),
                    (
                        "Scored at",
                        datetime_label(health.get("timestamp")),
                        None,
                    ),
                    (
                        "Age",
                        relative_age(health.get("timestamp")),
                        None,
                    ),
                ],
                columns=4,
            )

    # ------------------------------------------------------ engine state ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Prediction engines")

        engines = []

        for key, label in (
            ("forecast", "Forecasting engine"),
            ("dispatch", "Optimisation engine"),
            ("alerts", "Alert rule engine"),
            ("anomalies", "Anomaly detector"),
            ("maintenance", "Health scoring"),
        ):
            frame = data.frame(key)

            loaded = frame is not None

            engines.append(
                {
                    "Engine": label,
                    "Status": "reporting" if loaded else "no output",
                    "Rows": len(frame) if loaded else 0,
                    "Detail": ""
                    if loaded
                    else data.errors.get(key, "artefact not found"),
                }
            )

        st.dataframe(pd.DataFrame(engines), use_container_width=True, hide_index=True)

        reporting = sum(1 for engine in engines if engine["Status"] == "reporting")

        level = (
            Level.SAFE
            if reporting == len(engines)
            else (Level.ATTENTION if reporting else Level.CRITICAL)
        )

        st.write("")

        ui.accent_card(
            f"{reporting} of {len(engines)} engines reporting",
            "An engine with no output degrades its own cards only; the rest of "
            "the dashboard keeps working.",
            level,
            icon_name="memory",
        )

    # ------------------------------------------------------ anomalies ---
    st.write("")

    flagged = data.flagged_anomalies()

    with st.container(border=True):
        ui.card_title(
            "Anomaly detector",
            ui.pill(
                Level.ATTENTION if len(flagged) else Level.SAFE,
                f"{len(flagged)} flagged" if len(flagged) else "none flagged",
            ),
        )

        if flagged.empty:
            ui.accent_card(
                "No anomalies flagged",
                "Both the model and the physical sanity rules are satisfied over "
                "the trailing window.",
                Level.SAFE,
                icon_name="check_circle",
            )
        else:
            columns = [
                column
                for column in ("timestamp", "detected_category", "anomaly_score", "severity")
                if column in flagged.columns
            ]

            st.dataframe(
                flagged[columns].head(25),
                use_container_width=True,
                hide_index=True,
            )

            if "detected_category" in flagged.columns:
                counts = (
                    flagged["detected_category"]
                    .fillna("Unclassified")
                    .value_counts()
                    .rename("Count")
                    .rename_axis("Category")
                    .reset_index()
                )

                st.write("")
                ui.card_title("Detections by category")
                st.dataframe(counts, use_container_width=True, hide_index=True)
