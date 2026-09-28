"""Operator planning assumptions used by the decision pages.

Measured station state comes from the pipeline. Planning inputs - how soon a
ship is expected, which battery floor must never be crossed, how much margin
to add for adverse weather - are operator assumptions and are kept separate,
editable, and persisted so the numbers behind every recommendation stay
auditable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace

import streamlit as st

from core.paths import ASSUMPTIONS_PATH

SESSION_KEY = "cryosync_assumptions"


@dataclass(frozen=True)
class Assumptions:
    """Planning inputs, all editable from the settings page."""

    planned_resupply_days: float = 7.0
    battery_reserve_floor_pct: float = 20.0
    battery_reserve_target_pct: float = 35.0
    demand_safety_margin: float = 1.10
    scenario_months: int = 12
    logistics_delay_multiplier: float = 0.50
    storm_wind_threshold_ms: float = 18.0

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True)
class FieldMeta:
    """Editor metadata for one assumption."""

    label: str
    help: str
    unit: str
    minimum: float
    maximum: float
    step: float
    integer: bool = False


FIELD_META: dict[str, FieldMeta] = {
    "planned_resupply_days": FieldMeta(
        label="Planned resupply window",
        help=(
            "Days until the next resupply is expected. The conservative case "
            "adds the weather delay estimated from recent storm frequency."
        ),
        unit="d",
        minimum=0.5,
        maximum=365.0,
        step=0.5,
    ),
    "battery_reserve_floor_pct": FieldMeta(
        label="Battery reserve floor",
        help="State of charge the battery must never fall below, whatever the dispatch strategy.",
        unit="%",
        minimum=5.0,
        maximum=60.0,
        step=1.0,
    ),
    "battery_reserve_target_pct": FieldMeta(
        label="Battery reserve target",
        help="Planning target for the end of the operating horizon, above the hard floor.",
        unit="%",
        minimum=10.0,
        maximum=95.0,
        step=1.0,
    ),
    "demand_safety_margin": FieldMeta(
        label="Demand safety margin",
        help="Multiplier applied to the adverse (P90) demand estimate before it is used for autonomy.",
        unit="x",
        minimum=1.0,
        maximum=2.0,
        step=0.05,
    ),
    "scenario_months": FieldMeta(
        label="Condition scenarios",
        help=(
            "How many recent calendar months of measured net load are replayed as "
            "condition scenarios. Twelve covers a full year of weather."
        ),
        unit="months",
        minimum=3.0,
        maximum=12.0,
        step=1.0,
        integer=True,
    ),
    "logistics_delay_multiplier": FieldMeta(
        label="Logistics delay multiplier",
        help=(
            "Converts the share of storm days in the recent sample into a resupply "
            "delay spread. 0.5 means a fully stormy sample can delay the ship by 50%."
        ),
        unit="x",
        minimum=0.0,
        maximum=1.5,
        step=0.05,
    ),
    "storm_wind_threshold_ms": FieldMeta(
        label="Storm wind threshold",
        help="Wind speed treated as a storm, matching the load-shedding trigger in the station model.",
        unit="m/s",
        minimum=10.0,
        maximum=35.0,
        step=0.5,
    ),
}


def _load_from_disk() -> Assumptions:
    """Read persisted assumptions, ignoring anything unrecognised."""

    if not ASSUMPTIONS_PATH.exists():
        return Assumptions()

    try:
        raw = json.loads(ASSUMPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Assumptions()

    known = {field.name for field in fields(Assumptions)}

    payload = {key: value for key, value in raw.items() if key in known}

    try:
        return replace(Assumptions(), **payload)
    except (TypeError, ValueError):
        return Assumptions()


def _save_to_disk(assumptions: Assumptions) -> None:
    """Persist assumptions so a restart keeps the operator's planning basis."""

    try:
        ASSUMPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ASSUMPTIONS_PATH.write_text(
            json.dumps(assumptions.to_dict(), indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def current() -> Assumptions:
    """Current assumptions, loaded from disk on first use."""

    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = _load_from_disk()

    return st.session_state[SESSION_KEY]


def update(**changes: float | int) -> Assumptions:
    """Apply changes to the active assumptions and persist them."""

    updated = replace(current(), **changes)

    st.session_state[SESSION_KEY] = updated

    _save_to_disk(updated)

    return updated


def reset() -> Assumptions:
    """Return to the documented defaults."""

    return update(**Assumptions().to_dict())


def derive(base: Assumptions, **changes: float | int) -> Assumptions:
    # Return a variant of base without touching session or disk state. Used by
    # the experiment pages to evaluate a what-if planning basis: the operator's
    # saved assumptions must not be mutated just because a slider was moved.
    return replace(base, **changes)


def display_rows(assumptions: Assumptions | None = None) -> list[dict[str, str]]:
    """Assumption values formatted for the settings and methodology tables."""

    active = assumptions or current()

    rows: list[dict[str, str]] = []

    for key, meta in FIELD_META.items():
        value = getattr(active, key)

        rendered = f"{value:,.0f}" if meta.integer else f"{value:,.2f}"

        rows.append(
            {
                "Assumption": meta.label,
                "Value": f"{rendered} {meta.unit}".strip(),
                "Basis": meta.help,
            }
        )

    return rows
