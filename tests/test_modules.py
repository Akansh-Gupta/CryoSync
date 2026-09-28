import pandas as pd
from twin.config import STATION_CONFIG
from forecasting.forecast_engine import load_dataset, run_forecast_pipeline
from optimization.optimizer import optimize_dispatch
from anomaly.anomaly_detector import train_detector, detect_anomalies
from anomaly.health_scoring import calculate_health_scores
from alerts.alert_rules import build_alerts


def test_forecast():
    df = load_dataset("data/master_dataset.csv")
    f = run_forecast_pipeline("data/master_dataset.csv", "data/test_forecast.csv", model_type="xgboost")
    assert len(f) == 24
    assert (f.load_forecast_kw >= 0).all()
    assert (f.solar_forecast_kw >= 0).all()


def test_optimizer():
    f = pd.read_csv("data/test_forecast.csv", parse_dates=["timestamp"])
    cfg = STATION_CONFIG
    p = optimize_dispatch(f, cfg["battery_system"], cfg["generator_system"], 180, 10000)
    assert len(p) == 24
    assert (p.diesel_kw >= 0).all()
    assert (p.soc_kwh >= cfg["battery_system"]["min_soc_fraction"] * cfg["battery_system"]["capacity_kwh"]).all()


def test_anomaly_health_alerts():
    df = load_dataset("data/master_dataset.csv")
    model = train_detector(df.iloc[:6000])
    a = detect_anomalies(model, df.tail(168))
    h = calculate_health_scores(df.tail(168))
    alerts = build_alerts(df.tail(168), anomaly_df=a, health_df=h)
    assert len(a) == 168 and len(h) == 168
    assert set(a["is_anomaly"].unique()).issubset({True, False})
    assert set(alerts.columns) >= {"type", "severity", "message"}
