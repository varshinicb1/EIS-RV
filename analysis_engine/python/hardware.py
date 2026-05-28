"""
hardware.py — detect the available compute hardware (GPU / CPU).

Used by the Express API (`/api/hardware`) to display a badge in the UI and by
the analysis pipeline to decide whether to use a GPU-accelerated path for ML
diagnostics.

We deliberately avoid heavy imports (torch / cupy) so this module is fast,
cheap, and safe to call on every request.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GpuInfo:
    name: str
    memory_mb: int | None
    driver: str | None


@dataclass(frozen=True)
class HardwareInfo:
    platform: str
    python_version: str
    cpu_count: int
    has_gpu: bool
    gpu_vendor: str | None  # "nvidia" | "amd" | "apple" | None
    gpus: list[GpuInfo]
    accelerators: list[str]  # e.g. ["cuda", "torch", "cupy"]
    summary: str


def _run(cmd: list[str], timeout: float = 2.5) -> str | None:
    """Run a small command and return its stdout, or None on failure."""
    if not shutil.which(cmd[0]):
        return None
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _detect_nvidia() -> list[GpuInfo]:
    """Detect NVIDIA GPUs via nvidia-smi."""
    out = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    if not out:
        return []
    gpus: list[GpuInfo] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 1 and parts[0]:
            try:
                memory_mb = int(parts[1]) if len(parts) > 1 and parts[1] else None
            except ValueError:
                memory_mb = None
            driver = parts[2] if len(parts) > 2 else None
            gpus.append(GpuInfo(name=parts[0], memory_mb=memory_mb, driver=driver))
    return gpus


def _detect_amd() -> list[GpuInfo]:
    """Detect AMD GPUs via rocm-smi."""
    out = _run(["rocm-smi", "--showproductname", "--csv"])
    if not out:
        return []
    gpus: list[GpuInfo] = []
    for line in out.strip().splitlines():
        if "device" in line.lower() and "name" in line.lower():
            continue  # header
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[1]:
            gpus.append(GpuInfo(name=parts[1], memory_mb=None, driver=None))
    return gpus


def _detect_apple() -> list[GpuInfo]:
    """Detect Apple Silicon GPU via sysctl (Apple Metal)."""
    if platform.system() != "Darwin":
        return []
    out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if not out:
        return []
    brand = out.strip()
    if brand.startswith("Apple "):
        return [GpuInfo(name=f"{brand} (Metal)", memory_mb=None, driver=None)]
    return []


def _available_accelerator_libs() -> list[str]:
    """List installed Python accelerator libraries (without importing them).

    Uses `importlib.util.find_spec`, which only checks if the module *could*
    be imported. Calling `__import__("torch")` here would actually load
    PyTorch (multi-second CUDA initialisation), so we deliberately avoid it.
    """
    libs: list[str] = []
    for mod_name in ("torch", "cupy", "tensorflow", "jax", "numba"):
        try:
            if importlib.util.find_spec(mod_name) is not None:
                libs.append(mod_name)
        except (ImportError, ValueError):
            # Some namespace packages raise on find_spec when partially installed.
            pass
    return libs


def detect_hardware() -> HardwareInfo:
    nvidia = _detect_nvidia()
    amd = _detect_amd() if not nvidia else []
    apple = _detect_apple() if not (nvidia or amd) else []

    gpus = nvidia or amd or apple
    has_gpu = bool(gpus)
    vendor = "nvidia" if nvidia else "amd" if amd else "apple" if apple else None

    libs = _available_accelerator_libs()
    accelerators: list[str] = []
    if nvidia:
        accelerators.append("cuda")
    if amd:
        accelerators.append("rocm")
    if apple:
        accelerators.append("metal")
    accelerators.extend(libs)

    cpu_count = os.cpu_count() or 1

    if has_gpu and gpus:
        summary = f"{vendor.upper() if vendor else 'GPU'}: {gpus[0].name}"
        if gpus[0].memory_mb:
            summary += f" ({gpus[0].memory_mb // 1024} GB)"
        if len(gpus) > 1:
            summary += f" +{len(gpus) - 1} more"
    else:
        summary = f"CPU only · {cpu_count} cores"

    return HardwareInfo(
        platform=f"{platform.system()} {platform.machine()}",
        python_version=platform.python_version(),
        cpu_count=cpu_count,
        has_gpu=has_gpu,
        gpu_vendor=vendor,
        gpus=gpus,
        accelerators=accelerators,
        summary=summary,
    )


def hardware_to_dict(info: HardwareInfo) -> dict:
    """Serialise HardwareInfo to a plain dict (for JSON)."""
    return {
        "platform": info.platform,
        "pythonVersion": info.python_version,
        "cpuCount": info.cpu_count,
        "hasGpu": info.has_gpu,
        "gpuVendor": info.gpu_vendor,
        "gpus": [asdict(g) for g in info.gpus],
        "accelerators": info.accelerators,
        "summary": info.summary,
    }


def main() -> None:
    info = detect_hardware()
    json.dump(hardware_to_dict(info), sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
