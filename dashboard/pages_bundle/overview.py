"""Overview page - the headline answer to "is the station okay right now?".

The page is deliberately ordered the way an operator reads: overall verdict,
then the numbers behind it, then what changed and what is being done about it.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import settings
from core.autonomy import outlook
from core.formatting import (
    EM_DASH,
    datetime_label,
    kilowatts,
    litres,
    percent,
)
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def _renewable_share(latest: pd.Series) -> float:
    """Share of demand currently met by solar and wind."""

    load = _shared.numeric(latest, "total_station_load")

    if load <= 0:
        return 0.0

    renewables = _shared.numeric(latest, "solar_generation") + _shared.numeric(
        latest, "wind_generation"
    )

    return max(0.0, min(1.0, renewables / load))


def render() -> None:
    data = _shared.data()

    master = data.master

    ui.page_header(
        "Station overview",
        "Current operating state, the headline autonomy verdict and active alerts.",
        eyebrow="Operations",
    )

    if master is None or master.empty:
        ui.empty_state(
            "The master dataset is not available.",
            "Run `python run_twin.py` to generate the digital twin output.",
        )
        return

    latest = data.latest

    assumptions = settings.current()

    result = outlook(master, latest, assumptions)

    # ---------------------------------------------------- verdict cards ---
    verdict = result.cqrm

    left, right = st.columns([2, 1])

    with left:
        with st.container(border=True):
            ui.card_title("Autonomy verdict")

            ui.accent_card(
                verdict.verdict,
                (
                    f"Adverse horizon {verdict.horizon_days:,.1f} d versus a conservative "
                    f"resupply arrival of {verdict.resupply_days:,.1f} d."
                ),
                verdict.level,
                icon_name="shield",
            )

            st.write("")

            ui.metric_grid(
                [
                    ("Safe operability", f"{result.headline_days:,.1f} d", None),
                    ("CQRM margin", f"{verdict.margin_days:+,.1f} d", None),
                    (
                        "Energy reserve",
                        kilowatts(result.reserve.equivalent_kwh, 0).replace(
                            "kW", "kWh"
                        ),
                        None,
                    ),
                    (
                        "Generator headroom",
                        kilowatts(result.generator_headroom_kw),
                        None,
                    ),
                ],
                # This card occupies two thirds of the content width, so two
                # tiles per row keeps every label readable.
                columns=2,
            )

    with right:
        with st.container(border=True):
            ui.card_title("Live state")

            ui.rows(
                [
                    ("Recorded", datetime_label(data.latest_timestamp)),
                    ("Station load", kilowatts(_shared.numeric(latest, "total_station_load"))),
                    ("Battery", percent(_shared.numeric(latest, "battery_soc_pct"))),
                    ("Fuel", litres(_shared.numeric(latest, "fuel_level"))),
                    (
                        "Generator",
                        str(latest.get("generator_status", "off")).upper(),
                    ),
                    ("Renewable share", percent(_renewable_share(latest) * 100)),
                ]
            )

    # --------------------------------------------------------- alerts ---
    st.write("")

    alerts = data.active_alerts()

    with st.container(border=True):
        ui.card_title(
            "Active alerts",
            ui.pill(
                Level.CRITICAL if len(alerts) else Level.SAFE,
                f"{len(alerts)} active" if len(alerts) else "All clear",
            ),
        )

        if alerts.empty:
            ui.accent_card(
                "No active alerts",
                "Every deterministic rule and anomaly check is currently satisfied.",
                Level.SAFE,
                icon_name="check_circle",
            )
        else:
            for _, alert in alerts.head(6).iterrows():
                level = _shared_level(alert)

                ui.accent_card(
                    _alert_title(alert),
                    str(alert.get("message", "Active system alert")),
                    level,
                    icon_name="warning"
                    if level is Level.ATTENTION
                    else "error",
                )
                st.write("")

    # -------------------------------------------------- reserve detail ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Dispatchable reserve")

        ui.metric_grid(
            [
                ("Battery available", f"{result.reserve.battery_kwh:,.0f} kWh", None),
                ("Fuel on site", litres(result.reserve.fuel_litres), None),
                (
                    "Reserve floor",
                    percent(result.reserve.reserve_floor_pct),
                    None,
                ),
                (
                    "Fuel runway",
                    f"{result.reserve.fuel_runway_days:,.1f} d"
                    if result.reserve.fuel_runway_days is not None
                    else EM_DASH,
                    None,
                ),
            ],
            columns=4,
        )

        st.caption(
            "Battery energy counts only the charge above the operator's reserve "
            "floor; the autonomy figures above come from replaying measured "
            "conditions through the station's own dispatch physics."
        )


def _shared_level(alert: pd.Series):
    """Map an alert row onto a status level."""

    from core.status import level_from_severity

    return level_from_severity(alert.get("severity", "warning"))


def _alert_title(alert: pd.Series) -> str:
    """Readable title for an alert row."""

    from core.status import alert_label

    return alert_label(alert.get("type", ""))
