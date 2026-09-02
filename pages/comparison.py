from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.ui import page_header, section_header, decision_callout, signal_strip, style_plot, PLOTLY_CONFIG
from core.data_loader import load_baseline_results, load_nodes, load_hourly_parameters, load_tasks
from core.solver import solve_dispatch


def _pct(new, old):
    return 100.0 * (new - old) / old if abs(old) > 1e-12 else 0.0


def _pareto_candidates(df: pd.DataFrame) -> pd.DataFrame:
    d = df.sort_values(["cash_cost", "dispatch_carbon"]).reset_index(drop=True)
    keep = []
    best_carbon = float("inf")
    for i, r in d.iterrows():
        if float(r.dispatch_carbon) < best_carbon - 1e-9:
            keep.append(i)
            best_carbon = float(r.dispatch_carbon)
    return d.loc[keep].copy()


def render():
    page_header("策略比较", "五类基准策略与成本—碳权衡，并可实时扫描不同碳权重下的候选前沿")
    df = load_baseline_results().copy()
    df["展示方案"] = df["方案"].replace({"电碳算协同MILP": "电—碳—算协同MILP"})

    cost = df.loc[df["方案"] == "成本优先MILP"].iloc[0]
    our = df.loc[df["方案"] == "电碳算协同MILP"].iloc[0]
    carbon = df.loc[df["方案"] == "碳优先MILP"].iloc[0]
    cost_delta = _pct(float(our["现金成本_CNY"]), float(cost["现金成本_CNY"]))
    carbon_drop = -_pct(float(our["调度碳代理_kgCO2"]), float(cost["调度碳代理_kgCO2"]))
    market_drop = -_pct(float(our["市场法碳排_kgCO2"]), float(cost["市场法碳排_kgCO2"]))

    decision_callout(
        "推荐平衡点",
        f"公开校准基准场景下，协同方案相较成本优先：现金成本 {cost_delta:+.2f}%，"
        f"调度碳代理下降 {carbon_drop:.2f}%，市场法碳排下降 {market_drop:.2f}%，且任务完成率与SLA均为100%。"
        "该结论属于仿真场景中的策略比较，不应表述为真实客户减碳绩效。",
    )
    signal_strip([
        ("最低现金成本", f"¥{cost['现金成本_CNY']:.1f} · 成本优先"),
        ("最低调度碳", f"{carbon['调度碳代理_kgCO2']:.1f} kg · 碳优先"),
        ("推荐平衡点", f"¥{our['现金成本_CNY']:.1f} / {our['调度碳代理_kgCO2']:.1f} kg"),
        ("推荐点绿电占比", f"{our['绿电占比_%']:.1f}%"),
    ])

    section_header("五类策略基线", "先看静态基线，再用下方权重扫描验证推荐点并非单一参数偶然结果。")
    show = df[[
        "展示方案", "任务完成率_%", "SLA满足率_%", "现金成本_CNY", "调度碳代理_kgCO2",
        "位置法碳排_kgCO2", "市场法碳排_kgCO2", "绿电占比_%", "平均延迟_h",
    ]].copy()
    show.columns = ["方案", "完成率/%", "SLA/%", "成本/元", "调度碳/kg", "位置法/kg", "市场法/kg", "绿电/%", "平均延迟/h"]
    st.dataframe(show.round(3), use_container_width=True, hide_index=True)

    fig = px.scatter(
        df,
        x="现金成本_CNY", y="调度碳代理_kgCO2", color="展示方案", text="展示方案",
        hover_data=["位置法碳排_kgCO2", "市场法碳排_kgCO2", "SLA满足率_%", "绿电占比_%"],
        title="成本—调度碳二维权衡",
        labels={"现金成本_CNY": "现金成本 / 元", "调度碳代理_kgCO2": "调度碳代理 / kgCO₂", "展示方案": "方案"},
    )
    fig.update_traces(textposition="top center", marker=dict(size=13, line=dict(width=1, color="white")))
    fig.add_annotation(
        x=float(our["现金成本_CNY"]), y=float(our["调度碳代理_kgCO2"]),
        text="推荐平衡点", showarrow=True, arrowhead=2, ax=45, ay=38,
    )
    style_plot(fig, height=430, legend_horizontal=False)
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    section_header("碳权重试算", "改变影子碳价 λc 后实时求解同一任务集，观察成本、碳排和绿电占比如何变化。")
    lam = st.slider("影子碳价 λc / 元·kgCO₂⁻¹", 0.0, 1.0, 0.25, 0.05, key="cmp_lam")
    if st.button("重新求解该权重", key="cmp_solve", type="primary", use_container_width=True):
        nodes = load_nodes(); hourly = load_hourly_parameters(); tasks = load_tasks()
        with st.spinner("正在求解该权重下的协同方案…"):
            sol = solve_dispatch(nodes, hourly, tasks, carbon_weight=lam, objective_mode="balanced", time_limit=5.0)
        st.session_state.cmp_sol = sol
        st.session_state.cmp_sol_lam = lam

    if st.session_state.get("cmp_sol"):
        s = st.session_state.cmp_sol["summary"]
        used_lam = st.session_state.get("cmp_sol_lam", lam)
        c = st.columns(6)
        c[0].metric("λc", f"{used_lam:.2f}")
        c[1].metric("成本", f"¥{s['cash_cost']:.1f}")
        c[2].metric("调度碳", f"{s['dispatch_carbon']:.1f} kg")
        c[3].metric("市场法", f"{s['market_carbon']:.1f} kg")
        c[4].metric("绿电占比", f"{s['green_share']:.1f}%")
        c[5].metric("求解时间", f"{s['solve_time']:.3f}s")
        if abs(used_lam - lam) > 1e-12:
            st.caption(f"当前显示的是上一次 λc={used_lam:.2f} 的求解结果；如需更新，请再次点击求解。")

    section_header("权重扫描候选前沿", "一次性扫描多个 λc 值并保留非支配候选点。MILP 的离散性意味着这是一组权重扫描候选前沿，而非连续问题的解析Pareto曲线。")
    if st.button("生成 9 点权重扫描", key="cmp_scan", use_container_width=True):
        nodes = load_nodes(); hourly = load_hourly_parameters(); tasks = load_tasks()
        weights = [0.00, 0.05, 0.10, 0.15, 0.25, 0.40, 0.60, 0.80, 1.00]
        rows = []
        progress = st.progress(0.0, text="正在扫描不同碳权重…")
        for i, w in enumerate(weights):
            sol = solve_dispatch(nodes, hourly, tasks, carbon_weight=w, objective_mode="balanced", time_limit=5.0)
            s = sol["summary"]
            rows.append({
                "lambda_c": w, "cash_cost": s["cash_cost"], "dispatch_carbon": s["dispatch_carbon"],
                "market_carbon": s["market_carbon"], "green_share": s["green_share"],
                "sla_rate": s["sla_rate"], "solve_time": s["solve_time"],
            })
            progress.progress((i + 1) / len(weights), text=f"已完成 {i+1}/{len(weights)} 个权重点")
        progress.empty()
        st.session_state.cmp_scan_df = pd.DataFrame(rows)

    scan = st.session_state.get("cmp_scan_df")
    if isinstance(scan, pd.DataFrame) and not scan.empty:
        front = _pareto_candidates(scan)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=scan.cash_cost, y=scan.dispatch_carbon, mode="markers+text", name="权重扫描点",
            text=[f"λ={x:.2f}" for x in scan.lambda_c], textposition="top center",
            customdata=scan[["lambda_c", "market_carbon", "green_share"]],
            hovertemplate="λ=%{customdata[0]:.2f}<br>成本=%{x:.2f}元<br>调度碳=%{y:.2f}kg<br>市场法=%{customdata[1]:.2f}kg<br>绿电=%{customdata[2]:.1f}%<extra></extra>",
        ))
        fig2.add_trace(go.Scatter(
            x=front.cash_cost, y=front.dispatch_carbon, mode="lines+markers", name="非支配候选前沿",
        ))
        fig2.update_layout(title="λc 权重扫描：成本—调度碳候选前沿", xaxis_title="现金成本 / 元", yaxis_title="调度碳代理 / kgCO₂")
        style_plot(fig2, height=430)
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
        st.dataframe(scan.round(4), use_container_width=True, hide_index=True)
