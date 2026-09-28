"""Safety page - the hard constraints and interlocks the station must respect."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import settings
from core.autonomy import outlook
from core.formatting import EM_DASH, percent
from core.status import Level
from ui import components as ui
from twin.config import STATION_CONFIG

from pages_bundle import _shared


def _constraint(label: str, observed: float, limit: float, unit: str, lower_is_worse: bool = False):
    """Render one constraint as a pass/fail accent card."""

    if lower_is_worse:
        breached = observed < limit
    else:
        breached = observed > limit

    ui.accent_card(
        label,
        f"Observed {observed:,.1f} {unit} · limit {limit:,.1f} {unit}",
        Level.CRITICAL if breached else Level.SAFE,
        icon_name="dangerous" if breached else "check_circle",
    )


def render() -> None:
    data = _shared.data()

    master = data.master

    ui.page_header(
        "Safety constraints",
        "The interlocks that override any dispatch decision, and whether they hold.",
        eyebrow="Control",
    )

    if master is None or master.empty or data.latest is None:
        ui.empty_state("The master dataset is not available.")
        return

    latest = data.latest

    assumptions = settings.current()

    result = outlook(master, data.latest, assumptions)

    battery = STATION_CONFIG["battery_system"]
    generator = STATION_CONFIG["generator_system"]

    # ------------------------------------------------------ live checks ---
    with st.container(border=True):
        ui.card_title("Live constraint checks")

        soc = _shared.numeric(latest, "battery_soc_pct")
        gen_output = _shared.numeric(latest, "generator_output")

        bank = pd.DataFrame(
            [
                {
                    "Constraint": "Battery above hard floor",
                    "Observed": round(soc, 1),
                    "Limit": round(assumptions.battery_reserve_floor_pct, 1),
                    "Unit": "%",
                    "Status": "hold"
                    if soc >= assumptions.battery_reserve_floor_pct
                    else "breached",
                },
                {
                    "Constraint": "Generator within rated capacity",
                    "Observed": round(gen_output, 1),
                    "Limit": round(float(generator["capacity_kw"]), 1),
                    "Unit": "kW",
                    "Status": "hold"
                    if gen_output <= float(generator["capacity_kw"])
                    else "breached",
                },
                {
                    "Constraint": "Battery discharge within inverter limit",
                    "Observed": round(
                        abs(_shared.numeric(latest, "battery_discharge")), 1
                    ),
                    "Limit": round(float(battery["max_discharge_kw"]), 1),
                    "Unit": "kW",
                    "Status": "hold"
                    if abs(_shared.numeric(latest, "battery_discharge"))
                    <= float(battery["max_discharge_kw"])
                    else "breached",
                },
                {
                    "Constraint": "Battery charge within inverter limit",
                    "Observed": round(abs(_shared.numeric(latest, "battery_charge")), 1),
                    "Limit": round(float(battery["max_charge_kw"]), 1),
                    "Unit": "kW",
                    "Status": "hold"
                    if abs(_shared.numeric(latest, "battery_charge"))
                    <= float(battery["max_charge_kw"])
                    else "breached",
                },
            ]
        )

        breached = int((bank["Status"] == "breached").sum())

        ui.metric_grid(
            [
                ("Constraints checked", str(len(bank)), None),
                ("Breached", str(breached), None),
                ("Battery SoC", percent(soc), None),
                ("Generator output", f"{gen_output:,.1f} kW", None),
            ],
            columns=4,
        )

        st.write("")

        st.dataframe(bank, use_container_width=True, hide_index=True)

    # --------------------------------------------------- reserve floor ---
    st.write("")

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            ui.card_title("Battery reserve policy")

            reserve = result.reserve

            ui.rows(
                [
                    ("Hard floor", percent(reserve.reserve_floor_pct)),
                    ("Planning target", percent(reserve.reserve_target_pct)),
                    ("Current SoC", percent(reserve.battery_soc_pct)),
                    ("Effective floor", percent(reserve.effective_floor_pct)),
                    ("Above floor", "yes" if not reserve.floor_breached else "no"),
                    (
                        "Below target",
                        "yes" if reserve.battery_below_target else "no",
                    ),
                ]
            )

    with right:
        with st.container(border=True):
            ui.card_title("Diesel generator limits")

            ui.rows(
                [
                    ("Rated capacity", f"{float(generator['capacity_kw']):,.1f} kW"),
                    (
                        "Minimum loading",
                        f"{float(generator.get('min_load_fraction', 0)) * 100:,.0f}%",
                    ),
                    ("Current output", f"{gen_output:,.1f} kW"),
                    (
                        "Headroom",
                        f"{result.generator_headroom_kw:,.1f} kW",
                    ),
                    ("Status", str(latest.get("generator_status", "off")).upper()),
                ]
            )

    # ------------------------------------------------------ analysis ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Historic floor breaches")

        if "battery_soc_pct" not in master.columns:
            st.caption("Battery state of charge is not recorded in the dataset.")
        else:
            soc_series = pd.to_numeric(master["battery_soc_pct"], errors="coerce")

            floor = assumptions.battery_reserve_floor_pct

            breaches = int((soc_series < floor).sum())

            if breaches == 0:
                ui.accent_card(
                    "The floor has never been crossed",
                    f"Battery state of charge stayed above {floor:,.0f}% for all "
                    f"{len(master):,} recorded hours.",
                    Level.SAFE,
                    icon_name="verified_user",
                )
            else:
                first = master.loc[soc_series < floor, "timestamp"].min()

                ui.accent_card(
                    f"Floor crossed in {breaches:,} recorded hours",
                    f"First occurrence {first}. Review whether the floor is set "
                    "above what this station can physically maintain.",
                    Level.ATTENTION,
                    icon_name="battery_alert",
                )

            minimum = float(soc_series.min()) if not soc_series.dropna().empty else float("nan")

            ui.metric_grid(
                [
                    ("Recorded hours", f"{len(master):,}", None),
                    ("Hours below floor", f"{breaches:,}", None),
                    ("Minimum SoC", percent(minimum), None),
                    ("Floor", percent(floor), None),
                ],
                columns=4,
            )
