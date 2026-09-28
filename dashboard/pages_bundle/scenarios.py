"""Scenarios page - compare how the station fares under each condition set."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import settings
from core.autonomy import OUTCOME_LABELS, outlook
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def render() -> None:
    data = _shared.data()

    master = data.master

    ui.page_header(
        "Scenario comparison",
        "Measured months replayed to exhaustion, ranked by how long the station lasts.",
        eyebrow="Decision",
    )

    if master is None or master.empty or data.latest is None:
        ui.empty_state("The master dataset is not available.")
        return

    assumptions = settings.current()

    result = outlook(master, data.latest, assumptions)

    ranked = sorted(result.scenarios, key=lambda scenario: scenario.horizon_days)

    if not ranked:
        ui.empty_state("No condition scenarios could be built from the dataset.")
        return

    # --------------------------------------------------- outcome tiles ---
    ui.metric_grid(
        [
            (
                OUTCOME_LABELS["adverse"],
                f"{result.horizon_days.get('adverse', 0):,.1f} d",
                None,
            ),
            (
                OUTCOME_LABELS["expected"],
                f"{result.horizon_days.get('expected', 0):,.1f} d",
                None,
            ),
            (
                OUTCOME_LABELS["favourable"],
                f"{result.horizon_days.get('favourable', 0):,.1f} d",
                None,
            ),
            ("Scenarios", str(len(ranked)), None),
        ],
        columns=4,
    )

    st.write("")

    # ------------------------------------------------------- bar chart ---
    with st.container(border=True):
        ui.card_title("Horizon by scenario")

        chart_frame = pd.DataFrame(
            {
                "Month": [scenario.label for scenario in ranked],
                "Days": [round(scenario.horizon_days, 1) for scenario in ranked],
            }
        )

        _shared.bar_chart(
            chart_frame,
            x="Month",
            y="Days",
            height=340,
            y_title="Days",
            caption=(
                "The adverse outcome is the 10th percentile of these scenarios and "
                "is the number the autonomy verdict uses."
            ),
        )

    st.write("")

    # ---------------------------------------------------------- detail ---
    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            ui.card_title("Worst case scenarios")

            for scenario in ranked[:3]:
                ui.accent_card(
                    f"{scenario.label} · {scenario.horizon_days:,.1f} d",
                    (
                        "Ran out of energy within the planning window."
                        if not scenario.capped
                        else "Lasted beyond the planning window."
                    )
                    + f" Fuel used {scenario.fuel_used_l:,.0f} L.",
                    Level.ATTENTION if not scenario.capped else Level.SAFE,
                    icon_name="trending_down",
                )
                st.write("")

    with right:
        with st.container(border=True):
            ui.card_title("Best case scenarios")

            for scenario in reversed(ranked[-3:]):
                ui.accent_card(
                    f"{scenario.label} · {scenario.horizon_days:,.1f} d",
                    f"Mean net load {scenario.mean_deficit_kw:,.1f} kW.",
                    Level.SAFE,
                    icon_name="trending_up",
                )
                st.write("")

    # ---------------------------------------------------------- table ---
    st.write("")

    with st.container(border=True):
        ui.card_title("All scenarios")

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Month": scenario.label,
                        "Horizon (days)": round(scenario.horizon_days, 1),
                        "Simulated (days)": round(scenario.simulated_days, 1),
                        "Fuel used (L)": round(scenario.fuel_used_l, 0),
                        "Unserved (kWh)": round(scenario.unserved_kwh, 1),
                        "Mean net load (kW)": round(scenario.mean_deficit_kw, 1),
                        "Capped": scenario.capped,
                    }
                    for scenario in ranked
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
