"""
Step 5: Equipment Operating Model
Step 6: Zone-Wise Station Load
-----------------------------------
Determines each equipment item's operating factor (0-1) per hour from
time of day, occupancy, temperature, season, and research activity, then
aggregates to zone loads and total station load.

Zone Load = sum(equipment power * operating factor)
"""
import numpy as np
import pandas as pd
from twin.equipment_library import EQUIPMENT_LIBRARY


def _schedule_factor(hour):
    """Simple daily activity schedule: peaks at meal times / working hours."""
    # morning ramp, midday plateau, evening peak (dinner), low overnight
    base = (
        0.15
        + 0.35 * np.clip(np.sin(np.pi * (hour - 6) / 12), 0, 1)   # daytime
        + 0.35 * np.exp(-0.5 * ((hour - 18.5) / 1.5) ** 2)        # dinner peak
    )
    return np.clip(base, 0.1, 1.0)


def _thermal_factor(temperature, t_ref=0.0, t_floor=-35.0):
    """Heating demand rises as temperature falls below t_ref, saturating near t_floor."""
    span = t_ref - t_floor
    factor = (t_ref - temperature) / span
    return np.clip(factor, 0.15, 1.0)


def compute_operating_factors(env_df, occ_df):
    """Returns a DataFrame of operating factor (0-1) per equipment id per hour."""
    df = pd.merge(env_df, occ_df, on="timestamp")
    hour = df["timestamp"].dt.hour.values
    temperature = df["temperature"].values
    occupancy = df["occupancy"].values
    activity = df["activity_level"].values

    occ_norm = np.clip(occupancy / occupancy.max(), 0.2, 1.0)
    schedule = _schedule_factor(hour)
    thermal = _thermal_factor(temperature)
    research_activity = np.clip(0.3 + 0.7 * activity * occ_norm, 0.1, 1.0)

    factors = pd.DataFrame({"timestamp": df["timestamp"]})
    for eq in EQUIPMENT_LIBRARY:
        behavior = eq["behavior"]
        if behavior == "continuous":
            f = np.full(len(df), 0.95)
        elif behavior == "occupancy_driven":
            f = 0.2 + 0.8 * occ_norm
        elif behavior == "thermal_driven":
            f = thermal
        elif behavior == "schedule_driven":
            f = schedule
        elif behavior == "research_driven":
            f = research_activity
        else:
            f = np.full(len(df), 0.5)
        factors[eq["id"]] = np.clip(f, 0, 1)
    return factors


def compute_zone_loads(env_df, occ_df):
    factors = compute_operating_factors(env_df, occ_df)
    out = pd.DataFrame({"timestamp": factors["timestamp"]})

    zone_power = {"critical": np.zeros(len(factors)),
                  "residential": np.zeros(len(factors)),
                  "research": np.zeros(len(factors))}

    for eq in EQUIPMENT_LIBRARY:
        f = factors[eq["id"]].values
        power = eq["min_power_kw"] + (eq["nominal_power_kw"] - eq["min_power_kw"]) * f
        zone_power[eq["zone"]] += power

    out["critical_load"] = np.round(zone_power["critical"], 3)
    out["residential_load"] = np.round(zone_power["residential"], 3)
    out["research_load"] = np.round(zone_power["research"], 3)
    out["total_station_load"] = np.round(
        out["critical_load"] + out["residential_load"] + out["research_load"], 3
    )
    return out


def inject_residential_anomalies(load_df, anomaly_hours=6):
    """Inject deterministic residential demand spikes for anomaly testing."""
    out = load_df.copy()
    if out.empty or "residential_load" not in out.columns:
        return out

    starts = [
        max(0, len(out) - 144),
        max(0, len(out) - 72),
    ]
    for start in starts:
        end = min(len(out), start + anomaly_hours)
        out.loc[start:end - 1, "residential_load"] = np.round(
            out.loc[start:end - 1, "residential_load"] * 2.2,
            3,
        )

    out["total_station_load"] = np.round(
        out["critical_load"]
        + out["residential_load"]
        + out["research_load"],
        3,
    )
    return out
