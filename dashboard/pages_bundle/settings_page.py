"""Settings page - the operator's planning assumptions, made explicit."""

from __future__ import annotations

import streamlit as st

from core import decisions, settings
from core.dataset import ARTEFACT_KEYS
from core.formatting import datetime_label
from core.paths import ASSUMPTIONS_PATH, DATA_DIR
from core.status import Level
from ui import components as ui

from pages_bundle import _shared


def render() -> None:
    data = _shared.data()

    ui.page_header(
        "Settings",
        "Planning inputs are operator assumptions, not measurements - they are "
        "kept separate and persisted so every recommendation stays auditable.",
        eyebrow="System",
    )

    active = settings.current()

    # ------------------------------------------------------ assumption ---
    with st.container(border=True):
        ui.card_title(
            "Planning assumptions",
            ui.pill(Level.INFO, "persisted to disk"),
        )

        changes: dict[str, float | int] = {}

        left, right = st.columns(2)

        for index, (key, meta) in enumerate(settings.FIELD_META.items()):
            holder = left if index % 2 == 0 else right

            value = getattr(active, key)

            with holder:
                if meta.integer:
                    changes[key] = st.slider(
                        f"{meta.label} ({meta.unit})",
                        min_value=int(meta.minimum),
                        max_value=int(meta.maximum),
                        value=int(value),
                        step=int(meta.step),
                        help=meta.help,
                        key=f"assumption_{key}",
                    )
                else:
                    changes[key] = st.slider(
                        f"{meta.label} ({meta.unit})",
                        min_value=float(meta.minimum),
                        max_value=float(meta.maximum),
                        value=float(value),
                        step=float(meta.step),
                        help=meta.help,
                        key=f"assumption_{key}",
                    )

        st.write("")

        apply_col, reset_col, _spacer = st.columns([1, 1, 3])

        with apply_col:
            if st.button("Save assumptions", type="primary", use_container_width=True):
                settings.update(**changes)

                decisions.record(
                    "assumptions_updated",
                    reason="Planning assumptions changed from the settings page",
                    page="settings",
                    context={"changes": {k: v for k, v in changes.items()}},
                )

                st.success("Assumptions saved.")
                st.rerun()

        with reset_col:
            if st.button("Reset to defaults", use_container_width=True):
                settings.reset()

                decisions.record(
                    "assumptions_reset",
                    reason="Planning assumptions returned to defaults",
                    page="settings",
                )

                st.info("Assumptions reset to documented defaults.")
                st.rerun()

        st.caption(
            "Defaults come from the project's documented planning basis. "
            "Changing a slider re-simulates the autonomy envelope on the "
            "decision pages."
        )

    # -------------------------------------------------------- effective ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Effective assumptions")

        if active != settings.Assumptions():
            ui.accent_card(
                "The planning basis differs from the project defaults",
                "Values below are what the decision pages are currently using.",
                Level.ATTENTION,
                icon_name="tune",
            )
            st.write("")

        st.dataframe(
            active.to_dict(),
            use_container_width=True,
        )

    # --------------------------------------------------------- storage ---
    st.write("")

    with st.container(border=True):
        ui.card_title("Storage locations")

        ui.rows(
            [
                ("Data directory", str(DATA_DIR)),
                ("Assumptions file", str(ASSUMPTIONS_PATH)),
                (
                    "Assumptions persisted",
                    "yes" if ASSUMPTIONS_PATH.exists() else "no",
                ),
                ("Artefacts loaded", f"{len(data.frames)} of {len(ARTEFACT_KEYS)}"),
                ("Loaded at", datetime_label(data.loaded_at)),
            ]
        )

    # --------------------------------------------------------- audit ---
    st.write("")

    with st.container(border=True):
        ui.card_title(
            "Decision audit trail",
            f"{decisions.count()} recorded",
        )

        history = decisions.recent(limit=15)

        if history.empty:
            st.caption("No operator decisions have been recorded yet.")
        else:
            display = history.copy()

            if "timestamp" in display.columns:
                display["timestamp"] = display["timestamp"].apply(datetime_label)

            st.dataframe(display, use_container_width=True, hide_index=True)

        st.caption(
            "Writes to the same operator_overrides table the API service exposes."
        )
