import streamlit as st
from core.ui import CSS
from pages import overview, dispatch, hourly_view, comparison, stress_test, validation, data_notes

st.set_page_config(page_title="碳算智调｜电—碳—算协同调度决策系统", page_icon="⚙️", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 碳算智调")
    st.caption("电—碳—算协同调度决策系统")
    st.markdown('<span class="badge">Web原型 / Prototype</span>', unsafe_allow_html=True)
    st.divider()
    page = st.radio("导航", ["01 运行总览","02 智能调度","03 24h调度态势","04 策略比较","05 压力测试","06 技术验证","07 参数与数据说明"], label_visibility="collapsed")
    st.divider()
    st.caption("技术核心：多节点、多时段、碳感知MILP调度引擎")
    st.caption("数据口径：公开参数校准 + 情景仿真")

routes = {
    "01 运行总览": overview.render, "02 智能调度": dispatch.render,
    "03 24h调度态势": hourly_view.render, "04 策略比较": comparison.render,
    "05 压力测试": stress_test.render, "06 技术验证": validation.render,
    "07 参数与数据说明": data_notes.render,
}
routes[page]()
