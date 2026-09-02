from __future__ import annotations

import streamlit as st

from core.ui import page_header, section_header, decision_callout, signal_strip
from core.data_loader import load_nodes


def render():
    page_header("参数与数据说明", "明确区分公开参数、代理参数、情景仿真参数与未来企业接入参数")
    decision_callout(
        "数据边界",
        "当前MVP属于‘公开参数校准 + 情景仿真验证’。分时电价、电力碳因子等用于区域校准；实时可用CU、小时级绿电出力、链路剩余带宽和任务到达量等仍是情景参数，不应包装成具体企业真实运行数据。",
    )
    signal_strip([
        ("A类", "官方公开参数"),
        ("B类", "公开代理参数"),
        ("C类", "情景仿真参数"),
        ("D类", "未来企业接入参数"),
    ])

    section_header("参数分层", "产品原型先用A/B类校准区域差异、C类完成技术验证；生产接入后由D类实时数据替换C类。")
    tabs = st.tabs(["A 官方公开", "B 公开代理", "C 情景仿真", "D 企业接入"])
    with tabs[0]:
        st.markdown("- 分时电价\n- 省级电力碳因子\n- 政策绿电比例 / 可再生能源消纳目标")
        st.caption("用途：区域差异校准与核算口径基础。")
    with tabs[1]:
        st.markdown("- PUE\n- 网络时延\n- 区域算力条件")
        st.caption("用途：在缺乏企业实测数据时提供可解释代理；页面与BP均应标注‘代理参数’。")
    with tabs[2]:
        st.markdown("- 实时可用CU\n- 链路剩余带宽\n- 小时级绿电曲线\n- 任务到达量\n- 企业SLA")
        st.caption("用途：原型技术验证、压力测试和容量边界分析。")
    with tabs[3]:
        st.markdown("- GPU / CPU / NPU 实时负载\n- 任务队列\n- 电费合同\n- 绿电采购与证书\n- SLA\n- 网络状态")
        st.caption("用途：未来接入生产环境后替换C类情景参数，并形成真实运营闭环。")

    section_header("四个公开校准原型节点", "节点代表区域运行条件组合，不代表已经接入或服务对应地区的真实数据中心。")
    nodes = load_nodes().copy()
    display = nodes[[
        "node", "latency_ms", "grid_ci_kg_kwh", "green_share_base", "pue", "energy_kwh_per_cu",
        "latency_source_type", "carbon_source_type", "green_source_type", "capacity_source_type",
    ]].copy()
    display["node"] = display["node"].str.replace("_", "·", regex=False)
    display["green_share_base"] = display["green_share_base"] * 100
    display.columns = ["节点", "时延/ms", "电网碳强度/kg·kWh⁻¹", "绿电基准/%", "PUE", "能耗/kWh·CU⁻¹", "时延口径", "碳因子口径", "绿电口径", "容量口径"]
    st.dataframe(display.round(4), use_container_width=True, hide_index=True)

    section_header("三种碳核算口径", "调度优化指标与碳核算口径必须分开，避免把内部代理指标直接包装成真实减排。")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**调度碳代理**")
        st.latex(r"CO_2^{dispatch}=\sum_{i,t} CI_{it}(E_{it}-G_{it})")
        st.caption("用途：MILP内部优化与策略比较。")
    with c2:
        st.markdown("**位置法碳排**")
        st.latex(r"CO_2^{loc}=\sum_{i,t}CI_i^{province}E_{it}")
        st.caption("用途：反映任务迁移后落在不同区域电网的用电碳排。")
    with c3:
        st.markdown("**市场法碳排**")
        st.latex(r"CO_2^{mkt}=0.6096\sum_{i,t}(E_{it}-G_{it}^{trace})")
        st.caption("用途：反映可追溯绿电采购下的核算结果。")

    st.warning("禁止表述：‘已服务XX家数据中心’‘真实生产环境验证’‘实际减少61%碳排’‘50家企业验证’‘20节点5秒严格全局最优’。当前证据支持的是公开参数校准、情景仿真、50组随机运行情景与规模化计算测试。")
