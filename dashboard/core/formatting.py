"""Number, unit and time formatting for the CRYOSYNC dashboard.

Every user-visible value passes through here so units, precision and
typography stay identical on every page.
"""

from __future__ import annotations

import math
import pandas as pd

EM_DASH = "\u2014"

UNIT_KW = "kW"
UNIT_KWH = "kWh"
UNIT_LITRE = "L"
UNIT_LITRE_PER_HOUR = "L/h"
UNIT_DAYS = "d"
UNIT_PERCENT = "%"
UNIT_MPS = "m/s"


def is_missing(value: object) -> bool:
    """True when a value should render as an em dash."""

    if value is None:
        return True

    if isinstance(value, float) and math.isnan(value):
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _numeric(value: object) -> float | None:
    if is_missing(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def number(value: object, decimals: int = 1, unit: str = "") -> str:
    """Format a value with thousands separators and an optional unit."""

    numeric = _numeric(value)

    if numeric is None:
        return EM_DASH

    return f"{numeric:,.{decimals}f} {unit}".strip()


def signed(value: object, decimals: int = 2, unit: str = "") -> str:
    """Format a signed value, always keeping an explicit + or - sign."""

    numeric = _numeric(value)

    if numeric is None:
        return EM_DASH

    return f"{numeric:+,.{decimals}f} {unit}".strip()


def integer(value: object, unit: str = "") -> str:
    numeric = _numeric(value)

    if numeric is None:
        return EM_DASH

    return f"{round(numeric):,.0f} {unit}".strip()


def days(value: object, decimals: int = 1) -> str:
    return number(value, decimals, UNIT_DAYS)


def kilowatts(value: object, decimals: int = 1) -> str:
    return number(value, decimals, UNIT_KW)


def kilowatt_hours(value: object, decimals: int = 0) -> str:
    return number(value, decimals, UNIT_KWH)


def litres(value: object, decimals: int = 0) -> str:
    return number(value, decimals, UNIT_LITRE)


def percent(value: object, decimals: int = 1) -> str:
    numeric = _numeric(value)

    if numeric is None:
        return EM_DASH

    return f"{numeric:,.{decimals}f}{UNIT_PERCENT}"


def metres_per_second(value: object, decimals: int = 1) -> str:
    return number(value, decimals, UNIT_MPS)


def duration(hours: object) -> str:
    """Human-readable duration from an hour count."""

    numeric = _numeric(hours)

    if numeric is None:
        return EM_DASH

    if abs(numeric) < 48:
        return f"{numeric:,.1f} h"

    return f"{numeric / 24:,.1f} d"


def datetime_label(value: object) -> str:
    if is_missing(value):
        return EM_DASH

    return pd.Timestamp(value).strftime("%d %b %Y, %H:%M")


def date_label(value: object) -> str:
    if is_missing(value):
        return EM_DASH

    return pd.Timestamp(value).strftime("%d %b %Y")


def clock_label(value: object) -> str:
    if is_missing(value):
        return EM_DASH

    return pd.Timestamp(value).strftime("%H:%M")


def relative_age(value: object) -> str:
    """Age of a timestamp relative to now, for example 'age 3.4 y'."""

    if is_missing(value):
        return EM_DASH

    # The digital twin writes naive wall-clock timestamps for a simulated
    # year, so a naive value is compared against naive local now rather than
    # being forced into UTC: that previously produced negative ages whenever
    # the machine clock ran behind UTC. A future timestamp reads as "just now"
    # because a negative age is never meaningful to an operator.
    stamp = pd.Timestamp(value)

    if stamp.tzinfo is not None:
        reference = pd.Timestamp.now(tz="UTC")
    else:
        reference = pd.Timestamp.now()

    seconds = (reference - stamp).total_seconds()

    if seconds < 0:
        return "just now"

    if seconds < 90:
        return f"age {seconds:,.0f} s"

    if seconds < 5400:
        return f"age {seconds / 60:,.0f} min"

    if seconds < 172800:
        return f"age {seconds / 3600:,.1f} h"

    if seconds < 63072000:
        return f"age {seconds / 86400:,.0f} d"

    return f"age {seconds / 31557600:,.1f} y"


def clip_text(value: object, limit: int = 96) -> str:
    """Shorten long operator text while keeping it readable."""

    text = "" if is_missing(value) else str(value).strip()

    if len(text) <= limit:
        return text

    return text[: limit - 1].rstrip() + "\u2026"
