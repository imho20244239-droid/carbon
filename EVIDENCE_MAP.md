# 碳算智调 MVP｜证据映射表

本文件用于比赛现场快速回答“页面上的数字从哪里来、能否重新算”。

| 页面/功能 | 主要来源 | 是否实时重算 | 说明 |
|---|---|---:|---|
| 运行总览 | `public_v2_nodes.csv`、`public_v2_node_hourly.csv`、`public_v2_results.csv`、最近一次调度结果 | 部分 | 未交互时显示公开校准基准；完成智能调度后自动切换到最新求解结果 |
| 智能调度 | `core/solver.py` + 节点/小时参数 + 当前任务输入 | 是 | 点击按钮真实调用MILP，并同时生成成本优先对照组 |
| 调度结果导出 | 智能调度实时解 | 是 | 逐任务节点、时段、能耗、成本、碳排和SLA可导出CSV |
| 24h调度态势 | 最近一次实时调度解；无实时解时读取 `public_v2_our_schedule.csv` | 部分 | 热力图、节点能源—算力曲线、任务类型→节点桑基图 |
| 五类策略比较 | `public_v2_results.csv` | 否 | 本地、最近、成本优先、碳优先、协同五类既有基线 |
| 碳权重单点试算 | `core/solver.py` | 是 | 调整 λc 后实时重算 |
| 9点权重扫描 | `core/solver.py` | 是 | 扫描9个 λc 值并提取非支配候选前沿 |
| 组合压力测试 | `core/scenarios.py` + `core/solver.py` | 是 | 六类参数组合调整后重新求解成本优先与协同方案 |
| 单因素压力曲线 | `stress_bp_summary.csv` | 否 | 展示既有六组单因素压力测试 |
| 消融实验 | `ablation_results.csv` | 否 | 5组原始验证输出 |
| Monte Carlo | `monte_carlo_all.csv`、`monte_carlo_summary.csv` | 否 | 50组随机运行情景，不是50家企业 |
| 规模测试 | `scalability_results.csv` | 否 | 8–20节点为复制扰动的计算规模情景 |
| 验证脚本 | `legacy/carbon_compute_validation_suite_v4.py` | 可离线重跑 | 可重新运行消融、Monte Carlo 与规模测试 |
| 主模型原脚本 | `legacy/carbon_compute_public_calibrated_v2.py` | 可离线重跑 | 产品求解逻辑的原始科研脚本依据 |

## 必须保持的表述边界

- “公开参数校准 + 情景仿真验证”，不表述为具体数据中心生产环境实测。
- 61.13% 是“相较成本优先策略的调度碳指标下降”，不能直接写成“实际减碳61.13%”。
- 50组 Monte Carlo 是“随机运行情景”，不能写成“50家企业验证”。
- 8/12/16/20节点为复制扰动形成的计算规模情景，不是新增真实数据中心。
- 16/20节点设置5秒时限。达到时间上限时，MIP Gap、求解时间和 incumbent 会随机器性能略有波动；不能声称“5秒严格全局最优”。
