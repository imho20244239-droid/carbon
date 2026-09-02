# -*- coding: utf-8 -*-
"""
电—碳—算协同调度：公开参数校准版 v2
========================================

目标
----
1. 4 个代表性区域算力节点：安徽芜湖、江苏长三角、内蒙古和林格尔、四川天府；
2. 使用公开资料校准：2026年6月分时电价、最新省级电力CO2排放因子、
   2026年可再生能源消纳责任权重、PUE政策/准入代理、公开网络时延圈；
3. 对企业未公开参数（实时可用算力、链路可用带宽、任务负载、迁移费、
   小时级绿电出力）明确采用“情景参数/典型曲线”，不冒充企业实测数据；
4. 比较：本地立即执行、最近节点、成本优先MILP、碳优先MILP、
   电—碳—算协同MILP；
5. 同时输出三种碳指标：
   - 调度碳代理：区域碳因子 × 非绿电电量（用于优化决策，不作为正式盘查口径）；
   - 位置法：省级平均电力CO2因子 × 总用电量；
   - 市场法：0.6096 × 非可追溯绿电电量，可追溯绿电按0处理。

重要声明
--------
- 本脚本不是“企业真实运行数据仿真”。
- 公开参数仅用于构造具有现实区域差异的技术验证场景。
- CU 是异构算力归一化调度单元，不与 P、EFlops、GPU 数量直接等价。
- 小时级绿电可得量由公开年度/政策比例 + 典型化出力曲线生成，属于情景数据。
- 迁移费、实时容量利用率、带宽和任务到达为情景参数。

依赖
----
numpy, pandas, scipy>=1.9

运行
----
python carbon_compute_public_calibrated_v2.py
"""

import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix


OUT_DIR = Path(__file__).resolve().parent

# -----------------------------
# 公开校准参数 / 统一建模假设
# -----------------------------
GREEN_CERT_PREMIUM_CNY_KWH = 0.00596     # 2026-06 当年绿证均价 5.96元/个，1证=1000kWh
MARKET_RESIDUAL_CI_KG_KWH = 0.6096       # 市场法剩余购电因子（kgCO2/kWh）
BASE_IT_ENERGY_KWH_PER_CU = 0.30         # 归一化建模尺度：情景假设，不是公开实测值
GREEN_TARGET_NEW_HUB = 0.80               # 国家枢纽节点新建数据中心政策目标情景

# carbon_price 的单位为 CNY/kgCO2；用于协同优化中的“影子碳成本”，不是碳市场成交价。
DEFAULT_SHADOW_CARBON_PRICE = 0.25


def tou_price(region: str, hour: int) -> float:
    """2026年6月代表性110kV两部制工商业分时电价代理，hour按24小时循环。"""
    h = int(hour) % 24

    if region == "安徽_芜湖":
        # 公开价格：高峰0.8895、平段0.5830、低谷0.3271 元/kWh。
        if h in {6, 7, 16, 17, 18, 19, 20, 21}:
            return 0.8895
        if h in {23, 0, 1, 2, 3, 4, 5, 11, 12, 13}:
            return 0.3271
        return 0.5830

    if region == "江苏_长三角":
        # 6—8月：高峰14:00-22:00；低谷00:00-06:00、11:00-13:00。
        if h in set(range(14, 22)):
            return 0.8826
        if h in {0, 1, 2, 3, 4, 5, 11, 12}:
            return 0.3418
        return 0.5842

    if region == "内蒙古_和林格尔":
        # 6—8月“小风季”：尖峰19-21；高峰6-8、18-22；
        # 深谷13-15；低谷11-16；其他平段。
        if h in {19, 20}:
            return 0.734254
        if h in {6, 7, 18, 21}:
            return 0.633199
        if h in {13, 14}:
            return 0.243416
        if h in {11, 12, 15}:
            return 0.272289
        return 0.456025

    if region == "四川_天府":
        # 四川省属地方电网110kV公开代理：高峰10-12、17-22；低谷22-次日8；其他平段。
        if h in {10, 11, 17, 18, 19, 20, 21}:
            return 0.536852
        if h in {22, 23, 0, 1, 2, 3, 4, 5, 6, 7}:
            return 0.192878
        return 0.364865

    raise ValueError(f"Unknown region: {region}")


def make_public_calibrated_data(seed=42, green_policy_scenario=False):
    """
    构造公开参数校准场景。

    green_policy_scenario=False：绿电总量用省级2026可再生能源消纳责任权重做代理锚点。
    green_policy_scenario=True ：四节点统一按国家枢纽新建数据中心80%绿电目标生成可得量，
                                 用于政策压力测试，不代表实际消费比例。
    """
    rng = np.random.default_rng(seed)
    arrival_horizon = 24
    horizon = 31  # 最大允许延后6h，因此0~30
    hours = np.arange(horizon)
    h24 = hours % 24

    # A/B档公开校准 + C档情景参数并列记录，避免来源混淆。
    nodes = pd.DataFrame({
        "node": ["安徽_芜湖", "江苏_长三角", "内蒙古_和林格尔", "四川_天府"],
        "latency_ms": [5.0, 5.0, 20.0, 18.0],
        "grid_ci_kg_kwh": [0.6553, 0.5827, 0.6479, 0.1564],
        "green_share_base": [0.275, 0.285, 0.317, 0.700],
        "pue": [1.25, 1.30, 1.20, 1.30],
        # CU为归一化单元；能耗 = IT基准能耗 × PUE。
        "energy_kwh_per_cu": [
            BASE_IT_ENERGY_KWH_PER_CU * 1.25,
            BASE_IT_ENERGY_KWH_PER_CU * 1.30,
            BASE_IT_ENERGY_KWH_PER_CU * 1.20,
            BASE_IT_ENERGY_KWH_PER_CU * 1.30,
        ],
        # 企业内部网络传输/服务成本不可得：保留情景参数，并明确标注。
        "migration_fee_cny_gb": [0.000, 0.001, 0.003, 0.004],
        "latency_source_type": ["公开网络时延圈代理"] * 4,
        "carbon_source_type": ["生态环境部省级平均因子"] * 4,
        "green_source_type": ["2026可再生能源消纳责任权重代理"] * 4,
        "capacity_source_type": ["归一化情景容量"] * 4,
    })

    I = len(nodes)

    # -----------------------------------------------------
    # 实时可用算力：企业内部参数，不做“伪真实化”。
    # 每节点名义容量统一100CU/h，利用确定性周期波动+轻微随机扰动构造可用率。
    # -----------------------------------------------------
    nominal_capacity = np.full(I, 100.0)
    capacity = np.zeros((I, horizon))
    phase = [0, 2, 4, 6]
    for i in range(I):
        base_availability = 0.90 + 0.06 * np.sin((h24 + phase[i]) / 24 * 2 * np.pi)
        noise = rng.normal(0, 0.012, size=horizon)
        availability = np.clip(base_availability + noise, 0.78, 0.98)
        capacity[i, :] = nominal_capacity[i] * availability

    # 可用链路带宽同样为情景参数；不是物理端口带宽。
    bandwidth = np.array([
        np.full(horizon, 900.0),
        np.full(horizon, 900.0),
        np.full(horizon, 800.0),
        np.full(horizon, 800.0),
    ])

    # 2026年6月公开分时电价，31h按24h循环。
    grid_price = np.zeros((I, horizon))
    for i, region in enumerate(nodes["node"]):
        grid_price[i, :] = [tou_price(region, t) for t in hours]

    # 省级平均电力CO2因子：年度公开值，24/31小时保持不变。
    grid_ci = np.repeat(nodes["grid_ci_kg_kwh"].to_numpy()[:, None], horizon, axis=1)

    # -----------------------------------------------------
    # 小时级绿电可得量：公开比例锚定 + 典型出力曲线（情景数据）。
    # 总量锚定到“节点满负荷电耗 × 绿电比例”。
    # -----------------------------------------------------
    green_available = np.zeros((I, horizon))
    for i, region in enumerate(nodes["node"]):
        h = h24.astype(float)
        solar = np.maximum(0.0, np.sin((h - 6.0) / 12.0 * np.pi))
        wind = 0.65 + 0.35 * np.cos((h - 2.0) / 24.0 * 2.0 * np.pi)

        if region in {"安徽_芜湖", "江苏_长三角"}:
            raw = 0.35 + 1.25 * solar
        elif region == "内蒙古_和林格尔":
            raw = 0.55 + 0.95 * wind + 0.25 * solar
        else:  # 四川：用较平滑曲线表达水电占比较高的情景特征
            raw = 0.90 + 0.08 * np.sin((h + 3) / 24 * 2 * np.pi)

        share = GREEN_TARGET_NEW_HUB if green_policy_scenario else float(nodes.loc[i, "green_share_base"])
        nominal_energy = capacity[i, :] * float(nodes.loc[i, "energy_kwh_per_cu"])
        target_green_energy = share * nominal_energy.sum()
        green_available[i, :] = raw / raw.sum() * target_green_energy

    # -----------------------------------------------------
    # 任务负载：企业业务数据不可得，继续用可复现情景。
    # 三类任务体现跨时迁移和网络SLA差异。
    # -----------------------------------------------------
    task_types = {
        "实时型": {
            "share": 0.30,
            "max_defer": 0,
            "max_latency": 25,
            "data_gb_per_cu": 5.0,
            "delay_penalty": 0.25,
        },
        "交互型": {
            "share": 0.30,
            "max_defer": 2,
            "max_latency": 60,
            "data_gb_per_cu": 3.0,
            "delay_penalty": 0.035,
        },
        "批处理": {
            "share": 0.40,
            "max_defer": 6,
            "max_latency": 120,
            "data_gb_per_cu": 1.5,
            "delay_penalty": 0.006,
        },
    }

    rows = []
    for a in range(arrival_horizon):
        total = (
            150
            + 35 * np.exp(-((a - 10) / 3.0) ** 2)
            + 55 * np.exp(-((a - 20) / 2.5) ** 2)
            + rng.normal(0, 4)
        )
        for task_type, p in task_types.items():
            demand = max(10.0, total * p["share"] * (1 + rng.normal(0, 0.025)))
            rows.append({
                "batch": f"{a:02d}_{task_type}",
                "arrival": a,
                "type": task_type,
                "demand_cu": round(float(demand), 2),
                **p,
                "task_source_type": "合成业务负载情景",
            })

    tasks = pd.DataFrame(rows)
    return nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available


def solve_milp(
    nodes,
    tasks,
    capacity,
    bandwidth,
    grid_price,
    grid_ci,
    green_available,
    mode="multi",
    carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
    green_premium=GREEN_CERT_PREMIUM_CNY_KWH,
    time_limit=30,
):
    """
    每个任务批次整体选择一个节点和一个执行时段。

    mode:
      cost   : 现金成本 + 延迟惩罚
      carbon : 调度碳代理为主，成本/延迟仅作tie-breaker
      multi  : 现金成本 + 影子碳成本 + 延迟惩罚

    调度碳代理 = 区域碳因子 × 非可追溯绿电电量。
    它用于调度优化，不等同于正式“位置法”或“市场法”企业碳盘查。
    """
    I, H = capacity.shape

    y_idx, u_idx, g_idx = {}, {}, {}
    c, lb, ub, integrality = [], [], [], []

    def add_var(lo, hi, obj, int_type):
        j = len(c)
        c.append(obj)
        lb.append(lo)
        ub.append(hi)
        integrality.append(int_type)
        return j

    # y[b,i,t]: 任务批次 -> 节点/时段
    for b, r in tasks.iterrows():
        a = int(r.arrival)
        deadline = min(H - 1, a + int(r.max_defer))

        for i in range(I):
            if float(nodes.loc[i, "latency_ms"]) > float(r.max_latency):
                continue

            for t in range(a, deadline + 1):
                q = float(r.demand_cu)
                energy = q * float(nodes.loc[i, "energy_kwh_per_cu"])
                data_gb = q * float(r.data_gb_per_cu)

                # 先按普通电力计算；g变量随后用“绿电溢价/减碳收益”修正。
                cash = energy * grid_price[i, t] + data_gb * float(nodes.loc[i, "migration_fee_cny_gb"])
                dispatch_co2 = energy * grid_ci[i, t]
                delay = (t - a) * float(r.delay_penalty) * q

                if mode == "multi":
                    obj = cash + carbon_price * dispatch_co2 + delay
                elif mode == "cost":
                    obj = cash + delay
                elif mode == "carbon":
                    obj = dispatch_co2 + 0.002 * cash + 0.001 * delay
                else:
                    raise ValueError("mode must be cost/carbon/multi")

                y_idx[(b, i, t)] = add_var(0, 1, obj, 1)

    # u[b]: 未完成，大罚值确保优先满足任务/SLA。
    for b, _ in tasks.iterrows():
        u_idx[b] = add_var(0, 1, 10000.0, 1)

    # g[i,t]: 可追溯绿电使用量。
    # 绿电成本按“同节点普通电价 + 绿证等价溢价”构造。
    for i in range(I):
        for t in range(H):
            cash_delta = green_premium
            dispatch_co2_delta = -grid_ci[i, t]  # 代理指标中：绿电替代对应区域普通电力

            if mode == "multi":
                obj = cash_delta + carbon_price * dispatch_co2_delta
            elif mode == "cost":
                obj = cash_delta
            else:
                obj = dispatch_co2_delta + 0.002 * cash_delta

            g_idx[(i, t)] = add_var(0, float(green_available[i, t]), obj, 0)

    rows, lower, upper = [], [], []

    def add_constraint(coeff_dict, lo=-np.inf, hi=np.inf):
        rows.append(coeff_dict)
        lower.append(lo)
        upper.append(hi)

    y_by_batch = {b: [] for b in tasks.index}
    y_by_node_time = {(i, t): [] for i in range(I) for t in range(H)}

    for (b, i, t), j in y_idx.items():
        y_by_batch[b].append(j)
        y_by_node_time[(i, t)].append((b, j))

    # 每个任务批次：执行一次 or 未完成。
    for b, _ in tasks.iterrows():
        coeff = {u_idx[b]: 1.0}
        for j in y_by_batch[b]:
            coeff[j] = 1.0
        add_constraint(coeff, 1.0, 1.0)

    for i in range(I):
        for t in range(H):
            assignments = y_by_node_time[(i, t)]

            # 算力容量
            if assignments:
                add_constraint(
                    {j: float(tasks.loc[b, "demand_cu"]) for b, j in assignments},
                    hi=float(capacity[i, t]),
                )

                # 链路可用带宽
                add_constraint(
                    {
                        j: float(tasks.loc[b, "demand_cu"] * tasks.loc[b, "data_gb_per_cu"])
                        for b, j in assignments
                    },
                    hi=float(bandwidth[i, t]),
                )

            # 绿电不能超过实际耗电，也不能超过green_available的变量上界。
            green_coeff = {g_idx[(i, t)]: 1.0}
            for b, j in assignments:
                green_coeff[j] = -float(tasks.loc[b, "demand_cu"]) * float(nodes.loc[i, "energy_kwh_per_cu"])
            add_constraint(green_coeff, hi=0.0)

    A = lil_matrix((len(rows), len(c)), dtype=float)
    for r, coeff in enumerate(rows):
        for j, v in coeff.items():
            A[r, j] = v

    start = time.perf_counter()
    res = milp(
        c=np.array(c),
        integrality=np.array(integrality),
        bounds=Bounds(np.array(lb), np.array(ub)),
        constraints=LinearConstraint(A.tocsr(), np.array(lower), np.array(upper)),
        options={"time_limit": time_limit, "mip_rel_gap": 0.001, "disp": False},
    )
    elapsed = time.perf_counter() - start

    if res.x is None:
        raise RuntimeError(res.message)

    sol = res.x
    schedule_rows = []
    for (b, i, t), j in y_idx.items():
        if sol[j] > 0.5:
            r = tasks.loc[b]
            schedule_rows.append({
                "task_id": b,
                "batch": r.batch,
                "type": r.type,
                "arrival": int(r.arrival),
                "node_i": i,
                "node": nodes.loc[i, "node"],
                "exec_hour": t,
                "workload_cu": float(r.demand_cu),
                "delay_h": t - int(r.arrival),
            })

    schedule = pd.DataFrame(schedule_rows)
    unmet = np.array([sol[u_idx[b]] for b in tasks.index])
    green_used = np.array([[sol[g_idx[(i, t)]] for t in range(H)] for i in range(I)])
    return res, schedule, unmet, green_used, elapsed


def greedy_instant_baseline(nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available, policy="local"):
    """本地立即执行 / 最近节点立即执行。为保持可比性，baseline对可得绿电采用“优先使用”规则。"""
    I, H = capacity.shape
    rem_capacity = capacity.copy().astype(float)
    rem_bandwidth = bandwidth.copy().astype(float)
    rows = []
    unmet = np.ones(len(tasks))

    order = sorted(tasks.index, key=lambda b: (int(tasks.loc[b, "arrival"]), int(tasks.loc[b, "max_defer"])))

    for b in order:
        r = tasks.loc[b]
        t = int(r.arrival)
        q = float(r.demand_cu)
        data_gb = q * float(r.data_gb_per_cu)

        if policy == "local":
            candidates = [0] if float(nodes.loc[0, "latency_ms"]) <= float(r.max_latency) else []
        elif policy == "nearest":
            candidates = [
                i for i in np.argsort(nodes.latency_ms.values, kind="stable")
                if float(nodes.loc[i, "latency_ms"]) <= float(r.max_latency)
            ]
        else:
            raise ValueError("policy must be local or nearest")

        for i in candidates:
            if rem_capacity[i, t] + 1e-9 >= q and rem_bandwidth[i, t] + 1e-9 >= data_gb:
                rows.append({
                    "task_id": b,
                    "batch": r.batch,
                    "type": r.type,
                    "arrival": t,
                    "node_i": i,
                    "node": nodes.loc[i, "node"],
                    "exec_hour": t,
                    "workload_cu": q,
                    "delay_h": 0,
                })
                rem_capacity[i, t] -= q
                rem_bandwidth[i, t] -= data_gb
                unmet[b] = 0.0
                break

    schedule = pd.DataFrame(rows)
    energy = np.zeros_like(grid_price)
    for _, r in schedule.iterrows():
        i, t = int(r.node_i), int(r.exec_hour)
        energy[i, t] += float(r.workload_cu) * float(nodes.loc[i, "energy_kwh_per_cu"])

    green_used = np.minimum(energy, green_available)
    return schedule, unmet, green_used, 0.0


def evaluate(nodes, tasks, schedule, unmet, green_used, grid_price, grid_ci, green_available, solve_time,
             green_premium=GREEN_CERT_PREMIUM_CNY_KWH):
    """统一计算成本、SLA、绿电与三类碳指标。"""
    I, H = grid_price.shape
    energy = np.zeros((I, H))
    migration_cost = 0.0
    weighted_delay = 0.0

    for _, r in schedule.iterrows():
        b, i, t = int(r.task_id), int(r.node_i), int(r.exec_hour)
        q = float(r.workload_cu)
        task = tasks.loc[b]
        energy[i, t] += q * float(nodes.loc[i, "energy_kwh_per_cu"])
        migration_cost += q * float(task.data_gb_per_cu) * float(nodes.loc[i, "migration_fee_cny_gb"])
        weighted_delay += q * (t - int(task.arrival))

    green_used = np.minimum(green_used, energy)
    residual_energy = np.maximum(energy - green_used, 0.0)

    # 成本：全部电量支付分时普通电价；可追溯绿电额外支付绿证等价溢价。
    electricity_cost = float((energy * grid_price).sum())
    green_premium_cost = float(green_used.sum()) * green_premium
    cash_cost = electricity_cost + green_premium_cost + migration_cost

    # 1) 调度碳代理：用于优化与展示“区域电力结构 + 绿电替代”的调度影响。
    dispatch_carbon = float((residual_energy * grid_ci).sum())

    # 2) 位置法：使用省级平均因子，对总用电计量；绿电采购不从位置法中扣除。
    location_carbon = float((energy * grid_ci).sum())

    # 3) 市场法：可追溯绿电按0；剩余购电使用0.6096 kgCO2/kWh。
    market_carbon = float(residual_energy.sum() * MARKET_RESIDUAL_CI_KG_KWH)

    total_demand = float(tasks.demand_cu.sum())
    completed = sum(float(tasks.loc[b, "demand_cu"]) * (1.0 - float(unmet[b])) for b in tasks.index)
    sla_workload = completed  # 被创建/安排的变量均满足deadline与网络时延约束。

    return {
        "任务完成率_%": 100.0 * completed / total_demand,
        "SLA满足率_%": 100.0 * sla_workload / total_demand,
        "现金成本_CNY": cash_cost,
        "其中绿电溢价_CNY": green_premium_cost,
        "调度碳代理_kgCO2": dispatch_carbon,
        "位置法碳排_kgCO2": location_carbon,
        "市场法碳排_kgCO2": market_carbon,
        "单位成本_CNY_per_1000CU": 1000.0 * cash_cost / completed if completed > 0 else np.nan,
        "位置法单位碳排_kg_per_1000CU": 1000.0 * location_carbon / completed if completed > 0 else np.nan,
        "市场法单位碳排_kg_per_1000CU": 1000.0 * market_carbon / completed if completed > 0 else np.nan,
        "绿电占比_%": 100.0 * float(green_used.sum()) / float(energy.sum()) if energy.sum() > 0 else 0.0,
        "绿电利用率_%": 100.0 * float(green_used.sum()) / float(green_available.sum()) if green_available.sum() > 0 else 0.0,
        "平均延迟_h": weighted_delay / completed if completed > 0 else np.nan,
        "求解时间_s": solve_time,
    }


def export_inputs(nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available, prefix="public_v2"):
    nodes.to_csv(OUT_DIR / f"{prefix}_nodes.csv", index=False, encoding="utf-8-sig")
    tasks.to_csv(OUT_DIR / f"{prefix}_tasks.csv", index=False, encoding="utf-8-sig")

    I, H = capacity.shape
    hourly_rows = []
    for i in range(I):
        for t in range(H):
            hourly_rows.append({
                "node": nodes.loc[i, "node"],
                "node_i": i,
                "hour": t,
                "hour_of_day": t % 24,
                "capacity_cu": capacity[i, t],
                "bandwidth_gb": bandwidth[i, t],
                "grid_price_cny_kwh": grid_price[i, t],
                "grid_ci_kg_kwh": grid_ci[i, t],
                "green_available_kwh": green_available[i, t],
                "green_price_proxy_cny_kwh": grid_price[i, t] + GREEN_CERT_PREMIUM_CNY_KWH,
            })
    pd.DataFrame(hourly_rows).to_csv(OUT_DIR / f"{prefix}_node_hourly.csv", index=False, encoding="utf-8-sig")


def run_experiment(green_policy_scenario=False, prefix="public_v2"):
    nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = make_public_calibrated_data(
        seed=42, green_policy_scenario=green_policy_scenario
    )
    export_inputs(nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available, prefix=prefix)

    result_rows = []
    schedules = {}

    # 1 本地立即执行
    sched, unmet, g, elapsed = greedy_instant_baseline(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available, policy="local"
    )
    schedules["本地立即执行"] = sched
    result_rows.append({"方案": "本地立即执行", **evaluate(
        nodes, tasks, sched, unmet, g, grid_price, grid_ci, green_available, elapsed
    )})

    # 2 最近节点
    sched, unmet, g, elapsed = greedy_instant_baseline(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available, policy="nearest"
    )
    schedules["最近节点"] = sched
    result_rows.append({"方案": "最近节点", **evaluate(
        nodes, tasks, sched, unmet, g, grid_price, grid_ci, green_available, elapsed
    )})

    # 3 成本优先
    _, sched, unmet, g, elapsed = solve_milp(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="cost", carbon_price=0.0
    )
    schedules["成本优先MILP"] = sched
    result_rows.append({"方案": "成本优先MILP", **evaluate(
        nodes, tasks, sched, unmet, g, grid_price, grid_ci, green_available, elapsed
    )})

    # 4 碳优先
    _, sched, unmet, g, elapsed = solve_milp(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="carbon", carbon_price=0.0
    )
    schedules["碳优先MILP"] = sched
    result_rows.append({"方案": "碳优先MILP", **evaluate(
        nodes, tasks, sched, unmet, g, grid_price, grid_ci, green_available, elapsed
    )})

    # 5 协同优化
    _, sched, unmet, g, elapsed = solve_milp(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="multi", carbon_price=DEFAULT_SHADOW_CARBON_PRICE
    )
    schedules["电碳算协同MILP"] = sched
    result_rows.append({"方案": "电碳算协同MILP", **evaluate(
        nodes, tasks, sched, unmet, g, grid_price, grid_ci, green_available, elapsed
    )})

    results = pd.DataFrame(result_rows)
    results.to_csv(OUT_DIR / f"{prefix}_results.csv", index=False, encoding="utf-8-sig")
    schedules["电碳算协同MILP"].to_csv(OUT_DIR / f"{prefix}_our_schedule.csv", index=False, encoding="utf-8-sig")

    node_summary = (
        schedules["电碳算协同MILP"]
        .groupby(["node", "type"], as_index=False)["workload_cu"]
        .sum()
        .sort_values(["node", "type"])
    )
    node_summary.to_csv(OUT_DIR / f"{prefix}_our_node_summary.csv", index=False, encoding="utf-8-sig")

    return results



# ==========================================================
# 六组压力测试（Stress Tests）
# ==========================================================
# 设计原则：
# 1) 每个压力点都在同一场景下同时求解“成本优先MILP”和“电碳算协同MILP”；
# 2) 输出协同方案绝对指标 + 相对成本优先的成本/碳差异；
# 3) 除被测试参数外，其余参数保持不变（ceteris paribus）；
# 4) 所有冲击均为情景测试，不表述为真实企业运行预测。

STRESS_OUT_DIR = OUT_DIR / "stress_outputs"
STRESS_OUT_DIR.mkdir(exist_ok=True)


def _pct_change(new, old):
    return 100.0 * (new - old) / old if abs(old) > 1e-12 else np.nan


def _schedule_node_shares(nodes, schedule):
    total = float(schedule["workload_cu"].sum()) if not schedule.empty else 0.0
    out = {}
    for node in nodes["node"]:
        v = float(schedule.loc[schedule["node"] == node, "workload_cu"].sum()) if not schedule.empty else 0.0
        out[f"节点占比_{node}_%"] = 100.0 * v / total if total > 0 else 0.0
    return out


def _solve_and_compare(
    nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
    shadow_carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
    label="",
    stress_group="",
    stress_value=np.nan,
):
    """同一压力场景下，分别运行成本优先与协同优化，并生成一行可直接用于画图/写BP的结果。"""
    # 成本优先
    _, sched_cost, unmet_cost, g_cost, t_cost = solve_milp(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="cost", carbon_price=0.0
    )
    eval_cost = evaluate(
        nodes, tasks, sched_cost, unmet_cost, g_cost,
        grid_price, grid_ci, green_available, t_cost
    )

    # 电—碳—算协同
    _, sched_multi, unmet_multi, g_multi, t_multi = solve_milp(
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
        mode="multi", carbon_price=shadow_carbon_price
    )
    eval_multi = evaluate(
        nodes, tasks, sched_multi, unmet_multi, g_multi,
        grid_price, grid_ci, green_available, t_multi
    )

    row = {
        "压力测试": stress_group,
        "场景": label,
        "参数值": stress_value,
        "影子碳价_CNY_per_kg": shadow_carbon_price,
        **{f"协同_{k}": v for k, v in eval_multi.items()},
        **{f"成本优先_{k}": v for k, v in eval_cost.items()},
    }

    # 相对成本优先的关键权衡
    row.update({
        "相对成本优先_现金成本变化_%": _pct_change(eval_multi["现金成本_CNY"], eval_cost["现金成本_CNY"]),
        "相对成本优先_调度碳代理下降_%": -_pct_change(eval_multi["调度碳代理_kgCO2"], eval_cost["调度碳代理_kgCO2"]),
        "相对成本优先_位置法碳排下降_%": -_pct_change(eval_multi["位置法碳排_kgCO2"], eval_cost["位置法碳排_kgCO2"]),
        "相对成本优先_市场法碳排下降_%": -_pct_change(eval_multi["市场法碳排_kgCO2"], eval_cost["市场法碳排_kgCO2"]),
        "相对成本优先_绿电占比变化_pp": eval_multi["绿电占比_%"] - eval_cost["绿电占比_%"],
        "相对成本优先_SLA变化_pp": eval_multi["SLA满足率_%"] - eval_cost["SLA满足率_%"],
    })
    row.update(_schedule_node_shares(nodes, sched_multi))
    return row


def stress_test_carbon_price(seed=42):
    """压力测试1：影子碳价/碳成本偏好。单位：CNY/kgCO2。"""
    values = [0.00, 0.05, 0.10, 0.25, 0.50, 1.00]
    rows = []
    for v in values:
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = make_public_calibrated_data(seed=seed)
        rows.append(_solve_and_compare(
            nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available,
            shadow_carbon_price=v,
            label=f"影子碳价={v:.2f}元/kg",
            stress_group="1_碳价压力",
            stress_value=v,
        ))
    return pd.DataFrame(rows)


def stress_test_electricity_price(seed=42):
    """压力测试2：全市场电价水平冲击。1.0为2026年6月公开校准基准。"""
    values = [0.80, 0.90, 1.00, 1.10, 1.25, 1.50]
    rows = []
    for factor in values:
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = make_public_calibrated_data(seed=seed)
        shocked_price = grid_price * factor
        rows.append(_solve_and_compare(
            nodes, tasks, capacity, bandwidth, shocked_price, grid_ci, green_available,
            shadow_carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
            label=f"电价×{factor:.2f}",
            stress_group="2_电价压力",
            stress_value=factor,
        ))
    return pd.DataFrame(rows)


def stress_test_green_supply(seed=42):
    """压力测试3：绿电可得量冲击。保持小时形状不变，整体缩放可得量。"""
    values = [0.40, 0.60, 0.80, 1.00, 1.20, 1.50]
    rows = []
    for factor in values:
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = make_public_calibrated_data(seed=seed)
        green_shocked = green_available * factor
        rows.append(_solve_and_compare(
            nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_shocked,
            shadow_carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
            label=f"绿电可得量×{factor:.2f}",
            stress_group="3_绿电比例压力",
            stress_value=factor,
        ))
    return pd.DataFrame(rows)


def _apply_sla_factor(tasks, factor):
    """同时收紧/放宽最大可延迟时间和最大网络时延。实时任务max_defer仍保持0。"""
    t = tasks.copy(deep=True)
    t["max_latency"] = np.maximum(1.0, t["max_latency"].astype(float) * factor)

    def scale_defer(row):
        old = int(row["max_defer"])
        if old == 0:
            return 0
        # 收紧时向下取整，放宽时四舍五入；至少保留1小时给非实时任务。
        return max(1, int(round(old * factor)))

    t["max_defer"] = t.apply(scale_defer, axis=1)
    return t


def stress_test_sla(seed=42):
    """压力测试4：SLA严格程度。<1表示收紧，>1表示放宽。"""
    values = [0.50, 0.70, 0.85, 1.00, 1.20, 1.50]
    rows = []
    for factor in values:
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = make_public_calibrated_data(seed=seed)
        tasks_sla = _apply_sla_factor(tasks, factor)
        rows.append(_solve_and_compare(
            nodes, tasks_sla, capacity, bandwidth, grid_price, grid_ci, green_available,
            shadow_carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
            label=f"SLA阈值×{factor:.2f}",
            stress_group="4_SLA压力",
            stress_value=factor,
        ))
    return pd.DataFrame(rows)


def _reshape_green_volatility(green_available, volatility_factor):
    """
    在每个节点“总绿电量不变”的前提下改变小时波动强度：
      0   -> 完全平滑；
      1   -> 基准曲线；
      >1  -> 波动放大。
    这样可把“绿电总量效应”和“时序波动效应”分开。
    """
    g = np.asarray(green_available, dtype=float)
    out = np.zeros_like(g)
    for i in range(g.shape[0]):
        base = g[i].copy()
        total = base.sum()
        mean = base.mean()
        shaped = mean + volatility_factor * (base - mean)
        shaped = np.clip(shaped, 0.0, None)
        if shaped.sum() <= 1e-12:
            shaped[:] = 1.0
        out[i] = shaped / shaped.sum() * total
    return out


def stress_test_green_volatility(seed=42):
    """压力测试5：绿电小时波动。在总绿电量固定下，仅改变时序集中程度。"""
    values = [0.00, 0.50, 1.00, 1.50, 2.00, 3.00]
    rows = []
    for v in values:
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = make_public_calibrated_data(seed=seed)
        green_shocked = _reshape_green_volatility(green_available, v)
        rows.append(_solve_and_compare(
            nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_shocked,
            shadow_carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
            label=f"绿电波动系数={v:.2f}",
            stress_group="5_绿电波动压力",
            stress_value=v,
        ))
    return pd.DataFrame(rows)


def stress_test_demand_shock(seed=42):
    """压力测试6：算力需求冲击。1.0为基准业务负载。"""
    values = [0.70, 0.85, 1.00, 1.15, 1.30, 1.50]
    rows = []
    for factor in values:
        nodes, tasks, capacity, bandwidth, grid_price, grid_ci, green_available = make_public_calibrated_data(seed=seed)
        tasks_shocked = tasks.copy(deep=True)
        tasks_shocked["demand_cu"] = tasks_shocked["demand_cu"].astype(float) * factor
        rows.append(_solve_and_compare(
            nodes, tasks_shocked, capacity, bandwidth, grid_price, grid_ci, green_available,
            shadow_carbon_price=DEFAULT_SHADOW_CARBON_PRICE,
            label=f"算力需求×{factor:.2f}",
            stress_group="6_需求冲击",
            stress_value=factor,
        ))
    return pd.DataFrame(rows)


def run_all_stress_tests(seed=42):
    tests = [
        ("stress_01_carbon_price.csv", stress_test_carbon_price),
        ("stress_02_electricity_price.csv", stress_test_electricity_price),
        ("stress_03_green_supply.csv", stress_test_green_supply),
        ("stress_04_sla.csv", stress_test_sla),
        ("stress_05_green_volatility.csv", stress_test_green_volatility),
        ("stress_06_demand_shock.csv", stress_test_demand_shock),
    ]

    dfs = []
    for fn, func in tests:
        print(f"Running {func.__name__} ...")
        df = func(seed=seed)
        df.to_csv(STRESS_OUT_DIR / fn, index=False, encoding="utf-8-sig")
        dfs.append(df)

    all_results = pd.concat(dfs, ignore_index=True)
    all_results.to_csv(STRESS_OUT_DIR / "stress_all_results.csv", index=False, encoding="utf-8-sig")

    # BP用精简表：只保留最重要的技术指标。
    key_cols = [
        "压力测试", "场景", "参数值",
        "协同_任务完成率_%", "协同_SLA满足率_%", "协同_现金成本_CNY",
        "协同_单位成本_CNY_per_1000CU",
        "协同_调度碳代理_kgCO2", "协同_位置法碳排_kgCO2", "协同_市场法碳排_kgCO2",
        "协同_绿电占比_%", "协同_绿电利用率_%", "协同_平均延迟_h", "协同_求解时间_s",
        "相对成本优先_现金成本变化_%", "相对成本优先_调度碳代理下降_%",
        "相对成本优先_位置法碳排下降_%", "相对成本优先_市场法碳排下降_%",
        "相对成本优先_绿电占比变化_pp", "相对成本优先_SLA变化_pp",
    ]
    summary = all_results[key_cols].copy()
    summary.to_csv(STRESS_OUT_DIR / "stress_bp_summary.csv", index=False, encoding="utf-8-sig")
    return all_results, summary


def main():
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 280)

    print("=== 电—碳—算协同调度：六组压力测试 v3 ===")
    print("基准：public-calibrated v2；所有冲击均为情景测试。")
    all_results, summary = run_all_stress_tests(seed=42)

    print("\n=== BP精简结果 ===")
    show_cols = [
        "压力测试", "场景",
        "协同_任务完成率_%", "协同_SLA满足率_%", "协同_现金成本_CNY",
        "协同_调度碳代理_kgCO2", "协同_绿电占比_%",
        "相对成本优先_现金成本变化_%", "相对成本优先_调度碳代理下降_%",
    ]
    print(summary[show_cols].round(3).to_string(index=False))

    print("\n输出目录：", STRESS_OUT_DIR)
    for fn in [
        "stress_01_carbon_price.csv",
        "stress_02_electricity_price.csv",
        "stress_03_green_supply.csv",
        "stress_04_sla.csv",
        "stress_05_green_volatility.csv",
        "stress_06_demand_shock.csv",
        "stress_all_results.csv",
        "stress_bp_summary.csv",
    ]:
        print(" -", STRESS_OUT_DIR / fn)


if __name__ == "__main__":
    main()
