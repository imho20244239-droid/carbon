from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def _read(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"缺少数据文件: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def load_nodes() -> pd.DataFrame:
    return _read("public_v2_nodes.csv")


def load_tasks() -> pd.DataFrame:
    df = _read("public_v2_tasks.csv")
    # 与原“本地执行=节点0”的建模口径保持一致：基准任务默认接入安徽·芜湖。
    if "default_node" not in df.columns:
        df["default_node"] = "安徽_芜湖"
    if "allow_cross_node" not in df.columns:
        df["allow_cross_node"] = True
    return df


def load_hourly_parameters() -> pd.DataFrame:
    return _read("public_v2_node_hourly.csv")


def load_baseline_results() -> pd.DataFrame:
    return _read("public_v2_results.csv")


def load_reference_schedule() -> pd.DataFrame:
    return _read("public_v2_our_schedule.csv")


def load_reference_node_summary() -> pd.DataFrame:
    return _read("public_v2_our_node_summary.csv")


def load_stress_summary() -> pd.DataFrame:
    return _read("stress_bp_summary.csv")


def load_ablation_results() -> pd.DataFrame:
    return _read("ablation_results.csv")


def load_monte_carlo_all() -> pd.DataFrame:
    return _read("monte_carlo_all.csv")


def load_monte_carlo_summary() -> pd.DataFrame:
    return _read("monte_carlo_summary.csv")


def load_scalability_results() -> pd.DataFrame:
    return _read("scalability_results.csv")


def load_text(name: str) -> str:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"缺少文本文件: {path}")
    return path.read_text(encoding="utf-8-sig")


def arrays_from_hourly(nodes: pd.DataFrame, hourly: pd.DataFrame):
    """将长表转换为与原MILP一致的 [node, hour] 数组。"""
    node_order = nodes["node"].tolist()
    H = int(hourly["hour"].max()) + 1
    shape = (len(node_order), H)
    out = {k: np.zeros(shape, dtype=float) for k in [
        "capacity", "bandwidth", "grid_price", "grid_ci", "green_available"
    ]}
    for i, node in enumerate(node_order):
        sub = hourly.loc[hourly["node"] == node].sort_values("hour")
        if len(sub) != H:
            raise ValueError(f"节点 {node} 的小时参数不完整：{len(sub)} != {H}")
        out["capacity"][i] = sub["capacity_cu"].to_numpy(float)
        out["bandwidth"][i] = sub["bandwidth_gb"].to_numpy(float)
        out["grid_price"][i] = sub["grid_price_cny_kwh"].to_numpy(float)
        out["grid_ci"][i] = sub["grid_ci_kg_kwh"].to_numpy(float)
        out["green_available"][i] = sub["green_available_kwh"].to_numpy(float)
    return out


def optional_csv(name: str) -> pd.DataFrame | None:
    path = DATA_DIR / name
    return pd.read_csv(path, encoding="utf-8-sig") if path.exists() else None
