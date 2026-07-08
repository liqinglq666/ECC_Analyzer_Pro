"""Build ECC Analyzer Pro as a Windows portable executable package.

Usage on Windows:
    python -m pip install -r requirements.txt pyinstaller
    python scripts/build_exe.py

Output:
    dist/ECC_Analyzer_Pro/
        ECC Analyzer Pro.exe
        _internal/...

For PySide6 + Matplotlib desktop applications, the onedir package is more
reliable than onefile. Zip the whole dist/ECC_Analyzer_Pro folder when sharing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "ECC_Analyzer_Pro.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
TARGET = DIST / "ECC_Analyzer_Pro"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    if not SPEC.exists():
        raise FileNotFoundError(f"Missing spec file: {SPEC}")

    for path in (BUILD, TARGET):
        if path.exists():
            shutil.rmtree(path)

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC),
    ])

    exe = TARGET / "ECC Analyzer Pro.exe"
    if not exe.exists():
        raise FileNotFoundError(f"Build finished but executable was not found: {exe}")

    print("\nBuild finished successfully.")
    print(f"Portable package: {TARGET}")
    print("Zip the whole ECC_Analyzer_Pro folder before sharing.")


if __name__ == "__main__":
    main()
