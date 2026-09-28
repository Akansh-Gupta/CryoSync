"""The persistent CRYOSYNC shell: the dark top bar and the grouped sidebar.

This module owns everything that stays on screen no matter which page is
active, so an operator never loses their sense of place:

* the **top bar** carries the product badge, a tab strip for the pages of the
  section being viewed, and live status chips (overall state, active alerts,
  data age, clock);
* the **sidebar** carries the full navigation, grouped exactly as
  :mod:`core.registry` declares it, with the active page marked.

Navigation is rendered with real Streamlit buttons styled by the theme rather
than raw HTML links, because Streamlit buttons keep keyboard focus, work with
screen readers, and update session state without a full page reload.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import state
from core.formatting import datetime_label, relative_age
from core.registry import NAV_GROUPS, NavItem, group_for, item_for
from core.status import Level, worst_level
from ui import components as ui


def _status_chip(label: str, value: str, level: Level) -> str:
    """One chip in the top bar."""

    return (
        '<span class="cryosync-chip">'
        f'<span class="cryosync-chip-label">{ui._escape(label)}</span>'
        f'<span class="cryosync-chip-dot cryosync-dot-{level.value}"></span>'
        f"{ui._escape(value)}"
        "</span>"
    )


def _overall_level(active_alerts: int, missing_keys: int) -> Level:
    """Station-level status derived from alerts and missing data."""

    levels: list[Level] = []

    if missing_keys > 0:
        levels.append(Level.ATTENTION)

    if active_alerts >= 3:
        levels.append(Level.CRITICAL)
    elif active_alerts > 0:
        levels.append(Level.ATTENTION)
    else:
        levels.append(Level.SAFE)

    return worst_level(levels)


def top_bar(
    *,
    active_alerts: int = 0,
    missing_keys: int = 0,
    latest_timestamp: pd.Timestamp | None = None,
) -> None:
    """Render the dark top bar: badge, page tabs, status chips.

    The tab strip shows the sibling pages of the section the operator is
    currently in, which is how the reference product lets you move between
    related views without returning to the sidebar.
    """

    current = item_for(state.active_page())

    group = group_for(current.slug)

    level = _overall_level(active_alerts, missing_keys)

    alert_text = f"{active_alerts} active" if active_alerts else "None"

    alert_level = Level.SAFE
    if active_alerts >= 3:
        alert_level = Level.CRITICAL
    elif active_alerts > 0:
        alert_level = Level.ATTENTION
    stamp = (
        datetime_label(latest_timestamp) if latest_timestamp is not None else "no data"
    )

    data_level = Level.INFO if latest_timestamp is not None else Level.NEUTRAL
    chips = "".join(
        [
            _status_chip("Station", level.value.upper(), level),
            _status_chip("Alerts", alert_text, alert_level),
            _status_chip("Data", stamp, data_level),
            _status_chip("Updated", relative_age(state.last_refreshed()), Level.NEUTRAL),
        ]
    )

    st.markdown(
        '<div class="cryosync-topbar" style="margin-bottom:0.35rem;">'
        '<div class="cryosync-badge">'
        '<div class="cryosync-badge-mark">❄</div>'
        "<div>"
        '<div class="cryosync-badge-name">CRYOSYNC</div>'
        '<div class="cryosync-badge-sub">Energy Intelligence</div>'
        "</div>"
        "</div>"
        f'<div class="cryosync-chips">{chips}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    _tab_strip(group)


def _tab_strip(group) -> None:
    """Render the section's pages as flat tabs."""

    # Button keys are prefixed `tab_`; the stylesheet finds exactly these
    # buttons by that prefix and renders them as flat tabs.
    items = list(group.items)

    holders = st.columns([1] * len(items) + [3])

    for holder, item in zip(holders, items):
        with holder:
            if _nav_button(item, key=f"tab_{item.slug}", in_tab_strip=True):
                return


def _nav_button(item: NavItem, key: str, in_tab_strip: bool = False) -> bool:
    """Render one navigation button; return True when it was clicked."""

    active = state.active_page() == item.slug

    label = f"{item.icon} {item.label}" if not in_tab_strip else item.label

    clicked = st.button(
        label,
        key=key,
        type="primary" if active else "secondary",
        use_container_width=True,
        help=item.caption,
    )

    if clicked and not active:
        state.set_page(item.slug)
        st.rerun()

    return clicked and not active


def sidebar(*, active_alerts: int = 0, missing_keys: int = 0) -> None:
    """Render the grouped, collapsible navigation sidebar."""

    with st.sidebar:
        st.markdown(
            '<div class="cryosync-sidebar-meta">'
            "Offline-first decision support<br>for polar research stations"
            "</div>",
            unsafe_allow_html=True,
        )

        for group in NAV_GROUPS:
            open_now = state.group_is_open(group.key)

            arrow = "▾" if open_now else "▸"

            # The header doubles as the collapse control.
            if st.button(
                f"{arrow}  {group.label}",
                key=f"group_{group.key}",
                type="tertiary",
                use_container_width=True,
                help=group.blurb,
            ):
                state.toggle_group(group.key)
                st.rerun()

            if not open_now:
                continue

            for item in group.items:
                _nav_button(item, key=f"nav_{item.slug}")

        st.divider()

        ui.rows(
            [
                ("Active alerts", str(active_alerts)),
                ("Missing data", str(missing_keys)),
            ]
        )


def alert_count(data) -> int:
    """Number of unresolved alerts, tolerating a missing artefact."""

    try:
        return int(len(data.active_alerts()))
    except Exception:  # noqa: BLE001 - a broken artefact must not break chrome
        return 0
