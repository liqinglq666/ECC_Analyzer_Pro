import numpy as np
from typing import Tuple

def validate_and_sort_data(strain: np.ndarray, stress: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    数据清洗、校验与排序（科研级 V7.2）

    功能：
    1. 维度对齐与极少点检查
    2. NaN / Inf 清洗
    3. 排序并去除重复应变点 (利用 np.unique 同时完成)
    4. 物理有效性范围检查

    Args:
        strain: 应变数组 (1D)
        stress: 应力数组 (1D)

    Returns:
        (strain, stress): 清洗并排序后的 float64 数组
    """

    # --------------------------------------------------
    # 0. 类型强制 (Type Enforcement)
    # --------------------------------------------------
    # 确保是 numpy 数组且为 float64，防止 int 类型导致计算精度问题
    strain = np.asarray(strain, dtype=np.float64).ravel()
    stress = np.asarray(stress, dtype=np.float64).ravel()

    # --------------------------------------------------
    # 1. 基本维度检查 (Dimension Check)
    # --------------------------------------------------
    if strain.shape[0] != stress.shape[0]:
        raise ValueError(
            f"Data Dimension Mismatch: Strain({strain.shape[0]}) vs Stress({stress.shape[0]})"
        )

    if strain.shape[0] < 5:
        raise ValueError("Insufficient Data Points (<5). Cannot perform reliable mechanics analysis.")

    # --------------------------------------------------
    # 2. 移除 NaN / Inf (Sanity Check)
    # --------------------------------------------------
    finite_mask = np.isfinite(strain) & np.isfinite(stress)
    if not np.all(finite_mask):
        strain = strain[finite_mask]
        stress = stress[finite_mask]

    if strain.size < 5:
        raise ValueError("Insufficient Valid Data (After removing NaN/Inf, points < 5).")

    # --------------------------------------------------
    # 3. 排序与去重 (Sort & Unique) - 核心优化
    # --------------------------------------------------
    # np.unique 返回的 unique_strain 默认已排序 (sorted)。
    # return_index=True 返回的是唯一值在原数组中 首次出现 的索引。
    # 这一步同时完成了：排序 + 去重 + 同步Stress索引
    unique_strain, unique_indices = np.unique(strain, return_index=True)

    # 只有当确实存在重复或乱序时，才进行重组，节省内存拷贝
    if unique_strain.size < strain.size or np.any(np.diff(unique_indices) < 0):
        strain = unique_strain
        stress = stress[unique_indices]

    if strain.size < 5:
        raise ValueError("Insufficient Unique Data (After removing duplicates, points < 5).")

    # --------------------------------------------------
    # 4. 物理有效性范围检查 (Physical Validity)
    # --------------------------------------------------
    # 防止传入一条直线（例如传感器未连接，全是 0），导致后续求导除以 0
    strain_span = strain[-1] - strain[0]
    if strain_span < 1e-9:
        raise ValueError(f"Strain Range too small ({strain_span:.2e}). Data appears to be static noise.")

    stress_span = np.max(stress) - np.min(stress)
    if stress_span < 1e-9:
        raise ValueError("Stress Range is zero. Sensor might be disconnected.")

    return strain, stress