"""Live state page - the station as it evolved, with replay control.

The operator picks a trailing window, then either reads the whole window at
once or replays it hour by hour. The replay cursor lives in
:mod:`core.state`, so moving between pages does not lose the operator's place.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import state
from core.formatting import kilowatts, percent
from core.status import Level
from ui import components as ui

from pages_bundle import _shared

WINDOWS: tuple[tuple[str, int], ...] = (
    ("Last 24 hours", 24),
    ("Last 7 days", 168),
    ("Last 30 days", 720),
    ("Last 90 days", 2160),
)


def _window_frame(master: pd.DataFrame, hours: int) -> pd.DataFrame:
    """Trailing window, trimmed to the rows that exist."""

    return master.tail(max(1, hours)).copy()


def render() -> None:
    data = _shared.data()

    master = data.master

    ui.page_header(
        "Live state replay",
        "Replay the recorded station state and watch supply meet demand.",
        eyebrow="Operations",
    )

    if master is None or master.empty:
        ui.empty_state("The master dataset is not available.")
        return

    current = state.replay()

    control_left, control_mid, control_right = st.columns([2, 1, 1])

    with control_left:
        labels = [label for label, _ in WINDOWS]

        default_index = min(
            range(len(WINDOWS)),
            key=lambda index: abs(WINDOWS[index][1] - current.window_hours),
        )

        chosen = st.selectbox(
            "Replay window",
            labels,
            index=default_index,
            help="How much recorded history to load into the replay.",
        )

        hours = dict(WINDOWS)[chosen]

    with control_mid:
        speed = st.select_slider(
            "Replay speed",
            options=state.REPLAY_SPEEDS,
            value=current.speed,
            format_func=lambda value: f"×{value:g}",
            help="Rows revealed per second while the replay is running.",
        )

    with control_right:
        st.write("")
        st.write("")

        if st.button("Start replay", type="primary", use_container_width=True):
            state.reset_replay(window_hours=hours)
            state.set_replay(speed=speed)
            st.rerun()

    if hours != current.window_hours or speed != current.speed:
        state.set_replay(window_hours=hours, speed=speed)

    window = _window_frame(master, hours)

    active = state.replay()

    if active.playing:
        # Reveal only the rows reached so far, then step the cursor on.
        visible = max(1, active.revealed(len(window)))
        shown = window.tail(visible).copy()
        state.advance_replay(len(window))
    else:
        shown = window.copy()

    pause_col, meta_col = st.columns([1, 4])

    with pause_col:
        if active.playing and st.button("Pause", use_container_width=True):
            state.set_replay(playing=False)
            st.rerun()

    with meta_col:
        st.caption(
            f"{chosen} · {len(shown):,} of {len(window):,} hours shown"
            + (" · replaying" if state.replay().playing else " · paused")
        )

    # ------------------------------------------------------- headline ---
    latest_shown = shown.iloc[-1]

    ui.metric_grid(
        [
            (
                "Station load",
                kilowatts(_shared.numeric(latest_shown, "total_station_load")),
                None,
            ),
            (
                "Solar",
                kilowatts(_shared.numeric(latest_shown, "solar_generation")),
                None,
            ),
            (
                "Wind",
                kilowatts(_shared.numeric(latest_shown, "wind_generation")),
                None,
            ),
            (
                "Battery",
                percent(_shared.numeric(latest_shown, "battery_soc_pct")),
                None,
            ),
            (
                "Diesel",
                kilowatts(_shared.numeric(latest_shown, "generator_output")),
                None,
            ),
            ("Fuel", f"{_shared.numeric(latest_shown, 'fuel_level'):,.0f} L", None),
        ],
        columns=6,
    )

    st.write("")

    # ---------------------------------------------------------- chart ---
    with st.container(border=True):
        ui.card_title("Power mix")

        _shared.line_chart(
            shown,
            [
                "total_station_load",
                "solar_generation",
                "wind_generation",
                "generator_output",
            ],
            caption=(
                "Station demand against each supply source. Diesel appears only "
                "when renewables and battery cannot meet the load."
            ),
        )

    lower_left, lower_right = st.columns(2)

    with lower_left:
        with st.container(border=True):
            ui.card_title("Battery state of charge")

            _shared.line_chart(
                shown,
                ["battery_soc_pct"],
                height=280,
                y_title="%",
                caption="Charge held in the battery across the replay window.",
            )

    with lower_right:
        with st.container(border=True):
            ui.card_title("Fuel level")

            _shared.line_chart(
                shown,
                ["fuel_level"],
                height=280,
                y_title="L",
                caption="Falling line indicates diesel consumption.",
            )

    # -------------------------------------------------- diesel insight ---
    if "generator_output" in window.columns:
        diesel_hours = int((window["generator_output"] > 0).sum())

        if diesel_hours == 0:
            ui.accent_card(
                "Diesel was not required in this window",
                "Renewables and storage met the whole load. Widen the window to "
                "find periods when the generator ran.",
                Level.SAFE,
                icon_name="check_circle",
            )
        else:
            ui.accent_card(
                f"Diesel ran for {diesel_hours:,} of {len(window):,} hours",
                f"{diesel_hours / len(window) * 100:,.1f}% of the window needed fossil backup.",
                Level.ATTENTION if diesel_hours / len(window) > 0.1 else Level.INFO,
                icon_name="local_gas_station",
            )
