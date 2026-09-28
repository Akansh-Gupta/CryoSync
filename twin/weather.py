"""
Step 3: Real Environmental Data
---------------------------------
Intended real sources: NCPOR (temperature, wind) and NASA POWER
(solar irradiance), per the project spec.

NOTE ON THIS ENVIRONMENT: this sandbox's network egress is restricted and
cannot reach power.larc.nasa.gov or NCPOR directly. This module is built so
that plugging in real data is a one-line change:

  - If you have a downloaded NCPOR/NASA POWER CSV, call
    `load_real_weather(csv_path)` with columns:
    timestamp, temperature, wind_speed, solar_irradiance
  - Otherwise `generate_fallback_weather()` produces a physically-reasonable
    placeholder climatology (diurnal + seasonal cycles typical of a coastal
    Antarctic site) so the rest of the pipeline can run end-to-end. This is
    clearly a SIMULATED placeholder, not an observation.

To get real data yourself outside this sandbox:
  NASA POWER hourly point API:
    https://power.larc.nasa.gov/api/temporal/hourly/point
      ?parameters=T2M,WS10M,ALLSKY_SFC_SW_DWN&community=RE
      &longitude=<lon>&latitude=<lat>&start=YYYYMMDD&end=YYYYMMDD&format=JSON
  NCPOR: https://ncpor.res.in (station-specific data portals / requests)
"""
import numpy as np
import pandas as pd


def load_real_weather(csv_path):
    """Load real environmental data from a CSV with columns:
    timestamp, temperature, wind_speed, solar_irradiance
    """
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    required = {"timestamp", "temperature", "wind_speed", "solar_irradiance"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Weather CSV missing columns: {missing}")
    return df.sort_values("timestamp").reset_index(drop=True)


def generate_fallback_weather(start_date, end_date, freq, latitude, seed=42):
    """
    Physically-reasonable SYNTHETIC placeholder for a coastal high-latitude
    polar site, used only when real NCPOR/NASA POWER data isn't available.

    - Temperature: strong seasonal cycle (Southern Hemisphere), mild diurnal
      cycle, plus weather noise (autocorrelated).
    - Wind: polar/katabatic-style baseline with gusts, seasonal bump.
    - Solar irradiance: zero during polar night, strong seasonal + diurnal
      envelope during polar day, clipped at zero, with cloud-driven noise.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start_date, end_date, freq=freq, inclusive="left")
    n = len(idx)
    doy = idx.dayofyear.values
    hour = idx.hour.values

    # --- Temperature (deg C) ---
    # Southern hemisphere: coldest ~ day 200 (mid-winter, ~July), warmest ~ day 15 (Jan)
    seasonal_phase = 2 * np.pi * (doy - 15) / 365.25
    seasonal_temp = -15.0 + 15.0 * np.cos(seasonal_phase)  # warmest ~day15 (~0C), coldest ~day200 (~-30C)
    diurnal_temp = 2.0 * np.sin(2 * np.pi * (hour - 14) / 24)
    noise_temp = _ar1_noise(n, sigma=1.2, phi=0.85, rng=rng)
    temperature = seasonal_temp + diurnal_temp + noise_temp

    # --- Wind speed (m/s) ---
    seasonal_wind = 9.0 + 2.0 * np.cos(seasonal_phase)  # slightly windier in winter
    gust_noise = np.abs(_ar1_noise(n, sigma=2.5, phi=0.7, rng=rng))
    wind_speed = np.clip(seasonal_wind + gust_noise, 0.5, 35.0)

    # --- Solar irradiance (W/m^2), latitude-aware polar day/night ---
    solar_irradiance = _polar_solar_irradiance(idx, latitude, rng)

    df = pd.DataFrame({
        "timestamp": idx,
        "temperature": np.round(temperature, 2),
        "wind_speed": np.round(wind_speed, 2),
        "solar_irradiance": np.round(solar_irradiance, 1),
    })
    df.attrs["source"] = "SYNTHETIC_PLACEHOLDER (no live NCPOR/NASA POWER access in this environment)"
    return df


def _ar1_noise(n, sigma, phi, rng):
    e = rng.normal(0, sigma, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _polar_solar_irradiance(idx, latitude, rng):
    """Simplified clear-sky-like model with polar day/night, then cloud noise."""
    doy = idx.dayofyear.values
    hour = idx.hour.values + idx.minute.values / 60.0
    lat_rad = np.radians(latitude)

    # solar declination (deg), standard approximation
    decl = 23.45 * np.sin(np.radians(360 / 365.25 * (doy - 81)))
    decl_rad = np.radians(decl)

    # hour angle
    hour_angle = np.radians(15 * (hour - 12))

    # solar elevation angle
    sin_elev = (np.sin(lat_rad) * np.sin(decl_rad) +
                np.cos(lat_rad) * np.cos(decl_rad) * np.cos(hour_angle))
    elevation = np.degrees(np.arcsin(np.clip(sin_elev, -1, 1)))

    # clear-sky irradiance approx, scaled by elevation above horizon
    max_irr = 1000.0
    clear_sky = np.clip(max_irr * np.sin(np.radians(np.clip(elevation, 0, 90))), 0, None)

    # cloud attenuation factor per hour (correlated across a day-ish window)
    cloud_factor = 0.55 + 0.45 * np.abs(_ar1_noise(len(idx), sigma=1.0, phi=0.9, rng=rng))
    cloud_factor = np.clip(cloud_factor, 0.15, 1.0)

    irradiance = clear_sky * cloud_factor
    irradiance[elevation <= 0] = 0.0
    return irradiance


if __name__ == "__main__":
    from twin.config import STATION_CONFIG
    cfg = STATION_CONFIG
    df = generate_fallback_weather(
        cfg["simulation"]["start_date"], cfg["simulation"]["end_date"],
        cfg["simulation"]["freq"], cfg["location"]["latitude"],
        seed=cfg["simulation"]["random_seed"],
    )
    print(df.describe())
