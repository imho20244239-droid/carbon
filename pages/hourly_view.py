import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.ui import page_header
from core.data_loader import load_nodes, load_hourly_parameters, load_reference_schedule


def render():
    page_header("24h调度态势", "看清任务去哪里算、什么时候算，以及电价与绿电条件如何变化")
    nodes = load_nodes(); hourly = load_hourly_parameters()
    live_sol = st.session_state.get("dispatch_solution")
    if live_sol and not live_sol["schedule"].empty:
        sched = live_sol["schedule"].copy()
        st.caption("当前态势图使用最近一次“智能调度”实时求解结果。")
    else:
        sched = load_reference_schedule()
        st.caption("当前态势图使用公开校准基准协同方案。")
    heat = sched.pivot_table(index="node", columns="exec_hour", values="workload_cu", aggfunc="sum", fill_value=0)
    order = nodes["node"].tolist(); heat = heat.reindex(order, fill_value=0)
    for h in range(int(hourly.hour.max())+1):
        if h not in heat.columns: heat[h] = 0
    heat = heat[sorted(heat.columns)]
    fig = px.imshow(heat, aspect="auto", labels=dict(x="执行时刻 / h", y="节点", color="执行CU"),
                    title="节点 × 时段执行负载热力图（0–23h到达，含SLA允许的跨日尾部）")
    fig.update_layout(height=360, margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("任务到达窗口为0–23h；批处理任务最多可延后6h，因此完整求解时域延伸至30h。")

    node = st.selectbox("查看节点运行曲线", order, format_func=lambda x:x.replace('_','·'))
    h = hourly[hourly.node==node].copy()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=h.hour, y=h.grid_price_cny_kwh, name="电价 元/kWh", mode="lines+markers"))
    fig2.add_trace(go.Scatter(x=h.hour, y=h.green_available_kwh, name="绿电可得 kWh", yaxis="y2", mode="lines"))
    fig2.update_layout(title=f"{node.replace('_','·')}：分时电价与绿电可得量", yaxis=dict(title="电价"),
                       yaxis2=dict(title="绿电", overlaying="y", side="right"), height=330, margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 任务类型 → 节点")
    flow = sched.groupby(["type","node"], as_index=False).workload_cu.sum()
    labels = list(flow.type.unique()) + [n.replace('_','·') for n in order]
    idx = {x:i for i,x in enumerate(labels)}
    sources=[]; targets=[]; values=[]
    for _,r in flow.iterrows():
        sources.append(idx[r.type]); targets.append(idx[r.node.replace('_','·')]); values.append(r.workload_cu)
    sankey = go.Figure(go.Sankey(node=dict(label=labels), link=dict(source=sources,target=targets,value=values)))
    sankey.update_layout(height=370, margin=dict(l=10,r=10,t=20,b=10))
    st.plotly_chart(sankey, use_container_width=True)
