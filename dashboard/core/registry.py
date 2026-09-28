"""Sidebar navigation registry for the CRYOSYNC dashboard.

Groups mirror the operator workflow: watch the station, decide, experiment,
control, then inspect the system itself. Every page is registered exactly
once here, and both the sidebar and the router read this table.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    """One dashboard page."""

    slug: str
    label: str
    icon: str
    module: str
    caption: str


@dataclass(frozen=True)
class NavGroup:
    """A collapsible sidebar group."""

    key: str
    label: str
    icon: str
    blurb: str
    items: tuple[NavItem, ...]


NAV_GROUPS: tuple[NavGroup, ...] = (
    NavGroup(
        key="operations",
        label="Operations",
        icon=":material/dashboard:",
        blurb="Live station state and the headline decision view",
        items=(
            NavItem(
                slug="overview",
                label="Overview",
                icon=":material/grid_view:",
                module="pages_bundle.overview",
                caption="Station overview",
            ),
            NavItem(
                slug="live_state",
                label="Live state",
                icon=":material/monitor_heart:",
                module="pages_bundle.live_state",
                caption="Live state replay",
            ),
        ),
    ),
    NavGroup(
        key="decision",
        label="Decision",
        icon=":material/alt_route:",
        blurb="Forecast, autonomy envelope and the accepted plan",
        items=(
            NavItem(
                slug="forecast",
                label="Forecast",
                icon=":material/query_stats:",
                module="pages_bundle.forecast",
                caption="24-hour forecast",
            ),
            NavItem(
                slug="safe_autonomy",
                label="Safe autonomy",
                icon=":material/shield:",
                module="pages_bundle.safe_autonomy",
                caption="Safe operability and CQRM horizon",
            ),
            NavItem(
                slug="recommended_plan",
                label="Recommended plan",
                icon=":material/bolt:",
                module="pages_bundle.recommended_plan",
                caption="Recommended operating plan",
            ),
            NavItem(
                slug="scenarios",
                label="Scenarios",
                icon=":material/layers:",
                module="pages_bundle.scenarios",
                caption="Scenario comparison",
            ),
        ),
    ),
    NavGroup(
        key="experiment",
        label="Experiment",
        icon=":material/science:",
        blurb="Validate models and candidate plans under test",
        items=(
            NavItem(
                slug="judge_sandbox",
                label="Judge sandbox",
                icon=":material/gavel:",
                module="pages_bundle.judge_sandbox",
                caption="Plan judging and model evaluation",
            ),
        ),
    ),
    NavGroup(
        key="control",
        label="Control",
        icon=":material/tune:",
        blurb="Fuel logistics and deterministic safety constraints",
        items=(
            NavItem(
                slug="resupply",
                label="Resupply",
                icon=":material/local_shipping:",
                module="pages_bundle.resupply",
                caption="Resupply risk and timing",
            ),
            NavItem(
                slug="safety",
                label="Safety",
                icon=":material/health_and_safety:",
                module="pages_bundle.safety",
                caption="Safety constraints and interlocks",
            ),
        ),
    ),
    NavGroup(
        key="system",
        label="System",
        icon=":material/settings_suggest:",
        blurb="Data lineage, history and engine health",
        items=(
            NavItem(
                slug="data_diagnostics",
                label="Data & diagnostics",
                icon=":material/database:",
                module="pages_bundle.data_diagnostics",
                caption="Data inventory and integrity",
            ),
            NavItem(
                slug="history",
                label="History",
                icon=":material/history:",
                module="pages_bundle.history",
                caption="Historical explorer",
            ),
            NavItem(
                slug="system_health",
                label="System health",
                icon=":material/memory:",
                module="pages_bundle.system_health",
                caption="Engine status",
            ),
            NavItem(
                slug="settings",
                label="Settings",
                icon=":material/settings:",
                module="pages_bundle.settings_page",
                caption="Station and planning settings",
            ),
        ),
    ),
)

NAV_ITEMS: tuple[NavItem, ...] = tuple(
    item for group in NAV_GROUPS for item in group.items
)

ITEM_BY_SLUG: dict[str, NavItem] = {item.slug: item for item in NAV_ITEMS}

GROUP_BY_SLUG: dict[str, NavGroup] = {
    item.slug: group for group in NAV_GROUPS for item in group.items
}

DEFAULT_PAGE = NAV_ITEMS[0].slug


def item_for(slug: str | None) -> NavItem:
    """Return the registered page for ``slug``, falling back to the default."""

    if slug and slug in ITEM_BY_SLUG:
        return ITEM_BY_SLUG[slug]

    return ITEM_BY_SLUG[DEFAULT_PAGE]


def group_for(slug: str) -> NavGroup:
    """Return the sidebar group that owns ``slug``."""

    return GROUP_BY_SLUG[slug]
