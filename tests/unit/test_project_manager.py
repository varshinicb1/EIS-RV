"""
Tests for the encrypted project store.

These exercise the actual security guarantees, not just shape:

* Round-trip with the real Fernet/PBKDF2 path.
* Tampering rejected.
* A file written with a different key (== different machine) cannot be
  read.
* Path-traversal in project ids is rejected.
* Display-name sanitisation strips dangerous characters.
* Index rebuild from project files when the index is corrupted.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backend.projects.project_manager import (  # noqa: E402
    Project,
    ProjectError,
    ProjectIntegrityError,
    ProjectManager,
    ProjectNotFound,
    _is_safe_id,
    _sanitise_display_name,
)


@pytest.fixture()
def tmp_pm(tmp_path: Path) -> ProjectManager:
    return ProjectManager(projects_dir=tmp_path)


# ---- create / get round-trip -----------------------------------------------


def test_create_then_get_roundtrip(tmp_pm: ProjectManager) -> None:
    p = tmp_pm.create_project(
        name="EIS study", description="graphene", tags=["a", "b"]
    )
    assert len(p.id) == 32
    assert p.name == "EIS study"
    p2 = tmp_pm.get_project(p.id)
    assert p2.name == p.name
    assert p2.description == p.description
    assert p2.tags == p.tags


def test_list_projects_uses_encrypted_index(tmp_pm: ProjectManager) -> None:
    a = tmp_pm.create_project(name="A")
    b = tmp_pm.create_project(name="B")
    listed = tmp_pm.list_projects()
    ids = {entry["id"] for entry in listed}
    assert a.id in ids and b.id in ids


def test_update_and_delete(tmp_pm: ProjectManager) -> None:
    p = tmp_pm.create_project(name="orig")
    tmp_pm.update_project(p.id, {"name": "renamed", "tags": ["x"]})
    p2 = tmp_pm.get_project(p.id)
    assert p2.name == "renamed"
    assert p2.tags == ["x"]
    tmp_pm.delete_project(p.id)
    with pytest.raises(ProjectNotFound):
        tmp_pm.get_project(p.id)


def test_add_simulation(tmp_pm: ProjectManager) -> None:
    p = tmp_pm.create_project(name="sim test")
    sim = tmp_pm.add_simulation(
        p.id, {"type": "eis", "params": {"Rs": 10}, "result": {}}
    )
    assert sim["type"] == "eis"
    assert len(sim["id"]) == 12
    p2 = tmp_pm.get_project(p.id)
    assert len(p2.simulations) == 1


# ---- security: tamper detection --------------------------------------------


def test_tamper_detection(tmp_pm: ProjectManager, tmp_path: Path) -> None:
    p = tmp_pm.create_project(name="tamper test")
    proj_path = tmp_path / f"{p.id}.proj"
    raw = bytearray(proj_path.read_bytes())
    raw[20] ^= 0x55  # flip a bit somewhere in the middle
    proj_path.write_bytes(bytes(raw))

    fresh = ProjectManager(projects_dir=tmp_path)
    with pytest.raises(ProjectIntegrityError):
        fresh.get_project(p.id)


def test_wrong_machine_key_cannot_read(tmp_path: Path) -> None:
    """A blob written with key K1 cannot be read with key K2."""
    pm_alice = ProjectManager(projects_dir=tmp_path)
    pm_alice._key = base64.urlsafe_b64encode(b"A" * 32)
    p = pm_alice.create_project(name="alice's project")

    pm_bob = ProjectManager(projects_dir=tmp_path)
    pm_bob._key = base64.urlsafe_b64encode(b"B" * 32)
    with pytest.raises(ProjectIntegrityError):
        pm_bob.get_project(p.id)


# ---- security: id / name validation ----------------------------------------


def test_path_traversal_in_id_rejected(tmp_pm: ProjectManager) -> None:
    for bad in (
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "abc/def",
        "abc def",
        "",
        "x" * 100,
    ):
        with pytest.raises(ProjectError):
            tmp_pm.get_project(bad)


def test_is_safe_id_only_hex_uuid_chars() -> None:
    assert _is_safe_id("deadbeef" * 4)        # 32 chars
    assert _is_safe_id("DEAD-BEEF-1234-5678") # uuid-style
    assert not _is_safe_id("../etc")
    assert not _is_safe_id("hello world")
    assert not _is_safe_id("")
    assert not _is_safe_id("g" * 32)          # non-hex letter


def test_display_name_sanitiser_strips_html_and_paths() -> None:
    out = _sanitise_display_name("../../<script>alert(1)</script>")
    # No path components, no angle brackets, no parens, no semicolons.
    for ch in ("/", "<", ">", "(", ")", ";"):
        assert ch not in out


def test_display_name_empty_falls_back() -> None:
    assert _sanitise_display_name("") == "Untitled Project"
    assert _sanitise_display_name("   ") == "Untitled Project"
    # Pure-strip-result also falls back.
    assert _sanitise_display_name("<<<>>>") == "Untitled Project"


# ---- index rebuild ---------------------------------------------------------


def test_index_rebuild_when_index_corrupted(
    tmp_pm: ProjectManager, tmp_path: Path
) -> None:
    p = tmp_pm.create_project(name="indexed")
    index_path = tmp_path / ProjectManager.INDEX_FILENAME
    index_path.write_bytes(b"not a valid fernet token")  # corrupt the index

    fresh = ProjectManager(projects_dir=tmp_path)
    listed = fresh.list_projects()
    assert any(entry["id"] == p.id for entry in listed), \
        "rebuild should recover the project from its individual file"


# ---- import / export -------------------------------------------------------


def test_import_reissues_id(tmp_pm: ProjectManager) -> None:
    """Imported projects must NEVER keep the source id (collision risk + traversal)."""
    payload = {
        "id": "../../etc/passwd",  # malicious id in the import payload
        "name": "imported",
        "description": "from elsewhere",
        "tags": [],
    }
    p = tmp_pm.import_project(payload)
    assert p.id != "../../etc/passwd"
    assert _is_safe_id(p.id)
