"""History page - explore any trailing window of recorded station operation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.formatting import datetime_label, kilowatts, percent
from core.status import Level
from ui import components as ui

from pages_bundle import _shared

METRICS: tuple[tuple[str, str, str], ...] = (
    ("total_station_load", "Station load", "kW"),
    ("renewable_generation", "Renewables", "kW"),
    ("battery_soc_pct", "Battery SoC", "%"),
    ("fuel_level", "Fuel level", "L"),
    ("generator_output", "Diesel", "kW"),
    ("wind_speed", "Wind speed", "m/s"),
    ("temperature", "Temperature", "°C"),
    ("occupancy", "Occupancy", "people"),
)


def render() -> None:
    data = _shared.data()

    master = data.master

    ui.page_header(
        "Historical explorer",
        "Query any window of recorded operation and compare series side by side.",
        eyebrow="System",
    )

    if master is None or master.empty or "timestamp" not in master.columns:
        ui.empty_state("The master dataset is not available.")
        return

    available = [
        (column, label, unit)
        for column, label, unit in METRICS
        if column in master.columns
    ]

    # -------------------------------------------------------- controls ---
    with st.container(border=True):
        ui.card_title("Query")

        latest = pd.Timestamp(master["timestamp"].max())
        earliest = pd.Timestamp(master["timestamp"].min())

        control_left, control_right = st.columns(2)

        with control_left:
            start_date = st.date_input(
                "From",
                value=(latest - pd.Timedelta(days=30)).date(),
                min_value=earliest.date(),
                max_value=latest.date(),
            )

        with control_right:
            end_date = st.date_input(
                "To",
                value=latest.date(),
                min_value=earliest.date(),
                max_value=latest.date(),
            )

        chosen = st.multiselect(
            "Series to plot",
            options=[label for _, label, _ in available],
            default=[label for _, label, _ in available][:4],
            help="Compare any combination of recorded measurements.",
        )

        aggregation = st.radio(
            "Resolution",
            ["Hourly", "Daily mean"],
            horizontal=True,
            help="Daily mean smooths the diurnal cycle to show longer trends.",
        )

    lookup = {label: (column, unit) for column, label, unit in available}

    selected_columns = [lookup[label][0] for label in chosen if label in lookup]

    if not selected_columns:
        ui.empty_state("Select at least one series to plot.")
        return

    # ---------------------------------------------------------- filter ---
    window = master[
        (master["timestamp"] >= pd.Timestamp(start_date))
        & (master["timestamp"] <= pd.Timestamp(end_date) + pd.Timedelta(days=1))
    ].copy()

    if window.empty:
        ui.empty_state("No records fall inside the selected window.")
        return

    if aggregation == "Daily mean":
        numeric = window.set_index("timestamp")[selected_columns].apply(
            pd.to_numeric, errors="coerce"
        )

        window = (
            numeric.resample("D")
            .mean()
            .reset_index()
            .dropna(how="all", subset=selected_columns)
        )

        caption = "Daily mean of each selected series."
    else:
        caption = "Recorded hourly values."

    # --------------------------------------------------------- summary ---
    first = window.iloc[0]
    last = window.iloc[-1]

    ui.metric_grid(
        [
            (
                "Window start",
                datetime_label(window["timestamp"].min()),
                None,
            ),
            (
                "Window end",
                datetime_label(window["timestamp"].max()),
                None,
            ),
            ("Points", f"{len(window):,}", None),
            ("Series", str(len(selected_columns)), None),
        ],
        columns=4,
    )

    st.write("")

    # ----------------------------------------------------------- chart ---
    with st.container(border=True):
        ui.card_title("Time series")

        units = {lookup[label][1] for label in chosen if label in lookup}

        _shared.line_chart(
            window,
            selected_columns,
            height=420,
            y_title=next(iter(units)) if len(units) == 1 else "value",
            caption=caption
            + (
                " Note the series use different units, so compare shape rather than height."
                if len(units) > 1
                else ""
            ),
        )

    # ----------------------------------------------------------- stats ---
    st.write("")

    summary = []

    for column in selected_columns:
        series = pd.to_numeric(window[column], errors="coerce").dropna()

        if series.empty:
            continue

        summary.append(
            {
                "Series": _shared.label_for(column),
                "Minimum": round(float(series.min()), 2),
                "Mean": round(float(series.mean()), 2),
                "Maximum": round(float(series.max()), 2),
                "Latest": round(float(series.iloc[-1]), 2),
            }
        )

    if summary:
        with st.container(border=True):
            ui.card_title("Summary statistics")

            st.dataframe(
                pd.DataFrame(summary),
                use_container_width=True,
                hide_index=True,
            )

    # --------------------------------------------------------- records ---
    with st.expander("Show raw records"):
        raw_columns = ["timestamp"] + selected_columns

        st.dataframe(
            window[raw_columns].tail(500),
            use_container_width=True,
            hide_index=True,
        )

        st.caption("Showing the most recent 500 rows of the selected window.")
