from __future__ import annotations
import time
import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix

from .data_loader import arrays_from_hourly

GREEN_CERT_PREMIUM_CNY_KWH = 0.00596
MARKET_RESIDUAL_CI_KG_KWH = 0.6096
DEFAULT_SHADOW_CARBON_PRICE = 0.25

TASK_PRESETS = {
    "实时型": {"max_defer": 0, "max_latency": 25.0, "data_gb_per_cu": 5.0, "delay_penalty": 0.25},
    "交互型": {"max_defer": 2, "max_latency": 60.0, "data_gb_per_cu": 3.0, "delay_penalty": 0.035},
    "批处理": {"max_defer": 6, "max_latency": 120.0, "data_gb_per_cu": 1.5, "delay_penalty": 0.006},
}


def _normalize_tasks(tasks: pd.DataFrame) -> pd.DataFrame:
    t = tasks.copy(deep=True).reset_index(drop=True)
    required = ["arrival", "type", "demand_cu", "max_defer", "max_latency", "data_gb_per_cu", "delay_penalty"]
    missing = [c for c in required if c not in t.columns]
    if missing:
        raise ValueError(f"任务表缺少字段: {missing}")
    if "batch" not in t.columns:
        t["batch"] = [f"task_{i:03d}" for i in range(len(t))]
    if "default_node" not in t.columns:
        t["default_node"] = "安徽_芜湖"
    if "allow_cross_node" not in t.columns:
        t["allow_cross_node"] = True
    t["arrival"] = t["arrival"].astype(int)
    t["max_defer"] = t["max_defer"].astype(int)
    t["demand_cu"] = t["demand_cu"].astype(float)
    t["max_latency"] = t["max_latency"].astype(float)
    t["data_gb_per_cu"] = t["data_gb_per_cu"].astype(float)
    t["delay_penalty"] = t["delay_penalty"].astype(float)
    t["allow_cross_node"] = t["allow_cross_node"].astype(bool)
    return t


def solve_dispatch(
    nodes: pd.DataFrame,
    hourly: pd.DataFrame,
    tasks: pd.DataFrame,
    carbon_weight: float = DEFAULT_SHADOW_CARBON_PRICE,
    objective_mode: str = "balanced",
    time_limit: float = 5.0,
    green_premium: float = GREEN_CERT_PREMIUM_CNY_KWH,
):
    """产品统一求解接口。沿用原项目MILP结构，并增加“默认节点/是否允许跨节点”约束。"""
    arr = arrays_from_hourly(nodes, hourly)
    capacity = arr["capacity"]
    bandwidth = arr["bandwidth"]
    grid_price = arr["grid_price"]
    grid_ci = arr["grid_ci"]
    green_available = arr["green_available"]
    tasks = _normalize_tasks(tasks)

    mode_map = {"balanced": "multi", "cost": "cost", "carbon": "carbon", "multi": "multi"}
    mode = mode_map.get(objective_mode, objective_mode)
    if mode not in {"multi", "cost", "carbon"}:
        raise ValueError("objective_mode must be balanced/cost/carbon")

    I, H = capacity.shape
    node_lookup = {n: i for i, n in enumerate(nodes["node"].tolist())}
    y_idx, u_idx, g_idx = {}, {}, {}
    c, lb, ub, integrality = [], [], [], []

    def add_var(lo, hi, obj, int_type):
        j = len(c)
        c.append(obj); lb.append(lo); ub.append(hi); integrality.append(int_type)
        return j

    for b, r in tasks.iterrows():
        a = int(r.arrival)
        if a < 0 or a >= H:
            raise ValueError(f"任务 {r.batch} 到达时间 {a} 超出求解时域 0~{H-1}")
        deadline = min(H - 1, a + int(r.max_defer))
        default_i = node_lookup.get(str(r.default_node), 0)
        for i in range(I):
            if not bool(r.allow_cross_node) and i != default_i:
                continue
            if float(nodes.loc[i, "latency_ms"]) > float(r.max_latency):
                continue
            for t in range(a, deadline + 1):
                q = float(r.demand_cu)
                energy = q * float(nodes.loc[i, "energy_kwh_per_cu"])
                data_gb = q * float(r.data_gb_per_cu)
                cash = energy * grid_price[i, t] + data_gb * float(nodes.loc[i, "migration_fee_cny_gb"])
                dispatch_co2 = energy * grid_ci[i, t]
                delay = (t - a) * float(r.delay_penalty) * q
                if mode == "multi":
                    obj = cash + carbon_weight * dispatch_co2 + delay
                elif mode == "cost":
                    obj = cash + delay
                else:
                    obj = dispatch_co2 + 0.002 * cash + 0.001 * delay
                y_idx[(b, i, t)] = add_var(0, 1, obj, 1)

    for b in tasks.index:
        u_idx[b] = add_var(0, 1, 10000.0, 1)

    for i in range(I):
        for t in range(H):
            cash_delta = green_premium
            dispatch_delta = -grid_ci[i, t]
            if mode == "multi":
                obj = cash_delta + carbon_weight * dispatch_delta
            elif mode == "cost":
                obj = cash_delta
            else:
                obj = dispatch_delta + 0.002 * cash_delta
            g_idx[(i, t)] = add_var(0, float(green_available[i, t]), obj, 0)

    rows, lower, upper = [], [], []
    def add_constraint(coeff, lo=-np.inf, hi=np.inf):
        rows.append(coeff); lower.append(lo); upper.append(hi)

    y_by_batch = {b: [] for b in tasks.index}
    y_by_node_time = {(i, t): [] for i in range(I) for t in range(H)}
    for (b, i, t), j in y_idx.items():
        y_by_batch[b].append(j)
        y_by_node_time[(i, t)].append((b, j))

    for b in tasks.index:
        coeff = {u_idx[b]: 1.0}
        for j in y_by_batch[b]: coeff[j] = 1.0
        add_constraint(coeff, 1.0, 1.0)

    for i in range(I):
        for t in range(H):
            assignments = y_by_node_time[(i, t)]
            if assignments:
                add_constraint({j: float(tasks.loc[b, "demand_cu"]) for b, j in assignments}, hi=float(capacity[i, t]))
                add_constraint({j: float(tasks.loc[b, "demand_cu"] * tasks.loc[b, "data_gb_per_cu"]) for b, j in assignments}, hi=float(bandwidth[i, t]))
            green_coeff = {g_idx[(i, t)]: 1.0}
            for b, j in assignments:
                green_coeff[j] = -float(tasks.loc[b, "demand_cu"]) * float(nodes.loc[i, "energy_kwh_per_cu"])
            add_constraint(green_coeff, hi=0.0)

    A = lil_matrix((len(rows), len(c)), dtype=float)
    for r, coeff in enumerate(rows):
        for j, v in coeff.items(): A[r, j] = v

    start = time.perf_counter()
    res = milp(
        c=np.asarray(c, float), integrality=np.asarray(integrality, int),
        bounds=Bounds(np.asarray(lb, float), np.asarray(ub, float)),
        constraints=LinearConstraint(A.tocsr(), np.asarray(lower, float), np.asarray(upper, float)),
        options={"time_limit": float(time_limit), "mip_rel_gap": 0.001, "disp": False},
    )
    elapsed = time.perf_counter() - start
    if res.x is None:
        raise RuntimeError(str(res.message))

    sol = res.x
    schedule_rows = []
    for (b, i, t), j in y_idx.items():
        if sol[j] > 0.5:
            r = tasks.loc[b]
            q = float(r.demand_cu)
            energy = q * float(nodes.loc[i, "energy_kwh_per_cu"])
            schedule_rows.append({
                "task_id": int(b), "batch": r.batch, "type": r.type,
                "arrival": int(r.arrival), "default_node": r.default_node,
                "node_i": i, "node": nodes.loc[i, "node"], "exec_hour": int(t),
                "workload_cu": q, "delay_h": int(t) - int(r.arrival),
                "energy_kwh": energy,
            })
    schedule = pd.DataFrame(schedule_rows)
    unmet = np.array([sol[u_idx[b]] for b in tasks.index], float)
    green_used = np.array([[sol[g_idx[(i, t)]] for t in range(H)] for i in range(I)], float)

    summary, schedule, node_summary, hourly_summary = calculate_metrics(
        nodes, tasks, schedule, unmet, green_used,
        capacity, grid_price, grid_ci, green_available, elapsed, green_premium,
        mip_gap=float(getattr(res, "mip_gap", np.nan)) if getattr(res, "mip_gap", None) is not None else np.nan,
    )
    return {"summary": summary, "schedule": schedule, "node_summary": node_summary,
            "hourly_summary": hourly_summary, "raw_result": res}


def calculate_metrics(nodes, tasks, schedule, unmet, green_used, capacity, grid_price, grid_ci,
                      green_available, solve_time, green_premium=GREEN_CERT_PREMIUM_CNY_KWH, mip_gap=np.nan):
    I, H = grid_price.shape
    energy = np.zeros((I, H), float)
    workload = np.zeros((I, H), float)
    migration_cost = 0.0
    weighted_delay = 0.0
    green_alloc = np.zeros((I, H), float)

    if not schedule.empty:
        for _, r in schedule.iterrows():
            b, i, t = int(r.task_id), int(r.node_i), int(r.exec_hour)
            q = float(r.workload_cu)
            task = tasks.loc[b]
            e = q * float(nodes.loc[i, "energy_kwh_per_cu"])
            energy[i, t] += e; workload[i, t] += q
            migration_cost += q * float(task.data_gb_per_cu) * float(nodes.loc[i, "migration_fee_cny_gb"])
            weighted_delay += q * (t - int(task.arrival))

    green_used = np.minimum(np.asarray(green_used), energy)
    residual = np.maximum(energy - green_used, 0.0)
    electricity_cost = float((energy * grid_price).sum())
    green_premium_cost = float(green_used.sum()) * green_premium
    cash_cost = electricity_cost + green_premium_cost + migration_cost
    dispatch_carbon = float((residual * grid_ci).sum())
    location_carbon = float((energy * grid_ci).sum())
    market_carbon = float(residual.sum() * MARKET_RESIDUAL_CI_KG_KWH)

    total_demand = float(tasks.demand_cu.sum())
    completed = sum(float(tasks.loc[b, "demand_cu"]) * (1.0 - float(unmet[b])) for b in tasks.index)
    completion = 100.0 * completed / total_demand if total_demand else 100.0
    sla = completion  # 所有被安排变量在建模时已满足时延窗与网络时延限制。
    green_share = 100.0 * float(green_used.sum()) / float(energy.sum()) if energy.sum() else 0.0
    green_util = 100.0 * float(green_used.sum()) / float(green_available.sum()) if green_available.sum() else 0.0
    avg_delay = weighted_delay / completed if completed else np.nan

    hourly_rows = []
    for i, node in enumerate(nodes["node"]):
        for t in range(H):
            hourly_rows.append({
                "node": node, "node_i": i, "hour": t, "workload_cu": workload[i, t],
                "capacity_cu": capacity[i, t],
                "load_rate_pct": 100.0 * workload[i, t] / capacity[i, t] if capacity[i, t] else 0.0,
                "energy_kwh": energy[i, t], "green_used_kwh": green_used[i, t],
                "green_available_kwh": green_available[i, t], "grid_price_cny_kwh": grid_price[i, t],
                "grid_ci_kg_kwh": grid_ci[i, t],
            })
    hourly_summary = pd.DataFrame(hourly_rows)
    node_summary = hourly_summary.groupby("node", as_index=False).agg(
        workload_cu=("workload_cu", "sum"), energy_kwh=("energy_kwh", "sum"),
        green_used_kwh=("green_used_kwh", "sum"), avg_load_rate_pct=("load_rate_pct", "mean"),
        peak_load_rate_pct=("load_rate_pct", "max"),
    )
    node_summary["green_share_pct"] = np.where(node_summary.energy_kwh > 0,
        100.0 * node_summary.green_used_kwh / node_summary.energy_kwh, 0.0)

    # 逐任务补充产品展示字段；绿电分配按节点小时内能耗占比分摊。
    if not schedule.empty:
        enriched = []
        for _, r in schedule.iterrows():
            i, t = int(r.node_i), int(r.exec_hour)
            e = float(r.energy_kwh)
            total_e = energy[i, t]
            g = green_used[i, t] * e / total_e if total_e > 0 else 0.0
            task = tasks.loc[int(r.task_id)]
            grid_cost = e * grid_price[i, t]
            mig_cost = float(r.workload_cu) * float(task.data_gb_per_cu) * float(nodes.loc[i, "migration_fee_cny_gb"])
            cost = grid_cost + g * green_premium + mig_cost
            dispatch = max(e - g, 0.0) * grid_ci[i, t]
            loc = e * grid_ci[i, t]
            mkt = max(e - g, 0.0) * MARKET_RESIDUAL_CI_KG_KWH
            d = dict(r)
            d.update({"green_used_kwh": g, "cash_cost_cny": cost, "dispatch_carbon_kg": dispatch,
                      "location_carbon_kg": loc, "market_carbon_kg": mkt,
                      "sla_ok": True, "migrated": str(r.node) != str(r.default_node)})
            enriched.append(d)
        schedule = pd.DataFrame(enriched)

    summary = {
        "cash_cost": cash_cost, "dispatch_carbon": dispatch_carbon,
        "location_carbon": location_carbon, "market_carbon": market_carbon,
        "completion_rate": completion, "sla_rate": sla, "green_share": green_share,
        "green_utilization": green_util, "avg_delay": avg_delay,
        "solve_time": float(solve_time), "mip_gap": mip_gap,
        "total_demand_cu": total_demand, "completed_cu": completed,
        "avg_load_rate": float(hourly_summary.load_rate_pct.mean()),
        "peak_load_rate": float(hourly_summary.load_rate_pct.max()),
    }
    return summary, schedule, node_summary, hourly_summary


def run_baselines(nodes, hourly, tasks, time_limit=5.0):
    rows, solutions = [], {}
    for label, mode, cw in [
        ("成本优先MILP", "cost", 0.0), ("碳优先MILP", "carbon", 0.0),
        ("电碳算协同MILP", "balanced", DEFAULT_SHADOW_CARBON_PRICE)
    ]:
        sol = solve_dispatch(nodes, hourly, tasks, carbon_weight=cw, objective_mode=mode, time_limit=time_limit)
        s = sol["summary"]
        rows.append({"方案": label, "任务完成率_%": s["completion_rate"], "SLA满足率_%": s["sla_rate"],
                     "现金成本_CNY": s["cash_cost"], "调度碳代理_kgCO2": s["dispatch_carbon"],
                     "位置法碳排_kgCO2": s["location_carbon"], "市场法碳排_kgCO2": s["market_carbon"],
                     "绿电占比_%": s["green_share"], "平均延迟_h": s["avg_delay"], "求解时间_s": s["solve_time"]})
        solutions[label] = sol
    return pd.DataFrame(rows), solutions
