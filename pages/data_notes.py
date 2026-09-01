import streamlit as st
from core.ui import page_header
from core.data_loader import load_nodes


def render():
    page_header("参数与数据说明", "区分公开参数、代理参数、情景参数与未来企业接入参数")
    st.markdown("""
| 分类 | 当前MVP中的典型参数 | 使用原则 |
|---|---|---|
| A 官方公开参数 | 分时电价、省级电力碳因子、政策绿电比例 | 用于区域差异校准 |
| B 公开代理参数 | PUE、网络时延、区域算力条件 | 作为可解释代理，不声称企业实测 |
| C 情景仿真参数 | 实时可用CU、链路剩余带宽、小时级绿电、任务到达量、企业SLA | 用于原型技术验证 |
| D 未来企业接入 | GPU/CPU/NPU实时负载、任务队列、电费合同、绿电采购、SLA、网络状态 | 接入生产环境后替换C类参数 |
""")
    st.info("当前MVP属于“公开参数校准 + 情景仿真验证”，不等同于具体数据中心生产环境实测。")
    st.markdown("### 四个公开校准节点")
    st.dataframe(load_nodes(),use_container_width=True,hide_index=True)
    st.markdown("### 三种碳口径")
    st.markdown("- **调度碳代理**：用于MILP内部优化与策略比较；区域碳因子 × 非可追溯绿电电量。\n- **位置法碳排**：省级平均电力碳因子 × 总用电量。\n- **市场法碳排**：可追溯绿电按0处理，剩余购电使用0.6096 kgCO₂/kWh。")
