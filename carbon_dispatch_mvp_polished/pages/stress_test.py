from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.ui import page_header, section_header, decision_callout, signal_strip, style_plot, PLOTLY_CONFIG
from core.data_loader import load_nodes, load_hourly_parameters, load_tasks, load_stress_summary
from core.scenarios import run_stress_scenario

PRESETS = {
    "自定义": dict(carbon=.25, elec=1.0, green=1.0, sla=1.0, volatility=1.0, demand=1.0),
    "基准场景": dict(carbon=.25, elec=1.0, green=1.0, sla=1.0, volatility=1.0, demand=1.0),
    "高碳价｜1.00元/kg": dict(carbon=1.0, elec=1.0, green=1.0, sla=1.0, volatility=1.0, demand=1.0),
    "绿电紧张｜0.40×": dict(carbon=.25, elec=1.0, green=.4, sla=1.0, volatility=1.0, demand=1.0),
    "绿电充足｜1.50×": dict(carbon=.25, elec=1.0, green=1.5, sla=1.0, volatility=1.0, demand=1.0),
    "高波动｜3.00×": dict(carbon=.25, elec=1.0, green=1.0, sla=1.0, volatility=3.0, demand=1.0),
    "需求冲击｜1.30×": dict(carbon=.25, elec=1.0, green=1.0, sla=1.0, volatility=1.0, demand=1.3),
}

FRIENDLY = {
    "1_碳价压力": "碳价压力",
    "2_电价压力": "电价压力",
    "3_绿电比例压力": "绿电供给压力",
    "4_SLA压力": "SLA压力",
    "5_绿电波动压力": "绿电波动压力",
    "6_需求冲击": "算力需求冲击",
}


def _scenario_conclusion(group: str, sub: pd.DataFrame) -> str:
    sub = sub.sort_values("参数值")
    first, last = sub.iloc[0], sub.iloc[-1]
    if "碳价" in group:
        return f"影子碳价从 {first['参数值']:.2f} 提高到 {last['参数值']:.2f} 后，成本增幅由 {first['相对成本优先_现金成本变化_%']:.2f}% 变化至 {last['相对成本优先_现金成本变化_%']:.2f}%，调度碳代理下降由 {first['相对成本优先_调度碳代理下降_%']:.2f}% 提高至 {last['相对成本优先_调度碳代理下降_%']:.2f}%。"
    if "绿电" in group and "波动" not in group:
        return f"绿电可得量从 {first['参数值']:.2f}× 提升至 {last['参数值']:.2f}× 时，协同绿电占比由 {first['协同_绿电占比_%']:.2f}% 提升至 {last['协同_绿电占比_%']:.2f}%，市场法碳排相对成本优先的下降幅度同步扩大。"
    if "绿电波动" in group:
        return f"保持绿电总量口径不变、仅增强时序波动时，最高测试波动系数 {last['参数值']:.2f}× 下任务完成率仍为 {last['协同_任务完成率_%']:.1f}%，SLA 为 {last['协同_SLA满足率_%']:.1f}%。"
    if "需求冲击" in group:
        bad = sub[sub["协同_任务完成率_%"] < 99.999]
        if not bad.empty:
            r = bad.iloc[0]
            return f"在当前4节点情景下，需求倍率达到 {r['参数值']:.2f}× 时首次出现任务无法全部完成，完成率降至 {r['协同_任务完成率_%']:.2f}%。容量边界应由实时求解识别，而不是写死为固定阈值。"
    return f"该单因素测试覆盖参数区间 {first['参数值']:.2f}–{last['参数值']:.2f}，用于观察协同方案在参数变化下的成本、碳排与SLA响应。"


def render():
    page_header("压力测试", "组合调整碳价、电价、绿电、SLA、绿电波动和算力需求，并重新求解")

    section_header("组合压力场景", "先选择一个现场演示预设，再按需微调六类参数。所有风险提示均来自本次实时求解。")
    preset_name = st.selectbox("快速场景", list(PRESETS), index=1, key="stress_preset")
    p = PRESETS[preset_name]
    key_suffix = preset_name.replace("｜", "_").replace("/", "_")

    a, b, c = st.columns(3)
    carbon = a.slider("影子碳价 / 元·kgCO₂⁻¹", 0.0, 1.0, float(p["carbon"]), 0.05, key=f"stress_carbon_{key_suffix}")
    elec = b.slider("电价倍率", 0.8, 1.5, float(p["elec"]), 0.05, key=f"stress_elec_{key_suffix}")
    green = c.slider("绿电可得量倍率", 0.4, 1.5, float(p["green"]), 0.05, key=f"stress_green_{key_suffix}")
    d, e, f = st.columns(3)
    sla = d.slider("SLA阈值倍率", 0.5, 1.5, float(p["sla"]), 0.05, key=f"stress_sla_{key_suffix}")
    volatility = e.slider("绿电波动系数", 0.0, 3.0, float(p["volatility"]), 0.1, key=f"stress_vol_{key_suffix}")
    demand = f.slider("算力需求倍率", 0.7, 1.5, float(p["demand"]), 0.05, key=f"stress_demand_{key_suffix}")

    signal_strip([
        ("碳价", f"{carbon:.2f} 元/kg"),
        ("电价 / 绿电", f"{elec:.2f}× / {green:.2f}×"),
        ("SLA / 波动", f"{sla:.2f}× / {volatility:.2f}×"),
        ("算力需求", f"{demand:.2f}×"),
    ])

    if st.button("重新计算组合压力场景", type="primary", use_container_width=True):
        nodes = load_nodes(); hourly = load_hourly_parameters(); tasks = load_tasks()
        with st.spinner("正在对成本优先与协同方案分别求解…"):
            out = run_stress_scenario(nodes, hourly, tasks, carbon, elec, green, sla, volatility, demand, 5.0)
        st.session_state.stress_out = out
        st.session_state.stress_label = preset_name

    out = st.session_state.get("stress_out")
    if out:
        s = out["multi"]["summary"]
        dlt = out["comparison"]
        risk = s["completion_rate"] < 99.999 or s["peak_load_rate"] > 95
        decision_callout(
            "压力场景结论",
            f"相较同一压力场景下的成本优先策略：现金成本 {dlt['cost_change_pct']:+.2f}%，"
            f"调度碳代理下降 {dlt['dispatch_reduction_pct']:.2f}%，市场法碳排下降 {dlt['market_reduction_pct']:.2f}%。"
            f"任务完成率 {s['completion_rate']:.2f}%，峰值负载 {s['peak_load_rate']:.1f}%。",
        )
        c = st.columns(7)
        for col, (k, v) in zip(c, [
            ("成本", f"¥{s['cash_cost']:.1f}"), ("调度碳", f"{s['dispatch_carbon']:.1f}kg"), ("位置法", f"{s['location_carbon']:.1f}kg"),
            ("市场法", f"{s['market_carbon']:.1f}kg"), ("SLA", f"{s['sla_rate']:.1f}%"), ("完成率", f"{s['completion_rate']:.1f}%"), ("绿电占比", f"{s['green_share']:.1f}%"),
        ]):
            col.metric(k, v)
        signal_strip([
            ("容量风险", "高" if risk else "可控"),
            ("峰值负载", f"{s['peak_load_rate']:.1f}%"),
            ("平均负载", f"{s['avg_load_rate']:.1f}%"),
            ("求解时间", f"{s['solve_time']:.3f} s"),
        ])
        if risk:
            st.warning("当前算力需求已接近或超过容量安全区间。风险提示依据本次实时求解结果，而非固定1.30阈值。")
        else:
            st.success("当前组合压力下任务仍位于可行容量区间。")

    section_header("既有单因素压力测试", "直接读取此前已完成的压力测试结果，适合在答辩追问时快速展示敏感性与边界。")
    hist = load_stress_summary().copy()
    choices = hist["压力测试"].drop_duplicates().tolist()
    display = {x: FRIENDLY.get(x, x) for x in choices}
    group = st.selectbox("选择压力类型", choices, format_func=lambda x: display[x], key="stress_hist_group")
    sub = hist[hist["压力测试"] == group].copy().sort_values("参数值")
    decision_callout("单因素结论", _scenario_conclusion(group, sub))

    left, right = st.columns(2)
    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sub["参数值"], y=sub["相对成本优先_现金成本变化_%"], mode="lines+markers", name="现金成本变化 / %"))
        fig.add_trace(go.Scatter(x=sub["参数值"], y=sub["相对成本优先_调度碳代理下降_%"], mode="lines+markers", name="调度碳代理下降 / %"))
        fig.update_layout(title=f"{display[group]}：成本—碳响应", xaxis_title="参数值", yaxis_title="变化 / %")
        style_plot(fig, height=350)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    with right:
        if "需求冲击" in group:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=sub["参数值"], y=sub["协同_任务完成率_%"], mode="lines+markers", name="任务完成率 / %"))
            fig2.add_trace(go.Scatter(x=sub["参数值"], y=sub["协同_SLA满足率_%"], mode="lines+markers", name="SLA / %"))
            fig2.update_layout(title="容量边界：完成率与SLA", xaxis_title="需求倍率", yaxis_title="比例 / %", yaxis_range=[0, 105])
        else:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=sub["参数值"], y=sub["协同_绿电占比_%"], mode="lines+markers", name="绿电占比 / %"))
            fig2.add_trace(go.Scatter(x=sub["参数值"], y=sub["相对成本优先_市场法碳排下降_%"], mode="lines+markers", name="市场法碳排下降 / %"))
            fig2.update_layout(title=f"{display[group]}：绿电—市场法响应", xaxis_title="参数值", yaxis_title="比例 / %")
        style_plot(fig2, height=350)
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    with st.expander("查看该压力测试原始数据"):
        st.dataframe(sub.round(4), use_container_width=True, hide_index=True)
