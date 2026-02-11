import json
from pathlib import Path
from typing import Any, Dict


class MaterialConstants:
    """
    ECC 物理常数与全局配置管理器 V21.1 (Robust Edition)
    - 核心功能：管理物理参数、算法阈值及绘图样式。
    - 健壮性：增加了类型强制转换和默认值回滚机制。
    - 持久化：配置保存在用户主目录，跨会话生效。
    """

    # --- 配置文件路径 (跨平台兼容) ---
    # Windows: C:\Users\Username\.ecc_analyzer_config.json
    # Linux/Mac: /home/username/.ecc_analyzer_config.json
    _CONFIG_PATH = Path.home().resolve() / ".ecc_analyzer_config.json"

    # ==========================================
    # 1. 几何与物理参数 (Geometry & Physics)
    # ==========================================
    GAUGE_LENGTH_MM: float = 80.0  # 标距 (mm)
    STRAIN_PERCENT_THRESHOLD: float = 0.2  # 应变阈值

    # ==========================================
    # 2. 弹性模量 (Modulus)
    # ==========================================
    ELASTIC_LOWER_RATIO: float = 0.10  # 拟合起点 (10% Peak)
    ELASTIC_UPPER_RATIO: float = 0.40  # 拟合终点 (40% Peak)
    INITIAL_MODULUS_SEARCH_LIMIT: float = 0.15

    # ==========================================
    # 3. 开裂判定 (Cracking)
    # ==========================================
    CRACK_TOLERANCE_BASE: float = 0.05  # 偏离线性的容差 (MPa)

    # ==========================================
    # 4. 极限状态 (Ultimate)
    # ==========================================
    ULTIMATE_STRAIN_RATIO: float = 0.85  # 峰后下降至 85% 视为破坏

    # ==========================================
    # 5. 数据处理 (Processing)
    # ==========================================
    SMOOTH_WINDOW: int = 11  # 平滑窗口 (必须是奇数)
    SMOOTH_POLY: int = 3  # 多项式阶数

    # ==========================================
    # 6. 绘图样式 (Visualization)
    # ==========================================
    STYLE_LINE_WIDTH: float = 1.5  # 默认线宽
    STYLE_COLOR_RAW: str = "#2c3e50"  # 默认曲线颜色 (Scientific Blue)
    STYLE_RAW_ALPHA: float = 0.8  # 透明度

    # 备份默认值用于重置
    _DEFAULTS = {}

    @classmethod
    def _cache_defaults(cls):
        """缓存类加载时的初始值"""
        if not cls._DEFAULTS:
            for key in dir(cls):
                if key.isupper() and not key.startswith("_"):
                    cls._DEFAULTS[key] = getattr(cls, key)

    @classmethod
    def load_config(cls):
        """从本地 JSON 加载配置，覆盖内存值"""
        cls._cache_defaults()  # 首次运行时缓存默认值

        if not cls._CONFIG_PATH.exists():
            return

        try:
            with open(cls._CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 动态更新类属性 (仅更新已存在的大写属性)
            for key, value in data.items():
                if hasattr(cls, key) and key.isupper():
                    # [Critical] 类型安全转换：确保加载的数据类型与默认值一致
                    target_type = type(cls._DEFAULTS.get(key, value))
                    try:
                        if target_type == int:
                            setattr(cls, key, int(value))
                        elif target_type == float:
                            setattr(cls, key, float(value))
                        else:
                            setattr(cls, key, value)
                    except (ValueError, TypeError):
                        print(f"Warning: Config type mismatch for {key}, keeping default.")
                        continue
        except Exception as e:
            print(f"Config load failed: {e}")

    @classmethod
    def update_config(cls, **kwargs):
        """
        更新配置并自动保存。
        用法: MaterialConstants.update_config(GAUGE_LENGTH_MM=100.0)
        """
        changed = False
        cls._cache_defaults()

        for key, value in kwargs.items():
            if hasattr(cls, key) and key.isupper():
                # [Critical] 强制类型检查
                default_val = cls._DEFAULTS.get(key)
                if default_val is not None:
                    target_type = type(default_val)
                    if not isinstance(value, target_type):
                        try:
                            value = target_type(value)
                        except:
                            continue  # 转换失败则忽略该参数

                setattr(cls, key, value)
                changed = True

        if changed:
            cls._save_config()

    @classmethod
    def reset_defaults(cls):
        """恢复出厂设置"""
        if not cls._DEFAULTS: return

        for key, val in cls._DEFAULTS.items():
            setattr(cls, key, val)
        cls._save_config()

    @classmethod
    def _save_config(cls):
        """持久化保存到 JSON"""
        data = {}
        for key in dir(cls):
            if key.isupper() and not key.startswith("_"):
                val = getattr(cls, key)
                # 仅保存基础类型
                if isinstance(val, (int, float, str, bool)):
                    data[key] = val

        try:
            with open(cls._CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Config save failed: {e}")


# 初始化缓存
MaterialConstants._cache_defaults()