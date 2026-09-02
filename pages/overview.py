from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.ui import page_header, section_header, decision_callout, signal_strip, style_plot, PLOTLY_CONFIG
from core.data_loader import load_nodes, load_hourly_parameters, load_baseline_results, load_reference_schedule


def _pct(new, old):
    return 100.0 * (new - old) / old if abs(old) > 1e-12 else 0.0


def render():
    page_header("运行总览", "多节点电力、碳强度、绿电与算力负载的一体化运营视图")
    nodes = load_nodes()
    hourly = load_hourly_parameters()
    results = load_baseline_results()
    sched = load_reference_schedule()

    our = results.loc[results["方案"] == "电碳算协同MILP"].iloc[0]
    cost_ref = results.loc[results["方案"] == "成本优先MILP"].iloc[0]
    live_sol = st.session_state.get("dispatch_solution")
    live_cost = st.session_state.get("dispatch_cost_solution")

    if live_sol:
        s = live_sol["summary"]
        sched = live_sol["schedule"].copy()
        baseline_s = live_cost["summary"] if live_cost else None
        scene_label = "最近一次实时求解"
    else:
        s = {
            "cash_cost": float(our["现金成本_CNY"]),
            "dispatch_carbon": float(our["调度碳代理_kgCO2"]),
            "location_carbon": float(our["位置法碳排_kgCO2"]),
            "market_carbon": float(our["市场法碳排_kgCO2"]),
            "sla_rate": float(our["SLA满足率_%"]),
            "completion_rate": float(our["任务完成率_%"]),
            "green_share": float(our["绿电占比_%"]),
            "avg_delay": float(our["平均延迟_h"]),
        }
        baseline_s = {
            "cash_cost": float(cost_ref["现金成本_CNY"]),
            "dispatch_carbon": float(cost_ref["调度碳代理_kgCO2"]),
            "market_carbon": float(cost_ref["市场法碳排_kgCO2"]),
        }
        scene_label = "公开校准基准场景"

    cost_change = _pct(s["cash_cost"], baseline_s["cash_cost"]) if baseline_s else 0.0
    dispatch_drop = -_pct(s["dispatch_carbon"], baseline_s["dispatch_carbon"]) if baseline_s else 0.0
    market_drop = -_pct(s["market_carbon"], baseline_s["market_carbon"]) if baseline_s else 0.0

    decision_callout(
        "当前决策摘要",
        f"{scene_label}：相较同一任务集的成本优先策略，现金成本 {cost_change:+.2f}%，"
        f"调度碳代理下降 {dispatch_drop:.2f}%，市场法碳排下降 {market_drop:.2f}%；"
        f"任务完成率 {s['completion_rate']:.1f}%，SLA 满足率 {s['sla_rate']:.1f}%。",
    )

    cols = st.columns(6)
    metrics = [
        ("任务规模", f"{sched['workload_cu'].sum():,.0f} CU"),
        ("预计运行成本", f"¥{s['cash_cost']:,.1f}"),
        ("调度碳代理", f"{s['dispatch_carbon']:,.1f} kg"),
        ("市场法碳排", f"{s['market_carbon']:,.1f} kg"),
        ("绿电占比", f"{s['green_share']:.1f}%"),
        ("SLA满足率", f"{s['sla_rate']:.1f}%"),
    ]
    for c, (k, v) in zip(cols, metrics):
        c.metric(k, v)

    signal_strip([
        ("策略状态", "协同调度已启用"),
        ("任务完成", f"{s['completion_rate']:.1f}%"),
        ("平均延迟", f"{s.get('avg_delay', 0.0):.2f} h"),
        ("数据口径", "公开校准 · 情景仿真"),
    ])

    section_header("节点运行状态", "选择一个情景小时，查看四个原型节点的算力、价格、绿电与负载状态。")
    hour = st.slider("查看运行时刻 / h", 0, 23, 12, 1, key="overview_hour")
    cards = st.columns(4)
    for c, (_, n) in zip(cards, nodes.iterrows()):
        node = n["node"]
        hrow = hourly[(hourly.node == node) & (hourly.hour == hour)].iloc[0]
        used = float(sched[(sched.node == node) & (sched.exec_hour == hour)]["workload_cu"].sum())
        load = 100 * used / float(hrow.capacity_cu) if hrow.capacity_cu else 0.0
        if load >= 90:
            status, cls = "容量风险", "status-risk"
        elif load >= 75:
            status, cls = "负载偏高", "status-warn"
        else:
            status, cls = "运行正常", "status-ok"
        c.markdown(
            f'''<div class="node-card"><div class="node-name">{node.replace('_','·')}</div>
            <div class="node-sub">情景时刻 {hour:02d}:00 · 原型节点</div>
            <div class="node-grid">
            <span>可用算力</span><b>{hrow.capacity_cu:.1f} CU</b>
            <span>已分配负载</span><b>{used:.1f} CU</b>
            <span>当前负载率</span><b>{load:.1f}%</b>
            <span>分时电价</span><b>{hrow.grid_price_cny_kwh:.3f} 元/kWh</b>
            <span>电网碳强度</span><b>{n.grid_ci_kg_kwh:.4f} kg/kWh</b>
            <span>绿电可得</span><b>{hrow.green_available_kwh:.1f} kWh</b>
            <span>PUE</span><b>{n.pue:.2f}</b>
            <span>网络时延</span><b>{n.latency_ms:.0f} ms</b>
            <span>节点状态</span><b class="{cls}">{status}</b>
            </div></div>''',
            unsafe_allow_html=True,
        )

    section_header("24h 运转轮廓", "一眼观察任务在节点与时段之间的迁移，以及可利用的能源条件。")
    left, right = st.columns([1.12, 1.0])
    with left:
        curve = sched.groupby(["exec_hour", "node"], as_index=False)["workload_cu"].sum()
        curve["节点"] = curve["node"].str.replace("_", "·", regex=False)
        fig = px.bar(
            curve, x="exec_hour", y="workload_cu", color="节点",
            labels={"exec_hour": "执行时刻 / h", "workload_cu": "执行任务 / CU"},
            title="任务执行负载：节点 × 时段", barmode="stack",
        )
        style_plot(fig, height=330)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    with right:
        h24 = hourly[hourly["hour"] <= 23].groupby("hour", as_index=False).agg(
            avg_price=("grid_price_cny_kwh", "mean"),
            green=("green_available_kwh", "sum"),
        )
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=h24.hour, y=h24.avg_price, mode="lines+markers", name="平均电价 / 元·kWh⁻¹"))
        fig2.add_trace(go.Scatter(x=h24.hour, y=h24.green, mode="lines", name="全网绿电可得 / kWh", yaxis="y2"))
        fig2.update_layout(
            title="能源条件：平均电价与绿电可得量",
            xaxis_title="时刻 / h",
            yaxis=dict(title="平均电价 / 元·kWh⁻¹"),
            yaxis2=dict(title="绿电 / kWh", overlaying="y", side="right", showgrid=False),
        )
        style_plot(fig2, height=330)
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    st.info("当前页面用于原型演示。公开参数用于区域校准，实时容量、任务到达、小时级绿电等仍属于情景参数，不等同于具体数据中心生产环境实测。")
