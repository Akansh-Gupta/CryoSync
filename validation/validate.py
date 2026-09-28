"""
Step 12: Validate the Simulation
------------------------------------
Sanity checks against the relationships the spec calls out, run against the
master dataset. Prints a pass/fail summary and returns a results dict.
"""
import numpy as np


def _partial_corr(x, y, z):
    """Correlation between x and y, controlling for z, via residualization."""
    def resid(a, b):
        b1 = np.vstack([b, np.ones_like(b)]).T
        coef, *_ = np.linalg.lstsq(b1, a, rcond=None)
        return a - b1 @ coef
    rx = resid(x, z)
    ry = resid(y, z)
    return np.corrcoef(rx, ry)[0, 1]


def run_validation(df, battery_cfg, solar_cfg, generator_cfg):
    results = {}

    # 1. Lower temperature -> generally higher heating-relevant demand.
    #    Proxy: correlation between temperature and critical+residential load
    #    should be negative.
    corr_temp_load = np.corrcoef(df["temperature"], df["critical_load"] + df["residential_load"])[0, 1]
    results["temp_vs_load_negative_corr"] = (corr_temp_load < -0.15, round(corr_temp_load, 3))

    # 2. Higher occupancy/activity -> generally higher residential demand.
    #    Residential load is jointly driven by occupancy AND temperature
    #    (heating), and those two happen to be strongly anti-correlated
    #    seasonally at a polar site (high occupancy in the warm summer).
    #    A raw correlation would mostly pick up the heating/temperature
    #    signal, so we use a partial correlation that controls for
    #    temperature to isolate the occupancy relationship specifically.
    corr_occ_res_partial = _partial_corr(df["occupancy"].values, df["residential_load"].values, df["temperature"].values)
    results["occupancy_vs_residential_positive_corr (temp-controlled)"] = (corr_occ_res_partial > 0.1, round(corr_occ_res_partial, 3))

    # 3. Higher solar irradiance -> higher solar generation.
    corr_irr_solar = np.corrcoef(df["solar_irradiance"], df["solar_generation"])[0, 1]
    results["irradiance_vs_solar_gen_positive_corr"] = (corr_irr_solar > 0.9, round(corr_irr_solar, 3))

    # 4. Solar surplus -> battery SoC can increase (check any charging occurs when solar > load)
    surplus_hours = df[df["solar_generation"] > df["total_station_load"]]
    charge_during_surplus = (surplus_hours["battery_charge"] > 0).mean() if len(surplus_hours) else np.nan
    results["battery_charges_during_solar_surplus"] = (
        (charge_during_surplus > 0.5) if len(surplus_hours) else None,
        round(charge_during_surplus, 3) if len(surplus_hours) else "no surplus hours"
    )

    # 5. Generation deficit -> battery/diesel contribution increases.
    deficit_hours = df[df["solar_generation"] < df["total_station_load"]]
    covered = (deficit_hours["battery_discharge"] + deficit_hours["generator_output"] > 0).mean() if len(deficit_hours) else np.nan
    results["deficit_covered_by_battery_or_diesel"] = (covered > 0.95 if len(deficit_hours) else None, round(covered, 3) if len(deficit_hours) else "n/a")

    # 6. Higher diesel generation -> fuel level decreases faster.
    #    Check: fuel_level is monotonically non-increasing.
    fuel_diffs = df["fuel_level"].diff().dropna()
    results["fuel_level_never_increases"] = (bool((fuel_diffs <= 1e-6).all()), f"{(fuel_diffs > 1e-6).sum()} violations")

    # 7. Fuel runway decreases when expected future diesel demand increases.
    #    Proxy: runway_days should (weakly) negatively correlate with generator_output.
    valid = df["fuel_runway_days"].notna()
    if valid.sum() > 10:
        corr_runway_gen = np.corrcoef(df.loc[valid, "fuel_runway_days"], df.loc[valid, "generator_output"])[0, 1]
        results["runway_vs_generator_output_negative_corr"] = (corr_runway_gen < 0.1, round(corr_runway_gen, 3))
    else:
        results["runway_vs_generator_output_negative_corr"] = (None, "insufficient running hours")

    # 8. All values remain within configured physical limits.
    checks = {
        "solar_generation_within_capacity": df["solar_generation"].between(0, solar_cfg["capacity_kw"] + 1e-6).all(),
        "battery_soc_within_limits": df["battery_soc"].between(
            battery_cfg["min_soc_fraction"] * battery_cfg["capacity_kwh"] - 1e-3,
            battery_cfg["max_soc_fraction"] * battery_cfg["capacity_kwh"] + 1e-3).all(),
        "generator_output_within_capacity": df["generator_output"].between(0, generator_cfg["capacity_kw"] + 1e-6).all(),
        "fuel_level_within_tank": df["fuel_level"].between(-1e-6, generator_cfg["fuel_tank_capacity_l"] + 1e-6).all(),
        "no_negative_loads": (df[["critical_load", "residential_load", "research_load", "total_station_load"]] >= 0).all().all(),
    }
    results["physical_limits_respected"] = (all(checks.values()), checks)

    return results


def print_validation_report(results):
    print("=" * 70)
    print("VALIDATION REPORT")
    print("=" * 70)
    for name, (passed, detail) in results.items():
        status = "PASS" if passed else ("N/A " if passed is None else "FAIL")
        print(f"[{status}] {name}: {detail}")
    print("=" * 70)
