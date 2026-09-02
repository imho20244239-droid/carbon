from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.ui import page_header, section_header, decision_callout, signal_strip, style_plot, PLOTLY_CONFIG
from core.data_loader import load_nodes, load_hourly_parameters, load_reference_schedule


def render():
    page_header("24h调度态势", "看清任务去哪里算、什么时候算，以及电价与绿电条件如何变化")
    nodes = load_nodes()
    hourly = load_hourly_parameters()
    live_sol = st.session_state.get("dispatch_solution")
    if live_sol and not live_sol["schedule"].empty:
        sched = live_sol["schedule"].copy()
        source = "最近一次智能调度实时求解"
    else:
        sched = load_reference_schedule().copy()
        source = "公开校准基准协同方案"

    max_hour = max(int(hourly.hour.max()), int(sched.exec_hour.max()) if not sched.empty else 23)
    tail_cu = float(sched.loc[sched.exec_hour > 23, "workload_cu"].sum()) if not sched.empty else 0.0
    total_cu = float(sched.workload_cu.sum()) if not sched.empty else 0.0
    decision_callout(
        "态势说明",
        f"当前展示来源：{source}。任务到达窗口为0–23h；批处理任务可在SLA允许范围内延后，"
        f"因此求解域延伸至{max_hour}h。跨日尾部执行量占当前完成任务的 {100*tail_cu/total_cu if total_cu else 0:.1f}%。",
    )

    # Build workload/load heatmaps.
    workload = sched.groupby(["node", "exec_hour"], as_index=False)["workload_cu"].sum()
    cap = hourly[["node", "hour", "capacity_cu"]].rename(columns={"hour": "exec_hour"})
    heat_long = cap.merge(workload, on=["node", "exec_hour"], how="left")
    heat_long["workload_cu"] = heat_long["workload_cu"].fillna(0.0)
    heat_long["load_rate_pct"] = 100 * heat_long["workload_cu"] / heat_long["capacity_cu"]

    peak = float(heat_long.load_rate_pct.max())
    peak_row = heat_long.loc[heat_long.load_rate_pct.idxmax()]
    migrated = float(sched.loc[sched.get("migrated", False) == True, "workload_cu"].sum()) if "migrated" in sched.columns else float("nan")
    signal_strip([
        ("总执行任务", f"{total_cu:,.0f} CU"),
        ("峰值负载", f"{peak:.1f}%"),
        ("峰值节点 / 时刻", f"{str(peak_row.node).replace('_','·')} · {int(peak_row.exec_hour):02d}h"),
        ("跨节点迁移", "基准明细未记录" if pd.isna(migrated) else f"{100*migrated/total_cu if total_cu else 0:.1f}%"),
    ])

    section_header("节点 × 时段调度热力图", "主视图默认展示实际执行CU；切换负载率可快速判断容量风险。")
    metric = st.radio("热力图指标", ["执行CU", "负载率%"], horizontal=True, key="heat_metric")
    value_col = "workload_cu" if metric == "执行CU" else "load_rate_pct"
    value_label = "执行CU" if metric == "执行CU" else "负载率 / %"
    heat = heat_long.pivot_table(index="node", columns="exec_hour", values=value_col, aggfunc="sum", fill_value=0)
    heat = heat.reindex(nodes["node"].tolist(), fill_value=0)
    heat.index = [x.replace("_", "·") for x in heat.index]
    fig = px.imshow(
        heat, aspect="auto", text_auto=".0f" if metric == "执行CU" else ".0f",
        labels=dict(x="执行时刻 / h", y="节点", color=value_label),
        title=f"节点 × 时段：{value_label}",
    )
    fig.update_traces(hovertemplate="节点=%{y}<br>时刻=%{x}h<br>" + value_label + "=%{z:.1f}<extra></extra>")
    style_plot(fig, height=390, legend_horizontal=False)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    section_header("单节点能源—算力联动", "将任务负载与分时电价、绿电可得量放在同一时间轴上，解释调度为何发生。")
    node = st.selectbox("查看节点", nodes["node"].tolist(), format_func=lambda x: x.replace("_", "·"), key="hourly_node")
    h = hourly[hourly.node == node].copy()
    node_load = heat_long[heat_long.node == node][["exec_hour", "workload_cu", "load_rate_pct"]]
    h = h.merge(node_load, left_on="hour", right_on="exec_hour", how="left")
    h24 = h[h.hour <= 23].copy()

    left, right = st.columns([1.15, 1.0])
    with left:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=h24.hour, y=h24.load_rate_pct, name="负载率 / %", opacity=0.42))
        fig2.add_trace(go.Scatter(x=h24.hour, y=h24.grid_price_cny_kwh, name="电价 / 元·kWh⁻¹", mode="lines+markers", yaxis="y2"))
        fig2.update_layout(
            title=f"{node.replace('_','·')}：负载与分时电价",
            xaxis_title="时刻 / h", yaxis=dict(title="负载率 / %", rangemode="tozero"),
            yaxis2=dict(title="电价 / 元·kWh⁻¹", overlaying="y", side="right", showgrid=False),
        )
        style_plot(fig2, height=340)
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
    with right:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=h24.hour, y=h24.green_available_kwh, name="绿电可得 / kWh", mode="lines", fill="tozeroy"))
        fig3.add_trace(go.Scatter(x=h24.hour, y=h24.workload_cu, name="执行任务 / CU", mode="lines+markers", yaxis="y2"))
        fig3.update_layout(
            title=f"{node.replace('_','·')}：绿电与执行任务",
            xaxis_title="时刻 / h", yaxis=dict(title="绿电 / kWh"),
            yaxis2=dict(title="执行任务 / CU", overlaying="y", side="right", showgrid=False),
        )
        style_plot(fig3, height=340)
        st.plotly_chart(fig3, use_container_width=True, config=PLOTLY_CONFIG)

    section_header("空间迁移结构", "桑基图用CU作为流量权重，展示三类任务最终流向哪些节点。")
    flow = sched.groupby(["type", "node"], as_index=False).workload_cu.sum()
    task_labels = list(flow.type.drop_duplicates())
    node_labels = [n.replace("_", "·") for n in nodes["node"].tolist()]
    labels = task_labels + node_labels
    task_idx = {x: i for i, x in enumerate(task_labels)}
    node_idx = {raw: len(task_labels) + i for i, raw in enumerate(nodes["node"].tolist())}
    sources, targets, values = [], [], []
    for _, r in flow.iterrows():
        sources.append(task_idx[r.type])
        targets.append(node_idx[r.node])
        values.append(float(r.workload_cu))
    sankey = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, pad=18, thickness=18, line=dict(width=.5)),
        link=dict(source=sources, target=targets, value=values),
    ))
    sankey.update_layout(title="任务类型 → 调度节点（CU流量）")
    style_plot(sankey, height=390, legend_horizontal=False)
    st.plotly_chart(sankey, use_container_width=True, config=PLOTLY_CONFIG)
