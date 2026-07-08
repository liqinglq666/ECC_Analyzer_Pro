import json
from pathlib import Path
from typing import Any, Dict


class MaterialConstants:
    """
    ECC Analyzer Pro global configuration manager.

    Notes
    -----
    The values in this class are intentionally plain Python types so they can be
    safely serialized to ~/.ecc_analyzer_config.json and restored across runs.
    """

    # --- Config file path ---
    _CONFIG_PATH = Path.home().resolve() / ".ecc_analyzer_config.json"

    # ==========================================
    # 1. Geometry & units
    # ==========================================
    GAUGE_LENGTH_MM: float = 80.0

    # Strain unit policy:
    #   "auto"    -> infer by STRAIN_PERCENT_THRESHOLD
    #   "percent" -> input is 0.5 for 0.5%, internally converted to 0.005
    #   "decimal" -> input is 0.005 for 0.5%
    STRAIN_UNIT: str = "auto"
    STRAIN_PERCENT_THRESHOLD: float = 0.2

    # Compression machines often export compressive stress as negative values.
    # When enabled, compressive stress is converted to magnitude before analysis.
    COMPRESSIVE_STRESS_ABS: bool = True

    # ==========================================
    # 2. Modulus extraction
    # ==========================================
    ELASTIC_LOWER_RATIO: float = 0.10
    ELASTIC_UPPER_RATIO: float = 0.40
    ELASTIC_STRAIN_LIMIT: float = 0.0005
    INITIAL_MODULUS_SEARCH_LIMIT: float = 0.15
    INITIAL_MODULUS_PERCENTILE: float = 0.10

    # ==========================================
    # 3. First cracking / LOP criteria
    # ==========================================
    CRACK_TOLERANCE_BASE: float = 0.05
    CRACK_TOLERANCE_RATIO: float = 0.01
    CRACK_STIFFNESS_CONSTRAINT: float = 0.85
    CRACK_MIN_STRESS_RATIO: float = 0.10

    # ==========================================
    # 4. Ultimate / failure criterion
    # ==========================================
    ULTIMATE_STRAIN_RATIO: float = 0.85
    ZERO_STRESS_THRESHOLD: float = 0.01

    # ==========================================
    # 5. Signal processing
    # ==========================================
    PEAK_SMOOTH_WINDOW: int = 5
    SMOOTH_WINDOW: int = 15
    SMOOTH_POLY: int = 3

    # ==========================================
    # 6. Visualization
    # ==========================================
    STYLE_COLOR_RAW: str = "#2c3e50"
    STYLE_COLOR_SMOOTH: str = "#2c3e50"
    STYLE_LINE_WIDTH: float = 1.5
    STYLE_RAW_ALPHA: float = 0.6

    _DEFAULTS: Dict[str, Any] = {}

    @classmethod
    def _cache_defaults(cls):
        """Cache default uppercase configuration values once."""
        if not cls._DEFAULTS:
            for key in dir(cls):
                if key.isupper() and not key.startswith("_"):
                    cls._DEFAULTS[key] = getattr(cls, key)

    @classmethod
    def _coerce_value(cls, key: str, value: Any) -> Any:
        """Coerce loaded UI/JSON values back to their default Python types."""
        default = cls._DEFAULTS.get(key, getattr(cls, key, value))
        target_type = type(default)

        if target_type is bool:
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
        if target_type is int and not isinstance(value, bool):
            return int(value)
        if target_type is float:
            return float(value)
        if target_type is str:
            return str(value)
        return value

    @classmethod
    def load_config(cls):
        """Load user configuration from ~/.ecc_analyzer_config.json."""
        cls._cache_defaults()
        if not cls._CONFIG_PATH.exists():
            return

        try:
            with open(cls._CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, value in data.items():
                if hasattr(cls, key) and key.isupper():
                    try:
                        setattr(cls, key, cls._coerce_value(key, value))
                    except (ValueError, TypeError):
                        print(f"Warning: Config type mismatch for {key}, keeping current value.")
        except Exception as e:
            print(f"Config load failed: {e}")

    @classmethod
    def update_config(cls, **kwargs):
        """Update configuration values and persist them to disk."""
        cls._cache_defaults()
        changed = False

        for key, value in kwargs.items():
            if hasattr(cls, key) and key.isupper():
                try:
                    setattr(cls, key, cls._coerce_value(key, value))
                    changed = True
                except (ValueError, TypeError):
                    print(f"Warning: Config update ignored for {key}: {value!r}")

        if changed:
            cls._save_config()

    @classmethod
    def reset_defaults(cls):
        """Restore factory defaults and save them."""
        cls._cache_defaults()
        for key, val in cls._DEFAULTS.items():
            setattr(cls, key, val)
        cls._save_config()

    @classmethod
    def _save_config(cls):
        """Persist primitive uppercase configuration values to JSON."""
        data = {}
        for key in dir(cls):
            if key.isupper() and not key.startswith("_"):
                val = getattr(cls, key)
                if isinstance(val, (int, float, str, bool)):
                    data[key] = val

        try:
            with open(cls._CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Config save failed: {e}")


MaterialConstants._cache_defaults()
