from __future__ import annotations
import numpy as np
import pandas as pd
from .solver import solve_dispatch, DEFAULT_SHADOW_CARBON_PRICE


def apply_sla_factor(tasks: pd.DataFrame, factor: float) -> pd.DataFrame:
    t = tasks.copy(deep=True)
    t["max_latency"] = np.maximum(1.0, t["max_latency"].astype(float) * factor)
    def scale(v):
        v = int(v)
        return 0 if v == 0 else max(1, int(round(v * factor)))
    t["max_defer"] = t["max_defer"].map(scale)
    return t


def reshape_green_volatility(hourly: pd.DataFrame, factor: float) -> pd.DataFrame:
    h = hourly.copy(deep=True)
    for node, idx in h.groupby("node").groups.items():
        vals = h.loc[idx, "green_available_kwh"].to_numpy(float)
        total, mean = vals.sum(), vals.mean()
        shaped = np.clip(mean + factor * (vals - mean), 0.0, None)
        if shaped.sum() <= 1e-12: shaped[:] = 1.0
        h.loc[idx, "green_available_kwh"] = shaped / shaped.sum() * total
    return h


def run_stress_scenario(nodes, hourly, tasks, carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
                        electricity_factor=1.0, green_factor=1.0, sla_factor=1.0,
                        green_volatility=1.0, demand_factor=1.0, time_limit=5.0):
    h = hourly.copy(deep=True)
    t = tasks.copy(deep=True)
    h["grid_price_cny_kwh"] *= float(electricity_factor)
    h["green_available_kwh"] *= float(green_factor)
    h = reshape_green_volatility(h, float(green_volatility))
    t = apply_sla_factor(t, float(sla_factor))
    t["demand_cu"] = t["demand_cu"].astype(float) * float(demand_factor)

    cost = solve_dispatch(nodes, h, t, carbon_weight=0.0, objective_mode="cost", time_limit=time_limit)
    multi = solve_dispatch(nodes, h, t, carbon_weight=float(carbon_price), objective_mode="balanced", time_limit=time_limit)
    a, b = cost["summary"], multi["summary"]
    def pct(new, old): return 100.0 * (new - old) / old if abs(old) > 1e-12 else np.nan
    comparison = {
        "cost_change_pct": pct(b["cash_cost"], a["cash_cost"]),
        "dispatch_reduction_pct": -pct(b["dispatch_carbon"], a["dispatch_carbon"]),
        "location_reduction_pct": -pct(b["location_carbon"], a["location_carbon"]),
        "market_reduction_pct": -pct(b["market_carbon"], a["market_carbon"]),
        "green_share_change_pp": b["green_share"] - a["green_share"],
        "sla_change_pp": b["sla_rate"] - a["sla_rate"],
    }
    return {"cost": cost, "multi": multi, "comparison": comparison, "hourly": h, "tasks": t}
