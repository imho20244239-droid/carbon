from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.ui import page_header
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
    if pd.isna(x):
        return "—"
    return f"{x:.{digits}f}%"


def render():
    page_header("技术验证", "有效性、机制来源、随机稳健性与规模求解能力")
    st.markdown(
        '<div class="note">本页已接入 validation_suite_v4 原始输出：消融实验、50组 Monte Carlo、规模—求解时间测试。'
        '结果均来自公开参数校准与情景仿真，不代表真实数据中心生产环境实测。</div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    st.markdown("### 1. Baseline：是否有效")
    base = load_baseline_results().copy()
    show_cols = [
        "方案", "现金成本_CNY", "调度碳代理_kgCO2", "位置法碳排_kgCO2",
        "市场法碳排_kgCO2", "任务完成率_%", "SLA满足率_%", "绿电占比_%"
    ]
    st.dataframe(base[show_cols].round(3), use_container_width=True, hide_index=True)

    cost_row = base.loc[base["方案"] == "成本优先MILP"].iloc[0]
    our_row = base.loc[base["方案"] == "电碳算协同MILP"].iloc[0]
    cost_delta = (our_row["现金成本_CNY"] / cost_row["现金成本_CNY"] - 1) * 100
    carbon_drop = (1 - our_row["调度碳代理_kgCO2"] / cost_row["调度碳代理_kgCO2"]) * 100
    market_drop = (1 - our_row["市场法碳排_kgCO2"] / cost_row["市场法碳排_kgCO2"]) * 100
    k = st.columns(4)
    k[0].metric("协同成本变化", f"+{cost_delta:.2f}%", help="相较成本优先MILP")
    k[1].metric("调度碳指标下降", f"{carbon_drop:.2f}%", help="调度代理口径，不等同实际碳减排")
    k[2].metric("市场法碳排下降", f"{market_drop:.2f}%")
    k[3].metric("任务 / SLA", "100% / 100%")
    st.caption("正确表述：在公开参数校准仿真下，相较成本优先策略，协同方案以约1.90%的现金成本增幅换取显著的调度碳指标下降；不同碳核算口径下减排幅度不同。")

    # ------------------------------------------------------------------
    st.markdown("### 2. 消融：为什么有效")
    abl = load_ablation_results().copy()

    c1, c2, c3 = st.columns(3)
    no_space = abl.loc[abl["方案"] == "固定节点+时间迁移"].iloc[0]
    space_only = abl.loc[abl["方案"] == "仅空间迁移"].iloc[0]
    no_green = abl.loc[abl["方案"] == "无绿电感知"].iloc[0]
    c1.metric("取消空间决策后", f"+{no_space['相对完整模型_调度碳恶化_%']:.2f}%", "调度碳恶化")
    c2.metric("取消时间调度后", f"+{space_only['相对完整模型_调度碳恶化_%']:.2f}%", "仅保留空间迁移")
    c3.metric("取消绿电时序感知后", f"+{no_green['相对完整模型_调度碳恶化_%']:.2f}%", "调度碳恶化")

    chart_df = abl[["方案", "调度碳代理_kgCO2", "市场法碳排_kgCO2"]].melt(
        id_vars="方案", var_name="指标", value_name="kgCO2"
    )
    fig = px.bar(
        chart_df, x="方案", y="kgCO2", color="指标", barmode="group",
        title="消融实验：不同机制组合下的碳指标"
    )
    fig.update_layout(legend_title_text="", yaxis_title="kgCO₂", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看消融实验原始明细"):
        st.dataframe(abl.round(4), use_container_width=True, hide_index=True)
        st.caption("解释链：空间迁移是主要减碳来源；时间迁移继续改善任务—能源匹配；绿电时序感知在此基础上提供边际优化。")

    # ------------------------------------------------------------------
    st.markdown("### 3. Monte Carlo：换参数是否稳定")
    mc = load_monte_carlo_all().copy()
    mc_summary = load_monte_carlo_summary().copy()

    mean_cost = _summary_value(mc_summary, "相对成本优先_现金成本变化_%")
    mean_carbon = _summary_value(mc_summary, "相对成本优先_调度碳下降_%")
    p05_carbon = _summary_value(mc_summary, "相对成本优先_调度碳下降_%", "P05")
    p95_carbon = _summary_value(mc_summary, "相对成本优先_调度碳下降_%", "P95")
    mean_market = _summary_value(mc_summary, "相对成本优先_市场法碳排下降_%")
    win_rate = _summary_value(mc_summary, "调度碳减排胜率_%")

    cols = st.columns(5)
    cols[0].metric("随机场景", f"{len(mc)}组")
    cols[1].metric("平均成本增幅", _fmt_pct(mean_cost))
    cols[2].metric("调度碳平均下降", _fmt_pct(mean_carbon))
    cols[3].metric("P05–P95", f"{p05_carbon:.2f}%–{p95_carbon:.2f}%")
    cols[4].metric("调度减碳胜率", _fmt_pct(win_rate, 0))

    scatter = px.scatter(
        mc,
        x="相对成本优先_现金成本变化_%",
        y="相对成本优先_调度碳下降_%",
        hover_data=["scenario_id", "需求总体系数", "平均容量系数", "平均绿电系数"],
        title="50组随机运行情景：成本—调度碳权衡",
        labels={
            "相对成本优先_现金成本变化_%": "现金成本变化 / %",
            "相对成本优先_调度碳下降_%": "调度碳指标下降 / %",
        },
    )
    scatter.add_hline(y=0, line_dash="dash", annotation_text="减碳分界")
    scatter.add_vline(x=5, line_dash="dot", annotation_text="成本+5%参考线")
    st.plotly_chart(scatter, use_container_width=True)

    st.caption(
        f"50组随机情景中，任务完成率与SLA满足率均保持100%；市场法碳排平均下降约{mean_market:.2f}%。"
        "随机扰动对象包括任务需求、可用容量、电价与绿电供给，因此这里只能称为运行情景稳健性验证，不能写成‘50家企业验证’。"
    )
    with st.expander("查看 Monte Carlo 原始明细与统计摘要"):
        st.dataframe(mc_summary.round(4), use_container_width=True, hide_index=True)
        st.dataframe(mc.round(4), use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    st.markdown("### 4. 规模求解：规模变大还能不能算")
    sc = load_scalability_results().copy()
    sc["MIP_Gap_%"] = sc["MIP_Gap"] * 100.0
    sc["求解状态简写"] = sc["求解状态码"].map({0: "最优", 1: "达到时限"}).fillna("其他")

    top = sc.iloc[-1]
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("最大测试节点", f"{int(top['节点数'])}")
    s2.metric("任务批次", f"{int(top['任务批次数'])}")
    s3.metric("二元变量", f"{int(top['二元变量数']):,}")
    s4.metric("5秒时限 MIP Gap", f"{top['MIP_Gap_%']:.3f}%")

    scale_fig = go.Figure()
    scale_fig.add_trace(go.Scatter(
        x=sc["节点数"], y=sc["求解时间_s"], mode="lines+markers+text",
        text=[f"{x:.2f}s" for x in sc["求解时间_s"]], textposition="top center",
        name="求解时间 / s",
    ))
    scale_fig.add_hline(y=5.0, line_dash="dash", annotation_text="5秒时限")
    scale_fig.update_layout(
        title="规模扩展与求解时间",
        xaxis_title="节点数",
        yaxis_title="求解时间 / s",
        showlegend=False,
    )
    st.plotly_chart(scale_fig, use_container_width=True)

    show_scale = sc[[
        "节点数", "任务批次数", "二元变量数", "约束数", "求解时间_s", "MIP_Gap_%",
        "求解状态简写", "任务完成率_%", "SLA满足率_%"
    ]].copy()
    st.dataframe(show_scale.round({"求解时间_s": 3, "MIP_Gap_%": 3, "任务完成率_%": 2, "SLA满足率_%": 2}), use_container_width=True, hide_index=True)
    st.warning(
        "规模测试中的8/12/16/20节点均为基于4个公开校准原型节点复制并轻微扰动形成的计算规模情景。"
        "16/20节点达到5秒时限，因此正确表述是‘5秒时限内获得可行方案，20节点本次记录MIP Gap约0.56%’，不能声称‘20节点5秒严格全局最优’。"
        "由于达到时间上限时求解器会返回当时的 incumbent，不同机器/负载下16–20节点的求解时间、MIP Gap和可行解目标值可能有小幅波动；完成率、SLA及规模量级才是应重点复核的稳定结论。"
    )

    # ------------------------------------------------------------------
    st.markdown("### 5. 验证证据与可追溯性")
    left, right = st.columns(2)
    with left:
        st.markdown("**验证脚本**")
        st.code("legacy/carbon_compute_validation_suite_v4.py", language="text")
        st.caption("可重新运行消融、50组 Monte Carlo 与规模测试；依赖同目录 public-calibrated v2 主模型。")
    with right:
        st.markdown("**原始输出文件**")
        st.code(
            "data/ablation_results.csv\n"
            "data/monte_carlo_all.csv\n"
            "data/monte_carlo_summary.csv\n"
            "data/scalability_results.csv",
            language="text",
        )

    findings = load_text("validation_key_findings.txt")
    run_log = load_text("validation_run_log.txt")
    with st.expander("查看验证关键结论自动提取文本"):
        st.text(findings)
    with st.expander("查看原验证运行日志"):
        st.text(run_log)

    st.download_button(
        "下载验证关键结论 TXT",
        data=findings.encode("utf-8"),
        file_name="validation_key_findings.txt",
        mime="text/plain",
        use_container_width=False,
    )
