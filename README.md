# 碳算智调｜电—碳—算协同调度决策系统 Web 原型

面向智算中心/数据中心运营场景的 Streamlit MVP。核心算法为多节点、多时段、碳感知 MILP 调度引擎。

## 1. 启动

```bash
pip install -r requirements.txt
streamlit run app.py
```

Windows 可直接双击 `run_windows.bat`（前提是当前 Python 环境已安装 requirements）。

## 2. 页面

1. 运行总览：4个公开校准原型节点的运营态势与关键 KPI。
2. 智能调度：输入任务后真实调用 MILP，返回节点、时段与碳/成本/SLA指标。
3. 24h调度态势：节点×24小时负载热力图及运行参数。
4. 策略比较：本地、最近、成本优先、碳优先、协同五类策略。
5. 压力测试：碳价、电价、绿电、SLA、绿电波动、需求冲击组合重算。
6. 技术验证：Baseline、消融、50组 Monte Carlo、4–20节点规模测试。
7. 参数与数据说明：公开参数、代理参数、情景参数及未来企业接入参数边界。

## 3. 已接入的原始验证证据

本版已补充 `carbon_compute_validation_suite_v4` 全套输出，不再使用交接摘要回退：

- `data/ablation_results.csv`
- `data/monte_carlo_all.csv`
- `data/monte_carlo_summary.csv`
- `data/scalability_results.csv`
- `data/validation_key_findings.txt`
- `data/validation_run_log.txt`
- `legacy/carbon_compute_validation_suite_v4.py`

技术验证页会直接读取这些原始文件。`EVIDENCE_MAP.md` 给出每个页面与底层证据的映射关系。

## 4. 重要口径

当前 MVP 属于**公开参数校准 + 情景仿真验证**，不等同于具体数据中心生产环境实测。

- “调度碳代理”“位置法碳排”“市场法碳排”必须分开。
- 61.13% 应表述为相较成本优先策略的**调度碳指标下降**，不能直接称“实际减碳61.13%”。
- Monte Carlo 是50组随机运行情景，不是50家企业。
- 8/12/16/20节点规模实验来自4个公开校准原型节点的复制扰动，仅用于计算规模测试。
- 16/20节点设置5秒求解时限。时间受限档位重新运行时，MIP Gap、求解时间和 incumbent 可能因机器负载略有变化；正确表述为“5秒时限内获得可行方案”，不能说“5秒严格全局最优”。

## 5. 快速自检

```bash
python smoke_test.py
python validation_evidence_test.py
```

`smoke_test.py` 检查产品封装后的核心 MILP 是否复现基准协同结果；`validation_evidence_test.py` 检查消融、Monte Carlo 和规模证据文件是否完整、关键业务结论是否一致。

## 6. 目录

```text
carbon_dispatch_mvp/
├── app.py
├── core/
├── pages/
├── data/
├── legacy/
├── smoke_test.py
├── validation_evidence_test.py
├── EVIDENCE_MAP.md
├── MVP_TEST_REPORT.md
├── requirements.txt
└── run_windows.bat
```
