"""Minimal core smoke test for ECC Analyzer Pro.

Run from repository root:
    python scripts/smoke_test.py

This does not open the GUI. It only checks that the core analyzers can process
representative tensile and compressive arrays.
"""

import numpy as np

from app.core.physics import MaterialConstants
from app.core.algorithms import TensileAnalyzer, CompressiveAnalyzer


def main():
    MaterialConstants.update_config(STRAIN_UNIT="percent")

    strain_pct = np.linspace(0.0, 4.0, 240)
    stress = np.piecewise(
        strain_pct,
        [strain_pct <= 0.06, (strain_pct > 0.06) & (strain_pct <= 3.2), strain_pct > 3.2],
        [
            lambda x: 30.0 * x,
            lambda x: 1.8 + 0.25 * np.sin(x * 8.0) + 0.12 * x,
            lambda x: 2.1 - 0.9 * (x - 3.2),
        ],
    )
    tensile = TensileAnalyzer(strain_pct, stress).run_analysis()
    assert tensile["Ultimate Stress (MPa)"] > 0
    assert tensile["Ultimate Strain (%)"] > 0

    comp = CompressiveAnalyzer(np.array([0.0]), np.array([-42.5])).run_analysis()
    assert comp["Peak Stress (MPa)"] == 42.5

    print("Smoke test passed.")
    print("Tensile ultimate stress:", round(tensile["Ultimate Stress (MPa)"], 3), "MPa")
    print("Compressive strength:", comp["Peak Stress (MPa)"], "MPa")


if __name__ == "__main__":
    main()
