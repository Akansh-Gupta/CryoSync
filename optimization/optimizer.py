"""M4 — Fuel-minimizing diesel/solar/battery dispatch optimizer."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix


def optimize_dispatch(
    forecast_df: pd.DataFrame,
    battery_cfg: dict,
    generator_cfg: dict,
    initial_soc_kwh: float,
    initial_fuel_l: float,
) -> pd.DataFrame:

    required = {
        "timestamp",
        "load_forecast_kw",
        "solar_forecast_kw",
    }

    missing = required - set(forecast_df.columns)

    if missing:
        raise ValueError(
            f"Missing forecast columns: {sorted(missing)}"
        )

    d = forecast_df.copy().reset_index(drop=True)

    n = len(d)

    if n == 0:
        return d

    # ------------------------------------------------------------------
    # Battery configuration
    # ------------------------------------------------------------------

    capacity_kwh = float(battery_cfg["capacity_kwh"])

    min_soc = float(
        battery_cfg["min_soc_fraction"] * capacity_kwh
    )

    max_soc = float(
        battery_cfg["max_soc_fraction"] * capacity_kwh
    )

    max_charge_kw = float(
        battery_cfg["max_charge_kw"]
    )

    max_discharge_kw = float(
        battery_cfg["max_discharge_kw"]
    )

    round_trip_efficiency = float(
        battery_cfg["round_trip_efficiency"]
    )

    charge_efficiency = np.sqrt(
        round_trip_efficiency
    )

    discharge_efficiency = np.sqrt(
        round_trip_efficiency
    )

    # ------------------------------------------------------------------
    # Generator configuration
    # ------------------------------------------------------------------

    generator_capacity_kw = float(
        generator_cfg["capacity_kw"]
    )

    minimum_generator_kw = float(
        generator_cfg["min_load_fraction"]
        * generator_capacity_kw
    )

    fuel_fixed_l_per_hr = float(
        generator_cfg["fuel_curve_a_l_per_hr"]
    )

    fuel_variable_l_per_kwh = float(
        generator_cfg["fuel_curve_b_l_per_kwh"]
    )

    # ------------------------------------------------------------------
    # Decision variables
    #
    # 0 = solar -> load
    # 1 = solar -> battery
    # 2 = battery -> load
    # 3 = diesel generation
    # 4 = battery SoC
    # 5 = generator ON/OFF
    # ------------------------------------------------------------------

    VARIABLES_PER_HOUR = 6
    variable_count = VARIABLES_PER_HOUR * n

    def ix(variable: int, hour: int) -> int:
        return VARIABLES_PER_HOUR * hour + variable

    # ------------------------------------------------------------------
    # Objective function
    # ------------------------------------------------------------------

    objective = np.zeros(variable_count)

    for hour in range(n):

        # Small penalty discourages unnecessary battery cycling.
        objective[ix(1, hour)] = 0.001
        objective[ix(2, hour)] = 0.001

        # Diesel fuel cost.
        objective[ix(3, hour)] = fuel_variable_l_per_kwh

        # Fixed generator running fuel.
        objective[ix(5, hour)] = fuel_fixed_l_per_hr

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    rows = []
    lower_bounds = []
    upper_bounds = []

    def add_constraint(items, lower, upper):

        row = {}

        for column, value in items:
            row[column] = row.get(column, 0.0) + value

        rows.append(row)
        lower_bounds.append(lower)
        upper_bounds.append(upper)

    for hour in range(n):

        load_kw = max(
            0.0,
            float(d.loc[hour, "load_forecast_kw"])
        )

        solar_kw = max(
            0.0,
            float(d.loc[hour, "solar_forecast_kw"])
        )

        # --------------------------------------------------------------
        # 1. Load balance
        #
        # solar_to_load
        # + battery_to_load
        # + diesel
        # = load
        # --------------------------------------------------------------

        add_constraint(
            [
                (ix(0, hour), 1.0),
                (ix(2, hour), 1.0),
                (ix(3, hour), 1.0),
            ],
            load_kw,
            load_kw,
        )

        # --------------------------------------------------------------
        # 2. Solar availability
        #
        # solar_to_load + solar_to_battery <= solar generation
        # --------------------------------------------------------------

        add_constraint(
            [
                (ix(0, hour), 1.0),
                (ix(1, hour), 1.0),
            ],
            -np.inf,
            solar_kw,
        )

        # --------------------------------------------------------------
        # 3. Generator maximum output
        #
        # diesel <= capacity * generator_on
        # --------------------------------------------------------------

        add_constraint(
            [
                (ix(3, hour), 1.0),
                (ix(5, hour), -generator_capacity_kw),
            ],
            -np.inf,
            0.0,
        )

        # --------------------------------------------------------------
        # 4. Generator minimum loading
        #
        # diesel >= minimum_output * generator_on
        # --------------------------------------------------------------

        add_constraint(
            [
                (ix(3, hour), 1.0),
                (ix(5, hour), -minimum_generator_kw),
            ],
            0.0,
            np.inf,
        )

        # --------------------------------------------------------------
        # 5. Battery state equation
        # --------------------------------------------------------------

        if hour == 0:

            add_constraint(
                [
                    (ix(4, hour), 1.0),
                    (
                        ix(1, hour),
                        -charge_efficiency,
                    ),
                    (
                        ix(2, hour),
                        1.0 / discharge_efficiency,
                    ),
                ],
                initial_soc_kwh,
                initial_soc_kwh,
            )

        else:

            add_constraint(
                [
                    (ix(4, hour), 1.0),
                    (ix(4, hour - 1), -1.0),
                    (
                        ix(1, hour),
                        -charge_efficiency,
                    ),
                    (
                        ix(2, hour),
                        1.0 / discharge_efficiency,
                    ),
                ],
                0.0,
                0.0,
            )

    # ------------------------------------------------------------------
    # 6. Total available fuel constraint
    #
    # Fixed fuel + variable fuel for all selected hours must not exceed
    # the available fuel in the station.
    # ------------------------------------------------------------------

    add_constraint(
        [
            (
                ix(5, hour),
                fuel_fixed_l_per_hr,
            )
            for hour in range(n)
        ]
        + [
            (
                ix(3, hour),
                fuel_variable_l_per_kwh,
            )
            for hour in range(n)
        ],
        -np.inf,
        max(0.0, float(initial_fuel_l)),
    )

    # ------------------------------------------------------------------
    # Convert constraints to sparse matrix
    # ------------------------------------------------------------------

    matrix = lil_matrix(
        (len(rows), variable_count)
    )

    for row_index, row in enumerate(rows):

        for column, value in row.items():
            matrix[row_index, column] = value

    # ------------------------------------------------------------------
    # Variable bounds
    # ------------------------------------------------------------------

    variable_lower = np.zeros(variable_count)
    variable_upper = np.full(
        variable_count,
        np.inf,
    )

    for hour in range(n):

        # Solar -> load
        variable_upper[
            ix(0, hour)
        ] = np.inf

        # Solar -> battery
        variable_upper[
            ix(1, hour)
        ] = max_charge_kw

        # Battery -> load
        variable_upper[
            ix(2, hour)
        ] = max_discharge_kw

        # Diesel
        variable_upper[
            ix(3, hour)
        ] = generator_capacity_kw

        # Battery SoC
        variable_lower[
            ix(4, hour)
        ] = min_soc

        variable_upper[
            ix(4, hour)
        ] = max_soc

        # Generator ON/OFF
        variable_upper[
            ix(5, hour)
        ] = 1.0

    # Generator status is binary/integer.
    integrality = np.zeros(variable_count)

    for hour in range(n):
        integrality[ix(5, hour)] = 1

    # ------------------------------------------------------------------
    # Solve MILP
    # ------------------------------------------------------------------

    result = milp(
        objective,
        integrality=integrality,
        bounds=Bounds(
            variable_lower,
            variable_upper,
        ),
        constraints=LinearConstraint(
            matrix.tocsr(),
            np.array(lower_bounds),
            np.array(upper_bounds),
        ),
        options={
            "time_limit": 10,
        },
    )

    if not result.success:

        raise RuntimeError(
            f"Optimization failed: {result.message}"
        )

    x = result.x

    # ------------------------------------------------------------------
    # Build dispatch result
    # ------------------------------------------------------------------

    out = pd.DataFrame(
        {
            "timestamp": d["timestamp"].values,

            "load_forecast_kw":
                d["load_forecast_kw"].astype(float).values,

            "solar_forecast_kw":
                d["solar_forecast_kw"].astype(float).values,

            "solar_to_load_kw":
                [
                    x[ix(0, hour)]
                    for hour in range(n)
                ],

            "solar_to_battery_kw":
                [
                    x[ix(1, hour)]
                    for hour in range(n)
                ],

            "battery_to_load_kw":
                [
                    x[ix(2, hour)]
                    for hour in range(n)
                ],

            "diesel_kw":
                [
                    x[ix(3, hour)]
                    for hour in range(n)
                ],

            "soc_kwh":
                [
                    x[ix(4, hour)]
                    for hour in range(n)
                ],

            "diesel_status":
                [
                    "running"
                    if x[ix(5, hour)] > 0.5
                    else "off"
                    for hour in range(n)
                ],
        }
    )

    # ------------------------------------------------------------------
    # Fuel calculations
    # ------------------------------------------------------------------

    generator_running = (
        out["diesel_status"] == "running"
    ).astype(float)

    out["estimated_fuel_l"] = (
        fuel_fixed_l_per_hr * generator_running
        + fuel_variable_l_per_kwh * out["diesel_kw"]
    )

    out["fuel_remaining_l"] = np.maximum(
        0.0,
        float(initial_fuel_l)
        - out["estimated_fuel_l"].cumsum(),
    )

    # Baseline: generator-only operation.
    all_diesel_fuel = (
        fuel_fixed_l_per_hr * n
        + fuel_variable_l_per_kwh
        * out["load_forecast_kw"].sum()
    )

    total_optimized_fuel = (
        out["estimated_fuel_l"].sum()
    )

    fuel_saving = max(
        0.0,
        all_diesel_fuel - total_optimized_fuel,
    )

    out["fuel_saving_vs_all_diesel_l"] = fuel_saving

    out["optimization_status"] = "optimal"

    # Do not round timestamps.
    numeric_columns = out.select_dtypes(
        include=[np.number]
    ).columns

    out[numeric_columns] = out[
        numeric_columns
    ].round(3)

    return out