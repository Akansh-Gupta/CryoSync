"""Data and diagnostics page - what the dashboard is actually reading."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.formatting import EM_DASH, datetime_label, relative_age
from core.paths import PIPELINE_FILES
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def render() -> None:
    data = _shared.data()

    ui.page_header(
        "Data & diagnostics",
        "Every pipeline artefact the dashboard reads, and whether it loaded.",
        eyebrow="System",
    )

    master = data.master

    present = len(data.frames)
    missing = len(data.missing_keys)

    ui.metric_grid(
        [
            ("Artefacts found", f"{present} of {len(PIPELINE_FILES)}", None),
            ("Missing", str(missing), None),
            (
                "Master rows",
                f"{len(master):,}" if master is not None else EM_DASH,
                None,
            ),
            ("Loaded", relative_age(data.loaded_at), None),
        ],
        columns=4,
    )

    st.write("")

    # -------------------------------------------------------- inventory ---
    with st.container(border=True):
        ui.card_title("Artefact inventory")

        rows = []

        for artefact in PIPELINE_FILES:
            loaded = artefact.key in data.frames
            error = data.errors.get(artefact.key)

            frame = data.frames.get(artefact.key)

            rows.append(
                {
                    "Artefact": artefact.label,
                    "File": artefact.filename,
                    "Producer": artefact.producer,
                    "Cadence": artefact.cadence,
                    "Rows": len(frame) if frame is not None else 0,
                    "Size (KB)": artefact.size_kb,
                    "Status": "loaded"
                    if loaded
                    else ("missing" if not artefact.exists else "failed"),
                    "Detail": error or "",
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ----------------------------------------------------------- errors ---
    if data.errors:
        st.write("")

        with st.container(border=True):
            ui.card_title("Load problems")

            for key, message in data.errors.items():
                ui.accent_card(key, message, Level.ATTENTION, icon_name="warning")

    # ------------------------------------------------------ column check ---
    if master is not None and not master.empty:
        st.write("")

        with st.container(border=True):
            ui.card_title("Master dataset columns")

            expected = [
                "timestamp",
                "total_station_load",
                "solar_generation",
                "wind_generation",
                "battery_soc_pct",
                "fuel_level",
                "generator_output",
            ]

            rows = []

            for column in sorted(master.columns):
                series = master[column]

                rows.append(
                    {
                        "Column": column,
                        "Type": str(series.dtype),
                        "Non-null": int(series.notna().sum()),
                        "Null": int(series.isna().sum()),
                        "Expected": column in expected,
                    }
                )

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            absent = [column for column in expected if column not in master.columns]

            if absent:
                st.warning(
                    "Expected columns not present: " + ", ".join(absent)
                )

    # ---------------------------------------------------------- quality ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Integrity checks")

        problems: list[tuple[str, str]] = []

        if master is None:
            problems.append(("Master dataset", "Not loaded."))
        else:
            if "timestamp" in master.columns:
                if master["timestamp"].isna().any():
                    problems.append(
                        ("Timestamps", "Some rows have unparseable timestamps.")
                    )

                if not master["timestamp"].is_monotonic_increasing:
                    problems.append(
                        ("Ordering", "Rows are not in ascending time order.")
                    )

                duplicates = int(master["timestamp"].duplicated().sum())

                if duplicates:
                    problems.append(
                        ("Duplicates", f"{duplicates:,} repeated timestamps.")
                    )
            else:
                problems.append(("Timestamps", "No timestamp column present."))

            if "battery_flows_reconstructed" in master.columns:
                problems.append(
                    (
                        "Battery flows",
                        "Charge/discharge were reconstructed from the SoC "
                        "trajectory because the recorded flows were degenerate.",
                    )
                )

        if problems:
            for title, detail in problems:
                ui.accent_card(title, detail, Level.ATTENTION, icon_name="warning")
                st.write("")
        else:
            ui.accent_card(
                "All integrity checks passed",
                "Ordering, timestamps and recorded columns look consistent.",
                Level.SAFE,
                icon_name="verified",
            )
