"""验证证据完整性与关键结论检查。

注意：16/20节点规模测试设5秒时限，重新运行时 incumbent / MIP Gap / 求解时间
会受机器性能与瞬时负载影响，因此这里只检查原始证据文件的口径、维度和稳定业务结论，
不要求时间受限档位逐位复现。
"""
from __future__ import annotations

import math
from core.data_loader import (
    load_ablation_results,
    load_monte_carlo_all,
    load_monte_carlo_summary,
    load_scalability_results,
)


def close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def main():
    abl = load_ablation_results()
    assert len(abl) == 5
    assert set(abl["方案"]) == {"成本优先", "仅空间迁移", "固定节点+时间迁移", "无绿电感知", "完整协同"}
    full = abl.loc[abl["方案"] == "完整协同"].iloc[0]
    assert close(full["现金成本_CNY"], 585.8225517033877)
    assert close(full["调度碳代理_kgCO2"], 243.63196257630665)
    assert close(full["市场法碳排_kgCO2"], 263.5077911228035)

    mc = load_monte_carlo_all()
    summary = load_monte_carlo_summary()
    assert len(mc) == 50
    assert (mc["协同_任务完成率_%"] > 99.999).all()
    assert (mc["协同_SLA满足率_%"] > 99.999).all()
    assert (mc["相对成本优先_调度碳下降_%"] > 0).all()
    assert (mc["相对成本优先_市场法碳排下降_%"] > 0).all()
    mean_carbon = summary.loc[summary["指标"] == "相对成本优先_调度碳下降_%", "均值"].iloc[0]
    assert close(mean_carbon, 60.32219522507226)

    scale = load_scalability_results()
    assert list(scale["节点数"]) == [4, 8, 12, 16, 20]
    assert list(scale["任务批次数"]) == [72, 144, 216, 288, 360]
    assert list(scale["二元变量数"]) == [1128, 4368, 9720, 17184, 26760]
    assert (scale["任务完成率_%"] > 99.999).all()
    assert (scale["SLA满足率_%"] > 99.999).all()
    # 原始记录中的20节点MIP gap为比例值0.005559 -> 约0.556%。
    gap20 = scale.loc[scale["节点数"] == 20, "MIP_Gap"].iloc[0]
    assert 0 <= gap20 < 0.01

    print("VALIDATION EVIDENCE TEST PASSED")
    print(f"ablation={len(abl)} rows, monte_carlo={len(mc)} scenarios, scale={len(scale)} levels")
    print(f"20-node recorded MIP Gap = {gap20 * 100:.3f}%")


if __name__ == "__main__":
    main()
