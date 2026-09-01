# -*- coding: utf-8 -*-
"""
电—碳—算协同调度：实证验证套件 v4
==================================

在 public-calibrated v2 基础上补充三类创业赛核心证据：
1) 消融实验：解释“为什么有效”；
2) Monte Carlo 随机重复实验：解释“是否依赖单一漂亮场景”；
3) 规模—求解时间实验：解释“规模增大后还能不能算”。

输出目录：validation_outputs/
- ablation_results.csv
- monte_carlo_all.csv
- monte_carlo_summary.csv
- scalability_results.csv
- validation_key_findings.txt

说明
----
A. 本脚本必须与 carbon_compute_public_calibrated_v2.py 放在同一目录；
B. 消融与Monte Carlo仍基于4个公开校准节点；
C. 规模实验中的8/12/16/20节点不是新增“真实数据中心”，而是基于4个原型节点
   复制并作轻微扰动形成的计算规模情景，仅用于检验MILP计算复杂度；
D. Monte Carlo扰动的是企业真实运行中常变化但当前不可得的参数：任务需求、可用容量、
   绿电可得量及小幅电价扰动，不改变公开省级碳因子等基本口径。

依赖
----
numpy, pandas, scipy>=1.9

运行
----
python carbon_compute_validation_suite_v4.py
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "validation_outputs"
OUT.mkdir(exist_ok=True)

BASE_FILE = HERE / "carbon_compute_public_calibrated_v2.py"
if not BASE_FILE.exists():
    raise FileNotFoundError(
        "缺少 carbon_compute_public_calibrated_v2.py。请将本脚本与v2文件放在同一文件夹。"
    )

spec = importlib.util.spec_from_file_location("carbon_v2", BASE_FILE)
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


# ============================================================
# 通用工具
# ============================================================

def green_from_schedule(nodes, tasks, schedule, green_available, grid_price_shape):
    """给定一个已确定的调度结果，按“可得绿电优先使用”规则计算实际绿电使用量。"""
    I, H = grid_price_shape
    energy = np.zeros((I, H), dtype=float)
    if schedule is not None and len(schedule) > 0:
        for _, r in schedule.iterrows():
            i = int(r.node_i)
            t = int(r.exec_hour)
            q = float(r.workload_cu)
            energy[i, t] += q * float(nodes.loc[i, "energy_kwh_per_cu"])
    return np.minimum(energy, green_available)


def solve_eval(
    nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
    mode="multi", carbon_price=None, time_limit=20,
):
    """求解并返回统一评估结果。"""
    if carbon_price is None:
        carbon_price = v2.DEFAULT_SHADOW_CARBON_PRICE
    res, schedule, unmet, green_used, elapsed = v2.solve_milp(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode=mode, carbon_price=carbon_price, time_limit=time_limit,
    )
    metrics = v2.evaluate(
        nodes, tasks, schedule, unmet, green_used,
        grid_price, grid_ci, green_available, elapsed,
    )
    return res, schedule, unmet, green_used, metrics


def pct_change(new, base):
    if base == 0 or pd.isna(base):
        return np.nan
    return 100.0 * (new - base) / base


def pct_reduction(new, base):
    if base == 0 or pd.isna(base):
        return np.nan
    return 100.0 * (base - new) / base


# ============================================================
# 1. 消融实验
# ============================================================

def _static_partition_tasks(nodes, tasks, capacity):
    """将任务批次按到达时刻的相对负载静态分配到节点，不允许优化器改变节点。"""
    I = len(nodes)
    assigned = {i: [] for i in range(I)}
    load = np.zeros_like(capacity, dtype=float)

    order = sorted(tasks.index, key=lambda b: (int(tasks.loc[b, "arrival"]), int(tasks.loc[b, "max_defer"])))
    for b in order:
        r = tasks.loc[b]
        a = int(r.arrival)
        feasible = [i for i in range(I) if float(nodes.loc[i, "latency_ms"]) <= float(r.max_latency)]
        if not feasible:
            feasible = [0]
        # 只依据到达时刻的静态负载率做初始归属，不看电价/碳/绿电。
        i_star = min(feasible, key=lambda i: load[i, a] / max(float(capacity[i, a]), 1e-9))
        assigned[i_star].append(b)
        load[i_star, a] += float(r.demand_cu)
    return assigned


def _run_time_only_partition(nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available):
    """固定节点归属，仅允许任务在各自节点内跨时段调度。"""
    assigned = _static_partition_tasks(nodes, tasks, capacity)
    total_demand = float(tasks.demand_cu.sum())

    sums = {
        "现金成本_CNY": 0.0,
        "其中绿电溢价_CNY": 0.0,
        "调度碳代理_kgCO2": 0.0,
        "位置法碳排_kgCO2": 0.0,
        "市场法碳排_kgCO2": 0.0,
        "completed_cu": 0.0,
        "sla_cu": 0.0,
        "green_used_kwh": 0.0,
        "energy_kwh": 0.0,
        "weighted_delay": 0.0,
        "solve_time": 0.0,
    }

    for i in range(len(nodes)):
        ids = assigned[i]
        if not ids:
            continue
        tsub = tasks.loc[ids].copy().reset_index(drop=True)
        nsub = nodes.iloc[[i]].copy().reset_index(drop=True)
        csub = capacity[i:i+1, :]
        bsub = bandwidth[i:i+1, :]
        psub = grid_price[i:i+1, :]
        cisub = grid_ci[i:i+1, :]
        gsub = green_available[i:i+1, :]

        _, sch, unmet, gu, m = solve_eval(
            nsub, tsub, csub, bsub, psub, cisub, gsub,
            mode="multi", carbon_price=v2.DEFAULT_SHADOW_CARBON_PRICE, time_limit=20,
        )
        demand_i = float(tsub.demand_cu.sum())
        completed_i = demand_i * float(m["任务完成率_%"]) / 100.0
        sla_i = demand_i * float(m["SLA满足率_%"]) / 100.0
        energy_i = 0.0
        if len(sch) > 0:
            energy_i = float((sch["workload_cu"].astype(float) * float(nsub.loc[0, "energy_kwh_per_cu"])).sum())

        sums["现金成本_CNY"] += float(m["现金成本_CNY"])
        sums["其中绿电溢价_CNY"] += float(m["其中绿电溢价_CNY"])
        sums["调度碳代理_kgCO2"] += float(m["调度碳代理_kgCO2"])
        sums["位置法碳排_kgCO2"] += float(m["位置法碳排_kgCO2"])
        sums["市场法碳排_kgCO2"] += float(m["市场法碳排_kgCO2"])
        sums["completed_cu"] += completed_i
        sums["sla_cu"] += sla_i
        sums["green_used_kwh"] += float(gu.sum())
        sums["energy_kwh"] += energy_i
        sums["weighted_delay"] += float(m["平均延迟_h"]) * completed_i if completed_i > 0 else 0.0
        sums["solve_time"] += float(m["求解时间_s"])

    completed = sums["completed_cu"]
    return {
        "任务完成率_%": 100.0 * completed / total_demand,
        "SLA满足率_%": 100.0 * sums["sla_cu"] / total_demand,
        "现金成本_CNY": sums["现金成本_CNY"],
        "其中绿电溢价_CNY": sums["其中绿电溢价_CNY"],
        "调度碳代理_kgCO2": sums["调度碳代理_kgCO2"],
        "位置法碳排_kgCO2": sums["位置法碳排_kgCO2"],
        "市场法碳排_kgCO2": sums["市场法碳排_kgCO2"],
        "单位成本_CNY_per_1000CU": 1000.0 * sums["现金成本_CNY"] / completed if completed else np.nan,
        "位置法单位碳排_kg_per_1000CU": 1000.0 * sums["位置法碳排_kgCO2"] / completed if completed else np.nan,
        "市场法单位碳排_kg_per_1000CU": 1000.0 * sums["市场法碳排_kgCO2"] / completed if completed else np.nan,
        "绿电占比_%": 100.0 * sums["green_used_kwh"] / sums["energy_kwh"] if sums["energy_kwh"] else 0.0,
        "绿电利用率_%": 100.0 * sums["green_used_kwh"] / float(green_available.sum()),
        "平均延迟_h": sums["weighted_delay"] / completed if completed else np.nan,
        "求解时间_s": sums["solve_time"],
    }


def run_ablation(seed=42):
    """
    五组：成本优先、仅空间迁移、固定节点+时间迁移、无绿电感知、完整协同。
    """
    nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = \
        v2.make_public_calibrated_data(seed=seed)

    rows = []

    _, _, _, _, m = solve_eval(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="cost", carbon_price=0.0,
    )
    rows.append({"方案": "成本优先", "机制说明": "空间✓ 时间✓ 绿电感知× 碳权重×", **m})

    tasks_space = tasks.copy(deep=True)
    tasks_space["max_defer"] = 0
    _, _, _, _, m = solve_eval(
        nodes, tasks_space, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="multi",
    )
    rows.append({"方案": "仅空间迁移", "机制说明": "空间✓ 时间× 绿电感知✓ 碳权重✓", **m})

    m = _run_time_only_partition(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available
    )
    rows.append({"方案": "固定节点+时间迁移", "机制说明": "空间决策× 时间✓ 绿电感知✓ 碳权重✓", **m})

    zero_green = np.zeros_like(green_available)
    _, sch, unmet, _, elapsed = v2.solve_milp(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, zero_green,
        mode="multi", carbon_price=v2.DEFAULT_SHADOW_CARBON_PRICE, time_limit=20,
    )
    gu_actual = green_from_schedule(nodes, tasks, sch, green_available, grid_price.shape)
    m = v2.evaluate(
        nodes, tasks, sch, unmet, gu_actual,
        grid_price, grid_ci, green_available, elapsed,
    )
    rows.append({"方案": "无绿电感知", "机制说明": "空间✓ 时间✓ 绿电感知× 碳权重✓", **m})

    _, _, _, _, m = solve_eval(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="multi",
    )
    rows.append({"方案": "完整协同", "机制说明": "空间✓ 时间✓ 绿电感知✓ 碳权重✓", **m})

    df = pd.DataFrame(rows)
    full = df.loc[df["方案"] == "完整协同"].iloc[0]
    df["相对完整模型_现金成本变化_%"] = df["现金成本_CNY"].apply(lambda x: pct_change(x, full["现金成本_CNY"]))
    df["相对完整模型_调度碳恶化_%"] = df["调度碳代理_kgCO2"].apply(lambda x: pct_change(x, full["调度碳代理_kgCO2"]))
    df["相对完整模型_市场法碳排恶化_%"] = df["市场法碳排_kgCO2"].apply(lambda x: pct_change(x, full["市场法碳排_kgCO2"]))
    df["相对完整模型_绿电占比变化_百分点"] = df["绿电占比_%"] - full["绿电占比_%"]
    df.to_csv(OUT / "ablation_results.csv", index=False, encoding="utf-8-sig")
    return df


# ============================================================
# 2. Monte Carlo随机重复实验
# ============================================================

def perturb_operating_scenario(base, rng):
    """
    围绕同一公开校准基准场景生成一个“运行日”情景。

    扰动范围刻意控制在中等范围，不用极端随机数制造结论：
    - 全局任务需求：±15%，叠加批次级±5%；
    - 可用容量：节点级±8%，时段级±3%；
    - 绿电可得量：节点日总量±20%，小时级±12%；
    - 分时电价：节点级±5%（仅作市场波动敏感性，不替代公开基准价）；
    - 省级碳因子不随机修改，保持公开口径。
    """
    nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = base

    tasks2 = tasks.copy(deep=True)
    cap2 = capacity.copy().astype(float)
    bw2 = bandwidth.copy().astype(float)
    price2 = grid_price.copy().astype(float)
    ci2 = grid_ci.copy().astype(float)
    green2 = green_available.copy().astype(float)

    # 任务需求
    global_demand = rng.uniform(0.85, 1.15)
    batch_noise = rng.uniform(0.95, 1.05, size=len(tasks2))
    tasks2["demand_cu"] = tasks2["demand_cu"].astype(float).to_numpy() * global_demand * batch_noise

    # 容量：保持物理上限合理
    I, H = cap2.shape
    node_cap = rng.uniform(0.92, 1.08, size=(I, 1))
    hour_cap = rng.uniform(0.97, 1.03, size=(I, H))
    cap2 = np.clip(cap2 * node_cap * hour_cap, 55.0, 110.0)

    # 带宽给轻微扰动
    bw2 *= rng.uniform(0.95, 1.05, size=(I, 1))

    # 电价：同一节点整体±5%，保留峰谷结构
    price2 *= rng.uniform(0.95, 1.05, size=(I, 1))

    # 绿电：节点总量±20% + 小时扰动，防止出现负值
    green2 *= rng.uniform(0.80, 1.20, size=(I, 1))
    green2 *= rng.uniform(0.88, 1.12, size=(I, H))
    green2 = np.maximum(green2, 0.0)

    scenario_meta = {
        "需求总体系数": global_demand,
        "平均容量系数": float(np.mean(node_cap)),
        "平均电价系数": float(np.mean(price2 / grid_price)),
        "平均绿电系数": float(np.sum(green2) / np.sum(green_available)),
    }
    return (nodes.copy(deep=True), tasks2, cap2, bw2, price2, ci2, green2), scenario_meta


def run_monte_carlo(n_scenarios=50, seed=20260901):
    """每个随机情景同时跑成本优先与完整协同，形成分布证据。"""
    base = v2.make_public_calibrated_data(seed=42)
    rng = np.random.default_rng(seed)
    rows = []

    for s in range(1, n_scenarios + 1):
        scenario, meta = perturb_operating_scenario(base, rng)
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = scenario

        # 成本优先
        _, _, _, _, m_cost = solve_eval(
            nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
            mode="cost", carbon_price=0.0, time_limit=15,
        )

        # 协同
        _, _, _, _, m_ours = solve_eval(
            nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
            mode="multi", carbon_price=v2.DEFAULT_SHADOW_CARBON_PRICE, time_limit=15,
        )

        row = {
            "scenario_id": s,
            **meta,
            "成本优先_现金成本_CNY": m_cost["现金成本_CNY"],
            "成本优先_调度碳代理_kgCO2": m_cost["调度碳代理_kgCO2"],
            "成本优先_位置法碳排_kgCO2": m_cost["位置法碳排_kgCO2"],
            "成本优先_市场法碳排_kgCO2": m_cost["市场法碳排_kgCO2"],
            "成本优先_任务完成率_%": m_cost["任务完成率_%"],
            "成本优先_SLA满足率_%": m_cost["SLA满足率_%"],
            "协同_现金成本_CNY": m_ours["现金成本_CNY"],
            "协同_调度碳代理_kgCO2": m_ours["调度碳代理_kgCO2"],
            "协同_位置法碳排_kgCO2": m_ours["位置法碳排_kgCO2"],
            "协同_市场法碳排_kgCO2": m_ours["市场法碳排_kgCO2"],
            "协同_任务完成率_%": m_ours["任务完成率_%"],
            "协同_SLA满足率_%": m_ours["SLA满足率_%"],
            "协同_绿电占比_%": m_ours["绿电占比_%"],
            "协同_求解时间_s": m_ours["求解时间_s"],
        }
        row["相对成本优先_现金成本变化_%"] = pct_change(
            m_ours["现金成本_CNY"], m_cost["现金成本_CNY"]
        )
        row["相对成本优先_调度碳下降_%"] = pct_reduction(
            m_ours["调度碳代理_kgCO2"], m_cost["调度碳代理_kgCO2"]
        )
        row["相对成本优先_位置法碳排下降_%"] = pct_reduction(
            m_ours["位置法碳排_kgCO2"], m_cost["位置法碳排_kgCO2"]
        )
        row["相对成本优先_市场法碳排下降_%"] = pct_reduction(
            m_ours["市场法碳排_kgCO2"], m_cost["市场法碳排_kgCO2"]
        )
        rows.append(row)

        if s % 10 == 0:
            print(f"Monte Carlo: {s}/{n_scenarios} scenarios finished")

    all_df = pd.DataFrame(rows)
    all_df.to_csv(OUT / "monte_carlo_all.csv", index=False, encoding="utf-8-sig")

    focus = [
        "相对成本优先_现金成本变化_%",
        "相对成本优先_调度碳下降_%",
        "相对成本优先_位置法碳排下降_%",
        "相对成本优先_市场法碳排下降_%",
        "协同_任务完成率_%",
        "协同_SLA满足率_%",
        "协同_绿电占比_%",
        "协同_求解时间_s",
    ]
    summary_rows = []
    for col in focus:
        x = all_df[col].astype(float)
        summary_rows.append({
            "指标": col,
            "均值": x.mean(),
            "标准差": x.std(ddof=1),
            "P05": x.quantile(0.05),
            "中位数": x.quantile(0.50),
            "P95": x.quantile(0.95),
            "最小值": x.min(),
            "最大值": x.max(),
        })

    summary = pd.DataFrame(summary_rows)

    # 胜率是BP最直观的稳健性表达之一
    extra = pd.DataFrame([
        {"指标": "调度碳减排胜率_%", "均值": 100 * (all_df["相对成本优先_调度碳下降_%"] > 0).mean()},
        {"指标": "市场法减排胜率_%", "均值": 100 * (all_df["相对成本优先_市场法碳排下降_%"] > 0).mean()},
        {"指标": "完整完成场景占比_%", "均值": 100 * (all_df["协同_任务完成率_%"] >= 99.999).mean()},
        {"指标": "SLA全满足场景占比_%", "均值": 100 * (all_df["协同_SLA满足率_%"] >= 99.999).mean()},
        {"指标": "成本增幅不超过5%的场景占比_%", "均值": 100 * (all_df["相对成本优先_现金成本变化_%"] <= 5).mean()},
    ])
    summary = pd.concat([summary, extra], ignore_index=True, sort=False)
    summary.to_csv(OUT / "monte_carlo_summary.csv", index=False, encoding="utf-8-sig")
    return all_df, summary


# ============================================================
# 3. 规模—求解时间实验
# ============================================================

def build_scaled_case(node_count: int, seed=100):
    """
    按4节点:72任务的比例扩展到8/12/16/20节点。
    新节点是公开校准原型的复制扰动版本，仅用于计算复杂度测试。
    """
    if node_count % 4 != 0 or node_count < 4:
        raise ValueError("node_count需为4的整数倍且>=4")

    base_nodes, base_tasks, base_cap, base_bw, base_price, base_ci, base_green = \
        v2.make_public_calibrated_data(seed=42)
    factor = node_count // 4
    rng = np.random.default_rng(seed + node_count)
    H = base_cap.shape[1]

    node_frames = []
    caps, bws, prices, cis, greens = [], [], [], [], []

    for k in range(factor):
        nd = base_nodes.copy(deep=True)
        if k > 0:
            nd["node"] = [f"扩展{k+1:02d}_{x}" for x in nd["node"]]
            # 轻微扰动，打破完全对称；仍不代表真实地区参数。
            nd["latency_ms"] = np.maximum(1.0, nd["latency_ms"].astype(float) * rng.uniform(0.92, 1.08, 4))
            nd["energy_kwh_per_cu"] = nd["energy_kwh_per_cu"].astype(float) * rng.uniform(0.98, 1.02, 4)
            nd["capacity_source_type"] = "规模测试复制扰动节点"
        node_frames.append(nd)

        c = base_cap.copy() * rng.uniform(0.97, 1.03, size=(4, 1))
        b = base_bw.copy() * rng.uniform(0.97, 1.03, size=(4, 1))
        p = base_price.copy() * rng.uniform(0.985, 1.015, size=(4, 1))
        ci = base_ci.copy()
        g = base_green.copy() * rng.uniform(0.95, 1.05, size=(4, 1))
        caps.append(c); bws.append(b); prices.append(p); cis.append(ci); greens.append(g)

    nodes = pd.concat(node_frames, ignore_index=True)
    capacity = np.vstack(caps)
    bandwidth = np.vstack(bws)
    grid_price = np.vstack(prices)
    grid_ci = np.vstack(cis)
    green_available = np.vstack(greens)

    # 任务也按相同比例复制，保持总体负载/总体容量近似不变。
    task_frames = []
    for k in range(factor):
        tt = base_tasks.copy(deep=True)
        tt["batch"] = [f"R{k+1:02d}_{x}" for x in tt["batch"]]
        tt["demand_cu"] = tt["demand_cu"].astype(float) * rng.uniform(0.97, 1.03, size=len(tt))
        tt["task_source_type"] = "规模测试复制扰动任务"
        task_frames.append(tt)
    tasks = pd.concat(task_frames, ignore_index=True)

    return nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available


def count_model_size(nodes, tasks, capacity):
    """按v2变量创建逻辑精确计算y/u/g数量，并近似计数约束。"""
    I, H = capacity.shape
    y_count = 0
    assignment_exists = np.zeros((I, H), dtype=bool)

    for b, r in tasks.iterrows():
        a = int(r.arrival)
        deadline = min(H - 1, a + int(r.max_defer))
        for i in range(I):
            if float(nodes.loc[i, "latency_ms"]) > float(r.max_latency):
                continue
            for t in range(a, deadline + 1):
                y_count += 1
                assignment_exists[i, t] = True

    u_count = len(tasks)
    g_count = I * H
    total_vars = y_count + u_count + g_count
    binary_vars = y_count + u_count

    # 每任务1条；每(i,t)绿电约束1条；有候选任务的(i,t)再加容量+带宽2条。
    constraint_count = len(tasks) + I * H + int(2 * assignment_exists.sum())
    return {
        "变量总数": total_vars,
        "二元变量数": binary_vars,
        "连续变量数": g_count,
        "约束数": constraint_count,
    }


def run_scalability(node_levels=(4, 8, 12, 16, 20), time_limit=30):
    rows = []
    for n_nodes in node_levels:
        case = build_scaled_case(n_nodes)
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = case
        size = count_model_size(nodes, tasks, capacity)

        try:
            res, sch, unmet, gu, metrics = solve_eval(
                nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
                mode="multi", carbon_price=v2.DEFAULT_SHADOW_CARBON_PRICE,
                time_limit=time_limit,
            )
            status = int(getattr(res, "status", -1))
            message = str(getattr(res, "message", ""))
            gap = float(getattr(res, "mip_gap", np.nan))
            node_count_solver = float(getattr(res, "mip_node_count", np.nan))
            row = {
                "节点数": n_nodes,
                "任务批次数": len(tasks),
                **size,
                "求解状态码": status,
                "求解状态": message,
                "MIP_Gap": gap,
                "分支节点数": node_count_solver,
                "求解时间_s": metrics["求解时间_s"],
                "任务完成率_%": metrics["任务完成率_%"],
                "SLA满足率_%": metrics["SLA满足率_%"],
                "现金成本_CNY": metrics["现金成本_CNY"],
                "调度碳代理_kgCO2": metrics["调度碳代理_kgCO2"],
            }
        except Exception as e:
            row = {
                "节点数": n_nodes,
                "任务批次数": len(tasks),
                **size,
                "求解状态码": -999,
                "求解状态": f"ERROR: {e}",
                "MIP_Gap": np.nan,
                "分支节点数": np.nan,
                "求解时间_s": time_limit,
                "任务完成率_%": np.nan,
                "SLA满足率_%": np.nan,
                "现金成本_CNY": np.nan,
                "调度碳代理_kgCO2": np.nan,
            }
        rows.append(row)
        print(
            f"Scale test: nodes={n_nodes}, tasks={len(tasks)}, vars={size['变量总数']}, "
            f"time={row['求解时间_s']:.3f}s, gap={row['MIP_Gap']}"
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "scalability_results.csv", index=False, encoding="utf-8-sig")
    return df


# ============================================================
# 自动提炼可用于BP核对的关键数字
# ============================================================

def write_findings(ablation, mc_all, mc_summary, scale):
    full = ablation.loc[ablation["方案"] == "完整协同"].iloc[0]
    cost = ablation.loc[ablation["方案"] == "成本优先"].iloc[0]

    lines = []
    lines.append("电—碳—算协同调度 v4 实证验证关键数字（仅供BP撰写前核对）")
    lines.append("=" * 72)
    lines.append("")
    lines.append("[1] 消融实验")
    lines.append(
        f"完整协同相对成本优先：成本变化 {pct_change(full['现金成本_CNY'], cost['现金成本_CNY']):.2f}%，"
        f"调度碳下降 {pct_reduction(full['调度碳代理_kgCO2'], cost['调度碳代理_kgCO2']):.2f}%，"
        f"市场法碳排下降 {pct_reduction(full['市场法碳排_kgCO2'], cost['市场法碳排_kgCO2']):.2f}%。"
    )
    for _, r in ablation.iterrows():
        if r["方案"] == "完整协同":
            continue
        lines.append(
            f"去除/限制机制 [{r['方案']}]：相对完整模型调度碳恶化 "
            f"{r['相对完整模型_调度碳恶化_%']:.2f}%，市场法碳排恶化 "
            f"{r['相对完整模型_市场法碳排恶化_%']:.2f}%。"
        )

    lines.append("")
    lines.append("[2] Monte Carlo 随机重复")
    lines.append(
        f"场景数：{len(mc_all)}；调度碳减排胜率："
        f"{100*(mc_all['相对成本优先_调度碳下降_%']>0).mean():.1f}%；"
        f"市场法减排胜率：{100*(mc_all['相对成本优先_市场法碳排下降_%']>0).mean():.1f}%；"
        f"成本增幅<=5%的场景占比：{100*(mc_all['相对成本优先_现金成本变化_%']<=5).mean():.1f}%。"
    )
    lines.append(
        "成本增幅：均值 {:.2f}%，P05 {:.2f}%，P95 {:.2f}%。".format(
            mc_all["相对成本优先_现金成本变化_%"].mean(),
            mc_all["相对成本优先_现金成本变化_%"].quantile(.05),
            mc_all["相对成本优先_现金成本变化_%"].quantile(.95),
        )
    )
    lines.append(
        "调度碳下降：均值 {:.2f}%，P05 {:.2f}%，P95 {:.2f}%。".format(
            mc_all["相对成本优先_调度碳下降_%"].mean(),
            mc_all["相对成本优先_调度碳下降_%"].quantile(.05),
            mc_all["相对成本优先_调度碳下降_%"].quantile(.95),
        )
    )

    lines.append("")
    lines.append("[3] 规模—求解时间")
    for _, r in scale.iterrows():
        lines.append(
            f"{int(r['节点数'])}节点 / {int(r['任务批次数'])}批任务 / "
            f"{int(r['二元变量数'])}个二元变量：求解 {r['求解时间_s']:.3f}s，"
            f"MIP Gap={r['MIP_Gap']}，完成率={r['任务完成率_%']:.2f}%。"
        )

    lines.append("")
    lines.append("重要：规模测试扩展节点为复制扰动情景，只能用于说明计算规模，不得写成真实20节点生产验证。")
    (OUT / "validation_key_findings.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    print("\n[1/3] Running ablation study...")
    ablation = run_ablation()
    print(ablation[[
        "方案", "现金成本_CNY", "调度碳代理_kgCO2", "市场法碳排_kgCO2",
        "绿电占比_%", "任务完成率_%", "SLA满足率_%"
    ]].round(3).to_string(index=False))

    print("\n[2/3] Running Monte Carlo robustness study...")
    mc_all, mc_summary = run_monte_carlo(n_scenarios=50)
    print(mc_summary.round(3).to_string(index=False))

    print("\n[3/3] Running scalability study...")
    scale = run_scalability(node_levels=(4, 8, 12, 16, 20), time_limit=5)  # 规模实验重点看时间与Gap，不要求每档无限等待到严格最优
    print(scale[[
        "节点数", "任务批次数", "二元变量数", "约束数", "求解时间_s", "MIP_Gap",
        "任务完成率_%", "SLA满足率_%"
    ]].round(4).to_string(index=False))

    write_findings(ablation, mc_all, mc_summary, scale)
    print(f"\nDone. Outputs saved to: {OUT}")
