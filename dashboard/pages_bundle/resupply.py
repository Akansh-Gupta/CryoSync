"""Resupply page - fuel logistics and the risk that a ship arrives late."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import settings
from core.autonomy import outlook, storm_day_share
from core.formatting import EM_DASH, litres, percent
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def render() -> None:
    data = _shared.data()

    master = data.master

    ui.page_header(
        "Resupply risk",
        "How the expected ship arrival compares with the station's autonomy.",
        eyebrow="Control",
    )

    if master is None or master.empty or data.latest is None:
        ui.empty_state("The master dataset is not available.")
        return

    assumptions = settings.current()

    result = outlook(master, data.latest, assumptions)

    plan = result.resupply

    verdict = result.cqrm

    # --------------------------------------------------------- verdict ---
    with st.container(border=True):
        ui.card_title(
            "Logistics margin",
            ui.pill(verdict.level, f"{verdict.margin_days:+,.1f} d"),
        )

        ui.accent_card(
            verdict.verdict,
            (
                f"Autonomy {verdict.horizon_days:,.1f} d · conservative arrival "
                f"{plan.conservative_days:,.1f} d."
            ),
            verdict.level,
            icon_name="local_shipping",
        )

        st.write("")

        ui.metric_grid(
            [
                ("Planned arrival", f"{plan.expected_days:,.1f} d", None),
                ("Optimistic", f"{plan.optimistic_days:,.1f} d", None),
                ("Conservative", f"{plan.conservative_days:,.1f} d", None),
                ("Delay spread", percent(plan.delay_spread * 100), None),
            ],
            columns=4,
        )

    st.write("")

    # -------------------------------------------------------- weather ---
    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            ui.card_title("Storm exposure")

            share = storm_day_share(master, assumptions.storm_wind_threshold_ms)

            ui.rows(
                [
                    ("Storm threshold", f"{assumptions.storm_wind_threshold_ms:,.1f} m/s"),
                    ("Storm day share", percent(share * 100)),
                    ("Delay multiplier", f"×{assumptions.logistics_delay_multiplier:,.2f}"),
                    ("Resulting spread", percent(plan.delay_spread * 100)),
                ]
            )

            st.caption(
                "The delay spread is the storm-day share scaled by the delay "
                "multiplier, capped so one stormy fortnight cannot dominate."
            )

    with right:
        with st.container(border=True):
            ui.card_title("Fuel position")

            latest = data.latest

            ui.rows(
                [
                    ("Fuel on site", litres(result.reserve.fuel_litres)),
                    (
                        "Fuel runway",
                        f"{result.reserve.fuel_runway_days:,.1f} d"
                        if result.reserve.fuel_runway_days is not None
                        else EM_DASH,
                    ),
                    ("Autonomy horizon", f"{verdict.horizon_days:,.1f} d"),
                    (
                        "Reserve to arrival",
                        f"{verdict.horizon_days - plan.conservative_days:+,.1f} d",
                    ),
                ]
            )

    # -------------------------------------------------- fuel trajectory ---
    if "fuel_level" in master.columns:
        st.write("")

        with st.container(border=True):
            ui.card_title("Fuel level, trailing 30 days")

            window = master.tail(720)

            _shared.line_chart(
                window,
                ["fuel_level"],
                height=300,
                y_title="L",
                caption="Consumption trend behind the runway estimate.",
            )

    # -------------------------------------------- sensitivity to delay ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Sensitivity to arrival delay")

        rows = []

        for days in (3, 5, 7, 10, 14, 21, 30):
            study = outlook(master, data.latest, assumptions.__class__(
                **{**assumptions.to_dict(), "planned_resupply_days": float(days)}
            ), cap_days=180)

            rows.append(
                {
                    "Planned arrival (d)": days,
                    "Conservative arrival (d)": round(
                        study.resupply.conservative_days, 1
                    ),
                    "Autonomy (d)": round(study.headline_days, 1),
                    "Margin (d)": round(study.cqrm.margin_days, 1),
                    "Verdict": study.cqrm.level.value,
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.caption(
            "Re-simulates the autonomy envelope for a range of planned arrivals so "
            "the operator can see where the margin disappears."
        )
