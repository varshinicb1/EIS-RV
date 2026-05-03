"""
Stable per-machine fingerprint.

Why not ``uuid.getnode()`` alone
--------------------------------
Per the Python docs, ``uuid.getnode()`` falls back to a *random* 48-bit
integer when no readable MAC is available, with the multicast bit set
to indicate randomness. That means two consecutive calls on a machine
without a readable MAC can return different values — fatal for a
hardware-bound license.

What we use
-----------
We combine three platform-stable sources, hashed with SHA-256:

* **Linux**   — ``/etc/machine-id`` (set once at install, persistent).
* **macOS**   — ``IOPlatformUUID`` from ``ioreg`` (one per board).
* **Windows** — ``MachineGuid`` from
  ``HKLM\\SOFTWARE\\Microsoft\\Cryptography``.

If we cannot read the primary identifier, we fall back to a digest of:
hostname + cpu vendor/family/model + boot disk serial (best-effort) +
``uuid.getnode()`` with the random bit *cleared* — then explicitly
record that the fingerprint is degraded so the caller knows.

The function is pure-Python, no shell injection.
"""
from __future__ import annotations

import hashlib
import logging
import os
import platform
import socket
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HardwareFingerprint:
    """Result of a fingerprint computation. ``hex`` is what tokens bind to."""
    hex: str            # 64-char SHA-256 hex of the underlying inputs
    primary_source: str # "machine_id" | "macos_ioreg" | "windows_machineguid" | "fallback"
    degraded: bool      # True if we had to use the fallback path
    inputs: list[str]   # short, non-secret list of which sources we read

    @property
    def short(self) -> str:
        """First 12 chars of the hex — for human display only."""
        return self.hex[:12]


# ---- Per-OS readers --------------------------------------------------------


def _read_linux_machine_id() -> Optional[str]:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            text = Path(path).read_text(encoding="ascii", errors="replace").strip()
            if text and len(text) >= 8:
                return text
        except (OSError, FileNotFoundError):
            continue
    return None


def _read_macos_platform_uuid() -> Optional[str]:
    """Run ``ioreg`` to extract IOPlatformUUID. Pure subprocess, no shell."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    for line in out.splitlines():
        if "IOPlatformUUID" in line:
            # Line looks like: "IOPlatformUUID" = "ABCD-1234-..."
            parts = line.split("=")
            if len(parts) >= 2:
                value = parts[1].strip().strip('"').strip()
                if value:
                    return value
    return None


def _read_windows_machine_guid() -> Optional[str]:
    """Read MachineGuid from the registry without invoking a shell."""
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        try:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
        finally:
            winreg.CloseKey(key)
        return str(value) if value else None
    except OSError:
        return None


def _stable_node() -> Optional[str]:
    """Return the MAC address from ``uuid.getnode()`` ONLY if it isn't random."""
    node = uuid.getnode()
    # Per the Python docs: if no MAC is readable, getnode sets the multicast
    # bit (0x010000000000) to indicate randomness.
    if (node >> 40) & 0x01:
        return None
    return f"{node:012x}"


# ---- Public API ------------------------------------------------------------


def compute_fingerprint() -> HardwareFingerprint:
    """
    Compute and return the local machine fingerprint.

    Cheap to call; we don't memoise here so callers can re-evaluate after
    a known hardware change. Most code should go through
    ``LicenseManager`` which caches.
    """
    inputs: list[str] = []
    primary = "fallback"
    raw: Optional[str] = None

    if sys.platform.startswith("linux"):
        raw = _read_linux_machine_id()
        if raw:
            primary = "machine_id"
            inputs.append("machine_id")
    elif sys.platform == "darwin":
        raw = _read_macos_platform_uuid()
        if raw:
            primary = "macos_ioreg"
            inputs.append("ioreg")
    elif sys.platform.startswith("win"):
        raw = _read_windows_machine_guid()
        if raw:
            primary = "windows_machineguid"
            inputs.append("machineguid")

    degraded = raw is None

    if degraded:
        # Fallback: combine multiple noisy-but-correlated signals so the
        # hash is at least stable across a single boot, even if it can be
        # different across reinstalls.
        hostname = socket.gethostname() or "unknown-host"
        node = _stable_node() or "no-mac"
        plat = platform.platform()
        cpu = platform.processor() or platform.machine() or "unknown-cpu"
        raw = "|".join([hostname, node, plat, cpu])
        inputs = ["hostname", "node", "platform", "cpu"]
        logger.warning(
            "Hardware fingerprint is using degraded fallback "
            "(install /etc/machine-id or run as a real user to get a "
            "stable id)."
        )

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return HardwareFingerprint(
        hex=digest,
        primary_source=primary,
        degraded=degraded,
        inputs=inputs,
    )
