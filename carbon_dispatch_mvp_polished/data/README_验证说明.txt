电—碳—算协同调度 v4 验证套件

1. ablation_results.csv
   - 成本优先
   - 仅空间迁移
   - 固定节点+时间迁移
   - 无绿电感知
   - 完整协同
   用于解释空间迁移、时间迁移、绿电感知分别贡献了什么。

2. monte_carlo_all.csv
   50组随机运行情景的逐场结果。

3. monte_carlo_summary.csv
   随机重复的均值、标准差、P05、P50、P95及减排胜率等，可直接用于BP稳健性表述。

4. scalability_results.csv
   4/8/12/16/20节点规模测试。
   8~20节点为基于4个公开校准原型节点复制扰动的计算规模情景，不是真实新增数据中心。
   16/20节点设置5秒求解时限，重点观察求解时间与MIP Gap。

5. validation_key_findings.txt
   自动提取的BP写作核对数字。

运行：
python carbon_compute_validation_suite_v4.py

依赖：numpy, pandas, scipy>=1.9
要求：carbon_compute_validation_suite_v4.py 与 carbon_compute_public_calibrated_v2.py 位于同一目录。
