import streamlit as st
import pandas as pd
import numpy as np
from core.ui import page_header
from core.data_loader import load_nodes, load_hourly_parameters, load_baseline_results, load_reference_schedule


def render():
    page_header("运行总览", "多节点电力、碳强度、绿电与算力负载的一体化运营视图")
    nodes = load_nodes(); hourly = load_hourly_parameters(); results = load_baseline_results(); sched = load_reference_schedule()
    our = results.loc[results["方案"] == "电碳算协同MILP"].iloc[0]
    live_sol = st.session_state.get("dispatch_solution")
    if live_sol:
        ls = live_sol["summary"]
        sched = live_sol["schedule"]
        st.caption("当前总览已切换为最近一次“智能调度”实时求解结果。")
    else:
        ls = None
        st.caption("当前总览显示公开校准基准场景；完成一次“智能调度”后会自动切换到最新求解结果。")
    hour = st.slider("查看运行时刻（情景小时）", 0, 23, 12, 1)

    cols = st.columns(6)
    vals = [
        ("任务规模", f"{sched['workload_cu'].sum():,.0f} CU"),
        ("预计运行成本", f"¥{(ls['cash_cost'] if ls else our['现金成本_CNY']):,.1f}"),
        ("调度碳代理", f"{(ls['dispatch_carbon'] if ls else our['调度碳代理_kgCO2']):,.1f} kg"),
        ("SLA满足率", f"{(ls['sla_rate'] if ls else our['SLA满足率_%']):.1f}%"),
        ("绿电占比", f"{(ls['green_share'] if ls else our['绿电占比_%']):.1f}%"),
        ("任务完成率", f"{(ls['completion_rate'] if ls else our['任务完成率_%']):.1f}%"),
    ]
    for c, (k, v) in zip(cols, vals): c.metric(k, v)

    st.markdown("### 节点运行状态")
    cards = st.columns(4)
    for c, (_, n) in zip(cards, nodes.iterrows()):
        node = n["node"]
        h = hourly[(hourly.node == node) & (hourly.hour_of_day == hour)].iloc[0]
        used = float(sched[(sched.node == node) & ((sched.exec_hour % 24) == hour)]["workload_cu"].sum())
        load = 100 * used / h.capacity_cu if h.capacity_cu else 0
        if load >= 90: status, cls = "容量风险", "status-risk"
        elif load >= 75: status, cls = "负载偏高", "status-warn"
        else: status, cls = "运行正常", "status-ok"
        c.markdown(f'''<div class="node-card"><div class="node-name">{node.replace('_','·')}</div>
        <div class="node-grid">
        <span>可用算力</span><b>{h.capacity_cu:.1f} CU</b>
        <span>当前负载</span><b>{load:.1f}%</b>
        <span>电价</span><b>{h.grid_price_cny_kwh:.3f} 元/kWh</b>
        <span>碳强度</span><b>{n.grid_ci_kg_kwh:.4f} kg/kWh</b>
        <span>绿电基准</span><b>{n.green_share_base*100:.1f}%</b>
        <span>PUE</span><b>{n.pue:.2f}</b>
        <span>网络时延</span><b>{n.latency_ms:.0f} ms</b>
        <span>节点状态</span><span class="{cls}">{status}</span>
        </div></div>''', unsafe_allow_html=True)

    st.markdown("### 当前基准场景解释")
    st.info("当前总览基于公开参数校准 + 情景仿真。它用于展示调度系统原型能力，不等同于具体数据中心生产环境实测。")
