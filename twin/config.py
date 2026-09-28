"""
Step 1: Station Model Configuration
------------------------------------
Configurable assumptions for a GENERIC polar research center.
These are simulation parameters only -- not a claim about the exact
equipment or electrical characteristics of any real station.
"""

STATION_CONFIG = {
    "station_type": "Permanent generic polar research center",
    "location": {
        "name": "Generic Polar Site (representative coastal Antarctic location)",
        "latitude": -69.40,
        "longitude": 76.19,
        "timezone_offset_hours": 5,  # local standard time offset from UTC
    },
    "occupancy": {
        "summer_max": 40,
        "winter_min": 20,
        # Austral summer ~ Nov-Mar, winter ~ Apr-Oct (Southern Hemisphere)
        "summer_months": [11, 12, 1, 2, 3],
    },
    "zones": ["critical", "residential", "research"],
        "energy_sources": ["solar", "wind", "battery", "diesel_generator"],

    "solar_system": {
        "capacity_kw": 220.0,
        "efficiency": 0.82,
        "panel_area_m2": 1450.0,
    },

    "wind_system": {
        "capacity_kw": 50.0,
        "cut_in_speed_ms": 3.0,
        "rated_speed_ms": 12.0,
        "cut_out_speed_ms": 25.0,
        "efficiency": 0.90,
    },

    "battery_system": {
        "capacity_kwh": 300.0,
        "initial_soc_fraction": 0.6,
        "min_soc_fraction": 0.20,
        "max_soc_fraction": 0.95,
        "max_charge_kw": 60.0,
        "max_discharge_kw": 60.0,
        "round_trip_efficiency": 0.92,
    },

    "generator_system": {
        "capacity_kw": 120.0,
        "min_load_fraction": 0.30,     # generators run poorly below this
        # Sized for a realistic annual diesel reserve (polar stations are
        # typically resupplied once per year by ship), not just a few weeks.
        "fuel_tank_capacity_l": 260000.0,
        "initial_fuel_l": 240000.0,
        # simplified linear fuel curve: l/hr = a + b * kW_output
        "fuel_curve_a_l_per_hr": 3.0,
        "fuel_curve_b_l_per_kwh": 0.28,
    },

    "simulation": {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "freq": "h",
        "random_seed": 42,
    },

    "load_shedding": {
        "enabled": True,
        "trigger_metric": "wind_speed",       # which column drives the decision
        # Thresholds calibrated to this site's actual wind distribution
        # (mean ~11.8 m/s, p95 ~16.4, p99 ~18.5) so "shed" means a genuine
        # storm outlier, not an average day.
        "trigger_threshold": 18.0,             # shed when metric >= this (~p97, real storm)
        "release_threshold": 13.0,             # restore when metric <= this (~p65, storm has passed)
        "confirm_hours": 2,                    # metric must stay past threshold this many hours before shedding
        "min_shed_duration_hours": 6,          # once shed, stays off at least this long
        "cooldown_hours": 3,                   # after restoring, wait this long before it can shed again
        "priorities_to_shed": ["Low", "Medium"],
    },
}
