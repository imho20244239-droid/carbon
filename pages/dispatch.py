import streamlit as st
import pandas as pd
from core.ui import page_header
from core.data_loader import load_nodes, load_hourly_parameters, load_tasks
from core.solver import solve_dispatch, TASK_PRESETS


def _init_queue():
    if "custom_tasks" not in st.session_state:
        st.session_state.custom_tasks = []


def render():
    page_header("智能调度", "输入任务与SLA约束，实时调用MILP生成节点—时段分配方案")
    _init_queue()
    nodes = load_nodes(); hourly = load_hourly_parameters(); base_tasks = load_tasks()
    mode = st.radio("任务来源", ["72批基准任务", "自定义任务队列"], horizontal=True)

    if mode == "自定义任务队列":
        with st.form("task_form", clear_on_submit=False):
            a,b,c,d = st.columns(4)
            task_type = a.selectbox("任务类型", list(TASK_PRESETS))
            demand = b.number_input("任务量 / CU", min_value=1.0, max_value=95.0, value=40.0, step=1.0)
            arrival = c.number_input("到达时刻 / h", min_value=0, max_value=23, value=8, step=1)
            default_node = d.selectbox("默认接入节点", nodes["node"].tolist(), format_func=lambda x:x.replace('_','·'))
            p = TASK_PRESETS[task_type]
            e,f,g,h = st.columns(4)
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
                    "allow_cross_node": bool(allow_cross), "task_source_type": "用户输入情景任务"
                })
        if st.session_state.custom_tasks:
            st.dataframe(pd.DataFrame(st.session_state.custom_tasks), use_container_width=True, hide_index=True)
            if st.button("清空自定义队列"):
                st.session_state.custom_tasks = []; st.rerun()
        else:
            st.caption("尚未加入任务。")
        tasks = pd.DataFrame(st.session_state.custom_tasks)
    else:
        tasks = base_tasks
        st.caption("采用项目既有72批任务情景；默认接入节点与原“本地执行=安徽·芜湖”口径一致。")

    carbon_weight = st.slider("影子碳价 / 元·kgCO₂⁻¹", 0.0, 1.0, 0.25, 0.05)
    can_run = len(tasks) > 0
    if st.button("生成协同调度方案", type="primary", use_container_width=True, disabled=not can_run):
        try:
            with st.spinner("正在求解MILP…"):
                sol = solve_dispatch(nodes, hourly, tasks, carbon_weight=carbon_weight, objective_mode="balanced", time_limit=5.0)
                cost = solve_dispatch(nodes, hourly, tasks, carbon_weight=0.0, objective_mode="cost", time_limit=5.0)
            st.session_state.dispatch_solution = sol
            st.session_state.dispatch_cost_solution = cost
            st.session_state.dispatch_solution_mode = mode
        except Exception as e:
            st.error(f"求解失败：{e}")

    sol = st.session_state.get("dispatch_solution") if st.session_state.get("dispatch_solution_mode") == mode else None
    cost = st.session_state.get("dispatch_cost_solution") if st.session_state.get("dispatch_solution_mode") == mode else None
    if sol:
        s = sol["summary"]
        kpis = st.columns(7)
        for col, (label, value) in zip(kpis, [
            ("现金成本", f"¥{s['cash_cost']:.2f}"), ("调度碳代理", f"{s['dispatch_carbon']:.1f} kg"),
            ("位置法碳排", f"{s['location_carbon']:.1f} kg"), ("市场法碳排", f"{s['market_carbon']:.1f} kg"),
            ("SLA", f"{s['sla_rate']:.1f}%"), ("任务完成率", f"{s['completion_rate']:.1f}%"),
            ("绿电占比", f"{s['green_share']:.1f}%")]): col.metric(label, value)
        if cost:
            c0 = cost["summary"]
            cost_change = 100*(s['cash_cost']-c0['cash_cost'])/c0['cash_cost'] if c0['cash_cost'] else 0
            carbon_red = 100*(c0['dispatch_carbon']-s['dispatch_carbon'])/c0['dispatch_carbon'] if c0['dispatch_carbon'] else 0
            st.success(f"当前方案相较同一任务集的成本优先策略：现金成本 {cost_change:+.2f}% ，调度碳代理下降 {carbon_red:.2f}% ，SLA {s['sla_rate']:.1f}% 。")
        show = sol["schedule"].copy()
        if not show.empty:
            show = show[["batch","type","arrival","default_node","node","exec_hour","delay_h","workload_cu","energy_kwh","cash_cost_cny","dispatch_carbon_kg","sla_ok"]]
            show.columns = ["任务ID","任务类型","到达","默认节点","调度节点","执行时刻","延迟/h","任务CU","能耗/kWh","成本/元","调度碳/kg","SLA"]
        st.markdown("### 调度明细")
        st.dataframe(show, use_container_width=True, hide_index=True)
        if s["completion_rate"] < 99.999:
            st.warning("存在未完成任务：当前任务规模或约束已超过可行安全区间。")
