"""CRYOSYNC - Energy Intelligence Dashboard.

This module is only the application shell. It does three things and nothing
else:

1. configures the page and injects the stylesheet,
2. renders the persistent chrome (dark top bar and grouped sidebar),
3. resolves the active page from the address bar and calls its ``render()``.

All reasoning lives in ``core/``, all presentation in ``ui/``, and all page
content in ``pages_bundle/``. Adding a page means registering it in
``core/registry.py`` and writing one module - this file does not change.

Run from the project root:

    streamlit run dashboard/app.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import streamlit as st

# Streamlit puts ``dashboard/`` on sys.path, which is exactly the import root
# this package expects: ``core``, ``ui`` and ``pages_bundle`` are siblings.
DASHBOARD_DIR = Path(__file__).resolve().parent

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from core import state  # noqa: E402  (path must be patched first)
from core.dataset import load_station_data  # noqa: E402
from core.registry import item_for  # noqa: E402
from ui import chrome, theme  # noqa: E402

st.set_page_config(
    page_title="CRYOSYNC Energy Intelligence",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_page(module_name: str):
    """Import a page module, surfacing a clear error instead of a traceback."""

    try:
        return importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - one bad page must not kill the shell
        st.error(f"Could not load page module `{module_name}`.")
        st.exception(exc)
        return None


def main() -> None:
    theme.apply()

    state.init_state()

    data = load_station_data()

    alerts = chrome.alert_count(data)

    chrome.top_bar(
        active_alerts=alerts,
        missing_keys=len(data.missing_keys),
        latest_timestamp=data.latest_timestamp,
    )

    chrome.sidebar(
        active_alerts=alerts,
        missing_keys=len(data.missing_keys),
    )

    item = item_for(state.active_page())

    module = _load_page(item.module)

    if module is None:
        st.divider()
        return

    if not hasattr(module, "render"):
        st.error(f"Page `{item.module}` does not define a `render()` function.")
        st.divider()
        return

    module.render()

    st.divider()

    st.markdown(
        '<div class="cryosync-foot">'
        "CRYOSYNC · AI energy intelligence for polar research stations · "
        "offline-first local prototype"
        "</div>",
        unsafe_allow_html=True,
    )


main()
