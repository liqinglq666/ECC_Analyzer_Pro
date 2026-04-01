import numpy as np
from typing import List, Dict, Any, Union


class StatisticsCalculator:
    """
    核心统计模块 (V7.1 Optimized)
    负责计算一组实验数据的统计特征 (Mean, SD)。
    优化了键识别逻辑，防止因首个样本数据缺失导致整列被忽略的问题。
    """

    @staticmethod
    def get_group_stats(data_list: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        计算一组数据的统计摘要。

        Args:
            data_list: 包含多个样本结果字典的列表。

        Returns:
            dict: 统计结果字典。键名格式为 "{原键名}_mean" 和 "{原键名}_sd"。
        """
        if not data_list:
            return {}

        # 1. 鲁棒的键识别 (Robust Key Discovery)
        # 获取第一个有效项的所有潜在键，不再依赖其值是否为数字
        # 这样即使第一个样本的某个值为 None，只要它存在于键中，后续样本的值仍会被统计
        first_item = next((i for i in data_list if i), None)
        if not first_item:
            return {}

        candidate_keys = [k for k in first_item.keys() if not k.startswith("_")]

        # 初始化收集器
        collected_values = {k: [] for k in candidate_keys}

        # 2. 数据收集与清洗 (Collection & Cleaning)
        for item in data_list:
            for k in candidate_keys:
                val = item.get(k)
                # 严格过滤:
                # 1. 非 None
                # 2. 是数字 (int, float, 或 numpy 数值类型)
                # 3. 不是布尔值 (防止 True/False 干扰计算)
                if val is not None and isinstance(val, (int, float, np.number)) and not isinstance(val, bool):
                    # 4. 剔除 inf / nan
                    if np.isfinite(val):
                        collected_values[k].append(val)

        # 3. 统计计算 (Calculation)
        stats = {"count": len(data_list)}

        for k, vals in collected_values.items():
            # 只有收集到有效数据才计算，否则该字段在统计结果中不存在（比置0更安全，避免误导）
            if len(vals) > 0:
                arr = np.array(vals, dtype=np.float64)

                # 计算平均值
                mean_val = np.mean(arr)

                # 计算标准差 (Sample Standard Deviation, ddof=1)
                # 只有一个数据时 std=0
                std_val = np.std(arr, ddof=1) if len(arr) > 1 else 0.0

                # [Critical] 转回 Python float，防止 JSON/Excel 序列化问题
                stats[f"{k}_mean"] = float(mean_val)
                stats[f"{k}_sd"] = float(std_val)
            else:
                # 若某列完全无有效数据，显式置为 0 或 NaN，视需求而定，这里保持为 0
                stats[f"{k}_mean"] = 0.0
                stats[f"{k}_sd"] = 0.0

        return stats