"""
Lab dataset manager — encrypted-at-rest storage for user-supplied data.

Why this exists
---------------
We want the user's own measurements to be the **first** thing
``AlchemiBridge.estimate_properties`` consults — before the curated 48-
material reference DB, before the LLM estimate, before any cloud call.
Their lab data is more relevant to their work than any general
prediction.

Storage format
--------------
Same envelope as ``ProjectManager``: per-dataset Fernet blob under

    <user_data_dir>/lab_datasets/<dataset_id>.lds

with a separate encrypted index file mapping ``dataset_id → metadata``
for fast listing. The encryption key is derived from the local hardware
fingerprint via PBKDF2-SHA256 (600 000 iterations); moving a dataset
file to another machine renders it unreadable. That is by design —
the user's data is bound to their license seat.

Schema
------
A dataset is a list of rows. Each row is::

    {
      "formula":     str,            # e.g. "MnO2"
      "name":        str | None,     # human-friendly tag
      "conditions":  dict,           # arbitrary kv: pH, T_K, electrolyte, etc.
      "properties":  dict,           # measurements: band_gap_eV, conductivity_S_m, ...
      "notes":       str,
      "source":      str | None,     # "internal", "doi:...", etc.
      "created_at":  float (unix s)
    }

Dataset-level metadata::

    {
      "id":          str (uuid),
      "name":        str,
      "description": str,
      "row_count":   int,
      "created_at":  float,
      "modified_at": float
    }

Lookup semantics
----------------
``lookup(formula)`` returns the most-recently-modified row whose formula
matches the query (case-insensitive, whitespace-stripped). If multiple
rows match, return them all so the caller can decide.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


# ---- Storage ----------------------------------------------------------


PBKDF2_ITERS = 600_000
KDF_SALT = b"raman-studio-lab-datasets-v1"
DATASET_FILE_EXT = ".lds"
MAX_NAME_LENGTH = 100
NAME_DISPLAY_RE = re.compile(r"[^a-zA-Z0-9_\-\s.]")
MAX_ROWS_PER_DATASET = 100_000
MAX_FORMULA_LEN = 80


def _user_data_dir() -> Path:
    """Same logic as license_manager / project_manager."""
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    out = base / "raman-studio" / "lab_datasets"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ---- Errors ---------------------------------------------------------


class LabError(RuntimeError):
    """Generic lab-data error."""


class DatasetNotFound(LabError):
    pass


class DatasetIntegrityError(LabError):
    """Decryption failed — file tampered, corrupted, or from another machine."""


class ImportError_(LabError):
    """Bad CSV / JSON payload at import."""


# ---- Helpers --------------------------------------------------------


def _is_safe_id(s: str) -> bool:
    if not s or len(s) > 64:
        return False
    return all(c in "0123456789abcdefABCDEF-" for c in s)


def _normalise_formula(f: Any) -> str:
    """Cheap canonical form for lookup: trim + collapse whitespace."""
    s = str(f or "").strip()
    return re.sub(r"\s+", "", s)[:MAX_FORMULA_LEN]


def _safe_dict(d: Any) -> dict[str, Any]:
    """Return ``d`` if it's a real dict; else an empty one."""
    return dict(d) if isinstance(d, dict) else {}


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    """Validate + normalise a single dataset row."""
    formula = _normalise_formula(row.get("formula"))
    if not formula:
        raise ImportError_("row is missing a non-empty 'formula' field")
    return {
        "formula":    formula,
        "name":       (str(row.get("name")) if row.get("name") else None),
        "conditions": _safe_dict(row.get("conditions")),
        "properties": _safe_dict(row.get("properties")),
        "notes":      str(row.get("notes") or ""),
        "source":     (str(row.get("source")) if row.get("source") else None),
        "created_at": float(row.get("created_at") or time.time()),
    }


def _sanitise_name(s: Any) -> str:
    s = (str(s or "")).strip()
    if not s:
        return "Untitled dataset"
    s = NAME_DISPLAY_RE.sub("", s)[:MAX_NAME_LENGTH].strip()
    return s or "Untitled dataset"


# ---- Manager --------------------------------------------------------


@dataclass
class Dataset:
    id: str
    name: str
    description: str = ""
    rows: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rows": list(self.rows),
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Dataset":
        rows = [_coerce_row(r) for r in (data.get("rows") or [])
                if isinstance(r, dict)]
        return cls(
            id=str(data["id"]),
            name=_sanitise_name(data.get("name")),
            description=str(data.get("description") or ""),
            rows=rows,
            created_at=float(data.get("created_at") or time.time()),
            modified_at=float(data.get("modified_at") or time.time()),
        )


def _index_entry(d: Dataset) -> dict[str, Any]:
    return {
        "id":          d.id,
        "name":        d.name,
        "description": d.description,
        "row_count":   len(d.rows),
        "created_at":  d.created_at,
        "modified_at": d.modified_at,
    }


class LabDatasetManager:
    """Encrypted-at-rest store for user-supplied experimental data."""

    INDEX_FILENAME = "index.dat"

    def __init__(self, *, datasets_dir: Optional[Path] = None) -> None:
        self._dir = datasets_dir or _user_data_dir()
        self._key: Optional[bytes] = None

    # ---- Crypto --------------------------------------------------

    def _derive_key(self) -> bytes:
        if self._key is not None:
            return self._key
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
            raise DatasetIntegrityError(
                f"Failed to decrypt {path.name}: {e}. "
                f"This usually means the file was created on another machine."
            ) from e
        try:
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            raise DatasetIntegrityError(
                f"Decrypted {path.name} but contents are not valid JSON: {e}"
            ) from e

    # ---- Index ---------------------------------------------------

    def _index_path(self) -> Path:
        return self._dir / self.INDEX_FILENAME

    def _read_index(self) -> dict[str, dict[str, Any]]:
        path = self._index_path()
        if not path.exists():
            return {}
        try:
            data = self._decrypt_file(path)
            entries = data.get("datasets", {})
            return entries if isinstance(entries, dict) else {}
        except DatasetIntegrityError as e:
            logger.warning("Lab index unreadable (%s); rebuilding.", e)
            return self._rebuild_index()

    def _write_index(self, entries: dict[str, dict[str, Any]]) -> None:
        self._encrypt_to_file(
            self._index_path(),
            {"datasets": entries, "updated_at": time.time()},
        )

    def _rebuild_index(self) -> dict[str, dict[str, Any]]:
        entries: dict[str, dict[str, Any]] = {}
        for path in sorted(self._dir.glob(f"*{DATASET_FILE_EXT}")):
            ds_id = path.stem
            if not _is_safe_id(ds_id):
                continue
            try:
                d = Dataset.from_dict(self._decrypt_file(path))
                entries[d.id] = _index_entry(d)
            except DatasetIntegrityError:
                continue
        try:
            self._write_index(entries)
        except Exception as e:
            logger.warning("Could not write rebuilt lab index: %s", e)
        return entries

    # ---- Per-dataset ops ----------------------------------------

    def _dataset_path(self, dataset_id: str) -> Path:
        if not _is_safe_id(dataset_id):
            raise LabError(f"invalid dataset id {dataset_id!r}")
        return self._dir / f"{dataset_id}{DATASET_FILE_EXT}"

    def _save_dataset(self, ds: Dataset) -> None:
        self._encrypt_to_file(self._dataset_path(ds.id), ds.to_dict())

    # ---- Public API ---------------------------------------------

    def list_datasets(self) -> list[dict[str, Any]]:
        """Return summary metadata for every dataset; rows excluded."""
        return sorted(
            self._read_index().values(),
            key=lambda e: e.get("modified_at", 0),
            reverse=True,
        )

    def create_dataset(self, *, name: str, description: str = "") -> Dataset:
        ds = Dataset(
            id=uuid.uuid4().hex,
            name=_sanitise_name(name),
            description=str(description or ""),
        )
        self._save_dataset(ds)
        index = self._read_index()
        index[ds.id] = _index_entry(ds)
        self._write_index(index)
        return ds

    def get_dataset(self, dataset_id: str) -> Dataset:
        path = self._dataset_path(dataset_id)
        if not path.exists():
            raise DatasetNotFound(dataset_id)
        return Dataset.from_dict(self._decrypt_file(path))

    def delete_dataset(self, dataset_id: str) -> None:
        path = self._dataset_path(dataset_id)
        index = self._read_index()
        index.pop(dataset_id, None)
        self._write_index(index)
        if path.exists():
            try:
                path.unlink()
            except OSError as e:
                logger.warning("Could not delete %s: %s", path, e)

    def add_rows(
        self,
        dataset_id: str,
        rows: Iterable[dict[str, Any]],
    ) -> int:
        ds = self.get_dataset(dataset_id)
        new_rows: list[dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            try:
                new_rows.append(_coerce_row(r))
            except ImportError_ as e:
                logger.warning("Skipping bad row: %s", e)
        ds.rows.extend(new_rows)
        if len(ds.rows) > MAX_ROWS_PER_DATASET:
            raise LabError(
                f"dataset would exceed {MAX_ROWS_PER_DATASET} rows"
            )
        ds.modified_at = time.time()
        self._save_dataset(ds)
        index = self._read_index()
        index[ds.id] = _index_entry(ds)
        self._write_index(index)
        return len(new_rows)

    # ---- Imports -------------------------------------------------

    def import_csv(
        self,
        dataset_id: str,
        csv_text: str,
        *,
        formula_col: str = "formula",
    ) -> int:
        """
        Import rows from a CSV string. Required column: ``formula``.
        Other columns are partitioned into ``properties`` if their name
        looks like a property (band_gap, conductivity, density, ...) or
        ``conditions`` (pH, temperature, electrolyte, ...). Numeric values
        are coerced to floats; everything else is kept as a string.
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames or formula_col not in reader.fieldnames:
            raise ImportError_(
                f"CSV must have a '{formula_col}' column. "
                f"Got: {reader.fieldnames}"
            )

        property_keys = {
            "band_gap_ev", "bandgap_ev", "conductivity_s_m",
            "density_g_cm3", "formation_energy_ev_per_atom",
            "specific_capacitance_f_g", "rs_ohm", "rct_ohm",
            "cdl_f", "cdl_f_cm2", "ionic_conductivity_s_cm",
        }
        rows: list[dict[str, Any]] = []
        for raw in reader:
            formula = raw.get(formula_col)
            if not formula or not formula.strip():
                continue
            properties: dict[str, Any] = {}
            conditions: dict[str, Any] = {}
            notes_parts: list[str] = []
            name = None
            source = None
            for k, v in raw.items():
                if k == formula_col or v is None or v == "":
                    continue
                key = k.strip().lower()
                if key == "name":
                    name = v
                    continue
                if key == "source" or key == "doi":
                    source = v
                    continue
                if key == "notes":
                    notes_parts.append(str(v))
                    continue
                # Try float coerce; fall back to string.
                try:
                    val: Any = float(v)
                except (ValueError, TypeError):
                    val = str(v)
                if key in property_keys:
                    properties[key] = val
                else:
                    conditions[key] = val
            rows.append({
                "formula":    formula,
                "name":       name,
                "conditions": conditions,
                "properties": properties,
                "notes":      "; ".join(notes_parts),
                "source":     source,
            })

        return self.add_rows(dataset_id, rows)

    def import_json(
        self,
        dataset_id: str,
        json_payload: list[dict[str, Any]] | dict[str, Any],
    ) -> int:
        """Import rows from a JSON array or {"rows": [...]} object."""
        if isinstance(json_payload, dict):
            json_payload = json_payload.get("rows") or []
        if not isinstance(json_payload, list):
            raise ImportError_(
                "JSON payload must be a list of rows or {'rows': [...]}"
            )
        return self.add_rows(dataset_id, json_payload)

    # ---- Lookup --------------------------------------------------

    def lookup(self, formula: str) -> list[dict[str, Any]]:
        """
        Return every row across all datasets whose normalised formula
        matches the query. Sorted newest-first. Includes the
        dataset_id and dataset_name so the caller can show provenance.
        """
        query = _normalise_formula(formula).lower()
        if not query:
            return []
        out: list[dict[str, Any]] = []
        for entry in self._read_index().values():
            try:
                ds = self.get_dataset(entry["id"])
            except (DatasetIntegrityError, DatasetNotFound):
                continue
            for row in ds.rows:
                if _normalise_formula(row.get("formula")).lower() == query:
                    out.append({
                        **row,
                        "dataset_id":   ds.id,
                        "dataset_name": ds.name,
                    })
        out.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        return out


# ---- Module-level singleton -----------------------------------------

_singleton: Optional[LabDatasetManager] = None


def get_lab_dataset_manager() -> LabDatasetManager:
    global _singleton
    if _singleton is None:
        _singleton = LabDatasetManager()
    return _singleton


def reset_lab_dataset_manager() -> None:
    """For tests."""
    global _singleton
    _singleton = None
