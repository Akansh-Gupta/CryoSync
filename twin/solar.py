"""
Step 7: Simulate Solar Generation
------------------------------------
Converts real (or fallback) solar irradiance into available solar power,
bounded by installed capacity and system efficiency.
"""
import numpy as np


def simulate_solar(env_df, solar_cfg):
    # Standard test conditions reference irradiance = 1000 W/m^2
    fraction_of_stc = env_df["solar_irradiance"].values / 1000.0
    raw_kw = fraction_of_stc * solar_cfg["capacity_kw"] * solar_cfg["efficiency"]
    solar_generation = np.clip(raw_kw, 0, solar_cfg["capacity_kw"])
    return np.round(solar_generation, 3)
