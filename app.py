import streamlit as st
from core.ui import CSS
from pages import overview, dispatch, hourly_view, comparison, stress_test, validation, data_notes

st.set_page_config(
    page_title="碳算智调｜电—碳—算协同调度决策系统",
    page_icon="碳",
    layout="wide",
    initial_sidebar_state="auto",
)
st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        '<div class="brand-lockup">'
        '<div class="brand-mark" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M19.5 4.5C12 4.5 6.5 8.2 6.5 14.2c0 2.9 2.1 5.3 5.2 5.3 5.3 0 7.8-5.7 7.8-15Z"/>'
        '<path d="M4.5 20c2.2-4.6 5.7-7.7 10.4-9.3"/><path d="M5.2 8.2v3.1M3.7 9.7h3.1"/>'
        '</svg></div>'
        '<div><div class="sidebar-brand">碳算智调</div>'
        '<div class="sidebar-sub">电 · 碳 · 算协同调度</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="engine">MILP 求解引擎在线</div>', unsafe_allow_html=True)
    st.caption("4 个校准节点 · 72 批任务 · 31 时段")
    st.markdown('<div class="sidebar-label">工作台导航</div>', unsafe_allow_html=True)
    page = st.radio(
        "导航",
        ["运行总览", "智能调度", "24h 调度态势", "策略比较", "压力测试", "技术验证", "参数与数据说明"],
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
    st.markdown(
        '<div class="sidebar-foot">技术核心：多节点、多时段、碳感知 MILP<br>'
        '数据边界：公开参数校准 + 情景仿真</div>',
        unsafe_allow_html=True,
    )

routes = {
    "运行总览": overview.render,
    "智能调度": dispatch.render,
    "24h 调度态势": hourly_view.render,
    "策略比较": comparison.render,
    "压力测试": stress_test.render,
    "技术验证": validation.render,
    "参数与数据说明": data_notes.render,
}
routes[page]()
