from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core.ui import page_header, section_header, decision_callout, signal_strip, style_plot, PLOTLY_CONFIG
from core.data_loader import load_nodes, load_hourly_parameters, load_tasks
from core.solver import solve_dispatch, TASK_PRESETS


def _init_queue():
    if "custom_tasks" not in st.session_state:
        st.session_state.custom_tasks = []


def _demo_queue(nodes: pd.DataFrame) -> list[dict]:
    n = nodes["node"].tolist()
    rows = [
        ("实时型", 42, 8, n[0]), ("实时型", 36, 9, n[1]),
        ("交互型", 55, 8, n[0]), ("交互型", 48, 11, n[1]),
        ("批处理", 72, 7, n[0]), ("批处理", 68, 12, n[0]),
    ]
    out = []
    for i, (tp, q, a, node) in enumerate(rows, 1):
        p = TASK_PRESETS[tp]
        out.append({
            "batch": f"DEMO{i:02d}_{tp}", "arrival": a, "type": tp, "demand_cu": float(q),
            "max_defer": int(p["max_defer"]), "max_latency": float(p["max_latency"]),
            "data_gb_per_cu": float(p["data_gb_per_cu"]), "delay_penalty": float(p["delay_penalty"]),
            "default_node": node, "allow_cross_node": True, "task_source_type": "现场演示情景任务",
        })
    return out


def _pct(new, old):
    return 100.0 * (new - old) / old if abs(old) > 1e-12 else 0.0


def render():
    page_header("智能调度", "输入任务与 SLA 约束，实时调用 MILP 生成节点—时段分配方案")
    _init_queue()
    nodes = load_nodes()
    hourly = load_hourly_parameters()
    base_tasks = load_tasks()

    section_header("任务输入", "基准场景用于稳定复现实验；自定义队列用于演示系统如何接收新的业务任务。")
    mode = st.radio("任务来源", ["72批基准任务", "自定义任务队列"], horizontal=True, key="dispatch_mode")

    if mode == "自定义任务队列":
        top_a, top_b = st.columns([1, 1])
        if top_a.button("载入现场演示任务", use_container_width=True, help="载入6批明确标注为情景仿真的示例任务"):
            st.session_state.custom_tasks = _demo_queue(nodes)
            st.rerun()
        if top_b.button("清空自定义队列", use_container_width=True, disabled=not bool(st.session_state.custom_tasks)):
            st.session_state.custom_tasks = []
            st.rerun()

        with st.expander("新增一批任务", expanded=not bool(st.session_state.custom_tasks)):
            with st.form("task_form", clear_on_submit=False):
                a, b, c, d = st.columns(4)
                task_type = a.selectbox("任务类型", list(TASK_PRESETS))
                demand = b.number_input("任务量 / CU", min_value=1.0, max_value=95.0, value=40.0, step=1.0)
                arrival = c.number_input("到达时刻 / h", min_value=0, max_value=23, value=8, step=1)
                default_node = d.selectbox("默认接入节点", nodes["node"].tolist(), format_func=lambda x: x.replace("_", "·"))
                p = TASK_PRESETS[task_type]
                e, f, g, h = st.columns(4)
                max_defer = e.number_input("最大可延期 / h", 0, 6, int(p["max_defer"]), 1)
                max_latency = f.number_input("最大网络时延 / ms", 1.0, 200.0, float(p["max_latency"]), 1.0)
                data_gb = g.number_input("数据量 / GB·CU⁻¹", .1, 20.0, float(p["data_gb_per_cu"]), .1)
                allow_cross = h.checkbox("允许跨节点", value=True)
                submitted = st.form_submit_button("加入任务队列", use_container_width=True)
                if submitted:
                    st.session_state.custom_tasks.append({
                        "batch": f"U{len(st.session_state.custom_tasks)+1:03d}_{task_type}", "arrival": int(arrival),
                        "type": task_type, "demand_cu": float(demand), "max_defer": int(max_defer),
                        "max_latency": float(max_latency), "data_gb_per_cu": float(data_gb),
                        "delay_penalty": float(p["delay_penalty"]), "default_node": default_node,
                        "allow_cross_node": bool(allow_cross), "task_source_type": "用户输入情景任务",
                    })
        tasks = pd.DataFrame(st.session_state.custom_tasks)
        if not tasks.empty:
            st.dataframe(tasks[["batch", "type", "demand_cu", "arrival", "default_node", "max_defer", "max_latency", "allow_cross_node"]], use_container_width=True, hide_index=True)
        else:
            st.caption("尚未加入任务。可载入现场演示任务，或手动新增任务。")
    else:
        tasks = base_tasks
        st.caption("采用项目既有72批公开校准基准任务；默认接入节点与原‘本地执行=安徽·芜湖’口径一致。")

    if not tasks.empty:
        mix = tasks.groupby("type")["demand_cu"].sum().to_dict()
        signal_strip([
            ("任务批次", f"{len(tasks)} 批"),
            ("总需求", f"{tasks['demand_cu'].sum():,.0f} CU"),
            ("实时 / 交互 / 批处理", f"{mix.get('实时型',0):.0f} / {mix.get('交互型',0):.0f} / {mix.get('批处理',0):.0f} CU"),
            ("求解时限", "5.0 s"),
        ])

    section_header("调度控制", "影子碳价用于控制成本与调度碳目标之间的权衡；按钮会同时求解协同方案与同任务集成本优先方案。")
    carbon_weight = st.slider("影子碳价 / 元·kgCO₂⁻¹", 0.0, 1.0, 0.25, 0.05, key="dispatch_carbon_weight")
    can_run = len(tasks) > 0
    if st.button("生成协同调度方案", type="primary", use_container_width=True, disabled=not can_run):
        try:
            with st.spinner("MILP 正在计算节点—时段分配，并同步求解成本优先对照组…"):
                sol = solve_dispatch(nodes, hourly, tasks, carbon_weight=carbon_weight, objective_mode="balanced", time_limit=5.0)
                cost = solve_dispatch(nodes, hourly, tasks, carbon_weight=0.0, objective_mode="cost", time_limit=5.0)
            st.session_state.dispatch_solution = sol
            st.session_state.dispatch_cost_solution = cost
            st.session_state.dispatch_solution_mode = mode
            st.session_state.dispatch_carbon_used = carbon_weight
        except Exception as e:
            st.error(f"求解失败：{e}")

    sol = st.session_state.get("dispatch_solution") if st.session_state.get("dispatch_solution_mode") == mode else None
    cost = st.session_state.get("dispatch_cost_solution") if st.session_state.get("dispatch_solution_mode") == mode else None
    if not sol:
        st.info("尚未生成当前任务集的调度方案。点击上方按钮后，系统会返回成本、三种碳口径、SLA、绿电利用和逐任务分配结果。")
        return

    s = sol["summary"]
    c0 = cost["summary"] if cost else None
    cost_change = _pct(s["cash_cost"], c0["cash_cost"]) if c0 else 0.0
    carbon_red = -_pct(s["dispatch_carbon"], c0["dispatch_carbon"]) if c0 else 0.0
    market_red = -_pct(s["market_carbon"], c0["market_carbon"]) if c0 else 0.0

    section_header("求解结果", "结果全部来自当前任务集实时求解；不会固定写死基准场景的1.90%或61.13%。")
    decision_callout(
        "系统建议",
        f"在影子碳价 {st.session_state.get('dispatch_carbon_used', carbon_weight):.2f} 元/kgCO₂ 下，"
        f"相较成本优先方案，现金成本 {cost_change:+.2f}%，调度碳代理下降 {carbon_red:.2f}%，"
        f"市场法碳排下降 {market_red:.2f}%；SLA {s['sla_rate']:.1f}%，任务完成率 {s['completion_rate']:.1f}%。",
    )

    kpis = st.columns(7)
    for col, (label, value) in zip(kpis, [
        ("现金成本", f"¥{s['cash_cost']:.2f}"), ("调度碳代理", f"{s['dispatch_carbon']:.1f} kg"),
        ("位置法碳排", f"{s['location_carbon']:.1f} kg"), ("市场法碳排", f"{s['market_carbon']:.1f} kg"),
        ("SLA", f"{s['sla_rate']:.1f}%"), ("任务完成率", f"{s['completion_rate']:.1f}%"),
        ("绿电占比", f"{s['green_share']:.1f}%"),
    ]):
        col.metric(label, value)

    schedule = sol["schedule"].copy()
    total_cu = schedule["workload_cu"].sum() if not schedule.empty else 0.0
    migrated_cu = schedule.loc[schedule.get("migrated", False) == True, "workload_cu"].sum() if not schedule.empty else 0.0
    delayed_cu = schedule.loc[schedule["delay_h"] > 0, "workload_cu"].sum() if not schedule.empty else 0.0
    gap = s.get("mip_gap", float("nan"))
    gap_text = "—" if pd.isna(gap) else f"{gap*100:.3f}%"
    signal_strip([
        ("跨节点迁移占比", f"{100*migrated_cu/total_cu if total_cu else 0:.1f}%"),
        ("延期执行占比", f"{100*delayed_cu/total_cu if total_cu else 0:.1f}%"),
        ("平均延迟", f"{s['avg_delay']:.2f} h"),
        ("求解时间 / MIP Gap", f"{s['solve_time']:.3f} s / {gap_text}"),
    ])

    if not schedule.empty:
        left, right = st.columns(2)
        with left:
            alloc = schedule.groupby(["node", "type"], as_index=False)["workload_cu"].sum()
            alloc["节点"] = alloc["node"].str.replace("_", "·", regex=False)
            fig = px.bar(alloc, x="节点", y="workload_cu", color="type", barmode="stack", title="空间分配：任务类型 → 执行节点", labels={"workload_cu": "任务量 / CU", "type": "任务类型"})
            style_plot(fig, height=335)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        with right:
            timeline = schedule.groupby(["exec_hour", "type"], as_index=False)["workload_cu"].sum()
            fig2 = px.bar(timeline, x="exec_hour", y="workload_cu", color="type", barmode="stack", title="时间分配：执行时段结构", labels={"exec_hour": "执行时刻 / h", "workload_cu": "任务量 / CU", "type": "任务类型"})
            style_plot(fig2, height=335)
            st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

        section_header("逐任务调度明细", "可用于现场追问、算法审计或导出后形成调度指令接口。")
        show = schedule[[
            "batch", "type", "arrival", "default_node", "node", "exec_hour", "delay_h", "workload_cu",
            "energy_kwh", "green_used_kwh", "cash_cost_cny", "dispatch_carbon_kg", "market_carbon_kg", "migrated", "sla_ok",
        ]].copy()
        show["default_node"] = show["default_node"].astype(str).str.replace("_", "·", regex=False)
        show["node"] = show["node"].astype(str).str.replace("_", "·", regex=False)
        show.columns = ["任务ID", "任务类型", "到达", "默认节点", "调度节点", "执行时刻", "延迟/h", "任务CU", "能耗/kWh", "绿电/kWh", "成本/元", "调度碳/kg", "市场法/kg", "跨节点", "SLA"]
        st.dataframe(show.round(4), use_container_width=True, hide_index=True)
        st.download_button(
            "下载本次调度结果 CSV",
            data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name="carbon_dispatch_solution.csv",
            mime="text/csv",
            use_container_width=False,
        )

    if s["completion_rate"] < 99.999:
        st.warning("存在未完成任务：当前任务规模、容量或SLA约束已超过可行安全区间。建议转到‘压力测试’进一步定位容量边界。")
