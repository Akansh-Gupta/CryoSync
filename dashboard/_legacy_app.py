"""
CRYOSYNC — Energy Intelligence Dashboard

Streamlit dashboard for the CRYOSYNC prototype.

Features:
- Current/latest station operating state
- Active alerts
- Historical / replay power mix
- Next 24-hour AI forecast
- Zone load distribution
- Battery and fuel status
- Forecast model information
- Robust local/offline data loading

Run from the project root:

    streamlit run dashboard/app.py
"""

from pathlib import Path
import sys
import pandas as pd
import numpy as np
import streamlit as st
# Make the pipeline packages (twin/, forecasting/, ...) importable when this
# file is launched directly via ``streamlit run dashboard/app.py``: Streamlit
# puts dashboard/ on sys.path, not the project root, so add the root here
# before importing anything from it.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from twin.config import STATION_CONFIG
from twin.wind import simulate_wind


# ---------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="CRYOSYNC Energy Intelligence",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

MASTER_PATH = DATA_DIR / "master_dataset.csv"
FORECAST_PATH = DATA_DIR / "forecast.csv"
ALERTS_PATH = DATA_DIR / "alerts.csv"
ANOMALIES_PATH = DATA_DIR / "anomalies.csv"
MAINTENANCE_PATH = DATA_DIR / "maintenance.csv"
DISPATCH_PATH = DATA_DIR / "dispatch_plan.csv"


# ---------------------------------------------------------------------
# GLOBAL CSS
# ---------------------------------------------------------------------

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1500px;
        }

        h1 {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
        }

        h2 {
            font-size: 1.55rem !important;
            margin-top: 2rem !important;
        }

        h3 {
            font-size: 1.15rem !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.65rem;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.9rem;
        }

        .status-card {
            padding: 0.9rem 1rem;
            border-radius: 0.55rem;
            margin-bottom: 0.5rem;
        }

        .status-good {
            background: rgba(46, 125, 50, 0.20);
            border: 1px solid rgba(76, 175, 80, 0.25);
        }

        .status-warning {
            background: rgba(245, 166, 35, 0.18);
            border: 1px solid rgba(245, 166, 35, 0.25);
        }

        .status-danger {
            background: rgba(198, 40, 40, 0.18);
            border: 1px solid rgba(198, 40, 40, 0.25);
        }

        .small-muted {
            color: #999;
            font-size: 0.82rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

@st.cache_data
def load_csv(path: str, parse_dates=None):
    """Load a CSV safely."""
    file_path = Path(path)

    if not file_path.exists():
        return None

    try:
        data = pd.read_csv(file_path)
        if parse_dates:
            for column in parse_dates:
                if column in data.columns:
                    data[column] = pd.to_datetime(
                        data[column],
                        format="mixed",
                        dayfirst=True,
                        errors="coerce",
                    )
        return data
    except Exception as exc:
        st.error(f"Unable to read {file_path.name}: {exc}")
        return None


def format_number(value, decimals=1):
    """Format numeric values for dashboard display."""
    if value is None or pd.isna(value):
        return "—"

    return f"{float(value):,.{decimals}f}"


def latest_value(df, column, default=np.nan):
    """Return the latest value from a dataframe column."""
    if df is None or column not in df.columns or df.empty:
        return default

    value = df[column].iloc[-1]

    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def find_column(df, candidates):
    """Return the first existing column from candidates."""
    if df is None:
        return None

    for column in candidates:
        if column in df.columns:
            return column

    return None


def make_chart(
    df,
    x,
    y_columns,
    title=None,
    height=430,
    y_min=None,
    y_max=None,
    y_axis_title="kW",
    description=None,
):
    """
    Create a Streamlit line chart.

    Uses Plotly when available and falls back to st.line_chart.
    """

    available = [
        c for c in y_columns
        if c in df.columns
    ]

    if not available:
        st.info("No data available for this chart.")
        return

    chart_df = df[
        [x] + available
    ].copy()

    try:
        import plotly.graph_objects as go

        fig = go.Figure()

        for column in available:
            fig.add_trace(
                go.Scatter(
                    x=chart_df[x],
                    y=chart_df[column],
                    mode="lines",
                    name=column,
                )
            )

        layout_kwargs = dict(
            height=height,
            margin=dict(
                l=20,
                r=20,
                t=50 if title else 20,
                b=20,
            ),
            hovermode="x unified",
            legend=dict(
                orientation="h"
            ),
            xaxis_title=x,
            yaxis_title=y_axis_title,
        )

        if title:
            layout_kwargs["title"] = title

        # Apply explicit Y-axis range when requested.
        if y_min is not None or y_max is not None:

            numeric_values = (
                chart_df[available]
                .apply(
                    pd.to_numeric,
                    errors="coerce",
                )
            )

            data_max = numeric_values.max().max()

            upper = y_max

            if (
                upper is None
                and pd.notna(data_max)
            ):
                upper = max(
                    float(data_max) * 1.10,
                    1.0,
                )

            lower = (
                y_min
                if y_min is not None
                else 0
            )

            layout_kwargs["yaxis"] = {
                "range": [
                    lower,
                    upper,
                ]
            }

        fig.update_layout(
            **layout_kwargs
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": False
            },
        )
        if description:
            st.caption(description)

    except ImportError:

        st.line_chart(
            chart_df.set_index(x)[available],
            height=height,
        )
        if description:
            st.caption(description)


def show_status(
    message,
    status="good",
):
    """Display a compact status card."""

    css_class = {
        "good": "status-good",
        "warning": "status-warning",
        "danger": "status-danger",
    }.get(
        status,
        "status-good",
    )

    st.markdown(
        f'<div class="status-card {css_class}">'
        f'{message}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------

master_df = load_csv(
    str(MASTER_PATH),
    parse_dates=["timestamp"],
)

forecast_df = load_csv(
    str(FORECAST_PATH),
    parse_dates=["timestamp"],
)

alerts_df = load_csv(
    str(ALERTS_PATH),
    parse_dates=(
        ["timestamp"]
        if ALERTS_PATH.exists()
        else None
    ),
)

anomalies_df = load_csv(
    str(ANOMALIES_PATH),
    parse_dates=(
        ["timestamp"]
        if ANOMALIES_PATH.exists()
        else None
    ),
)

maintenance_df = load_csv(
    str(MAINTENANCE_PATH),
    parse_dates=(
        ["timestamp"]
        if MAINTENANCE_PATH.exists()
        else None
    ),
)

dispatch_df = load_csv(
    str(DISPATCH_PATH),
    parse_dates=(
        ["timestamp"]
        if DISPATCH_PATH.exists()
        else None
    ),
)


# ---------------------------------------------------------------------
# DATA VALIDATION
# ---------------------------------------------------------------------

if master_df is None:

    st.error(
        "Master dataset not found.\n\n"
        "Run the digital twin first:\n\n"
        "`python run_twin.py`"
    )

    st.stop()


if "timestamp" not in master_df.columns:

    st.error(
        "master_dataset.csv does not contain "
        "a timestamp column."
    )

    st.stop()


master_df["timestamp"] = pd.to_datetime(
    master_df["timestamp"],
    format="mixed",
    dayfirst=True,
    errors="coerce",
)

master_df = (
    master_df
    .dropna(
        subset=["timestamp"]
    )
    .sort_values("timestamp")
    .reset_index(drop=True)
)


if (
    forecast_df is not None
    and "timestamp" in forecast_df.columns
):

    forecast_df["timestamp"] = pd.to_datetime(
        forecast_df["timestamp"],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )

    forecast_df = (
        forecast_df
        .dropna(
            subset=["timestamp"]
        )
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------

st.title(
    "CRYOSYNC Energy Intelligence"
)

st.markdown(
    '<div class="small-muted">'
    "Offline-first AI energy management "
    "for polar research stations"
    "</div>",
    unsafe_allow_html=True,
)

st.write("")


# ---------------------------------------------------------------------
# LATEST OPERATING STATE
# ---------------------------------------------------------------------

latest = master_df.iloc[-1]

latest_timestamp = latest["timestamp"]

load = latest.get(
    "total_station_load",
    np.nan,
)

solar = latest.get(
    "solar_generation",
    np.nan,
)

wind = latest.get(
    "wind_generation",
    np.nan,
)

if pd.isna(wind) and "wind_speed" in latest.index:
    wind_speed_value = pd.to_numeric(
        latest["wind_speed"],
        errors="coerce",
    )
    if pd.isna(wind_speed_value):
        wind_speed_value = 0.0
    wind = simulate_wind(
        np.array([wind_speed_value]),
        STATION_CONFIG["wind_system"],
    )[0]

battery_pct = latest.get(
    "battery_soc_pct",
    np.nan,
)

fuel = latest.get(
    "fuel_level",
    np.nan,
)

generator_output = latest.get(
    "generator_output",
    0.0,
)

generator_status = latest.get(
    "generator_status",
    "off",
)


m1, m2, m3, m4, m5 = st.columns(5)


with m1:

    st.metric(
        "Station Load",
        f"{format_number(load)} kW",
    )


with m2:

    st.metric(
        "Solar",
        f"{format_number(solar)} kW",
    )


with m3:

    st.metric(
        "Wind",
        f"{format_number(wind)} kW",
    )


with m4:

    st.metric(
        "Battery",
        f"{format_number(battery_pct)}%",
    )


with m5:

    st.metric(
        "Fuel",
        f"{format_number(fuel, 0)} L",
    )


st.caption(
    "Latest simulation state: "
    f"{latest_timestamp.strftime('%d %b %Y, %H:%M')}"
)


# ---------------------------------------------------------------------
# ALERTS
# ---------------------------------------------------------------------

st.header("Alert Window")

with st.container(border=True):

    st.caption("All triggered alerts are displayed here in one window.")

    active_alerts = pd.DataFrame()

    if (
        alerts_df is not None
        and not alerts_df.empty
    ):

        active_alerts = alerts_df.copy()

        # Try to determine whether an alert is active.
        if "active" in active_alerts.columns:

            active_alerts = active_alerts[
                active_alerts["active"]
                .astype(str)
                .str.lower()
                .isin(
                    [
                        "true",
                        "1",
                        "yes",
                        "active",
                    ]
                )
            ]

        elif "status" in active_alerts.columns:

            active_alerts = active_alerts[
                active_alerts["status"]
                .astype(str)
                .str.lower()
                .isin(
                    [
                        "active",
                        "open",
                        "triggered",
                    ]
                )
            ]

    if active_alerts.empty:

        show_status(
            "No active alerts",
            "good",
        )

    else:

        if "read_alert_ids" not in st.session_state:
            st.session_state.read_alert_ids = set()

        def render_alert(alert, alert_id, read_only=False):
            alert_type = str(alert.get("type", "")).upper()
            alert_label = {
                "STORM_RISK": "STORM ALERT",
                "LOW_BATTERY": "LOW BATTERY ALERT",
                "BATTERY_LEVEL_WARNING": "BATTERY LEVEL WARNING",
            }.get(alert_type, alert_type.replace("_", " ") or "SYSTEM ALERT")

            alert_message = (
                alert.get("message")
                or alert.get("alert")
                or alert.get("rule")
                or "Active system alert"
            )
            severity = str(alert.get("severity", "warning")).lower()
            if severity in {"critical", "high", "danger"}:
                status = "danger"
            elif severity in {"medium", "warning"}:
                status = "warning"
            else:
                status = "good"

            checked = st.checkbox(
                "Read alert",
                value=True if read_only else alert_id in st.session_state.read_alert_ids,
                key=f"read_alert_{alert_id}",
                disabled=read_only,
            )
            if checked and not read_only:
                st.session_state.read_alert_ids.add(alert_id)
            show_status(
                f"{alert_label}: {alert_message}",
                status,
            )

        unread_alerts = []
        read_alerts = []
        for alert_index, (_, alert) in enumerate(active_alerts.iterrows()):
            alert_id = (
                f"{alert.get('timestamp', alert_index)}|"
                f"{alert.get('type', '')}|{alert.get('message', '')}"
            )
            if alert_id in st.session_state.read_alert_ids:
                read_alerts.append((alert_id, alert))
            else:
                unread_alerts.append((alert_id, alert))

        if unread_alerts:
            st.subheader("Unread alerts")
            for alert_id, alert in unread_alerts:
                render_alert(alert, alert_id)
        else:
            show_status("No unread alerts", "good")

        if read_alerts:
            with st.expander(f"Read alerts ({len(read_alerts)})", expanded=False):
                for alert_id, alert in read_alerts:
                    render_alert(alert, alert_id, read_only=True)

# ---------------------------------------------------------------------
# HISTORICAL / REPLAY POWER MIX
# ---------------------------------------------------------------------

st.header(
    "Live / Replay Power Mix"
)

replay_options = {
    "Last 24 hours": 24,
    "Last 7 days": 168,
    "Last 30 days": 720,
    "Full year": len(master_df),
}
available_replay_options = {
    label: hours
    for label, hours in replay_options.items()
    if hours <= len(master_df)
}
replay_label = st.selectbox(
    "Replay window",
    list(available_replay_options),
    index=min(1, len(available_replay_options) - 1),
)
history_hours = available_replay_options[replay_label]

history = master_df.tail(
    history_hours
).copy()


def render_power_mix(data):
    """Render a static or row-by-row replay of the power mix."""

    if "power_mix_cursor" not in st.session_state:
        st.session_state.power_mix_cursor = len(data)

    if st.session_state.get("power_mix_window") != replay_label:
        st.session_state.power_mix_cursor = len(data)
        st.session_state.power_mix_window = replay_label

    live_replay = st.checkbox(
        "Live replay",
        help="Streams the selected historical window one row at a time.",
    )
    control_columns = st.columns(2)

    with control_columns[0]:
        if st.button("Start / Restart", use_container_width=True):
            st.session_state.power_mix_cursor = 0
            st.session_state.power_mix_live = True
            st.rerun()

    with control_columns[1]:
        if st.button("Pause", use_container_width=True):
            st.session_state.power_mix_live = False

    is_live = live_replay or st.session_state.get("power_mix_live", False)

    if is_live and len(data) > 0:
        cursor = min(st.session_state.power_mix_cursor + 1, len(data))
        st.session_state.power_mix_cursor = cursor
        display_data = data.iloc[:cursor].copy()
        st.caption(f"Live replay: {cursor} of {len(data)} rows received")
    else:
        display_data = data.copy()

    # Battery discharge is signed in the dataset; show its magnitude here.
    power_mix_display = display_data.copy()
    for column in [
        "total_station_load",
        "solar_generation",
        "wind_generation",
        "generator_output",
    ]:
        if column in power_mix_display.columns:
            power_mix_display[column] = pd.to_numeric(
                power_mix_display[column], errors="coerce"
            ).clip(lower=0)

    if "battery_power" in power_mix_display.columns:
        power_mix_display["battery_power"] = pd.to_numeric(
            power_mix_display["battery_power"], errors="coerce"
        ).abs()

    make_chart(
        power_mix_display,
        "timestamp",
        [
            "total_station_load",
            "solar_generation",
            "wind_generation",
            "generator_output",
            "battery_power",
        ],
        height=470,
        y_min=0,
        description="Shows station demand and each supply source over time. Live replay streams historical rows one at a time; generator output is backup diesel power.",
    )

    if "generator_output" in data.columns and not (data["generator_output"] > 0).any():
        st.info("The generator was not required during this replay window. Select Full year to see periods when diesel backup was dispatched.")


if hasattr(st, "fragment"):
    @st.fragment(run_every="1s")
    def live_power_mix():
        render_power_mix(history)

    live_power_mix()
else:
    render_power_mix(history)


# ---------------------------------------------------------------------
# NEXT 24-HOUR FORECAST
# ---------------------------------------------------------------------

st.header(
    "Next 24h Forecast"
)

if (
    forecast_df is None
    or forecast_df.empty
):

    st.warning(
        "Forecast data is not available. "
        "Run the forecasting engine first."
    )

else:

    forecast_columns = [
        "load_forecast_kw",
        "solar_forecast_kw",
        "wind_forecast_kw",
    ]

    available_forecast_columns = [
        c
        for c in forecast_columns
        if c in forecast_df.columns
    ]

    if available_forecast_columns:

        next24 = forecast_df.head(
            24
        ).copy()

        # Keep forecast values non-negative.
        for column in available_forecast_columns:

            next24[column] = (
                pd.to_numeric(
                    next24[column],
                    errors="coerce",
                )
                .clip(lower=0)
            )

        make_chart(
            next24,
            "timestamp",
            available_forecast_columns,
            height=470,
            y_min=0,
            description="Shows the next 24 hours of predicted station load and renewable generation in kW.",
        )

        if "wind_speed_forecast_ms" in next24.columns:
            st.subheader("Antarctic Wind Speed Forecast")
            make_chart(
                next24,
                "timestamp",
                ["wind_speed_forecast_ms"],
                height=320,
                y_min=0,
                y_axis_title="m/s",
                description="Shows predicted Antarctic wind speed in metres per second. Wind turbine power can remain flat when speed is above the turbine rated-speed threshold.",
            )

    else:

        st.warning(
            "Forecast CSV does not contain "
            "the expected forecast columns."
        )


# ---------------------------------------------------------------------
# FORECAST SUMMARY
# ---------------------------------------------------------------------

if (
    forecast_df is not None
    and not forecast_df.empty
):

    st.subheader(
        "Forecast Summary"
    )

    forecast_load_col = find_column(
        forecast_df,
        [
            "load_forecast_kw"
        ],
    )

    forecast_solar_col = find_column(
        forecast_df,
        [
            "solar_forecast_kw"
        ],
    )

    forecast_wind_col = find_column(
        forecast_df,
        [
            "wind_forecast_kw"
        ],
    )

    summary_columns = st.columns(3)


    if forecast_load_col:

        with summary_columns[0]:

            peak_load = forecast_df[
                forecast_load_col
            ].max()

            avg_load = forecast_df[
                forecast_load_col
            ].mean()

            st.metric(
                "Peak Forecast Load",
                f"{format_number(peak_load)} kW",
            )

            st.caption(
                "24h average: "
                f"{format_number(avg_load)} kW"
            )


    if forecast_solar_col:

        with summary_columns[1]:

            peak_solar = forecast_df[
                forecast_solar_col
            ].max()

            total_solar = forecast_df[
                forecast_solar_col
            ].sum()

            st.metric(
                "Peak Forecast Solar",
                f"{format_number(peak_solar)} kW",
            )

            st.caption(
                "24h simulated energy: "
                f"{format_number(total_solar)} kWh"
            )


    if forecast_wind_col:

        with summary_columns[2]:

            peak_wind = forecast_df[
                forecast_wind_col
            ].max()

            avg_wind = forecast_df[
                forecast_wind_col
            ].mean()

            st.metric(
                "Peak Forecast Wind",
                f"{format_number(peak_wind)} kW",
            )

            st.caption(
                "24h average: "
                f"{format_number(avg_wind)} kW"
            )


# ---------------------------------------------------------------------
# ZONE LOADS
# ---------------------------------------------------------------------

st.header(
    "Zone Loads"
)

zone_columns = [
    "critical_load",
    "residential_load",
    "research_load",
]

available_zone_columns = [
    c
    for c in zone_columns
    if c in latest.index
]


if available_zone_columns:

    zone_data = pd.DataFrame(
        {
            "Zone": [
                c
                .replace(
                    "_load",
                    "",
                )
                .replace(
                    "_",
                    " ",
                )
                .title()
                for c in available_zone_columns
            ],
            "Load (kW)": [
                max(
                    float(latest[c]),
                    0,
                )
                for c in available_zone_columns
            ],
        }
    )

    try:

        import plotly.express as px

        fig = px.bar(
            zone_data,
            x="Zone",
            y="Load (kW)",
        )

        fig.update_layout(
            height=400,
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20,
            ),
            showlegend=False,
            yaxis=dict(
                rangemode="tozero"
            ),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": False
            },
        )
        st.caption("Shows the latest electrical demand for critical, residential, and research zones so operators can compare where station power is being used.")

    except ImportError:

        st.bar_chart(
            zone_data.set_index(
                "Zone"
            ),
            height=400,
        )


# ---------------------------------------------------------------------
# ENERGY STORAGE
# ---------------------------------------------------------------------

st.header(
    "Energy Storage"
)

storage_col1, storage_col2 = st.columns(2)


with storage_col1:

    st.subheader(
        "Battery"
    )

    if "battery_soc_pct" in master_df.columns:

        battery_series = master_df[
            [
                "timestamp",
                "battery_soc_pct",
            ]
        ].tail(
            history_hours
        ).copy()

        battery_series[
            "battery_soc_pct"
        ] = (
            pd.to_numeric(
                battery_series[
                    "battery_soc_pct"
                ],
                errors="coerce",
            )
            .clip(
                lower=0
            )
        )

        make_chart(
            battery_series,
            "timestamp",
            [
                "battery_soc_pct"
            ],
            height=330,
            y_min=0,
            description="Shows battery state of charge over the selected replay window; lower values indicate less stored energy available for backup.",
        )

    else:

        st.info(
            "Battery SOC data unavailable."
        )


with storage_col2:

    st.subheader(
        "Fuel"
    )

    if "fuel_level" in master_df.columns:

        fuel_series = master_df[
            [
                "timestamp",
                "fuel_level",
            ]
        ].tail(
            history_hours
        ).copy()

        fuel_series[
            "fuel_level"
        ] = (
            pd.to_numeric(
                fuel_series[
                    "fuel_level"
                ],
                errors="coerce",
            )
            .clip(
                lower=0
            )
        )

        make_chart(
            fuel_series,
            "timestamp",
            [
                "fuel_level"
            ],
            height=330,
            y_min=0,
            description="Shows remaining diesel fuel over the selected replay window; a falling line indicates generator fuel consumption.",
        )

    else:

        st.info(
            "Fuel data unavailable."
        )


# ---------------------------------------------------------------------
# GENERATOR / FUEL STATUS
# ---------------------------------------------------------------------

st.header(
    "Generator & Fuel Status"
)

g1, g2, g3, g4 = st.columns(4)


with g1:

    st.metric(
        "Generator Output",
        f"{format_number(generator_output)} kW",
    )


with g2:

    st.metric(
        "Generator Status",
        str(
            generator_status
        ).upper(),
    )


with g3:

    runway = latest.get(
        "fuel_runway_days",
        np.nan,
    )

    if pd.isna(runway):

        runway_text = "—"

    else:

        runway_text = (
            f"{format_number(runway)} days"
        )

    st.metric(
        "Fuel Runway",
        runway_text,
    )


with g4:

    fuel_use = latest.get(
        "fuel_consumption",
        np.nan,
    )

    st.metric(
        "Fuel Use / Hour",
        f"{format_number(fuel_use)} L/h",
    )


# ---------------------------------------------------------------------
# DISPATCH PLAN
# ---------------------------------------------------------------------

st.header(
    "Energy Dispatch"
)

if (
    dispatch_df is not None
    and not dispatch_df.empty
):

    dispatch_display = (
        dispatch_df.copy()
    )

    if "timestamp" in dispatch_display.columns:

        dispatch_display[
            "timestamp"
        ] = pd.to_datetime(
            dispatch_display[
                "timestamp"
            ],
            errors="coerce",
        )

    st.dataframe(
        dispatch_display.tail(24),
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No dispatch plan file available yet."
    )


# ---------------------------------------------------------------------
# ANOMALIES
# ---------------------------------------------------------------------

st.header(
    "Anomaly Detection"
)

if (
    anomalies_df is None
    or anomalies_df.empty
):

    st.success(
        "No anomaly dataset available."
    )

else:

    anomaly_display = (
        anomalies_df.copy()
    )

    if "timestamp" in anomaly_display.columns:
        anomaly_display["timestamp"] = pd.to_datetime(
            anomaly_display["timestamp"],
            format="mixed",
            dayfirst=True,
            errors="coerce",
        )

    anomaly_dates = anomaly_display["timestamp"].dropna().dt.date
    if not anomaly_dates.empty:
        selected_anomaly_date = st.date_input(
            "Select anomaly date",
            value=anomaly_dates.max(),
            min_value=anomaly_dates.min(),
            max_value=anomaly_dates.max(),
        )
        anomaly_display = anomaly_display[
            anomaly_display["timestamp"].dt.date == selected_anomaly_date
        ].copy()
        st.caption(
            f"Showing anomaly records for {selected_anomaly_date.strftime('%d %b %Y')} only."
        )

    anomaly_col = find_column(
        anomaly_display,
        [
            "is_anomaly",
            "anomaly",
            "anomaly_label",
        ],
    )

    if anomaly_col:

        anomaly_values = (
            anomaly_display[
                anomaly_col
            ]
        )

        if anomaly_values.dtype == bool:

            anomaly_count = int(
                anomaly_values.sum()
            )

        else:

            anomaly_count = int(
                anomaly_values
                .astype(str)
                .str.lower()
                .isin(
                    [
                        "true",
                        "1",
                        "yes",
                        "anomaly",
                    ]
                )
                .sum()
            )

        if anomaly_count > 0:

            st.warning(
                f"{anomaly_count} anomaly "
                "record(s) detected."
            )

            detected = anomaly_display[
                anomaly_display[anomaly_col]
                .astype(str)
                .str.lower()
                .isin(["true", "1", "yes", "anomaly"])
            ].copy()
            if "detected_category" in detected.columns:
                detected["detected_category"] = detected[
                    "detected_category"
                ].fillna("Unclassified").astype(str)
                category_counts = detected["detected_category"].value_counts()
                st.subheader("Detected anomaly categories")
                st.dataframe(
                    category_counts.rename("Count")
                    .rename_axis("Category")
                    .reset_index(),
                    use_container_width=True,
                    hide_index=True,
                )
                st.dataframe(
                    detected[
                        [
                            column
                            for column in [
                                "timestamp",
                                "detected_category",
                                "anomaly_score",
                                "severity",
                            ]
                            if column in detected.columns
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        else:

            st.success(
                "No anomalies detected."
            )

    else:

        st.info(
            "Anomaly records exist, but no "
            "anomaly flag column was found."
        )


# ---------------------------------------------------------------------
# MAINTENANCE
# ---------------------------------------------------------------------

st.header(
    "Predictive Maintenance"
)

if (
    maintenance_df is None
    or maintenance_df.empty
):

    st.info(
        "No maintenance prediction "
        "data available yet."
    )

else:

    st.dataframe(
        maintenance_df.tail(20),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------
# FORECAST MODEL INFORMATION
# ---------------------------------------------------------------------

if (
    forecast_df is not None
    and not forecast_df.empty
):

    st.header(
        "AI Forecast Models"
    )

    model_columns = [
        c
        for c in [
            "load_model",
            "solar_model",
            "wind_model",
        ]
        if c in forecast_df.columns
    ]

    if model_columns:

        model_data = []

        for column in model_columns:

            values = (
                forecast_df[column]
                .dropna()
                .astype(str)
                .unique()
            )

            model_name = (
                values[0]
                if len(values)
                else "Unknown"
            )

            target_name = (
                column
                .replace(
                    "_model",
                    "",
                )
                .replace(
                    "_",
                    " ",
                )
                .title()
            )

            model_data.append(
                {
                    "Forecast": target_name,
                    "Model": model_name,
                }
            )

        st.dataframe(
            pd.DataFrame(
                model_data
            ),
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------
# SYSTEM INFORMATION
# ---------------------------------------------------------------------

with st.expander(
    "System Information"
):

    st.write(
        {
            "Project": "CRYOSYNC",
            "Architecture": (
                "Offline-first / edge-based"
            ),
            "Master dataset": str(
                MASTER_PATH
            ),
            "Forecast dataset": str(
                FORECAST_PATH
            ),
            "Simulation rows": len(
                master_df
            ),
            "Simulation start": str(
                master_df[
                    "timestamp"
                ].min()
            ),
            "Simulation end": str(
                master_df[
                    "timestamp"
                ].max()
            ),
            "Forecast rows": (
                len(forecast_df)
                if forecast_df is not None
                else 0
            ),
        }
    )


# ---------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------

st.divider()

st.caption(
    "CRYOSYNC • AI Energy Intelligence for "
    "Polar Research Stations • Local Prototype"
)