"""Small shared helpers used by more than one page.

Anything here is genuinely cross-page: loading the station data, pulling a
signed value safely out of a row, and the two chart constructors whose styling
must be identical wherever they appear. Page-specific logic stays in the page.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import streamlit as st

from core.dataset import StationData, load_station_data

# Chart styling kept here so every chart in the product matches.
CHART_COLOURS: dict[str, str] = {
    "total_station_load": "#2F6FB8",
    "renewable_generation": "#2E7D4F",
    "solar_generation": "#E8A33D",
    "wind_generation": "#5AA9C9",
    "wind_speed": "#5AA9C9",
    "generator_output": "#C62828",
    "battery_power": "#7A5BA6",
    "battery_soc_pct": "#2E7D4F",
    "fuel_level": "#B7791F",
    "net_load_kw": "#4A5568",
    "load_forecast_kw": "#2F6FB8",
    "solar_forecast_kw": "#E8A33D",
    "wind_forecast_kw": "#5AA9C9",
    "soc_kwh": "#2E7D4F",
    "diesel_kw": "#C62828",
}

PRETTY_LABELS: dict[str, str] = {
    "total_station_load": "Station load",
    "renewable_generation": "Renewables",
    "solar_generation": "Solar",
    "wind_generation": "Wind",
    "wind_speed": "Wind speed",
    "generator_output": "Diesel generator",
    "battery_power": "Battery flow",
    "battery_soc_pct": "Battery SoC",
    "fuel_level": "Fuel level",
    "net_load_kw": "Net load",
    "load_forecast_kw": "Load forecast",
    "solar_forecast_kw": "Solar forecast",
    "wind_forecast_kw": "Wind forecast",
    "soc_kwh": "Battery stored",
    "diesel_kw": "Diesel dispatch",
}


def data() -> StationData:
    """The cached station data for this run."""

    return load_station_data()


def label_for(column: str) -> str:
    """Readable legend label for a dataframe column."""

    return PRETTY_LABELS.get(column, column.replace("_", " ").title())


def numeric(row: pd.Series | None, key: str, default: float = 0.0) -> float:
    """Read a numeric value from a row without ever raising."""

    if row is None or key not in row.index:
        return default

    try:
        value = float(row[key])
    except (TypeError, ValueError):
        return default

    return default if np.isnan(value) else value


def line_chart(
    frame: pd.DataFrame,
    columns: Sequence[str],
    *,
    x: str = "timestamp",
    height: int = 340,
    y_title: str = "kW",
    zero_floor: bool = True,
    caption: str = "",
) -> None:
    """Draw a multi-series line chart with the standard CRYOSYNC styling."""

    if frame is None or frame.empty:
        st.caption("No data available for this chart.")
        return

    available = [column for column in columns if column in frame.columns]

    if not available:
        st.caption("No data available for this chart.")
        return

    plot = frame[[x] + available].copy()

    try:
        import plotly.graph_objects as go

        figure = go.Figure()

        for column in available:
            figure.add_trace(
                go.Scatter(
                    x=plot[x],
                    y=pd.to_numeric(plot[column], errors="coerce"),
                    mode="lines",
                    name=label_for(column),
                    line=dict(color=CHART_COLOURS.get(column), width=2),
                )
            )

        figure.update_layout(
            height=height,
            margin=dict(l=10, r=10, t=18, b=10),
            hovermode="x unified",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color="#4A5568"),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
            xaxis=dict(title=None, showgrid=False, linecolor="#E3E8EF"),
            yaxis=dict(
                title=y_title,
                gridcolor="#EEF1F5",
                zerolinecolor="#E3E8EF",
                rangemode="tozero" if zero_floor else "normal",
            ),
        )

        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displayModeBar": False},
        )

    except ImportError:
        st.line_chart(plot.set_index(x)[available], height=height)

    if caption:
        st.caption(caption)


def bar_chart(
    frame: pd.DataFrame,
    *,
    x: str,
    y: str,
    height: int = 320,
    x_title: str = "",
    y_title: str = "kW",
    caption: str = "",
) -> None:
    """Draw a single-series bar chart in the house style."""

    if frame is None or frame.empty or x not in frame.columns or y not in frame.columns:
        st.caption("No data available for this chart.")
        return

    try:
        import plotly.graph_objects as go

        figure = go.Figure(
            go.Bar(
                x=frame[x],
                y=pd.to_numeric(frame[y], errors="coerce"),
                marker_color="#2F6FB8",
                marker_line_width=0,
            )
        )

        figure.update_layout(
            height=height,
            margin=dict(l=10, r=10, t=18, b=10),
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color="#4A5568"),
            xaxis=dict(title=x_title or None, showgrid=False, linecolor="#E3E8EF"),
            yaxis=dict(title=y_title, gridcolor="#EEF1F5", rangemode="tozero"),
        )

        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displayModeBar": False},
        )

    except ImportError:
        st.bar_chart(frame.set_index(x)[y], height=height)

    if caption:
        st.caption(caption)


def forecast_band_chart(
    frame: pd.DataFrame,
    value_column: str,
    lower_column: str,
    upper_column: str,
    *,
    colour: str = "#2F6FB8",
    height: int = 300,
    y_title: str = "kW",
) -> None:
    """Forecast line with its confidence band, as shown on the forecast page."""

    if frame is None or frame.empty or value_column not in frame.columns:
        st.caption("No forecast data available.")
        return

    try:
        import plotly.graph_objects as go

        figure = go.Figure()

        if lower_column in frame.columns and upper_column in frame.columns:
            figure.add_trace(
                go.Scatter(
                    x=frame["timestamp"],
                    y=pd.to_numeric(frame[upper_column], errors="coerce"),
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=frame["timestamp"],
                    y=pd.to_numeric(frame[lower_column], errors="coerce"),
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor="rgba(47, 111, 184, 0.14)",
                    name="Confidence band",
                    hoverinfo="skip",
                )
            )

        figure.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=pd.to_numeric(frame[value_column], errors="coerce"),
                mode="lines",
                name=label_for(value_column),
                line=dict(color=colour, width=2),
            )
        )

        figure.update_layout(
            height=height,
            margin=dict(l=10, r=10, t=18, b=10),
            hovermode="x unified",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color="#4A5568"),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
            xaxis=dict(title=None, showgrid=False, linecolor="#E3E8EF"),
            yaxis=dict(title=y_title, gridcolor="#EEF1F5", rangemode="tozero"),
        )

        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displayModeBar": False},
        )

    except ImportError:
        line_chart(frame, [value_column], height=height, y_title=y_title)
