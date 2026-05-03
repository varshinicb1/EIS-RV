#!/usr/bin/env python3
"""
Nuitka Build Script
====================
Compiles the Python backend into a standalone binary using Nuitka.

Usage:
    python scripts/build_nuitka.py              # Release build
    python scripts/build_nuitka.py --debug       # Debug build
    python scripts/build_nuitka.py --onefile     # Single executable
"""

import argparse
import os
import platform
import subprocess
import sys


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_nuitka(debug=False, onefile=False):
    root = get_project_root()
    # Canonical FastAPI entry point lives at src/backend/api/server.py.
    # The old vanl/backend/main.py was retired in Phase 1.
    entry = os.path.join(root, "src", "backend", "api", "server.py")
    out_dir = os.path.join(root, "dist", "backend")

    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        f"--output-dir={out_dir}",
        "--python-flag=no_site",
        "--include-package=fastapi",
        "--include-package=uvicorn",
        "--include-package=pydantic",
        "--include-package=starlette",
        "--include-package=numpy",
        "--include-package=sklearn",
        "--include-data-dir=data/datasets=datasets",
        "--enable-plugin=numpy",
        "--company-name=VidyuthLabs",
        "--product-name=RAMAN-Studio-Backend",
        "--file-version=2.0.0",
        "--product-version=2.0.0",
    ]

    if onefile:
        cmd.append("--onefile")

    if debug:
        cmd.append("--debug")
    else:
        cmd.extend([
            "--lto=yes",
            "--remove-output",
        ])

    if platform.system() == "Linux":
        cmd.append("--linux-icon=resources/icon.png")
    elif platform.system() == "Windows":
        cmd.append("--windows-icon-from-ico=resources/icon.ico")
        cmd.append("--windows-console-mode=disable")

    cmd.append(entry)

    print(f"🔨 Nuitka build starting...")
    print(f"   Entry: {entry}")
    print(f"   Output: {out_dir}")
    print(f"   Mode: {'onefile' if onefile else 'standalone'}")
    print(f"   Config: {'debug' if debug else 'release'}")
    print()

    result = subprocess.run(cmd, cwd=root)
    if result.returncode != 0:
        print("❌ Nuitka build failed")
        sys.exit(1)

    print("✅ Nuitka build complete")
    print(f"📦 Output: {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Build RĀMAN backend with Nuitka")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--onefile", action="store_true")
    args = parser.parse_args()
    build_nuitka(debug=args.debug, onefile=args.onefile)


if __name__ == "__main__":
    main()
