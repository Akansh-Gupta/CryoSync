"""Recommended plan page - the dispatch schedule and the operator's decision.

Presents the optimiser's fuel-minimising schedule, states what it saves, and
lets the operator accept or reject it. Every decision is written to the audit
trail through :mod:`core.decisions`.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import decisions
from core.formatting import datetime_label, kilowatts, litres
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def render() -> None:
    data = _shared.data()

    dispatch = data.dispatch

    ui.page_header(
        "Recommended plan",
        "The fuel-minimising dispatch schedule for the next 24 hours.",
        eyebrow="Decision",
    )

    if dispatch is None or dispatch.empty:
        ui.empty_state(
            "No dispatch plan is available.",
            "Run `python run_pipeline.py` to generate the optimiser output.",
        )
        return

    horizon = dispatch.tail(24).copy()

    # -------------------------------------------------------- headline ---
    def total(column: str) -> float:
        if column not in horizon.columns:
            return 0.0

        return float(pd.to_numeric(horizon[column], errors="coerce").fillna(0).sum())

    diesel_kwh = total("diesel_kw")
    saving = total("fuel_saving_vs_all_diesel_l")

    diesel_hours = (
        int((pd.to_numeric(horizon["diesel_kw"], errors="coerce") > 0).sum())
        if "diesel_kw" in horizon.columns
        else 0
    )

    level = Level.SAFE if diesel_hours == 0 else (
        Level.ATTENTION if diesel_hours > 6 else Level.INFO
    )

    with st.container(border=True):
        ui.card_title("Plan summary", ui.pill(level, f"{diesel_hours} diesel hours"))

        ui.metric_grid(
            [
                ("Diesel energy", f"{diesel_kwh:,.0f} kWh", None),
                ("Fuel saved", litres(saving), None),
                (
                    "Solar to load",
                    f"{total('solar_to_load_kw'):,.0f} kWh",
                    None,
                ),
                (
                    "Battery to load",
                    f"{total('battery_to_load_kw'):,.0f} kWh",
                    None,
                ),
            ],
            columns=4,
        )

        st.caption(
            "Fuel saving is measured against running the generator for the whole "
            "horizon, which is the fallback if no plan is followed."
        )

    st.write("")

    # ----------------------------------------------------------- chart ---
    with st.container(border=True):
        ui.card_title("Dispatch schedule")

        _shared.line_chart(
            horizon,
            ["load_forecast_kw", "soc_kwh"],
            height=340,
            caption="Planned demand against the battery trajectory the plan assumes.",
        )

    # ----------------------------------------------------------- table ---
    columns = [
        column
        for column in (
            "timestamp",
            "load_forecast_kw",
            "solar_to_load_kw",
            "battery_to_load_kw",
            "diesel_kw",
            "soc_kwh",
            "fuel_remaining_l",
            "fuel_saving_vs_all_diesel_l",
        )
        if column in horizon.columns
    ]

    with st.container(border=True):
        ui.card_title("Hourly plan")

        st.dataframe(
            horizon[columns],
            use_container_width=True,
            hide_index=True,
        )

    # -------------------------------------------------------- decision ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Operator decision")

        st.caption(
            "Approving records the plan in the audit trail; rejecting records why "
            "it was not accepted."
        )

        reason = st.text_input(
            "Reason / note",
            placeholder="For example: hold battery reserve for the incoming storm",
        )

        approve, reject = st.columns(2)

        with approve:
            if st.button("Approve plan", type="primary", use_container_width=True):
                outcome = decisions.record(
                    "plan_approved",
                    reason=reason,
                    page="recommended_plan",
                    context={
                        "diesel_kwh": round(diesel_kwh, 1),
                        "fuel_saved_l": round(saving, 1),
                        "hours": len(horizon),
                    },
                )

                outcome_status = str(outcome["status"]).replace("_", chr(32))
                st.success(f"Plan approved ({outcome_status}).")
                st.rerun()

        with reject:
            if st.button("Reject plan", use_container_width=True):
                outcome = decisions.record(
                    "plan_rejected",
                    reason=reason,
                    page="recommended_plan",
                    context={"diesel_kwh": round(diesel_kwh, 1)},
                )

                outcome_status = str(outcome["status"]).replace("_", chr(32))
                st.warning(f"Plan rejected ({outcome_status}).")
                st.rerun()

    # ---------------------------------------------------------- audit ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Recent decisions", f"{decisions.count()} recorded")

        history = decisions.recent(limit=10)

        if history.empty:
            st.caption("No decisions have been recorded yet.")
        else:
            display = history.copy()

            if "timestamp" in display.columns:
                display["timestamp"] = display["timestamp"].apply(datetime_label)

            st.dataframe(display, use_container_width=True, hide_index=True)
