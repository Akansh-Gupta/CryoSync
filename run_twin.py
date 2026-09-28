"""
CRYOSYNC — Digital Twin Runner
Builds the hourly master dataset from the twin/ modules and validates it
via validation/validate.py. This is the reorganized, package-based version
of the original run_simulation.py.
"""
import sys
import pandas as pd

from twin.config import STATION_CONFIG
from twin.weather import generate_fallback_weather, load_real_weather
from twin.occupancy import simulate_occupancy
from twin.loads import compute_zone_loads, inject_residential_anomalies
from twin.solar import simulate_solar
from twin.wind import simulate_wind
from twin.power_balance import simulate_power_balance
from validation.validate import run_validation, print_validation_report


def build_master_dataset(cfg=STATION_CONFIG, real_weather_csv=None):
    sim_cfg = cfg["simulation"]

    if real_weather_csv:
        env_df = load_real_weather(real_weather_csv)
        weather_source = "REAL (user-provided CSV)"
    else:
        env_df = generate_fallback_weather(
            sim_cfg["start_date"],
            sim_cfg["end_date"],
            sim_cfg["freq"],
            cfg["location"]["latitude"],
            seed=sim_cfg["random_seed"],
        )
        weather_source = env_df.attrs.get(
            "source",
            "SYNTHETIC_PLACEHOLDER"
        )

    occ_df = simulate_occupancy(
        env_df["timestamp"],
        cfg["occupancy"],
        seed=sim_cfg["random_seed"],
    )

    load_df = compute_zone_loads(
        env_df,
        occ_df,
    )
    load_df = inject_residential_anomalies(load_df)

    solar_gen = simulate_solar(
        env_df,
        cfg["solar_system"],
    )

    wind_gen = simulate_wind(
        env_df["wind_speed"].values,
        cfg["wind_system"],
    )

    balance = simulate_power_balance(
        load_df["total_station_load"].values,
        solar_gen,
        wind_gen,
        cfg["battery_system"],
        cfg["generator_system"],
    )

    master = env_df.merge(
        occ_df,
        on="timestamp"
    ).merge(
        load_df,
        on="timestamp"
    )

    master["solar_generation"] = solar_gen
    master["wind_generation"] = wind_gen

    for key, values in balance.items():
        master[key] = values

    master = master[[
        "timestamp",
        "temperature",
        "wind_speed",
        "solar_irradiance",
        "occupancy",
        "activity_level",
        "critical_load",
        "residential_load",
        "research_load",
        "total_station_load",
        "solar_generation",
        "wind_generation",
        "battery_soc",
        "battery_soc_pct",
        "battery_charge",
        "battery_discharge",
        "battery_power",
        "generator_output",
        "generator_status",
        "fuel_consumption",
        "fuel_level",
        "fuel_runway_days",
    ]]

    return master, weather_source


if __name__ == "__main__":
    real_csv = sys.argv[1] if len(sys.argv) > 1 else None

    master_df, source = build_master_dataset(
        real_weather_csv=real_csv
    )

    print(f"Weather data source: {source}")
    print(f"Master dataset shape: {master_df.shape}")

    results = run_validation(
        master_df,
        STATION_CONFIG["battery_system"],
        STATION_CONFIG["solar_system"],
        STATION_CONFIG["generator_system"],
    )

    print_validation_report(results)

    out_path = "data/master_dataset.csv"
    master_df.to_csv(
        out_path,
        index=False
    )

    print(f"\nSaved master dataset -> {out_path}")