"""Session and URL state for the dashboard shell.

Navigation, sidebar group expansion, the live-replay cursor and the last
refresh time all live here, so every page reads the same state and the
address bar always reflects the page a reviewer is looking at.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd
import streamlit as st

from core.registry import DEFAULT_PAGE, ITEM_BY_SLUG, NAV_GROUPS

PAGE_PARAM = "page"
PAGE_KEY = "nav_page"
GROUPS_KEY = "nav_open_groups"
REPLAY_KEY = "live_replay"
REFRESH_KEY = "last_manual_refresh"

DEFAULT_WINDOW_HOURS = 168
REPLAY_SPEEDS: tuple[float, ...] = (1.0, 4.0, 12.0, 48.0)


@dataclass(frozen=True)
class ReplayState:
    """Position and speed of the live-state replay."""

    cursor: int = 0
    playing: bool = False
    speed: float = 4.0
    window_hours: int = DEFAULT_WINDOW_HOURS

    def revealed(self, total: int) -> int:
        return max(0, min(self.cursor, total))

    def progress(self, total: int) -> float:
        if total <= 0:
            return 0.0

        return self.revealed(total) / total


def init_state() -> None:
    """Initialise every piece of shell state exactly once per session."""

    if PAGE_KEY not in st.session_state:
        requested = st.query_params.get(PAGE_PARAM)

        st.session_state[PAGE_KEY] = (
            requested if requested in ITEM_BY_SLUG else DEFAULT_PAGE
        )

    if GROUPS_KEY not in st.session_state:
        st.session_state[GROUPS_KEY] = {group.key: True for group in NAV_GROUPS}

    if REPLAY_KEY not in st.session_state:
        st.session_state[REPLAY_KEY] = ReplayState()

    if REFRESH_KEY not in st.session_state:
        st.session_state[REFRESH_KEY] = pd.Timestamp.now()


def active_page() -> str:
    """Slug of the page currently being rendered."""

    return st.session_state.get(PAGE_KEY, DEFAULT_PAGE)


def set_page(slug: str) -> None:
    """Switch pages, keeping the URL in step."""

    if slug not in ITEM_BY_SLUG:
        return

    st.session_state[PAGE_KEY] = slug
    st.query_params[PAGE_PARAM] = slug

    groups = dict(st.session_state.get(GROUPS_KEY, {}))

    for group in NAV_GROUPS:
        if any(item.slug == slug for item in group.items):
            groups[group.key] = True

    st.session_state[GROUPS_KEY] = groups


def group_is_open(key: str) -> bool:
    return bool(st.session_state.get(GROUPS_KEY, {}).get(key, True))


def toggle_group(key: str) -> None:
    groups = dict(st.session_state.get(GROUPS_KEY, {}))

    groups[key] = not groups.get(key, True)

    st.session_state[GROUPS_KEY] = groups


def replay() -> ReplayState:
    return st.session_state.get(REPLAY_KEY, ReplayState())


def set_replay(**changes: object) -> ReplayState:
    updated = replace(replay(), **changes)

    st.session_state[REPLAY_KEY] = updated

    return updated


def reset_replay(window_hours: int | None = None) -> ReplayState:
    """Rewind to the start of the replay window and start playing."""

    current = replay()

    return set_replay(
        cursor=0,
        playing=True,
        window_hours=window_hours or current.window_hours,
    )


def advance_replay(total: int) -> ReplayState:
    """Move the replay cursor forward by the configured speed."""

    current = replay()

    step = max(1, int(round(current.speed)))

    cursor = min(current.cursor + step, total)

    if cursor >= total:
        return set_replay(cursor=total, playing=False)

    return set_replay(cursor=cursor)


def mark_refreshed() -> pd.Timestamp:
    stamp = pd.Timestamp.now()

    st.session_state[REFRESH_KEY] = stamp

    return stamp


def last_refreshed() -> pd.Timestamp:
    return st.session_state.get(REFRESH_KEY, pd.Timestamp.now())
