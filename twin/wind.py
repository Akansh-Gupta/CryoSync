"""
CRYOSYNC — Wind Turbine Simulation
----------------------------------
Generates hourly wind power from wind speed for the
generic polar research center digital twin.

These parameters are simulation assumptions only.
"""

import numpy as np


def simulate_wind(wind_speed, wind_cfg):
    """
    Simulate wind-turbine electrical generation in kW.

    Uses a simplified turbine power curve:
      - Below cut-in speed: 0 kW
      - Between cut-in and rated speed: cubic increase
      - Between rated and cut-out speed: rated capacity
      - At/above cut-out speed: 0 kW
    """

    wind_speed = np.asarray(wind_speed, dtype=float)

    capacity = float(wind_cfg["capacity_kw"])
    cut_in = float(wind_cfg["cut_in_speed_ms"])
    rated = float(wind_cfg["rated_speed_ms"])
    cut_out = float(wind_cfg["cut_out_speed_ms"])
    efficiency = float(wind_cfg["efficiency"])

    generation = np.zeros_like(wind_speed)

    # Between cut-in and rated speed
    ramp = (
        (wind_speed >= cut_in)
        & (wind_speed < rated)
    )

    generation[ramp] = capacity * (
        (wind_speed[ramp] ** 3 - cut_in ** 3)
        / (rated ** 3 - cut_in ** 3)
    )

    # Rated power region
    rated_region = (
        (wind_speed >= rated)
        & (wind_speed < cut_out)
    )

    generation[rated_region] = capacity

    # Apply system efficiency
    generation *= efficiency

    return np.clip(generation, 0.0, capacity)