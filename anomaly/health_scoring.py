"""M6 — simple explainable generator/battery health scoring."""
import numpy as np
import pandas as pd


def _score(condition):
    return np.clip(100.0 * np.asarray(condition, dtype=float), 0, 100)


def calculate_health_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["timestamp"]].copy()
    soc = df["battery_soc_pct"].astype(float)
    battery_stress = np.clip(np.abs(soc - 60) / 40, 0, 1)
    battery_health = 100 - 25 * battery_stress

    gen = df["generator_output"].astype(float)
    load_frac = gen / max(gen.max(), 1.0)
    low_load = np.where((gen > 0) & (load_frac < 0.30), 25, 0)
    fuel = df["fuel_consumption"].astype(float)
    generator_health = 100 - 15 * np.clip(load_frac, 0, 1) - low_load

    out["battery_health_score"] = np.round(battery_health, 1)
    out["generator_health_score"] = np.round(np.clip(generator_health, 0, 100), 1)
    out["battery_recommendation"] = np.where(battery_health < 70, "Inspect battery / deep cycling", "Normal")
    out["generator_recommendation"] = np.where(generator_health < 70, "Inspect generator loading/fuel system", "Normal")
    return out
