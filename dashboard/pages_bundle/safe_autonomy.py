"""Safe autonomy page - how long the station survives with no resupply.

This is the analytical core of the product: measured conditions are replayed
through the station's own dispatch physics to produce the safe operability
horizon, and the horizon is compared with the conservative resupply arrival to
produce the Confidence-Qualified Resupply Margin.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import settings
from core.autonomy import METHODOLOGY, OUTCOME_LABELS, outlook
from core.formatting import EM_DASH, percent
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def render() -> None:
    data = _shared.data()

    master = data.master

    ui.page_header(
        "Safe autonomy",
        "How long the critical load can be served, and how much margin that leaves.",
        eyebrow="Decision",
    )

    if master is None or master.empty or data.latest is None:
        ui.empty_state("The master dataset is not available.")
        return

    assumptions = settings.current()

    result = outlook(master, data.latest, assumptions)

    verdict = result.cqrm

    # --------------------------------------------------------- verdict ---
    with st.container(border=True):
        ui.card_title(
            "Confidence-Qualified Resupply Margin",
            ui.pill(
                verdict.level,
                f"{verdict.margin_days:+,.1f} d",
            ),
        )

        ui.accent_card(
            verdict.verdict,
            (
                f"Adverse horizon {verdict.horizon_days:,.1f} d · conservative "
                f"resupply {verdict.resupply_days:,.1f} d · expected resupply "
                f"{result.resupply.expected_days:,.1f} d."
            ),
            verdict.level,
            icon_name="shield",
        )

        st.write("")

        ui.metric_grid(
            [
                ("Adverse horizon", f"{result.horizon_days.get('adverse', 0):,.1f} d", None),
                ("Expected horizon", f"{result.horizon_days.get('expected', 0):,.1f} d", None),
                ("Favourable horizon", f"{result.horizon_days.get('favourable', 0):,.1f} d", None),
                ("Storm day share", percent(result.storm_day_share * 100), None),
            ],
            columns=4,
        )

    st.write("")

    # ------------------------------------------------------ scenarios ---
    with st.container(border=True):
        ui.card_title(
            "Condition scenarios",
            f"{len(result.scenarios)} months replayed",
        )

        st.caption(
            "Each recent calendar month of measured net load is replayed from "
            "today's battery and fuel state until the load can no longer be served."
        )

        scenario_frame = pd.DataFrame(
            [
                {
                    "Month": scenario.label,
                    "Horizon (days)": round(scenario.horizon_days, 1),
                    "Fuel used (L)": round(scenario.fuel_used_l, 0),
                    "Unserved (kWh)": round(scenario.unserved_kwh, 1),
                    "Outcome": "beyond planning window"
                    if scenario.capped
                    else "ran out",
                }
                for scenario in sorted(
                    result.scenarios, key=lambda item: item.horizon_days
                )
            ]
        )

        st.dataframe(
            scenario_frame,
            use_container_width=True,
            hide_index=True,
        )

    st.write("")

    # -------------------------------------------------------- resupply ---
    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            ui.card_title("Resupply window")

            ui.rows(
                [
                    ("Expected arrival", f"{result.resupply.expected_days:,.1f} d"),
                    ("Optimistic arrival", f"{result.resupply.optimistic_days:,.1f} d"),
                    (
                        "Conservative arrival",
                        f"{result.resupply.conservative_days:,.1f} d",
                    ),
                    ("Delay spread", percent(result.resupply.delay_spread * 100)),
                    ("Storm day share", percent(result.resupply.storm_day_share * 100)),
                ]
            )

    with right:
        with st.container(border=True):
            ui.card_title("Energy reserve today")

            reserve = result.reserve

            ui.rows(
                [
                    ("Battery SoC", percent(reserve.battery_soc_pct)),
                    ("Reserve floor", percent(reserve.reserve_floor_pct)),
                    ("Effective floor", percent(reserve.effective_floor_pct)),
                    ("Battery available", f"{reserve.battery_kwh:,.0f} kWh"),
                    ("Fuel on site", f"{reserve.fuel_litres:,.0f} L"),
                    (
                        "Fuel runway",
                        f"{reserve.fuel_runway_days:,.1f} d"
                        if reserve.fuel_runway_days is not None
                        else EM_DASH,
                    ),
                ]
            )

    # --------------------------------------------------------- reserve ---
    if result.reserve.floor_breached:
        st.write("")
        ui.accent_card(
            "Battery is below the assumed reserve floor",
            (
                f"Charge is {result.reserve.battery_soc_pct:,.1f}% against a floor of "
                f"{result.reserve.reserve_floor_pct:,.1f}%. The simulation caps the "
                "floor at today's charge so autonomy is not overstated."
            ),
            Level.ATTENTION,
            icon_name="battery_alert",
        )

    # ----------------------------------------------------- methodology ---
    st.write("")

    with st.expander("How this is calculated"):
        for title, explanation in METHODOLOGY:
            st.markdown(f"**{title}**")
            st.caption(explanation)
