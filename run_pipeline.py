"""Run the remaining CRYOSYNC modules sequentially for a local demo."""
from pathlib import Path
import pandas as pd
from twin.config import STATION_CONFIG
from forecasting.forecast_engine import run_forecast_pipeline
from optimization.optimizer import optimize_dispatch
from anomaly.anomaly_detector import train_detector, detect_anomalies, inject_faults, evaluate_fault_detection
from anomaly.health_scoring import calculate_health_scores
from alerts.alert_rules import build_alerts

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def main():
    master = pd.read_csv(DATA / "master_dataset.csv", parse_dates=["timestamp"])
    forecast = run_forecast_pipeline(DATA / "master_dataset.csv", DATA / "forecast.csv")
    latest = master.iloc[-1]
    plan = optimize_dispatch(forecast, STATION_CONFIG["battery_system"], STATION_CONFIG["generator_system"],
                             latest.battery_soc, latest.fuel_level)
    plan.to_csv(DATA / "dispatch_plan.csv", index=False)

    normal = master.iloc[:-168]
    detector = train_detector(normal)
    anomalies = detect_anomalies(detector, master.tail(168))
    anomalies.to_csv(DATA / "anomalies.csv", index=False)
    health = calculate_health_scores(master.tail(168))
    health.to_csv(DATA / "maintenance.csv", index=False)
    alerts = build_alerts(master.tail(168), forecast, anomalies, health)
    alerts.to_csv(DATA / "alerts.csv", index=False)

    faulty, labels = inject_faults(normal.tail(min(len(normal), 2000)))
    eval_pred = detect_anomalies(detector, faulty)["is_anomaly"]
    metrics = evaluate_fault_detection(eval_pred, labels)
    print("CRYOSYNC pipeline complete")
    print(f"Forecast rows: {len(forecast)} | Dispatch rows: {len(plan)}")
    print(f"Anomalies: {int(anomalies.is_anomaly.sum())} | Alerts: {len(alerts)}")
    print(f"Fault-injection evaluation: {metrics}")

if __name__ == "__main__":
    main()
