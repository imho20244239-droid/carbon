import streamlit as st
import plotly.express as px
from core.ui import page_header
from core.data_loader import load_nodes, load_hourly_parameters, load_tasks, load_stress_summary
from core.scenarios import run_stress_scenario


def render():
    page_header("压力测试", "组合调整碳价、电价、绿电、SLA、绿电波动和算力需求，并重新求解")
    a,b,c = st.columns(3)
    carbon = a.slider("影子碳价 / 元·kgCO₂⁻¹",0.0,1.0,0.25,0.05)
    elec = b.slider("电价倍率",0.8,1.5,1.0,0.05)
    green = c.slider("绿电可得量倍率",0.4,1.5,1.0,0.05)
    d,e,f = st.columns(3)
    sla = d.slider("SLA阈值倍率",0.5,1.5,1.0,0.05)
    volatility = e.slider("绿电波动系数",0.0,3.0,1.0,0.1)
    demand = f.slider("算力需求倍率",0.7,1.5,1.0,0.05)
    if st.button("重新计算组合压力场景", type="primary", use_container_width=True):
        nodes=load_nodes(); hourly=load_hourly_parameters(); tasks=load_tasks()
        with st.spinner("正在对成本优先与协同方案分别求解…"):
            out=run_stress_scenario(nodes,hourly,tasks,carbon,elec,green,sla,volatility,demand,5.0)
        st.session_state.stress_out=out
    out=st.session_state.get("stress_out")
    if out:
        s=out["multi"]["summary"]; dlt=out["comparison"]
        c=st.columns(7)
        for col,(k,v) in zip(c,[
            ("成本",f"¥{s['cash_cost']:.1f}"),("调度碳",f"{s['dispatch_carbon']:.1f}kg"),("位置法",f"{s['location_carbon']:.1f}kg"),
            ("市场法",f"{s['market_carbon']:.1f}kg"),("SLA",f"{s['sla_rate']:.1f}%"),("完成率",f"{s['completion_rate']:.1f}%"),("绿电占比",f"{s['green_share']:.1f}%")]): col.metric(k,v)
        st.info(f"相较同一压力场景下的成本优先：成本 {dlt['cost_change_pct']:+.2f}%；调度碳代理下降 {dlt['dispatch_reduction_pct']:.2f}%；市场法碳排下降 {dlt['market_reduction_pct']:.2f}%。")
        if s["completion_rate"] < 99.999 or s["peak_load_rate"] > 95:
            st.warning("当前算力需求已接近或超过容量安全区间。风险提示依据本次实时求解结果，而非固定1.30阈值。")
        else:
            st.success("当前组合压力下任务仍位于可行容量区间。")

    st.markdown("### 既有单因素压力测试")
    hist=load_stress_summary()
    group=st.selectbox("选择压力类型",hist["压力测试"].unique())
    sub=hist[hist["压力测试"]==group]
    fig=px.line(sub,x="参数值",y=["相对成本优先_现金成本变化_%","相对成本优先_调度碳代理下降_%"],markers=True,
                title="成本增幅与调度碳代理下降")
    st.plotly_chart(fig,use_container_width=True)
