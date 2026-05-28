#!/usr/bin/env python3
"""
C++ Engine Build Script
========================
Wraps CMake to build the raman_core C++ physics engine.

Usage:
    python scripts/build_cpp.py            # Build Release
    python scripts/build_cpp.py --debug    # Build Debug
    python scripts/build_cpp.py --test     # Build + Run tests
    python scripts/build_cpp.py --clean    # Clean build dir
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_cpp(build_type="Release", run_tests=False, clean=False):
    root = get_project_root()
    engine_dir = os.path.join(root, "engine_core")
    build_dir = os.path.join(engine_dir, "build")

    if clean:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
            print("✅ Build directory cleaned")
        return

    os.makedirs(build_dir, exist_ok=True)

    # CMake configure
    cmake_args = [
        "cmake",
        f"-DCMAKE_BUILD_TYPE={build_type}",
        "-DRAMAN_BUILD_TESTS=ON",
        "-DRAMAN_USE_OPENMP=ON",
        "..",
    ]

    print(f"🔧 Configuring CMake ({build_type})...")
    result = subprocess.run(cmake_args, cwd=build_dir)
    if result.returncode != 0:
        print("❌ CMake configure failed")
        sys.exit(1)

    # Build
    n_jobs = os.cpu_count() or 4
    build_args = ["cmake", "--build", ".", "--parallel", str(n_jobs)]

    print(f"🔨 Building with {n_jobs} parallel jobs...")
    result = subprocess.run(build_args, cwd=build_dir)
    if result.returncode != 0:
        print("❌ Build failed")
        sys.exit(1)

    print("✅ C++ engine built successfully")

    # Copy Python module to accessible location
    ext = ".pyd" if platform.system() == "Windows" else ".so"
    module_name = f"raman_core{ext}"
    module_path = None

    for dirpath, _, filenames in os.walk(build_dir):
        for f in filenames:
            if f.startswith("raman_core") and f.endswith(ext):
                module_path = os.path.join(dirpath, f)
                break

    if module_path:
        dest = os.path.join(root, "src", "backend", module_name)
        shutil.copy2(module_path, dest)
        print(f"📦 Module copied: {dest}")

    # Run tests
    if run_tests:
        print("\n🧪 Running C++ tests...")
        result = subprocess.run(["ctest", "--output-on-failure"],
                                cwd=build_dir)
        if result.returncode != 0:
            print("❌ Some tests failed")
            sys.exit(1)
        print("✅ All C++ tests passed")


def main():
    parser = argparse.ArgumentParser(description="Build RĀMAN C++ engine")
    parser.add_argument("--debug", action="store_true", help="Debug build")
    parser.add_argument("--test", action="store_true", help="Run tests after build")
    parser.add_argument("--clean", action="store_true", help="Clean build dir")
    args = parser.parse_args()

    build_type = "Debug" if args.debug else "Release"
    build_cpp(build_type, run_tests=args.test, clean=args.clean)


if __name__ == "__main__":
    main()
