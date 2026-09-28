"""
Step 8: Simulate the Battery
Step 9: Simulate Diesel Generation
Step 10: Simulate Fuel Level & Fuel Runway
--------------------------------------------
These three are combined into one hour-by-hour loop because each hour's
battery/diesel/fuel state depends on the previous hour's state.

Dispatch order per hour:
  1. net = load - solar - wind
  2. if net < 0 (renewable surplus): charge battery with surplus
  3. if net > 0 (deficit): discharge battery to cover it
  4. remaining deficit (if any) -> diesel generator
  5. diesel output -> fuel consumption via linear fuel curve
  6. fuel level decreases; fuel runway estimated from trailing average diesel use
"""

import numpy as np


def simulate_power_balance(
    total_load_kw,
    solar_gen_kw,
    wind_gen_kw,
    battery_cfg,
    generator_cfg,
    runway_lookback_hours=72,
):
    n = len(total_load_kw)

    capacity_kwh = battery_cfg["capacity_kwh"]
    min_soc = battery_cfg["min_soc_fraction"] * capacity_kwh
    max_soc = battery_cfg["max_soc_fraction"] * capacity_kwh
    max_charge_kw = battery_cfg["max_charge_kw"]
    max_discharge_kw = battery_cfg["max_discharge_kw"]

    rt_eff = battery_cfg["round_trip_efficiency"]
    charge_eff = np.sqrt(rt_eff)
    discharge_eff = np.sqrt(rt_eff)

    soc_kwh = np.zeros(n)
    battery_charge = np.zeros(n)
    battery_discharge = np.zeros(n)

    gen_capacity = generator_cfg["capacity_kw"]
    min_load_frac = generator_cfg["min_load_fraction"]
    fuel_a = generator_cfg["fuel_curve_a_l_per_hr"]
    fuel_b = generator_cfg["fuel_curve_b_l_per_kwh"]
    tank_capacity = generator_cfg["fuel_tank_capacity_l"]

    # Prevent unused-variable warnings and document the configured limit.
    _ = tank_capacity

    generator_output = np.zeros(n)
    generator_status = np.array(["off"] * n, dtype=object)
    fuel_consumption = np.zeros(n)
    fuel_level = np.zeros(n)

    soc = battery_cfg["initial_soc_fraction"] * capacity_kwh
    fuel = generator_cfg["initial_fuel_l"]

    for i in range(n):
        load = total_load_kw[i]
        solar = solar_gen_kw[i]
        wind = wind_gen_kw[i]

        # Renewable generation from both solar and wind.
        renewable_generation = solar + wind

        # Positive = deficit, negative = renewable surplus.
        net = load - renewable_generation

        if net < 0:
            # Renewable surplus: charge battery.
            surplus = -net

            room_kwh = max_soc - soc

            charge_kw = min(
                surplus,
                max_charge_kw,
                room_kwh / charge_eff if charge_eff > 0 else 0,
            )

            charge_kw = max(charge_kw, 0)

            soc += charge_kw * charge_eff
            battery_charge[i] = charge_kw
            remaining_deficit = 0.0

        else:
            # Deficit: discharge battery first.
            available_kwh = soc - min_soc

            discharge_kw = min(
                net,
                max_discharge_kw,
                max(available_kwh * discharge_eff, 0),
            )

            discharge_kw = max(discharge_kw, 0)

            soc -= (
                discharge_kw / discharge_eff
                if discharge_eff > 0
                else 0
            )

            battery_discharge[i] = discharge_kw
            remaining_deficit = net - discharge_kw

        soc = np.clip(soc, min_soc, max_soc)
        soc_kwh[i] = soc

        # Diesel covers any remaining deficit.
        if remaining_deficit > 1e-6 and fuel > 0:
            gen_out = min(remaining_deficit, gen_capacity)

            min_out = gen_capacity * min_load_frac

            if gen_out < min_out:
                gen_out = min(min_out, gen_capacity)

            generator_output[i] = gen_out
            generator_status[i] = "running"

            consumption = fuel_a + fuel_b * gen_out

            consumption = min(consumption, fuel)

            fuel_consumption[i] = consumption

            fuel -= consumption
            fuel = max(fuel, 0.0)

        else:
            generator_output[i] = 0.0
            generator_status[i] = "off"
            fuel_consumption[i] = 0.0

        fuel_level[i] = fuel

    # Fuel runway:
    # days remaining at trailing average diesel consumption rate.
    fuel_runway_days = np.zeros(n)

    for i in range(n):
        lo = max(0, i - runway_lookback_hours + 1)

        window = fuel_consumption[lo:i + 1]

        avg_hourly = (
            window.mean()
            if len(window) > 0
            else 0.0
        )

        if avg_hourly < 1e-6:
            fuel_runway_days[i] = np.nan
        else:
            fuel_runway_days[i] = (
                fuel_level[i]
                / (avg_hourly * 24.0)
            )

    # Charge and discharge are mutually exclusive in a given hour: the battery
    # is either filling from a renewable surplus or serving a deficit, never
    # both. Zero the flow that did not happen, then export the signed net.
    battery_discharge = np.where(
        battery_charge > 0.0,
        0.0,
        battery_discharge,
    )
    battery_charge = np.where(
        battery_discharge > 0.0,
        0.0,
        battery_charge,
    )

    # Signed battery power: positive while charging, negative while serving.
    battery_power = battery_charge - battery_discharge

    return {
        "battery_soc": np.round(soc_kwh, 2),
        "battery_soc_pct": np.round(
            100 * soc_kwh / capacity_kwh, 1
        ),
        "battery_charge": np.round(
            battery_charge, 3
        ),
        "battery_discharge": np.round(
            battery_discharge, 3
        ),
        "battery_power": np.round(
            battery_power, 3
        ),
        "generator_output": np.round(
            generator_output, 3
        ),
        "generator_status": generator_status,
        "fuel_consumption": np.round(
            fuel_consumption, 3
        ),
        "fuel_level": np.round(
            fuel_level, 1
        ),
        "fuel_runway_days": np.round(
            fuel_runway_days, 1
        ),
    }
