"""The CRYOSYNC visual system.

Every colour, radius, shadow and piece of spacing is declared once here as a
CSS custom property, and the rest of this module only ever refers to those
variables. That is what keeps the top bar, the sidebar, a metric tile and an
alert card visually consistent no matter which page renders them.

The design intent, taken from the reference product:

* A dark, slightly blue-charcoal top bar carries the product badge, the page
  tab strip, the status chips and the live clock - so an operator always knows
  which station, which page and what the current state is.
* A light, grouped sidebar holds the navigation. Groups are collapsible,
  items carry a Material Symbols icon, and the active item is marked with both
  a tinted background and a coloured left rail rather than colour alone.
* Content sits on cards: white, 1px border, soft radius, restrained shadow.
* Status is a coloured pill or a left-accent bar, never the sole carrier of
  meaning - the level label or icon is always present too.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------- palette ---
# Single source of truth. Change a value here and the whole dashboard follows.
PALETTE: dict[str, str] = {
    # Shell
    "shell": "#131A24",
    "shell_raised": "#1B2431",
    "shell_border": "#2A3646",
    "shell_text": "#E8EDF4",
    "shell_text_muted": "#94A3B8",
    # Page
    "page": "#F4F6F9",
    "surface": "#FFFFFF",
    "surface_alt": "#FAFBFD",
    "border": "#E3E8EF",
    "border_strong": "#CDD5DF",
    "text": "#111827",
    "text_muted": "#667085",
    "text_faint": "#98A2B3",
    # Brand accent - the operator action colour
    "accent": "#E8590C",
    "accent_hover": "#C94C08",
    "accent_soft": "#FEF0E6",
    # Status
    "critical": "#C62828",
    "critical_soft": "#FDEC",
    "attention": "#B7791F",
    "attention_soft": "#FDF6E7",
    "safe": "#2E7D4F",
    "safe_soft": "#EAF6EF",
    "info": "#2F6FB8",
    "info_soft": "#EAF2FB",
    "neutral": "#667085",
    "neutral_soft": "#F2F4F7",
}

# Radii and spacing kept in one place so cards, pills and inputs line up.
RADIUS = "10px"
RADIUS_SM = "6px"
RADIUS_PILL = "999px"
TOPBAR_HEIGHT = "58px"


def _variables() -> str:
    """Render the palette as CSS custom properties."""

    declarations = "\n".join(
        f"            --cryosync-{name.replace('_', '-')}: {value};"
        for name, value in PALETTE.items()
    )

    return (
        ":root {\n"
        f"{declarations}\n"
        f"            --cryosync-radius: {RADIUS};\n"
        f"            --cryosync-radius-sm: {RADIUS_SM};\n"
        f"            --cryosync-radius-pill: {RADIUS_PILL};\n"
        f"            --cryosync-topbar-height: {TOPBAR_HEIGHT};\n"
        "        }"
    )


STYLESHEET = f"""
<style>
    {_variables()}

    /* ---------------------------------------------------------- shell --- */
    /* Streamlit reserves space for its own header; the custom top bar
       replaces it, so the native one is removed and the block padding is
       pulled up to sit flush underneath our bar. */
    header[data-testid="stHeader"] {{
        background: transparent;
        height: 0;
    }}

    [data-testid="stAppViewContainer"] > .main {{
        background: var(--cryosync-page);
    }}

    .block-container {{
        padding-top: 1.1rem;
        padding-bottom: 3rem;
        max-width: 1560px;
    }}

    html, body, [class*="css"] {{
        font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
    }}

    /* -------------------------------------------------------- top bar --- */
    .cryosync-topbar {{
        display: flex;
        align-items: center;
        gap: 1.35rem;
        background: var(--cryosync-shell);
        border: 1px solid var(--cryosync-shell-border);
        border-radius: var(--cryosync-radius);
        padding: 0 1.05rem;
        height: var(--cryosync-topbar-height);
        margin-bottom: 1.15rem;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.16);
    }}

    .cryosync-badge {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding-right: 1.35rem;
        border-right: 1px solid var(--cryosync-shell-border);
        height: 100%;
        flex-shrink: 0;
    }}

    .cryosync-badge-mark {{
        display: grid;
        place-items: center;
        width: 30px;
        height: 30px;
        border-radius: 8px;
        background: var(--cryosync-accent);
        color: #FFFFFF;
        font-size: 1rem;
        line-height: 1;
    }}

    .cryosync-badge-name {{
        color: var(--cryosync-shell-text);
        font-size: 0.94rem;
        font-weight: 650;
        letter-spacing: 0.01em;
        line-height: 1.15;
    }}

    .cryosync-badge-sub {{
        color: var(--cryosync-shell-text-muted);
        font-size: 0.7rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }}

    /* --------------------------------------------------- tab strip --- */
    /* The top-bar tabs are real Streamlit buttons restyled as flat tabs, so
       navigation stays keyboard accessible instead of becoming raw HTML.
       Streamlit exposes each widget's key as a `st-key-<key>` class, which is
       the stable hook used here - the tab keys are prefixed `tab_`. The row
       they sit in is painted as part of the top bar so it does not read as a
       separate white card. */
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-tab_"]) {{
        background: var(--cryosync-shell);
        border: 1px solid var(--cryosync-shell-border);
        border-radius: var(--cryosync-radius);
        padding: 0.3rem 0.5rem;
        margin-bottom: 1.15rem;
        align-items: center;
        gap: 0.15rem;
    }}

    /* The spacer column after the tabs must not show as an empty widget. */
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-tab_"]) > div {{
        width: auto !important;
        flex: 0 0 auto !important;
    }}

    div[data-testid="stHorizontalBlock"]:has([class*="st-key-tab_"]) > div:last-child {{
        flex: 1 1 auto !important;
    }}
    div[class*="st-key-tab_"] button[kind="secondary"],
    div[class*="st-key-tab_"] button[kind="secondaryFormSubmit"] {{
        background: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: var(--cryosync-radius-sm) var(--cryosync-radius-sm) 0 0;
        color: var(--cryosync-shell-text-muted) !important;
        font-size: 0.85rem;
        font-weight: 550;
        padding: 0.32rem 0.7rem;
        margin-bottom: 0;
        min-height: 34px;
        box-shadow: none !important;
    }}

    div[class*="st-key-tab_"] button[kind="secondary"]:hover,
    div[class*="st-key-tab_"] button[kind="secondaryFormSubmit"]:hover {{
        background: var(--cryosync-shell-raised) !important;
        color: var(--cryosync-shell-text) !important;
        border-bottom: 2px solid var(--cryosync-shell-border) !important;
    }}

    /* Active tab: raised fill plus an accent underline. */
    div[class*="st-key-tab_"] button[kind="primary"],
    div[class*="st-key-tab_"] button[kind="primaryFormSubmit"] {{
        background: var(--cryosync-shell-raised) !important;
        border: none !important;
        border-bottom: 2px solid var(--cryosync-accent) !important;
        border-radius: var(--cryosync-radius-sm) var(--cryosync-radius-sm) 0 0;
        color: #FFFFFF !important;
        font-size: 0.85rem;
        font-weight: 650;
        padding: 0.32rem 0.7rem;
        margin-bottom: 0;
        min-height: 34px;
        box-shadow: none !important;
    }}

    /* ------------------------------------------------ status chips --- */
    .cryosync-chips {{
        display: flex;
        align-items: center;
        gap: 0.45rem;
        flex-shrink: 0;
    }}

    .cryosync-chip {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.3rem 0.62rem;
        border-radius: var(--cryosync-radius-pill);
        background: var(--cryosync-shell-raised);
        border: 1px solid var(--cryosync-shell-border);
        color: var(--cryosync-shell-text);
        font-size: 0.76rem;
        font-weight: 550;
        white-space: nowrap;
    }}

    .cryosync-chip-label {{
        color: var(--cryosync-shell-text-muted);
        font-weight: 500;
    }}

    .cryosync-chip-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex-shrink: 0;
    }}

    .cryosync-dot-critical {{ background: #F26B6B; }}
    .cryosync-dot-attention {{ background: #F0B04C; }}
    .cryosync-dot-safe {{ background: #5FCB8B; }}
    .cryosync-dot-info {{ background: #6FA8E8; }}
    .cryosync-dot-neutral {{ background: #8A94A6; }}

    /* ----------------------------------------------------- sidebar --- */
    section[data-testid="stSidebar"] {{
        background: var(--cryosync-surface);
        border-right: 1px solid var(--cryosync-border);
        width: 264px !important;
        min-width: 264px !important;
        max-width: 264px !important;
        flex: 0 0 264px !important;
        transform: none !important;
        margin-left: 0 !important;
        left: 0 !important;
    }}

    /* Streamlit nests the sidebar content in an inner scroller; padding is
       applied there so the gap matches the content edges. */
    section[data-testid="stSidebar"] > div:first-child {{
        padding-top: 0.9rem;
        width: 264px !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
        padding: 0 0.6rem 1rem 0.6rem;
        width: 100% !important;
    }}

    /* Streamlit centres sidebar widget labels; navigation must read as a
       left-aligned list, so every child of a sidebar button is anchored. */
    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] button * {{
        justify-content: flex-start !important;
        text-align: left !important;
    }}

    /* The label span inside a Streamlit button is centred by default; give it
       a normal inline flow so the icon sits immediately before the text. */
    section[data-testid="stSidebar"] button p,
    section[data-testid="stSidebar"] button span {{
        margin: 0 !important;
        width: auto !important;
        flex: 0 0 auto !important;
    }}

    /* Vertically stack the nav instead of letting Streamlit gap each row. */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 0.05rem;
    }}

    section[data-testid="stSidebar"] [data-testid="stElementContainer"] {{
        margin: 0;
    }}

    .cryosync-nav-group {{
        color: var(--cryosync-text-faint);
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        margin: 0.9rem 0 0.35rem 0;
        padding-left: 0.15rem;
    }}

    /* Sidebar nav items are Streamlit buttons restyled as a list. */
    section[data-testid="stSidebar"] button[kind="secondary"],
    section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {{
        display: flex;
        justify-content: flex-start;
        width: 100%;
        background: transparent !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        border-radius: 0 var(--cryosync-radius-sm) var(--cryosync-radius-sm) 0;
        color: var(--cryosync-text-muted) !important;
        font-size: 0.86rem;
        font-weight: 520;
        text-align: left;
        padding: 0.44rem 0.6rem;
        margin: 0;
        min-height: 32px;
        box-shadow: none !important;
    }}

    section[data-testid="stSidebar"] button[kind="secondary"]:hover,
    section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"]:hover {{
        background: var(--cryosync-neutral-soft) !important;
        color: var(--cryosync-text) !important;
        border: none !important;
        border-left: 3px solid var(--cryosync-border-strong) !important;
    }}

    /* Active nav item: tinted fill + accent left rail, and the label is
       also bolder, so the state is not signalled by colour alone. */
    section[data-testid="stSidebar"] button[kind="primary"],
    section[data-testid="stSidebar"] button[kind="primaryFormSubmit"] {{
        display: flex;
        justify-content: flex-start;
        width: 100%;
        background: var(--cryosync-accent-soft) !important;
        border: none;
        border-left: 3px solid var(--cryosync-accent) !important;
        border-radius: 0 var(--cryosync-radius-sm) var(--cryosync-radius-sm) 0;
        color: var(--cryosync-accent) !important;
        font-size: 0.86rem;
        font-weight: 700;
        text-align: left;
        padding: 0.44rem 0.6rem;
        margin: 0;
        min-height: 0;
        box-shadow: none;
    }}

    section[data-testid="stSidebar"] button[kind="primary"]:hover {{
        background: var(--cryosync-accent-soft);
        color: var(--cryosync-accent-hover);
        border: none;
        border-left: 3px solid var(--cryosync-accent-hover);
    }}

    /* Group headers are buttons too, but must read as labels. */
    section[data-testid="stSidebar"] button[kind="tertiary"],
    section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {{
        display: flex;
        justify-content: flex-start;
        width: 100%;
        background: transparent !important;
        border: none !important;
        color: var(--cryosync-text-faint) !important;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        text-align: left;
        padding: 0.7rem 0.15rem 0.15rem 0.15rem;
        margin: 0;
        min-height: 0;
        box-shadow: none;
    }}

    section[data-testid="stSidebar"] button[kind="tertiary"]:hover {{
        background: transparent;
        color: var(--cryosync-text-muted);
        border: none;
    }}

    .cryosync-sidebar-meta {{
        color: var(--cryosync-text-faint);
        font-size: 0.73rem;
        line-height: 1.5;
        padding: 0.15rem 0.15rem 0.5rem 0.15rem;
    }}

    /* ------------------------------------------------------- typography --- */
    h1 {{
        font-size: 1.5rem !important;
        font-weight: 680 !important;
        letter-spacing: -0.01em;
        color: var(--cryosync-text);
        margin-bottom: 0.15rem !important;
    }}

    h2 {{
        font-size: 1.12rem !important;
        font-weight: 650 !important;
        color: var(--cryosync-text);
        margin-top: 1.6rem !important;
        margin-bottom: 0.5rem !important;
    }}

    h3 {{
        font-size: 0.95rem !important;
        font-weight: 650 !important;
        color: var(--cryosync-text);
    }}

    .cryosync-eyebrow {{
        color: var(--cryosync-text-faint);
        font-size: 0.7rem;
        font-weight: 650;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }}

    .cryosync-page-sub {{
        color: var(--cryosync-text-muted);
        font-size: 0.88rem;
        margin-bottom: 1.1rem;
    }}

    /* --------------------------------------------------------- cards --- */
    /* st.container(border=True) is the canonical card. Streamlit 1.63 renders
       it as a stLayoutWrapper; older builds used stVerticalBlockBorderWrapper.
       Verified: only bordered containers emit stLayoutWrapper, so this does
       not accidentally style columns or plain blocks. */
    div[data-testid="stLayoutWrapper"],
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: var(--cryosync-surface);
        border: 1px solid var(--cryosync-border) !important;
        border-radius: var(--cryosync-radius);
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
        padding: 1rem 1.1rem;
    }}

    /* A card nested inside a card is a sub-panel, not another card. */
    div[data-testid="stLayoutWrapper"] div[data-testid="stLayoutWrapper"],
    div[data-testid="stVerticalBlockBorderWrapper"]
        div[data-testid="stVerticalBlockBorderWrapper"] {{
        box-shadow: none;
        background: var(--cryosync-surface-alt);
    }}

    .cryosync-card-title {{
        font-size: 0.82rem;
        font-weight: 650;
        color: var(--cryosync-text);
        margin-bottom: 0.1rem;
    }}

    .cryosync-card-head {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.6rem;
        margin-bottom: 0.7rem;
    }}

    /* --------------------------------------------------- metric tiles --- */
    div[data-testid="stMetric"] {{
        background: var(--cryosync-surface);
        border: 1px solid var(--cryosync-border);
        border-radius: var(--cryosync-radius);
        padding: 0.75rem 0.85rem;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}

    div[data-testid="stMetricLabel"] {{
        color: var(--cryosync-text-muted);
        font-size: 0.76rem !important;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }}

    div[data-testid="stMetricValue"] {{
        color: var(--cryosync-text);
        font-size: 1.42rem !important;
        font-weight: 680;
        letter-spacing: -0.015em;
    }}

    div[data-testid="stMetricDelta"] {{
        font-size: 0.78rem;
    }}

    /* A left accent bar marks a card whose state matters. */
    .cryosync-accent-card {{
        display: block;
        padding: 0.7rem 0.85rem;
        border-radius: var(--cryosync-radius);
        border: 1px solid var(--cryosync-border);
        border-left-width: 3px;
        border-left-style: solid;
        background: var(--cryosync-surface);
        font-size: 0.85rem;
        line-height: 1.45;
    }}

    .cryosync-accent-card p {{
        margin: 0;
    }}

    .cryosync-accent-card .cryosync-accent-title {{
        font-weight: 650;
        font-size: 0.86rem;
        display: block;
        margin-bottom: 0.12rem;
    }}

    /* Small tone marker beside an accent-card title. The title text already
       states the condition in words, so this is emphasis, not the only cue. */
    .cryosync-accent-marker {{
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        margin-right: 0.45rem;
        vertical-align: middle;
        background: var(--cryosync-neutral);
    }}

    .cryosync-tone-critical .cryosync-accent-marker {{
        background: var(--cryosync-critical);
    }}
    .cryosync-tone-attention .cryosync-accent-marker {{
        background: var(--cryosync-attention);
    }}
    .cryosync-tone-safe .cryosync-accent-marker {{
        background: var(--cryosync-safe);
    }}
    .cryosync-tone-info .cryosync-accent-marker {{
        background: var(--cryosync-info);
    }}

    .cryosync-accent-card .cryosync-accent-body {{
        color: var(--cryosync-text-muted);
        font-size: 0.82rem;
    }}

    /* Status modifier classes, shared by pills, badges and accent cards. */
    .cryosync-tone-critical {{
        border-left-color: var(--cryosync-critical);
        background: var(--cryosync-critical-soft);
    }}
    .cryosync-tone-attention {{
        border-left-color: var(--cryosync-attention);
        background: var(--cryosync-attention-soft);
    }}
    .cryosync-tone-safe {{
        border-left-color: var(--cryosync-safe);
        background: var(--cryosync-safe-soft);
    }}
    .cryosync-tone-info {{
        border-left-color: var(--cryosync-info);
        background: var(--cryosync-info-soft);
    }}
    .cryosync-tone-neutral {{
        border-left-color: var(--cryosync-neutral);
        background: var(--cryosync-neutral-soft);
    }}

    /* ---------------------------------------------------------- pills --- */
    .cryosync-pill {{
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.16rem 0.55rem;
        border-radius: var(--cryosync-radius-pill);
        font-size: 0.73rem;
        font-weight: 620;
        white-space: nowrap;
        border: 1px solid transparent;
    }}

    .cryosync-pill-critical {{
        background: var(--cryosync-critical-soft);
        color: var(--cryosync-critical);
        border-color: rgba(198, 40, 40, 0.22);
    }}
    .cryosync-pill-attention {{
        background: var(--cryosync-attention-soft);
        color: var(--cryosync-attention);
        border-color: rgba(183, 121, 31, 0.24);
    }}
    .cryosync-pill-safe {{
        background: var(--cryosync-safe-soft);
        color: var(--cryosync-safe);
        border-color: rgba(46, 125, 79, 0.22);
    }}
    .cryosync-pill-info {{
        background: var(--cryosync-info-soft);
        color: var(--cryosync-info);
        border-color: rgba(47, 111, 184, 0.22);
    }}
    .cryosync-pill-neutral {{
        background: var(--cryosync-neutral-soft);
        color: var(--cryosync-neutral);
        border-color: rgba(102, 112, 133, 0.22);
    }}

    /* ---------------------------------------------- label/value table --- */
    .cryosync-rows {{ display: block; }}

    .cryosync-row {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.42rem 0;
        border-bottom: 1px solid var(--cryosync-border);
        font-size: 0.85rem;
    }}

    .cryosync-row:last-child {{ border-bottom: none; }}

    .cryosync-row-label {{ color: var(--cryosync-text-muted); }}

    .cryosync-row-value {{
        color: var(--cryosync-text);
        font-weight: 620;
        font-variant-numeric: tabular-nums;
        text-align: right;
    }}

    /* -------------------------------------------------------- buttons --- */
    /* Streamlit paints primary buttons with its own blue; every primary
       button in this product is the operator accent colour instead. */
    div[data-testid="stButton"] > button[kind="primary"],
    div[data-testid="stButton"] > button[kind="primaryFormSubmit"] {{
        background: var(--cryosync-accent) !important;
        border: 1px solid var(--cryosync-accent) !important;
        color: #FFFFFF !important;
        border-radius: var(--cryosync-radius-sm);
        font-weight: 600;
        font-size: 0.84rem;
        box-shadow: none !important;
    }}

    div[data-testid="stButton"] > button[kind="primary"]:hover,
    div[data-testid="stButton"] > button[kind="primaryFormSubmit"]:hover {{
        background: var(--cryosync-accent-hover) !important;
        border-color: var(--cryosync-accent-hover) !important;
    }}

    div[data-testid="stButton"] > button[kind="secondary"],
    div[data-testid="stButton"] > button[kind="secondaryFormSubmit"] {{
        background: var(--cryosync-surface) !important;
        border: 1px solid var(--cryosync-border-strong) !important;
        color: var(--cryosync-text) !important;
        border-radius: var(--cryosync-radius-sm);
        font-weight: 600;
        font-size: 0.84rem;
        box-shadow: none !important;
    }}

    div[data-testid="stButton"] > button[kind="secondary"]:hover,
    div[data-testid="stButton"] > button[kind="secondaryFormSubmit"]:hover {{
        border-color: var(--cryosync-accent) !important;
        color: var(--cryosync-accent) !important;
        background: var(--cryosync-surface) !important;
    }}

    /* ------------------------------------------------------- controls --- */
    div[data-baseweb="select"] > div,
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stDateInput"] input {{
        border-radius: var(--cryosync-radius-sm);
        border-color: var(--cryosync-border-strong);
        font-size: 0.85rem;
    }}

    div[data-testid="stExpander"] details {{
        border: 1px solid var(--cryosync-border);
        border-radius: var(--cryosync-radius);
        background: var(--cryosync-surface);
    }}

    div[data-testid="stDataFrame"] {{
        border: 1px solid var(--cryosync-border);
        border-radius: var(--cryosync-radius);
        overflow: hidden;
    }}

    hr {{ border-color: var(--cryosync-border); }}

    /* Streamlit alerts are aligned to the status palette. */
    div[data-testid="stAlert"] {{
        border-radius: var(--cryosync-radius);
        font-size: 0.85rem;
    }}

    .cryosync-foot {{
        color: var(--cryosync-text-faint);
        font-size: 0.76rem;
        padding-top: 0.4rem;
    }}
</style>
"""


def apply() -> None:
    """Inject the stylesheet. Call once per run, before any layout."""

    st.markdown(STYLESHEET, unsafe_allow_html=True)
