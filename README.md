# 碳算智调｜电—碳—算协同调度决策系统 Web 原型

面向智算中心/数据中心运营场景的 Streamlit MVP。核心算法为**多节点、多时段、碳感知 MILP 调度引擎**。

当前版本重点不是继续增加模型，而是把“算法—实验—产品界面—证据追溯”做成一套可现场演示的技术闭环。

## 1. 启动

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Windows 可在安装依赖后直接双击 `run_windows.bat`。

赛前建议先运行：

```bash
python smoke_test.py
python validation_evidence_test.py
```

## 2. 精修版新增内容

- 运行总览增加**决策摘要、节点状态卡和24h运转轮廓**；
- 智能调度增加**现场演示任务、一键真实求解、空间/时间分配图、迁移占比、延期占比、MIP Gap、CSV导出**；
- 24h态势增加**执行CU/负载率双模式热力图、节点能源—算力联动图**；
- 策略比较增加**单点碳权重重算 + 9点权重扫描 + 非支配候选前沿**；
- 压力测试增加**高碳价、绿电紧张/充足、高波动、需求冲击等快速演示预设**；
- 技术验证改为“有效性—机制来源—随机稳健性—规模求解”四标签证据链；
- 参数说明补充**参数四层分类、节点来源口径、三种碳核算公式**；
- 新增 `DEMO_GUIDE.md`，用于比赛现场3分钟演示与追问分流；
- 新增 `.streamlit/config.toml`，统一深蓝灰/冷白B端控制台视觉。

## 3. 页面

1. **运行总览**：4个公开校准原型节点的运营态势、关键KPI与决策摘要。
2. **智能调度**：输入任务后真实调用MILP，返回节点、时段、成本、三种碳口径、SLA与绿电指标。
3. **24h调度态势**：节点×时段热力图、节点运行曲线与任务迁移桑基图。
4. **策略比较**：五类基线、单点碳权重试算与9点权重扫描。
5. **压力测试**：碳价、电价、绿电、SLA、绿电波动、需求冲击组合重算。
6. **技术验证**：Baseline、消融、50组Monte Carlo、4–20节点规模测试。
7. **参数与数据说明**：公开参数、代理参数、情景参数及未来企业接入边界。

## 4. 已接入的原始验证证据

- `data/ablation_results.csv`
- `data/monte_carlo_all.csv`
- `data/monte_carlo_summary.csv`
- `data/scalability_results.csv`
- `data/validation_key_findings.txt`
- `data/validation_run_log.txt`
- `legacy/carbon_compute_validation_suite_v4.py`

技术验证页直接读取上述原始文件。`EVIDENCE_MAP.md` 给出每个页面与底层证据的映射关系。

## 5. 重要口径

当前 MVP 属于**公开参数校准 + 情景仿真验证**，不等同于具体数据中心生产环境实测。

- “调度碳代理”“位置法碳排”“市场法碳排”必须分开。
- 61.13% 应表述为相较成本优先策略的**调度碳指标下降**，不能直接称“实际减碳61.13%”。
- Monte Carlo 是50组随机运行情景，不是50家企业。
- 8/12/16/20节点规模实验来自4个公开校准原型节点的复制扰动，仅用于计算规模测试。
- 16/20节点设置5秒求解时限。时间受限档位重新运行时，MIP Gap、求解时间和 incumbent 可能因机器负载略有变化；正确表述为“5秒时限内获得可行方案”，不能说“5秒严格全局最优”。

## 6. 目录

```text
carbon_dispatch_mvp/
├── .streamlit/config.toml
├── app.py
├── core/
├── views/
├── data/
├── legacy/
├── smoke_test.py
├── validation_evidence_test.py
├── DEMO_GUIDE.md
├── EVIDENCE_MAP.md
├── MVP_TEST_REPORT.md
├── START_HERE.txt
├── requirements.txt
└── run_windows.bat
```

## 导航架构说明

本工程采用 **单入口 `app.py` + `views/` 展示模块 + 自定义中文侧边栏路由**。请勿把 `views/` 重命名为 `pages/`：`pages/` 是 Streamlit 的保留多页面目录，会被框架自动发现，从而生成额外的 `app / comparison / dispatch ...` 原生导航，与本工程的自定义路由冲突。

可运行 `python navigation_structure_test.py` 做结构自检。
