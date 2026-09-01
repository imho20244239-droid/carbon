# 碳算智调 MVP｜证据映射表

本文件用于比赛现场快速回答“页面上的数字从哪里来”。

| 页面/功能 | 主要来源 | 说明 |
|---|---|---|
| 运行总览 | `data/public_v2_nodes.csv`、`public_v2_node_hourly.csv`、`public_v2_our_node_summary.csv` | 公开参数校准 + 情景运行参数 |
| 智能调度 | `core/solver.py` + 节点/小时参数 + 用户任务输入 | 点击按钮真实调用 MILP，不是静态结果 |
| 24h调度态势 | `public_v2_our_schedule.csv`、`public_v2_node_hourly.csv` | 展示节点×时段任务分配及运行态势 |
| 策略比较 | `public_v2_results.csv` | 本地、最近、成本优先、碳优先、协同五类策略 |
| 压力测试 | `core/scenarios.py` + `core/solver.py`；参考 `stress_bp_summary.csv` | 页面重新求解；CSV用于对照已有实验 |
| 消融实验 | `ablation_results.csv` | 5组原始验证输出 |
| Monte Carlo | `monte_carlo_all.csv`、`monte_carlo_summary.csv` | 50组随机运行情景，不是50家企业 |
| 规模测试 | `scalability_results.csv` | 8–20节点为复制扰动的计算规模情景 |
| 验证脚本 | `legacy/carbon_compute_validation_suite_v4.py` | 可重新运行验证套件 |
| 主模型原脚本 | `legacy/carbon_compute_public_calibrated_v2.py` | 产品求解逻辑的原始科研脚本依据 |

## 必须保持的表述边界

- “公开参数校准 + 情景仿真验证”，不表述为具体数据中心生产环境实测。
- 61.13% 是“相较成本优先策略的调度碳指标下降”，不能直接写成“实际减碳61.13%”。
- 50组 Monte Carlo 是“随机运行情景”，不能写成“50家企业验证”。
- 8/12/16/20节点为复制扰动形成的计算规模情景，不是新增真实数据中心。
- 16/20节点设置5秒时限。达到时间上限时，MIP Gap、求解时间和 incumbent 会随机器性能略有波动；不能声称“5秒严格全局最优”。
