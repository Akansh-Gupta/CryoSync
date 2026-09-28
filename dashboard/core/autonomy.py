"""Safe operability and CQRM reasoning for the CRYOSYNC station.

The operator question is: *how long can the critical load survive with no
resupply?* The answer is produced by replaying measured conditions through
the station's own dispatch physics, never by a closed-form guess:

1. The last twelve calendar months of measured net load (station load minus
   solar and wind) become twelve condition scenarios.
2. Each scenario is cycled and simulated forward from the *current* battery
   and fuel state with :func:`twin.power_balance.simulate_power_balance` -
   the same code that generated the dataset - so battery limits, generator
   minimum loading and idle fuel burn are all respected.
3. A scenario ends at the first hour the load cannot be served.
4. The adverse scenario (10th percentile outcome) is the headline safe
   operability horizon. Subtracting the conservative resupply arrival gives
   the Confidence-Qualified Resupply Margin (CQRM).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.settings import Assumptions
from core.status import Level
from twin.config import STATION_CONFIG
from twin.power_balance import simulate_power_balance

# Conditions are sampled from the last twelve months of measured operation.
SCENARIO_COUNT = 12

# A scenario is stopped after this many simulated days; anything still running
# is reported as "beyond the planning window" rather than an infinite number.
HORIZON_CAP_DAYS = 365

# A scenario that has drawn almost no fuel for this long is indefinitely
# sustainable under those conditions, so it is stopped early: its exact
# horizon would not change any decision.
NO_DRAW_SHORT_CIRCUIT_HOURS = 2160
NO_DRAW_FUEL_FRACTION = 0.01

# Load this small is simulation noise, not an unserved-load event.
UNSERVED_TOLERANCE_KW = 1e-3

# Outcome quantiles across scenarios.
OUTCOME_QUANTILES: dict[str, float] = {
    "favourable": 0.90,
    "expected": 0.50,
    "adverse": 0.10,
}

OUTCOME_LABELS: dict[str, str] = {
    "favourable": "Favourable conditions",
    "expected": "Expected conditions",
    "adverse": "Adverse conditions",
}

# A margin below this many days leaves no reaction time, so it is reported as
# attention rather than safe.
CQRM_ATTENTION_DAYS = 3.0

# The resupply delay spread is capped so one stormy fortnight cannot produce
# an absurd horizon.
MAX_DELAY_SPREAD = 0.60

GENERATOR_INITIAL_FUEL_L = float(
    STATION_CONFIG["generator_system"]["initial_fuel_l"]
)

METHODOLOGY: tuple[tuple[str, str], ...] = (
    (
        "Condition scenarios",
        "The last twelve calendar months of measured net load (station load minus solar "
        "and wind) are each cycled into a scenario, so good and bad months are both "
        "represented instead of averaging them away.",
    ),
    (
        "Forward simulation",
        "Each scenario is simulated hour by hour from today's battery and fuel state "
        "using the station's own dispatch physics: battery limits, generator minimum "
        "loading, and idle fuel burn all apply.",
    ),
    (
        "Safe operability horizon (SOH)",
        "Days until the load can no longer be served. The adverse outcome (10th "
        "percentile across scenarios) is the headline number.",
    ),
    (
        "Resupply horizon R",
        "Days until the next resupply is expected, widened by the share of storm days in "
        "the recent sample to give an optimistic and a conservative arrival.",
    ),
    (
        "CQRM margin",
        "Adverse SOH minus conservative resupply arrival. A negative margin means "
        "autonomy ends before the ship can arrive.",
    ),
)


@dataclass(frozen=True)
class EnergyReserve:
    """Dispatchable energy on site right now."""

    battery_kwh: float
    fuel_litres: float
    equivalent_kwh: float
    battery_soc_pct: float
    reserve_floor_pct: float
    effective_floor_pct: float
    reserve_target_pct: float
    fuel_runway_days: float | None

    @property
    def floor_breached(self) -> bool:
        """True when the assumed floor sits above the charge actually held."""

        return self.battery_soc_pct + 0.05 < self.reserve_floor_pct

    @property
    def battery_is_at_floor(self) -> bool:
        return self.battery_soc_pct <= self.reserve_floor_pct + 0.05

    @property
    def battery_below_target(self) -> bool:
        return self.battery_soc_pct < self.reserve_target_pct

    @property
    def battery_share(self) -> float:
        if self.equivalent_kwh <= 0:
            return 0.0

        return self.battery_kwh / self.equivalent_kwh


@dataclass(frozen=True)
class Conditions:
    """Measured operating conditions behind the scenarios."""

    latest_deficit_kw: float
    mean_deficit_kw: float
    renewable_fraction: float
    scenario_months: int
    sample_days: int


@dataclass(frozen=True)
class Scenario:
    """One month of measured conditions replayed to exhaustion."""

    label: str
    horizon_days: float
    capped: bool
    simulated_days: float
    fuel_used_l: float
    unserved_kwh: float
    mean_deficit_kw: float


@dataclass(frozen=True)
class ResupplyPlan:
    """Expected, optimistic and conservative resupply arrivals."""

    expected_days: float
    optimistic_days: float
    conservative_days: float
    delay_spread: float
    storm_day_share: float


@dataclass(frozen=True)
class CqrmResult:
    """Margin between autonomy and logistics."""

    margin_days: float
    horizon_days: float
    resupply_days: float
    level: Level
    verdict: str


@dataclass(frozen=True)
class AutonomyOutlook:
    """Everything the decision pages need about the autonomy envelope."""

    reserve: EnergyReserve
    conditions: Conditions
    scenarios: tuple[Scenario, ...]
    horizon_days: dict[str, float]
    capped: dict[str, bool]
    headline_days: float
    storm_day_share: float
    resupply: ResupplyPlan
    cqrm: CqrmResult
    assumptions: Assumptions
    generator_headroom_kw: float


def cycle_profile(profile: np.ndarray, total_hours: int) -> np.ndarray:
    """Repeat a measured profile until it covers the simulation horizon."""

    if profile.size == 0 or total_hours <= 0:
        return np.zeros(0, dtype=float)

    repeats = int(np.ceil(total_hours / profile.size))

    return np.tile(profile, repeats)[:total_hours]


def simulate_profile(
    net_load_kw: np.ndarray,
    start_soc_fraction: float,
    start_fuel_l: float,
    floor_soc_fraction: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Replay a net-load profile with the station's dispatch physics.

    Renewable generation is already netted out of the profile, so the twin's
    balance function is given the signed net load as its demand and no
    generation, which reproduces charging on surplus and diesel support on
    deficit exactly as the dataset was produced.
    """

    battery_config = dict(STATION_CONFIG["battery_system"])
    battery_config["initial_soc_fraction"] = float(start_soc_fraction)

    if floor_soc_fraction is not None:
        # A hard floor above the present charge would let the battery gain
        # energy out of nowhere, so the simulated floor is capped at the
        # charge the station actually holds today.
        battery_config["min_soc_fraction"] = float(
            min(floor_soc_fraction, start_soc_fraction)
        )

    generator_config = dict(STATION_CONFIG["generator_system"])
    generator_config["initial_fuel_l"] = float(start_fuel_l)

    zeros = np.zeros_like(net_load_kw)

    balance = simulate_power_balance(
        net_load_kw,
        zeros,
        zeros,
        battery_config,
        generator_config,
    )

    served_kw = balance["battery_discharge"] + balance["generator_output"]

    unserved_kw = np.maximum(0.0, net_load_kw - served_kw)

    return balance["fuel_level"], balance["battery_soc_pct"], unserved_kw


def scenario_inputs(
    master: pd.DataFrame,
    months: int = SCENARIO_COUNT,
) -> tuple[tuple[str, np.ndarray], ...]:
    """Last ``months`` calendar months of measured net load, in order."""

    if master is None or master.empty or "net_load_kw" not in master.columns:
        return ()

    frame = master[["timestamp", "net_load_kw"]].dropna().copy()

    if frame.empty:
        return ()

    frame["month"] = frame["timestamp"].dt.to_period("M")

    ordered = list(dict.fromkeys(frame["month"].tolist()))[-months:]

    scenarios: list[tuple[str, np.ndarray]] = []

    for month in ordered:
        profile = (
            frame.loc[frame["month"] == month, "net_load_kw"]
            .astype(float)
            .to_numpy()
        )

        if profile.size:
            scenarios.append((str(month), profile))

    return tuple(scenarios)


def evaluate_scenario(
    label: str,
    profile: np.ndarray,
    start_soc_fraction: float,
    start_fuel_l: float,
    floor_soc_fraction: float,
    cap_hours: int,
) -> Scenario:
    """Replay one month of measured conditions until the load cannot be served.

    The month is repeated block by block, carrying battery and fuel state
    forward, so the simulation stops as soon as the station runs out instead
    of always running to the horizon cap.
    """

    block_hours = int(profile.size) or cap_hours

    hours_done = 0
    fuel_now = float(start_fuel_l)
    soc_now = float(start_soc_fraction)
    fuel_used = 0.0
    unserved_kwh = 0.0
    capped = True

    while hours_done < cap_hours:
        span = min(block_hours, cap_hours - hours_done)

        block = cycle_profile(profile, span)

        fuel_level, soc_pct, unserved_kw = simulate_profile(
            block,
            soc_now,
            fuel_now,
            floor_soc_fraction,
        )

        flagged = np.flatnonzero(unserved_kw > UNSERVED_TOLERANCE_KW)

        stop_index = int(flagged[0]) if flagged.size else None

        # The failing hour itself counts against the fuel already burned.
        consumed = span if stop_index is None else stop_index + 1

        fuel_used += fuel_now - float(fuel_level[consumed - 1])

        unserved_kwh += float(unserved_kw[:consumed].sum())

        if stop_index is not None:
            hours_done += stop_index
            capped = False
            break

        hours_done += span
        fuel_now = float(fuel_level[-1])
        soc_now = float(soc_pct[-1]) / 100.0

        if (
            hours_done >= NO_DRAW_SHORT_CIRCUIT_HOURS
            and fuel_used <= NO_DRAW_FUEL_FRACTION * float(start_fuel_l)
        ):
            break

    simulated_days = max(1, hours_done) / 24.0

    # A capped scenario only proves the station outlasted the planning window,
    # so it is reported at the cap: using the point where the short circuit
    # stopped would rank a sustainable month below a fuel-limited one.
    horizon_days = cap_hours / 24.0 if capped else simulated_days

    return Scenario(
        label=label,
        horizon_days=horizon_days,
        capped=capped,
        simulated_days=simulated_days,
        fuel_used_l=max(0.0, fuel_used),
        unserved_kwh=unserved_kwh,
        mean_deficit_kw=float(np.mean(profile)),
    )


def evaluate_scenarios(
    inputs: tuple[tuple[str, np.ndarray], ...],
    start_soc_fraction: float,
    start_fuel_l: float,
    floor_soc_fraction: float,
    cap_days: int = HORIZON_CAP_DAYS,
) -> tuple[Scenario, ...]:
    """Simulate every condition scenario from the current state."""

    cap_hours = cap_days * 24

    return tuple(
        evaluate_scenario(
            label,
            profile,
            start_soc_fraction,
            start_fuel_l,
            floor_soc_fraction,
            cap_hours,
        )
        for label, profile in inputs
        if profile.size
    )


def outcome_quantiles(
    scenarios: tuple[Scenario, ...],
) -> tuple[dict[str, float], dict[str, bool]]:
    """Horizon in days and capped flags at each outcome quantile.

    The nearest rank on the sorted scenario list is used instead of
    interpolating, so a reported horizon always corresponds to one real
    month of measured conditions.
    """

    if not scenarios:
        return (
            {key: 0.0 for key in OUTCOME_QUANTILES},
            {key: False for key in OUTCOME_QUANTILES},
        )

    ordered = sorted(scenarios, key=lambda scenario: scenario.horizon_days)

    last = len(ordered) - 1

    horizons: dict[str, float] = {}
    capped: dict[str, bool] = {}

    for key, quantile in OUTCOME_QUANTILES.items():
        index = int(np.clip(round(quantile * last), 0, last))

        horizons[key] = float(ordered[index].horizon_days)
        capped[key] = bool(ordered[index].capped)

    return horizons, capped


def conditions(frame: pd.DataFrame, inputs: tuple[tuple[str, np.ndarray], ...]) -> Conditions:
    """Operating conditions measured over the scenario sample."""

    if frame is None or frame.empty or "net_load_kw" not in frame.columns:
        return Conditions(0.0, 0.0, 0.0, 0, 0)

    net_load = pd.to_numeric(frame["net_load_kw"], errors="coerce").fillna(0.0)

    renewable_fraction = 0.0

    if "renewable_fraction" in frame.columns:
        renewable_fraction = float(
            pd.to_numeric(frame["renewable_fraction"], errors="coerce").fillna(0.0).mean()
        )

    sample_days = int(
        max(
            1,
            (frame["timestamp"].iloc[-1] - frame["timestamp"].iloc[0]).total_seconds()
            // 86400,
        )
    )

    return Conditions(
        latest_deficit_kw=float(max(0.0, net_load.iloc[-1])),
        mean_deficit_kw=float(max(0.0, net_load.clip(lower=0.0).mean())),
        renewable_fraction=renewable_fraction,
        scenario_months=len(inputs),
        sample_days=sample_days,
    )


def energy_reserve(latest: pd.Series, assumptions: Assumptions) -> EnergyReserve:
    """Dispatchable energy on site right now."""

    battery_soc_pct = float(latest.get("battery_soc_pct", 0.0))
    fuel_litres = float(latest.get("fuel_level", 0.0))

    capacity_kwh = float(STATION_CONFIG["battery_system"]["capacity_kwh"])

    # A floor above the charge actually held cannot create reserve, so the
    # effective floor is the lower of the operator's floor and today's charge.
    effective_floor_pct = min(
        assumptions.battery_reserve_floor_pct,
        battery_soc_pct,
    )

    battery_kwh = max(
        0.0,
        (battery_soc_pct - effective_floor_pct) / 100.0 * capacity_kwh,
    )

    # Nominal conversion, shown only for scale: the real autonomy comes from
    # the simulation, which includes the generator's idle fuel burn.
    marginal_kwh_per_litre = 1.0 / float(
        STATION_CONFIG["generator_system"]["fuel_curve_b_l_per_kwh"]
    )

    runway = latest.get("fuel_runway_days")

    return EnergyReserve(
        battery_kwh=battery_kwh,
        fuel_litres=max(0.0, fuel_litres),
        equivalent_kwh=battery_kwh + max(0.0, fuel_litres) * marginal_kwh_per_litre,
        battery_soc_pct=battery_soc_pct,
        reserve_floor_pct=assumptions.battery_reserve_floor_pct,
        effective_floor_pct=effective_floor_pct,
        reserve_target_pct=assumptions.battery_reserve_target_pct,
        fuel_runway_days=None if pd.isna(runway) else float(runway),
    )


def storm_day_share(frame: pd.DataFrame, threshold_ms: float) -> float:
    """Share of days in the sample that reached storm wind speed."""

    if frame is None or frame.empty or "wind_speed" not in frame.columns:
        return 0.0

    daily_peak = (
        frame.set_index("timestamp")["wind_speed"]
        .astype(float)
        .resample("D")
        .max()
        .dropna()
    )

    if daily_peak.empty:
        return 0.0

    return float((daily_peak >= threshold_ms).mean())


def resupply_plan(assumptions: Assumptions, storm_share: float) -> ResupplyPlan:
    """Expected resupply arrival widened by measured storm frequency."""

    spread = min(
        MAX_DELAY_SPREAD,
        float(assumptions.logistics_delay_multiplier) * storm_share,
    )

    expected = float(assumptions.planned_resupply_days)

    return ResupplyPlan(
        expected_days=expected,
        optimistic_days=expected * (1.0 - spread),
        conservative_days=expected * (1.0 + spread),
        delay_spread=spread,
        storm_day_share=storm_share,
    )


def cqrm(horizon_days: float, resupply_days: float) -> CqrmResult:
    """Confidence-qualified resupply margin."""

    margin = horizon_days - resupply_days

    if margin < 0:
        level = Level.CRITICAL
        verdict = "Resupply deficit: autonomy ends before the ship can arrive."
    elif margin < CQRM_ATTENTION_DAYS:
        level = Level.ATTENTION
        verdict = "Thin margin: less than three days of reaction time."
    else:
        level = Level.SAFE
        verdict = "Margin held: autonomy outlasts the conservative resupply arrival."

    return CqrmResult(
        margin_days=margin,
        horizon_days=horizon_days,
        resupply_days=resupply_days,
        level=level,
        verdict=verdict,
    )


def outlook(
    master: pd.DataFrame,
    latest: pd.Series,
    assumptions: Assumptions,
    cap_days: int = HORIZON_CAP_DAYS,
) -> AutonomyOutlook:
    """Assemble the complete autonomy outlook from measured state."""

    inputs = scenario_inputs(master, months=int(assumptions.scenario_months))

    start_soc_pct = float(latest.get("battery_soc_pct", 0.0))

    start_soc_fraction = start_soc_pct / 100.0

    start_fuel_l = float(latest.get("fuel_level", 0.0))

    floor_soc_fraction = (
        min(assumptions.battery_reserve_floor_pct, start_soc_pct) / 100.0
    )

    scenarios = evaluate_scenarios(
        inputs,
        start_soc_fraction,
        start_fuel_l,
        floor_soc_fraction,
        cap_days=cap_days,
    )

    horizon_days, capped = outcome_quantiles(scenarios)

    storm_share = storm_day_share(master, assumptions.storm_wind_threshold_ms)

    headline = horizon_days.get("adverse", 0.0)

    return AutonomyOutlook(
        reserve=energy_reserve(latest, assumptions),
        conditions=conditions(master, inputs),
        scenarios=scenarios,
        horizon_days=horizon_days,
        capped=capped,
        headline_days=headline,
        storm_day_share=storm_share,
        resupply=resupply_plan(assumptions, storm_share),
        cqrm=cqrm(headline, resupply_plan(assumptions, storm_share).conservative_days),
        assumptions=assumptions,
        generator_headroom_kw=max(
            0.0,
            float(STATION_CONFIG["generator_system"]["capacity_kw"])
            - float(latest.get("generator_output", 0.0)),
        ),
    )
