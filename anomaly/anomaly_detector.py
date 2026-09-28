"""M6 — anomaly detection using normal operating history + IsolationForest."""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = [
    "total_station_load",
    "residential_load",
    "solar_generation",
    "battery_soc_pct",
    "generator_output",
    "fuel_consumption",
]


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    missing = [c for c in FEATURES if c not in x.columns]
    if missing:
        raise ValueError(f"Missing anomaly features: {missing}")
    return x[FEATURES].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).interpolate().bfill().ffill()


def train_detector(normal_df: pd.DataFrame, contamination: float = 0.01, random_state: int = 42):
    model = IsolationForest(n_estimators=300, contamination=contamination, random_state=random_state, n_jobs=2)
    model.fit(prepare_features(normal_df))
    model._cryosync_load_max = float(normal_df["total_station_load"].max())
    model._cryosync_residential_max = float(normal_df["residential_load"].max())
    model._cryosync_fuel_p99 = float(normal_df["fuel_consumption"].quantile(0.99))
    normal_features = prepare_features(normal_df)
    model._cryosync_feature_mean = normal_features.mean()
    model._cryosync_feature_std = normal_features.std().replace(0, 1.0)
    return model


def detect_anomalies(model, df: pd.DataFrame) -> pd.DataFrame:
    out = df[["timestamp"]].copy() if "timestamp" in df else pd.DataFrame(index=df.index)
    features = prepare_features(df)
    out["anomaly_score"] = -model.score_samples(features)
    ml_flag = model.predict(features) == -1
    # Explainable physical sanity rules complement the statistical detector.
    # They are deliberately conservative so normal simulation noise is not flagged.
    load_limit = float(model._cryosync_load_max) * 1.20
    residential_limit = float(model._cryosync_residential_max) * 1.20
    fuel_limit = float(model._cryosync_fuel_p99) * 1.35
    category_flags = {
        "Residential load": features["residential_load"] > residential_limit,
        "Total station load": features["total_station_load"] > load_limit,
        "Battery level": features["battery_soc_pct"] < 10,
        "Fuel consumption": features["fuel_consumption"] > fuel_limit,
    }
    rule_flag = pd.Series(False, index=features.index)
    for flag in category_flags.values():
        rule_flag |= flag
    out["is_anomaly"] = ml_flag | rule_flag.to_numpy()
    out["ml_anomaly"] = ml_flag
    out["rule_anomaly"] = rule_flag.to_numpy()
    category_names = list(category_flags)
    category_values = []
    for index in range(len(features)):
        flagged_categories = [
            category for category, flags in category_flags.items()
            if flags.iloc[index]
        ]
        if flagged_categories:
            category_values.append(", ".join(flagged_categories))
            continue
        if ml_flag[index]:
            standardized_distance = (
                (features.iloc[index] - model._cryosync_feature_mean)
                / model._cryosync_feature_std
            ).abs()
            feature_name = standardized_distance.idxmax()
            category_values.append({
                "residential_load": "Residential load",
                "total_station_load": "Total station load",
                "battery_soc_pct": "Battery level",
                "fuel_consumption": "Fuel consumption",
                "solar_generation": "Solar generation",
            }.get(feature_name, feature_name.replace("_", " ").title()))
        else:
            category_values.append("Unclassified")
    out["detected_category"] = category_values
    out["severity"] = pd.cut(out["anomaly_score"], bins=[-np.inf, .5, .7, np.inf], labels=["low", "medium", "high"])
    return out


def inject_faults(df: pd.DataFrame, fault_hours: int = 6, seed: int = 42):
    """Create labelled synthetic faults for evaluation without changing the source dataset."""
    rng = np.random.default_rng(seed)
    faulty = df.copy()
    labels = np.zeros(len(faulty), dtype=int)
    candidates = np.arange(168, max(169, len(faulty) - fault_hours))
    starts = rng.choice(candidates, size=min(8, max(1, len(candidates)//500)), replace=False)
    for start in starts:
        end = min(len(faulty), start + fault_hours)
        labels[start:end] = 1
        idx = faulty.index[start:end]
        faulty.loc[idx, "total_station_load"] = faulty.loc[idx, "total_station_load"] * 1.80
        faulty.loc[idx, "solar_generation"] = 0.0
        faulty.loc[idx, "battery_soc_pct"] = 5.0
        faulty.loc[idx, "generator_output"] = 120.0
        faulty.loc[idx, "fuel_consumption"] = faulty.loc[idx, "fuel_consumption"] * 2.00
    return faulty, labels


def evaluate_fault_detection(predicted: pd.Series, labels) -> dict:
    from sklearn.metrics import precision_score, recall_score, f1_score
    return {
        "precision": float(precision_score(labels, predicted, zero_division=0)),
        "recall": float(recall_score(labels, predicted, zero_division=0)),
        "f1": float(f1_score(labels, predicted, zero_division=0)),
    }
