from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.ui import page_header, section_header, decision_callout, signal_strip, style_plot, PLOTLY_CONFIG
from core.data_loader import (
    load_baseline_results,
    load_ablation_results,
    load_monte_carlo_all,
    load_monte_carlo_summary,
    load_scalability_results,
    load_text,
)


def _summary_value(summary: pd.DataFrame, metric: str, col: str = "均值") -> float:
    row = summary.loc[summary["指标"] == metric]
    if row.empty:
        return float("nan")
    return float(row.iloc[0][col])


def _fmt_pct(x: float, digits: int = 2) -> str:
    return "—" if pd.isna(x) else f"{x:.{digits}f}%"


def render():
    page_header("技术验证", "有效性 → 机制来源 → 随机稳健性 → 规模求解能力，形成完整技术证据链")
    base = load_baseline_results().copy()
    abl = load_ablation_results().copy()
    mc = load_monte_carlo_all().copy()
    mc_summary = load_monte_carlo_summary().copy()
    sc = load_scalability_results().copy()

    cost_row = base.loc[base["方案"] == "成本优先MILP"].iloc[0]
    our_row = base.loc[base["方案"] == "电碳算协同MILP"].iloc[0]
    cost_delta = (our_row["现金成本_CNY"] / cost_row["现金成本_CNY"] - 1) * 100
    carbon_drop = (1 - our_row["调度碳代理_kgCO2"] / cost_row["调度碳代理_kgCO2"]) * 100
    market_drop = (1 - our_row["市场法碳排_kgCO2"] / cost_row["市场法碳排_kgCO2"]) * 100
    mean_carbon = _summary_value(mc_summary, "相对成本优先_调度碳下降_%")
    win_rate = _summary_value(mc_summary, "调度碳减排胜率_%")
    top = sc.iloc[-1]

    decision_callout(
        "证据链摘要",
        f"基准场景证明‘有效’：协同方案以 {cost_delta:.2f}% 成本增幅换取 {carbon_drop:.2f}% 调度碳指标下降；"
        f"消融实验解释‘为什么有效’；50组随机场景检验‘换参数是否稳定’，平均调度碳下降 {mean_carbon:.2f}%；"
        f"规模测试检验‘规模变大还能不能算’，最大测试为 {int(top['节点数'])} 节点、{int(top['任务批次数'])} 批任务。",
    )
    signal_strip([
        ("Baseline", "5类策略"),
        ("消融实验", f"{len(abl)}组"),
        ("Monte Carlo", f"{len(mc)}组 · 胜率{win_rate:.0f}%"),
        ("规模测试", f"4→{int(top['节点数'])}节点"),
    ])
    st.markdown('<div class="note">本页直接读取 validation_suite_v4 原始输出。所有结论属于公开参数校准与情景仿真，不代表真实数据中心生产环境实测。</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["① 有效性", "② 机制来源", "③ 随机稳健性", "④ 规模求解"])

    with tab1:
        section_header("Baseline：协同方案是否有效", "五类策略共享同一公开校准基准场景，用于建立成本、碳排、SLA和绿电利用的对照。")
        k = st.columns(4)
        k[0].metric("协同成本变化", f"+{cost_delta:.2f}%")
        k[1].metric("调度碳指标下降", f"{carbon_drop:.2f}%")
        k[2].metric("市场法碳排下降", f"{market_drop:.2f}%")
        k[3].metric("任务 / SLA", "100% / 100%")

        plot_df = base.copy()
        plot_df["展示方案"] = plot_df["方案"].replace({"电碳算协同MILP": "电—碳—算协同MILP"})
        fig = px.scatter(
            plot_df, x="现金成本_CNY", y="调度碳代理_kgCO2", color="展示方案", text="展示方案",
            hover_data=["市场法碳排_kgCO2", "绿电占比_%", "SLA满足率_%"],
            title="五类策略：成本—调度碳权衡",
            labels={"现金成本_CNY": "现金成本 / 元", "调度碳代理_kgCO2": "调度碳代理 / kgCO₂", "展示方案": "方案"},
        )
        fig.update_traces(textposition="top center", marker=dict(size=13, line=dict(width=1, color="white")))
        style_plot(fig, height=390, legend_horizontal=False)
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        with st.expander("查看5类策略原始结果"):
            cols = ["方案", "现金成本_CNY", "调度碳代理_kgCO2", "位置法碳排_kgCO2", "市场法碳排_kgCO2", "任务完成率_%", "SLA满足率_%", "绿电占比_%"]
            st.dataframe(base[cols].round(4), use_container_width=True, hide_index=True)
        st.caption("答辩口径：61.13%是‘调度碳代理下降’，不能简化成‘系统真实减碳61.13%’。位置法和市场法必须分开说明。")

    with tab2:
        section_header("消融：减碳来自哪里", "分别移除空间、时间和绿电时序感知机制，观察完整模型的边际价值。")
        no_space = abl.loc[abl["方案"] == "固定节点+时间迁移"].iloc[0]
        space_only = abl.loc[abl["方案"] == "仅空间迁移"].iloc[0]
        no_green = abl.loc[abl["方案"] == "无绿电感知"].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("取消空间决策", f"+{no_space['相对完整模型_调度碳恶化_%']:.2f}%", help="相对完整模型的调度碳恶化")
        c2.metric("取消时间调度", f"+{space_only['相对完整模型_调度碳恶化_%']:.2f}%", help="仅保留空间迁移")
        c3.metric("取消绿电时序感知", f"+{no_green['相对完整模型_调度碳恶化_%']:.2f}%")
        decision_callout("机制解释", "空间迁移是主要减碳来源；时间迁移进一步改善任务—能源匹配；绿电时序感知在此基础上继续提供边际优化。")

        chart_df = abl[["方案", "调度碳代理_kgCO2", "市场法碳排_kgCO2"]].melt(id_vars="方案", var_name="指标", value_name="kgCO2")
        fig = px.bar(chart_df, x="方案", y="kgCO2", color="指标", barmode="group", title="消融实验：不同机制组合下的碳指标")
        fig.update_layout(yaxis_title="kgCO₂", xaxis_title="")
        style_plot(fig, height=390)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        with st.expander("查看消融实验原始明细"):
            st.dataframe(abl.round(4), use_container_width=True, hide_index=True)

    with tab3:
        section_header("Monte Carlo：换参数是否稳定", "随机扰动任务需求、可用容量、电价与绿电供给，检查协同方案在50组运行情景中的表现。")
        mean_cost = _summary_value(mc_summary, "相对成本优先_现金成本变化_%")
        p05_carbon = _summary_value(mc_summary, "相对成本优先_调度碳下降_%", "P05")
        p95_carbon = _summary_value(mc_summary, "相对成本优先_调度碳下降_%", "P95")
        mean_market = _summary_value(mc_summary, "相对成本优先_市场法碳排下降_%")

        cols = st.columns(5)
        cols[0].metric("随机场景", f"{len(mc)}组")
        cols[1].metric("平均成本增幅", _fmt_pct(mean_cost))
        cols[2].metric("调度碳平均下降", _fmt_pct(mean_carbon))
        cols[3].metric("P05–P95", f"{p05_carbon:.2f}%–{p95_carbon:.2f}%")
        cols[4].metric("调度减碳胜率", _fmt_pct(win_rate, 0))

        scatter = px.scatter(
            mc, x="相对成本优先_现金成本变化_%", y="相对成本优先_调度碳下降_%",
            hover_data=["scenario_id", "需求总体系数", "平均容量系数", "平均电价系数", "平均绿电系数"],
            title="50组随机运行情景：成本—调度碳权衡",
            labels={"相对成本优先_现金成本变化_%": "现金成本变化 / %", "相对成本优先_调度碳下降_%": "调度碳指标下降 / %"},
        )
        scatter.add_hline(y=0, line_dash="dash", annotation_text="减碳分界")
        scatter.add_vline(x=float(mean_cost), line_dash="dot", annotation_text="平均成本增幅")
        scatter.add_hrect(y0=p05_carbon, y1=p95_carbon, opacity=.06, line_width=0, annotation_text="P05–P95")
        style_plot(scatter, height=420, legend_horizontal=False)
        st.plotly_chart(scatter, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption(f"50组随机情景中任务完成率与SLA满足率均保持100%；市场法碳排平均下降约{mean_market:.2f}%。这里是‘50组随机运行情景’，不能写成‘50家企业验证’。")
        with st.expander("查看 Monte Carlo 统计摘要与原始明细"):
            st.dataframe(mc_summary.round(4), use_container_width=True, hide_index=True)
            st.dataframe(mc.round(4), use_container_width=True, hide_index=True)

    with tab4:
        section_header("规模测试：规模变大还能不能算", "将4个公开校准原型节点复制并轻微扰动，形成8–20节点计算规模情景，测试求解时间与MIP Gap。")
        sc2 = sc.copy()
        sc2["MIP_Gap_%"] = sc2["MIP_Gap"] * 100.0
        sc2["求解状态简写"] = sc2["求解状态码"].map({0: "最优", 1: "达到时限"}).fillna("其他")
        top = sc2.iloc[-1]
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("最大测试节点", f"{int(top['节点数'])}")
        s2.metric("任务批次", f"{int(top['任务批次数'])}")
        s3.metric("二元变量", f"{int(top['二元变量数']):,}")
        s4.metric("原记录 MIP Gap", f"{top['MIP_Gap_%']:.3f}%")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sc2["节点数"], y=sc2["求解时间_s"], mode="lines+markers+text", text=[f"{x:.2f}s" for x in sc2["求解时间_s"]], textposition="top center", name="求解时间 / s"))
        fig.add_hline(y=5.0, line_dash="dash", annotation_text="5秒时限")
        fig.update_layout(title="规模扩展与求解时间", xaxis_title="节点数", yaxis_title="求解时间 / s")
        style_plot(fig, height=380)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        show_scale = sc2[["节点数", "任务批次数", "二元变量数", "约束数", "求解时间_s", "MIP_Gap_%", "求解状态简写", "任务完成率_%", "SLA满足率_%"]].copy()
        st.dataframe(show_scale.round({"求解时间_s": 3, "MIP_Gap_%": 3, "任务完成率_%": 2, "SLA满足率_%": 2}), use_container_width=True, hide_index=True)
        st.warning("16/20节点达到5秒时间上限，因此正确表述是‘5秒时限内获得可行调度方案’。20节点原始记录 MIP Gap=0.005559，应换算为约0.556%，不能误写成0.0056%。不同机器下时限场景的incumbent与Gap可能小幅变化。")

    section_header("证据文件与可追溯性", "页面不是孤立图表：原始CSV、验证脚本和运行日志均保留在工程包中。")
    left, right = st.columns(2)
    with left:
        st.markdown("**验证脚本**")
        st.code("legacy/carbon_compute_validation_suite_v4.py", language="text")
        st.caption("可重新运行消融、50组 Monte Carlo 与规模测试；依赖同目录 public-calibrated v2 主模型。")
    with right:
        st.markdown("**原始输出文件**")
        st.code("data/ablation_results.csv\ndata/monte_carlo_all.csv\ndata/monte_carlo_summary.csv\ndata/scalability_results.csv", language="text")

    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("消融 CSV", abl.to_csv(index=False).encode("utf-8-sig"), "ablation_results.csv", "text/csv", use_container_width=True)
    d2.download_button("Monte Carlo CSV", mc.to_csv(index=False).encode("utf-8-sig"), "monte_carlo_all.csv", "text/csv", use_container_width=True)
    d3.download_button("MC 汇总 CSV", mc_summary.to_csv(index=False).encode("utf-8-sig"), "monte_carlo_summary.csv", "text/csv", use_container_width=True)
    d4.download_button("规模测试 CSV", sc.to_csv(index=False).encode("utf-8-sig"), "scalability_results.csv", "text/csv", use_container_width=True)

    findings = load_text("validation_key_findings.txt")
    run_log = load_text("validation_run_log.txt")
    with st.expander("查看验证关键结论自动提取文本"):
        st.text(findings)
    with st.expander("查看原验证运行日志"):
        st.text(run_log)
