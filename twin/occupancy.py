"""
Step 4: Occupancy Simulator
------------------------------
Generates hourly occupancy and an "activity level" (0-1) from the seasonal
population assumption. Higher occupancy raises residential/general demand.
"""
import numpy as np
import pandas as pd


def simulate_occupancy(timestamps, occupancy_cfg, seed=42):
    rng = np.random.default_rng(seed + 1)
    timestamps = pd.to_datetime(timestamps)
    doy = timestamps.dt.dayofyear.values
    hour = timestamps.dt.hour.values
    month = timestamps.dt.month.values

    is_summer = np.isin(month, occupancy_cfg["summer_months"])
    base_occupancy = np.where(is_summer, occupancy_cfg["summer_max"],
                               occupancy_cfg["winter_min"]).astype(float)

    # smooth transition at season edges using a cosine ramp instead of a hard step
    # (approximate by blending with a seasonal sinusoid keyed to day-of-year)
    seasonal_phase = 2 * np.pi * (doy - 15) / 365.25
    smooth_fraction = 0.5 + 0.5 * np.cos(seasonal_phase)  # 1 near Jan, 0 near Jul
    smoothed = (occupancy_cfg["winter_min"] +
                (occupancy_cfg["summer_max"] - occupancy_cfg["winter_min"]) * smooth_fraction)

    occupancy_base = 0.5 * base_occupancy + 0.5 * smoothed

    # small day-to-day noise (field parties leaving/returning, etc.)
    daily_noise = rng.normal(0, 1.0, len(timestamps))
    occupancy = np.clip(np.round(occupancy_base + daily_noise), 5, None)

    # activity level: daytime hours higher, quiet overnight, small random variation
    diurnal_activity = 0.35 + 0.55 * np.clip(np.sin(np.pi * (hour - 6) / 14), 0, 1)
    activity_noise = rng.normal(0, 0.05, len(timestamps))
    activity_level = np.clip(diurnal_activity + activity_noise, 0.1, 1.0)

    return pd.DataFrame({
        "timestamp": timestamps,
        "occupancy": occupancy.astype(int),
        "activity_level": np.round(activity_level, 3),
    })
