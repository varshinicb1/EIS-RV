"""Tests for the encrypted lab dataset store."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backend.lab.dataset_manager import (  # noqa: E402
    DatasetIntegrityError,
    DatasetNotFound,
    ImportError_,
    LabDatasetManager,
    LabError,
    _is_safe_id,
    _normalise_formula,
    _sanitise_name,
)


@pytest.fixture()
def mgr(tmp_path: Path) -> LabDatasetManager:
    return LabDatasetManager(datasets_dir=tmp_path)


# ---- Round-trip ----------------------------------------------------------


def test_create_then_get(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="my EIS series", description="Cu wires, 25 C")
    assert len(ds.id) == 32
    assert ds.name == "my EIS series"

    ds2 = mgr.get_dataset(ds.id)
    assert ds2.name == ds.name
    assert ds2.description == ds.description
    assert ds2.rows == []


def test_list_datasets_excludes_rows(mgr: LabDatasetManager) -> None:
    a = mgr.create_dataset(name="a")
    mgr.add_rows(a.id, [{"formula": "Cu", "properties": {"density_g_cm3": 8.96}}])
    listed = mgr.list_datasets()
    assert len(listed) == 1
    entry = listed[0]
    assert entry["row_count"] == 1
    assert "rows" not in entry


def test_add_rows_and_lookup(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="test")
    mgr.add_rows(ds.id, [
        {"formula": "MnO2", "properties": {"specific_capacitance_f_g": 280}},
        {"formula": " mno2 ", "properties": {"specific_capacitance_f_g": 310},
         "conditions": {"electrolyte": "1 M Na2SO4"}},
        {"formula": "TiO2", "properties": {"band_gap_ev": 3.2}},
    ])

    hits = mgr.lookup("MnO2")
    assert len(hits) == 2
    for h in hits:
        assert h["dataset_id"] == ds.id
        assert h["dataset_name"] == "test"

    assert len(mgr.lookup("TiO2")) == 1
    assert len(mgr.lookup("graphene")) == 0


def test_delete_dataset(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="toremove")
    mgr.delete_dataset(ds.id)
    with pytest.raises(DatasetNotFound):
        mgr.get_dataset(ds.id)
    assert mgr.list_datasets() == []


# ---- CSV import ----------------------------------------------------------


def test_import_csv_partitions_columns(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="csv-test")
    csv_text = (
        "formula,band_gap_ev,density_g_cm3,electrolyte,temperature_K,source\n"
        "MnO2,1.3,5.03,1 M Na2SO4,298,my-lab\n"
        "TiO2,3.2,4.23,0.5 M H2SO4,298,doi:10.xxx\n"
    )
    n = mgr.import_csv(ds.id, csv_text)
    assert n == 2

    hits = mgr.lookup("MnO2")
    assert len(hits) == 1
    row = hits[0]
    assert row["properties"]["band_gap_ev"] == 1.3
    assert row["properties"]["density_g_cm3"] == 5.03
    assert row["conditions"]["electrolyte"] == "1 M Na2SO4"
    assert row["conditions"]["temperature_k"] == 298.0
    assert row["source"] == "my-lab"


def test_import_csv_rejects_missing_formula_column(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="bad-csv")
    with pytest.raises(ImportError_):
        mgr.import_csv(ds.id, "name,value\nfoo,1\n")


# ---- JSON import ----------------------------------------------------------


def test_import_json_array(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="json-test")
    rows = [
        {"formula": "graphene", "properties": {"conductivity_s_m": 1e8}},
        {"formula": "Au", "properties": {"density_g_cm3": 19.32}},
    ]
    n = mgr.import_json(ds.id, rows)
    assert n == 2
    assert len(mgr.lookup("Au")) == 1


def test_import_json_object_with_rows_key(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="json-obj")
    payload = {"rows": [{"formula": "Cu"}]}
    n = mgr.import_json(ds.id, payload)
    assert n == 1


def test_import_json_rejects_bad_payload(mgr: LabDatasetManager) -> None:
    ds = mgr.create_dataset(name="bad-json")
    with pytest.raises(ImportError_):
        mgr.import_json(ds.id, "not a list or dict")  # type: ignore[arg-type]


# ---- Security ------------------------------------------------------------


def test_id_safety_blocks_traversal(mgr: LabDatasetManager) -> None:
    for bad in ("../../etc/passwd", "abc/def", "abc def", ""):
        with pytest.raises(LabError):
            mgr.get_dataset(bad)


def test_is_safe_id_only_hex_uuid_chars() -> None:
    assert _is_safe_id("deadbeef" * 4)
    assert _is_safe_id("DEAD-BEEF-1234-5678")
    assert not _is_safe_id("../etc")
    assert not _is_safe_id("")
    assert not _is_safe_id("zzzz" * 8)


def test_normalise_formula_strips_whitespace() -> None:
    assert _normalise_formula("  MnO2  ") == "MnO2"
    assert _normalise_formula(" m n o 2 ") == "mno2"


def test_sanitise_name_strips_html() -> None:
    out = _sanitise_name("<script>alert(1)</script>my name")
    for ch in ("<", ">", ";", "(", ")"):
        assert ch not in out


def test_tamper_detection(mgr: LabDatasetManager, tmp_path: Path) -> None:
    ds = mgr.create_dataset(name="tamper")
    mgr.add_rows(ds.id, [{"formula": "Cu"}])
    path = tmp_path / f"{ds.id}.lds"
    raw = bytearray(path.read_bytes())
    raw[20] ^= 0x55
    path.write_bytes(bytes(raw))

    fresh = LabDatasetManager(datasets_dir=tmp_path)
    with pytest.raises(DatasetIntegrityError):
        fresh.get_dataset(ds.id)


def test_wrong_machine_key_cannot_read(tmp_path: Path) -> None:
    a = LabDatasetManager(datasets_dir=tmp_path)
    a._key = base64.urlsafe_b64encode(b"A" * 32)
    ds = a.create_dataset(name="alice")

    b = LabDatasetManager(datasets_dir=tmp_path)
    b._key = base64.urlsafe_b64encode(b"B" * 32)
    with pytest.raises(DatasetIntegrityError):
        b.get_dataset(ds.id)
