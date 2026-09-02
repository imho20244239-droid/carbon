import streamlit as st
from core.ui import CSS
from pages import overview, dispatch, hourly_view, comparison, stress_test, validation, data_notes

st.set_page_config(
    page_title="碳算智调｜电—碳—算协同调度决策系统",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="sidebar-brand">碳算智调</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">电—碳—算协同调度决策系统</div>', unsafe_allow_html=True)
    st.markdown('<span class="badge">Web Prototype</span>', unsafe_allow_html=True)
    st.markdown('<div class="engine">● MILP 求解引擎 · Ready</div>', unsafe_allow_html=True)
    st.caption("4个公开校准原型节点｜72批基准任务｜31时段求解域")
    st.divider()
    page = st.radio(
        "导航",
        ["01 运行总览", "02 智能调度", "03 24h调度态势", "04 策略比较", "05 压力测试", "06 技术验证", "07 参数与数据说明"],
        label_visibility="collapsed",
    )
    st.divider()
    with st.expander("现场演示路线", expanded=False):
        st.caption("建议：运行总览 → 智能调度 → 策略比较 → 技术验证。压力测试作为追问页。")
    if st.button("恢复基准场景", use_container_width=True, help="清除本次交互求解状态，不删除任何数据文件"):
        for k in list(st.session_state.keys()):
            if k.startswith(("dispatch_", "stress_", "cmp_")):
                del st.session_state[k]
        st.rerun()
    st.caption("技术核心：多节点、多时段、碳感知 MILP")
    st.caption("数据边界：公开参数校准 + 情景仿真")

routes = {
    "01 运行总览": overview.render,
    "02 智能调度": dispatch.render,
    "03 24h调度态势": hourly_view.render,
    "04 策略比较": comparison.render,
    "05 压力测试": stress_test.render,
    "06 技术验证": validation.render,
    "07 参数与数据说明": data_notes.render,
}
routes[page]()
