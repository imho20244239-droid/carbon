import streamlit as st
import plotly.express as px
from core.ui import page_header
from core.data_loader import load_baseline_results, load_nodes, load_hourly_parameters, load_tasks
from core.solver import solve_dispatch


def render():
    page_header("策略比较", "五类基准策略与成本—调度碳权衡；可试算不同碳权重下的推荐点")
    df = load_baseline_results().copy()
    st.dataframe(df[["方案","任务完成率_%","SLA满足率_%","现金成本_CNY","调度碳代理_kgCO2","位置法碳排_kgCO2","市场法碳排_kgCO2","绿电占比_%","平均延迟_h"]].round(3), use_container_width=True, hide_index=True)
    fig = px.scatter(df, x="现金成本_CNY", y="调度碳代理_kgCO2", size="绿电占比_%", text="方案",
                     hover_data=["位置法碳排_kgCO2","市场法碳排_kgCO2","SLA满足率_%"], title="成本—调度碳二维权衡")
    fig.update_traces(textposition="top center"); fig.update_layout(height=430)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 碳权重试算")
    lam = st.slider("影子碳价 λc / 元·kgCO₂⁻¹", 0.0, 1.0, 0.25, 0.05, key="cmp_lam")
    if st.button("重新求解该权重", key="cmp_solve"):
        nodes=load_nodes(); hourly=load_hourly_parameters(); tasks=load_tasks()
        with st.spinner("正在求解…"):
            sol=solve_dispatch(nodes,hourly,tasks,carbon_weight=lam,objective_mode="balanced",time_limit=5.0)
        st.session_state.cmp_sol=sol
    if st.session_state.get("cmp_sol"):
        s=st.session_state.cmp_sol["summary"]
        c=st.columns(5)
        c[0].metric("成本",f"¥{s['cash_cost']:.1f}"); c[1].metric("调度碳",f"{s['dispatch_carbon']:.1f} kg")
        c[2].metric("市场法",f"{s['market_carbon']:.1f} kg"); c[3].metric("绿电占比",f"{s['green_share']:.1f}%"); c[4].metric("求解时间",f"{s['solve_time']:.3f}s")
