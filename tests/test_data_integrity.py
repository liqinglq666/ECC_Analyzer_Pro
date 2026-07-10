from __future__ import annotations

import numpy as np

from app.core.algorithms import TensileAnalyzer
from app.data.loader import DataLoader


def test_missing_first_crack_is_not_replaced_by_peak():
    strain = np.linspace(0.0, 0.01, 101)
    stress = 20_000.0 * strain

    result = TensileAnalyzer(strain, stress).run_analysis()

    assert result["First Crack Status"] == "not_detected"
    assert np.isnan(result["First Crack Strength (MPa)"])
    assert result["_idx_cr"] is None


def test_malformed_csv_is_reported(tmp_path):
    path = tmp_path / "broken.csv"
    path.write_text("strain,stress\n0,0\n0.1,1,extra\n", encoding="utf-8")

    samples, error = DataLoader.load_file_smart(path)

    assert samples is None
    assert error is not None
    assert "CSV Parse Error" in error
