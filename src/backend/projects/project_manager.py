"""
Encrypted-at-rest project storage.

Compared to the previous version
--------------------------------
The previous ProjectManager (665 LOC) had a hardcoded HMAC secret
shipped to every client (``b'raman_studio_project_integrity_v1'``),
used a "is encrypted" detection check based on whether the file
contained ``b'::'`` (false-positive for any URL or IPv6 address), and
was never wired into the API — every existing project route in
``server.py`` wrote plaintext JSON to ``data/projects.json``.

This rewrite
------------
* One Fernet-encrypted file per project.
* One encrypted index file mapping ``project_id → metadata`` for
  ``list_projects`` without decrypting every project.
* The Fernet key is derived from the local hardware fingerprint via
  PBKDF2-SHA256 (600 000 iterations). Moving a project file to a
  different machine renders it unreadable; that is by design.
* Project IDs are server-generated UUIDs. We never use a
  user-supplied string in a filesystem path.
* Atomic writes (write to .tmp, then ``os.replace``).
* No HMAC with a shipped secret. Fernet's built-in MAC, keyed by the
  PBKDF2-derived key, is the integrity guarantee.
* One-shot migration of any pre-existing ``data/projects.json`` on
  first call to ``list_projects``.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


# ---- Storage configuration ------------------------------------------------


PBKDF2_ITERS = 600_000
KDF_SALT = b"raman-studio-projects-v1"
PROJECT_FILE_EXT = ".proj"
MAX_NAME_LENGTH = 100
NAME_DISPLAY_RE = re.compile(r"[^a-zA-Z0-9_\-\s.]")  # for sanitising display names


def _user_data_dir() -> Path:
    """Same logic as license_manager — keep all user data under one tree."""
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    out = base / "raman-studio" / "projects"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ---- Errors ---------------------------------------------------------------


class ProjectError(RuntimeError):
    """Generic project-store error (validation, decrypt, missing, etc.)."""


class ProjectNotFound(ProjectError):
    pass


class ProjectIntegrityError(ProjectError):
    """Decryption failed — file tampered, corrupted, or from another machine."""


# ---- Data --------------------------------------------------------------


@dataclass
class Project:
    id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    author: str = ""
    notes: str = ""
    simulations: list[dict[str, Any]] = field(default_factory=list)
    materials: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "author": self.author,
            "notes": self.notes,
            "simulations": list(self.simulations),
            "materials": list(self.materials),
            "results": list(self.results),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or "Untitled Project")[:MAX_NAME_LENGTH],
            description=str(data.get("description") or ""),
            tags=list(data.get("tags") or []),
            created_at=float(data.get("created_at") or time.time()),
            modified_at=float(data.get("modified_at") or time.time()),
            author=str(data.get("author") or ""),
            notes=str(data.get("notes") or ""),
            simulations=list(data.get("simulations") or []),
            materials=list(data.get("materials") or []),
            results=list(data.get("results") or []),
            schema_version=int(data.get("schema_version") or 1),
        )


# ---- Index entry (light metadata for list_projects) -----------------------


def _index_entry(p: Project) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "tags": list(p.tags),
        "created_at": p.created_at,
        "modified_at": p.modified_at,
    }


# ---- Helpers ---------------------------------------------------------------


def _is_safe_id(project_id: str) -> bool:
    """Project ids must be hex/UUID-like — no path traversal possible."""
    if not project_id or len(project_id) > 64:
        return False
    return all(c in "0123456789abcdefABCDEF-" for c in project_id)


def _sanitise_display_name(name: str) -> str:
    """For user-visible names. We never put names into a file path."""
    name = (name or "").strip()
    if not name:
        return "Untitled Project"
    name = NAME_DISPLAY_RE.sub("", name)[:MAX_NAME_LENGTH].strip()
    return name or "Untitled Project"


# ---- The manager ----------------------------------------------------------


class ProjectManager:
    """
    Encrypted-at-rest project store.

    Construction is cheap. The hardware fingerprint is computed on the
    first call that needs the encryption key, then memoised.
    """

    INDEX_FILENAME = "index.dat"

    def __init__(
        self,
        *,
        projects_dir: Optional[Path] = None,
        legacy_plaintext_path: Optional[Path] = None,
    ) -> None:
        self._dir = projects_dir or _user_data_dir()
        self._legacy_path = legacy_plaintext_path
        self._key: Optional[bytes] = None
        self._migrated = False

    # ---- Encryption key (derived from hardware id) ----------------------

    def _derive_key(self) -> bytes:
        if self._key is not None:
            return self._key
        # Lazy import — avoids pulling hardware_id into modules that don't
        # need projects.
        from src.backend.licensing.hardware_id import compute_fingerprint
        hw = compute_fingerprint().hex.encode("ascii")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=KDF_SALT,
            iterations=PBKDF2_ITERS,
        )
        derived = kdf.derive(hw)
        self._key = base64.urlsafe_b64encode(derived)
        return self._key

    def _fernet(self) -> Fernet:
        return Fernet(self._derive_key())

    # ---- Atomic encrypted file ops --------------------------------------

    def _encrypt_to_file(self, path: Path, payload: dict[str, Any]) -> None:
        blob = self._fernet().encrypt(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(blob)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    def _decrypt_file(self, path: Path) -> dict[str, Any]:
        try:
            blob = path.read_bytes()
            data = self._fernet().decrypt(blob)
        except (InvalidToken, OSError) as e:
            raise ProjectIntegrityError(
                f"Failed to decrypt {path.name}: {e}. "
                f"This usually means the file was created on another machine, "
                f"or has been tampered with."
            ) from e
        try:
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            raise ProjectIntegrityError(
                f"Decrypted {path.name} but contents are not valid JSON: {e}"
            ) from e

    # ---- Index --------------------------------------------------------

    def _index_path(self) -> Path:
        return self._dir / self.INDEX_FILENAME

    def _read_index(self) -> dict[str, dict[str, Any]]:
        path = self._index_path()
        if not path.exists():
            return {}
        try:
            data = self._decrypt_file(path)
            entries = data.get("projects", {})
            if isinstance(entries, dict):
                return entries
            return {}
        except ProjectIntegrityError as e:
            logger.warning(
                "Project index unreadable (%s); rebuilding from project files.",
                e,
            )
            return self._rebuild_index()

    def _write_index(self, entries: dict[str, dict[str, Any]]) -> None:
        self._encrypt_to_file(
            self._index_path(),
            {"projects": entries, "updated_at": time.time()},
        )

    def _rebuild_index(self) -> dict[str, dict[str, Any]]:
        """Walk *.proj files, decrypt each, build a fresh index."""
        entries: dict[str, dict[str, Any]] = {}
        for path in sorted(self._dir.glob(f"*{PROJECT_FILE_EXT}")):
            project_id = path.stem
            if not _is_safe_id(project_id):
                continue
            try:
                project = Project.from_dict(self._decrypt_file(path))
                entries[project.id] = _index_entry(project)
            except ProjectIntegrityError:
                logger.warning("Skipping unreadable project %s", path.name)
                continue
        # Best-effort write — index is regenerable.
        try:
            self._write_index(entries)
        except Exception as e:
            logger.warning("Could not write rebuilt index: %s", e)
        return entries

    # ---- One-shot migration of plaintext data/projects.json ------------

    def _migrate_legacy_if_needed(self) -> None:
        if self._migrated:
            return
        self._migrated = True
        legacy = self._legacy_path
        if legacy is None or not legacy.exists():
            return
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cannot migrate legacy %s: %s", legacy, e)
            return
        if not isinstance(data, list):
            return

        index = self._read_index()
        added = 0
        for raw in data:
            if not isinstance(raw, dict):
                continue
            try:
                # Always reissue an id: the legacy ids were 8-char prefixes
                # that aren't long enough to feel safe.
                project = Project.from_dict({**raw, "id": uuid.uuid4().hex})
            except Exception:  # noqa: BLE001
                continue
            self._save_project(project)
            index[project.id] = _index_entry(project)
            added += 1

        if added:
            self._write_index(index)
            try:
                legacy.rename(legacy.with_suffix(".json.migrated"))
                logger.info(
                    "Migrated %d projects from %s into the encrypted store.",
                    added,
                    legacy,
                )
            except OSError:
                pass

    # ---- Per-project file ops ------------------------------------------

    def _project_path(self, project_id: str) -> Path:
        if not _is_safe_id(project_id):
            raise ProjectError(f"invalid project id {project_id!r}")
        return self._dir / f"{project_id}{PROJECT_FILE_EXT}"

    def _save_project(self, project: Project) -> None:
        self._encrypt_to_file(self._project_path(project.id), project.to_dict())

    # ---- Public API ----------------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        self._migrate_legacy_if_needed()
        index = self._read_index()
        return sorted(index.values(),
                      key=lambda e: e.get("modified_at", 0),
                      reverse=True)

    def create_project(
        self,
        *,
        name: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        author: str = "",
    ) -> Project:
        self._migrate_legacy_if_needed()
        project = Project(
            id=uuid.uuid4().hex,
            name=_sanitise_display_name(name),
            description=str(description or ""),
            tags=list(tags or []),
            author=str(author or ""),
        )
        self._save_project(project)
        index = self._read_index()
        index[project.id] = _index_entry(project)
        self._write_index(index)
        return project

    def get_project(self, project_id: str) -> Project:
        self._migrate_legacy_if_needed()
        path = self._project_path(project_id)
        if not path.exists():
            raise ProjectNotFound(project_id)
        return Project.from_dict(self._decrypt_file(path))

    def update_project(
        self,
        project_id: str,
        updates: dict[str, Any],
    ) -> Project:
        project = self.get_project(project_id)
        # Only allow whitelisted fields to be updated from request bodies.
        for key in ("name", "description", "tags", "author", "notes",
                    "simulations", "materials", "results"):
            if key in updates:
                setattr(project, key,
                        _sanitise_display_name(updates[key])
                        if key == "name" else updates[key])
        project.modified_at = time.time()
        self._save_project(project)
        index = self._read_index()
        index[project.id] = _index_entry(project)
        self._write_index(index)
        return project

    def delete_project(self, project_id: str) -> None:
        self._migrate_legacy_if_needed()
        path = self._project_path(project_id)
        index = self._read_index()
        index.pop(project_id, None)
        self._write_index(index)
        if path.exists():
            try:
                path.unlink()
            except OSError as e:
                logger.warning("Could not delete %s: %s", path, e)

    def add_simulation(
        self,
        project_id: str,
        simulation: dict[str, Any],
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        sim = {
            "id": uuid.uuid4().hex[:12],
            "type": str(simulation.get("type") or "eis"),
            "params": dict(simulation.get("params") or {}),
            "result": dict(simulation.get("result") or {}),
            "timestamp": time.time(),
        }
        project.simulations.append(sim)
        project.modified_at = time.time()
        self._save_project(project)
        index = self._read_index()
        index[project.id] = _index_entry(project)
        self._write_index(index)
        return sim

    # ---- Import / export (clearly plaintext — caller's choice) ---------

    def export_project(self, project_id: str) -> dict[str, Any]:
        """
        Return the project as a plain dict. The caller is responsible
        for telling the user the export is not encrypted at rest if
        written to disk.
        """
        return self.get_project(project_id).to_dict()

    def import_project(self, payload: dict[str, Any]) -> Project:
        # Reissue the id — never trust the source's id (it may collide,
        # be malicious, or be a relative path that an old client wrote).
        payload = dict(payload)
        payload["id"] = uuid.uuid4().hex
        project = Project.from_dict(payload)
        project.modified_at = time.time()
        self._save_project(project)
        index = self._read_index()
        index[project.id] = _index_entry(project)
        self._write_index(index)
        return project


# ---- Module-level singleton ---------------------------------------------

_singleton: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    global _singleton
    if _singleton is None:
        # The legacy plaintext file the old routes used.
        legacy = Path(__file__).resolve().parents[3] / "data" / "projects.json"
        _singleton = ProjectManager(legacy_plaintext_path=legacy)
    return _singleton


def reset_project_manager() -> None:
    """For tests."""
    global _singleton
    _singleton = None
