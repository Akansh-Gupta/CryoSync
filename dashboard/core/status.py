"""Status vocabulary shared by metrics, badges, charts and tables.

One place decides what "critical" looks like so a red pill in the top bar,
a red badge on a tile and a red chart line always mean the same thing.
"""

from __future__ import annotations

from enum import Enum


class Level(str, Enum):
    """Operating status level, ordered from most to least severe."""

    CRITICAL = "critical"
    ATTENTION = "attention"
    SAFE = "safe"
    INFO = "info"
    NEUTRAL = "neutral"


# Severity order used when several signals are combined (higher = worse).
SEVERITY_RANK: dict[Level, int] = {
    Level.CRITICAL: 4,
    Level.ATTENTION: 3,
    Level.SAFE: 2,
    Level.INFO: 1,
    Level.NEUTRAL: 0,
}

# st.badge() color keywords.
BADGE_COLOR: dict[Level, str] = {
    Level.CRITICAL: "red",
    Level.ATTENTION: "orange",
    Level.SAFE: "green",
    Level.INFO: "blue",
    Level.NEUTRAL: "gray",
}

# Material Symbols icons (never emojis).
ICON: dict[Level, str] = {
    Level.CRITICAL: ":material/error:",
    Level.ATTENTION: ":material/warning:",
    Level.SAFE: ":material/check_circle:",
    Level.INFO: ":material/info:",
    Level.NEUTRAL: ":material/remove:",
}

# CSS modifier suffix used by the shared stylesheet.
TONE: dict[Level, str] = {
    Level.CRITICAL: "critical",
    Level.ATTENTION: "attention",
    Level.SAFE: "safe",
    Level.INFO: "info",
    Level.NEUTRAL: "neutral",
}

LEVEL_LABEL: dict[Level, str] = {
    Level.CRITICAL: "Critical",
    Level.ATTENTION: "Attention",
    Level.SAFE: "Safe",
    Level.INFO: "Info",
    Level.NEUTRAL: "No data",
}

SEVERITY_TO_LEVEL: dict[str, Level] = {
    "critical": Level.CRITICAL,
    "high": Level.CRITICAL,
    "danger": Level.CRITICAL,
    "medium": Level.ATTENTION,
    "warning": Level.ATTENTION,
    "moderate": Level.ATTENTION,
    "low": Level.SAFE,
    "info": Level.INFO,
    "normal": Level.SAFE,
}

ALERT_TYPE_LABEL: dict[str, str] = {
    "STORM_RISK": "Storm risk",
    "LOW_FUEL": "Low fuel runway",
    "LOW_BATTERY": "Battery reserve breach",
    "BATTERY_LEVEL_WARNING": "Battery below warning level",
    "BATTERY_MAINTENANCE": "Battery maintenance",
    "GENERATOR_MAINTENANCE": "Generator maintenance",
    "FORECAST_UNCERTAINTY": "Forecast uncertainty",
    "ANOMALY": "Anomaly detected",
}

ALERT_TYPE_ICON: dict[str, str] = {
    "STORM_RISK": ":material/storm:",
    "LOW_FUEL": ":material/local_gas_station:",
    "LOW_BATTERY": ":material/battery_alert:",
    "BATTERY_LEVEL_WARNING": ":material/battery_3_bar:",
    "BATTERY_MAINTENANCE": ":material/battery_charging_full:",
    "GENERATOR_MAINTENANCE": ":material/build:",
    "FORECAST_UNCERTAINTY": ":material/query_stats:",
    "ANOMALY": ":material/monitor_heart:",
}


def level_from_severity(severity: object) -> Level:
    """Map a pipeline severity string onto a status level."""

    return SEVERITY_TO_LEVEL.get(str(severity).strip().lower(), Level.ATTENTION)


def worst_level(levels: list[Level] | tuple[Level, ...]) -> Level:
    """Return the most severe level from a collection."""

    candidates = [level for level in levels if level is not None]

    if not candidates:
        return Level.NEUTRAL

    return max(candidates, key=lambda level: SEVERITY_RANK[level])


def alert_label(alert_type: object) -> str:
    """Readable label for an alert type."""

    key = str(alert_type).strip().upper()

    if key in ALERT_TYPE_LABEL:
        return ALERT_TYPE_LABEL[key]

    return key.replace("_", " ").title() if key else "System alert"


def alert_icon(alert_type: object) -> str:
    """Material Symbols icon for an alert type."""

    return ALERT_TYPE_ICON.get(str(alert_type).strip().upper(), ":material/notifications:")


def tone(level: Level) -> str:
    return TONE[level]


def badge_color(level: Level) -> str:
    return BADGE_COLOR[level]


def icon(level: Level) -> str:
    return ICON[level]
