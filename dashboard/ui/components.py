"""Reusable layout primitives shared by every CRYOSYNC page.

A page should describe *what* it wants to show and let this module decide how
that looks. Everything here returns or renders small, self-contained pieces of
markup, so two pages never invent two different looking cards.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import streamlit as st

from core.status import ICON, LEVEL_LABEL, Level, tone


def _escape(text: object) -> str:
    """Escape text before it goes into raw HTML."""

    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# --------------------------------------------------------------- headers ---


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    """Standard page heading: eyebrow, title, one-line explanation."""

    if eyebrow:
        st.markdown(
            f'<div class="cryosync-eyebrow">{_escape(eyebrow)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(f"# {_escape(title)}")

    if subtitle:
        st.markdown(
            f'<div class="cryosync-page-sub">{_escape(subtitle)}</div>',
            unsafe_allow_html=True,
        )


def section(title: str, subtitle: str = "") -> None:
    """A section break inside a page."""

    st.markdown(f"### {_escape(title)}")

    if subtitle:
        st.caption(subtitle)


# ------------------------------------------------------------------ pills ---


def pill(level: Level, label: str | None = None, with_icon: bool = False) -> str:
    """Return the HTML for one status pill."""

    text = label or LEVEL_LABEL[level]

    prefix = ""

    if with_icon:
        prefix = f'<span class="material-symbols-rounded">{ICON[level]}</span>'

    return (
        f'<span class="cryosync-pill cryosync-pill-{tone(level)}">'
        f"{prefix}{_escape(text)}"
        "</span>"
    )


def pill_row(pills: Sequence[str]) -> None:
    """Render several already-built pills on one line."""

    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:0.35rem;">'
        + "".join(pills)
        + "</div>",
        unsafe_allow_html=True,
    )


def badge(level: Level, label: str | None = None) -> None:
    """Render a single status pill inline."""

    st.markdown(pill(level, label), unsafe_allow_html=True)


# ------------------------------------------------------------ accent card ---


def accent_card(
    title: str,
    body: str = "",
    level: Level = Level.NEUTRAL,
    icon_name: str = "",
) -> None:
    """A card with a coloured left rail, used for the most important state."""

    icon_markup = ""

    # Streamlit only loads the Material Symbols font inside its own icon
    # components, so a `material-symbols-rounded` span in custom HTML renders
    # the icon's *name* as text. A tone-coloured marker is used instead: it
    # always renders, and it carries no meaning on its own because the level
    # is already stated in words.
    marker = '<span class="cryosync-accent-marker"></span>' if icon_name else ""

    body_markup = (
        f'<span class="cryosync-accent-body">{_escape(body)}</span>' if body else ""
    )

    st.markdown(
        f'<div class="cryosync-accent-card cryosync-tone-{tone(level)}">'
        f'<span class="cryosync-accent-title">{marker}{_escape(title)}</span>'
        f"{body_markup}"
        "</div>",
        unsafe_allow_html=True,
    )


def card_title(title: str, right: str = "") -> None:
    """Small heading row inside a card."""

    right_markup = f"<div>{right}</div>" if right else ""

    st.markdown(
        '<div class="cryosync-card-head">'
        f'<div class="cryosync-card-title">{_escape(title)}</div>'
        f"{right_markup}"
        "</div>",
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------ label/value ---


def rows(pairs: Iterable[tuple[str, str]]) -> None:
    """Render a compact label/value list, as used by detail cards."""

    items = list(pairs)

    if not items:
        st.caption("No values available.")
        return

    body = "".join(
        '<div class="cryosync-row">'
        f'<span class="cryosync-row-label">{_escape(label)}</span>'
        f'<span class="cryosync-row-value">{_escape(value)}</span>'
        "</div>"
        for label, value in items
    )

    st.markdown(f'<div class="cryosync-rows">{body}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- metrics ---


def _tiles_fit(columns: int) -> bool:
    # Whether this many tiles leave each label enough room to be read.
    usable_width = 1200
    return usable_width / max(1, columns) >= 150

def metric_grid(metrics: Sequence[tuple[str, str, str | None]], columns: int = 4):
    """Render metric tiles in a responsive grid.

    ``metrics`` is a sequence of ``(label, value, delta)``; ``delta`` may be
    ``None``. Rows are created on demand so a page can pass any count.
    """

    items = list(metrics)

    if not items:
        return
    # Treat the requested count as a maximum: a four-across row inside a
    # half-width card leaves ~79 px per label at a 1280 px viewport, which is
    # why labels wrapped and ellipsised. Stack more loosely when cramped.
    while columns > 1 and not _tiles_fit(columns):
        columns -= 1
    for start in range(0, len(items), columns):
        chunk = items[start : start + columns]

        holders = st.columns(columns)

        for holder, (label, value, delta) in zip(holders, chunk):
            with holder:
                if delta:
                    st.metric(label, value, delta)
                else:
                    st.metric(label, value)


def stat_line(label: str, value: str) -> None:
    """A single label/value pair rendered as a muted caption line."""

    st.markdown(
        '<div class="cryosync-row">'
        f'<span class="cryosync-row-label">{_escape(label)}</span>'
        f'<span class="cryosync-row-value">{_escape(value)}</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def sub_caption(text: str) -> None:
    """Muted explanatory text under a chart or table."""

    st.caption(text)


def empty_state(message: str, hint: str = "") -> None:
    """Consistent placeholder when an artefact is unavailable."""

    st.info(message)

    if hint:
        st.caption(hint)


def footer(text: str) -> None:
    st.markdown(
        f'<div class="cryosync-foot">{_escape(text)}</div>',
        unsafe_allow_html=True,
    )
