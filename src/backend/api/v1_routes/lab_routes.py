"""
/api/v2/lab/datasets/* — encrypted user-supplied lab data.

Every route is gated by ``Depends(verify_license())``. Datasets are
encrypted at rest using a key derived from the local hardware
fingerprint (see ``LabDatasetManager``).

Quickstart from the docs UI (``/docs``):

  1. POST  /api/v2/lab/datasets         {"name": "EIS Cu wires"}      → {id, ...}
  2. POST  /api/v2/lab/datasets/{id}/import/csv   (raw CSV body)
  3. GET   /api/v2/lab/datasets/{id}                                  → rows
  4. GET   /api/v2/lab/lookup?formula=MnO2
  5. POST  /api/v2/alchemi/properties   {"formula": "MnO2"}           → source=lab_dataset
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from src.backend.lab.dataset_manager import (
    DatasetIntegrityError,
    DatasetNotFound,
    ImportError_,
    LabError,
    get_lab_dataset_manager,
)
from src.backend.lab.xlsx_importer import (
    XlsxImportOptions,
    import_xlsx_bytes,
)
from src.backend.licensing.license_manager import verify_license


router = APIRouter(
    prefix="/api/v2/lab",
    tags=["lab_datasets"],
    dependencies=[Depends(verify_license())],
)


# ---- Schemas --------------------------------------------------------


class _CreateDatasetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=2000)


class _AddRowsRequest(BaseModel):
    rows: list[dict[str, Any]]


class _ImportJSONRequest(BaseModel):
    rows: list[dict[str, Any]]


# ---- Routes ---------------------------------------------------------


@router.get("/datasets")
async def list_datasets() -> list[dict[str, Any]]:
    """List dataset metadata. Rows are NOT included."""
    return get_lab_dataset_manager().list_datasets()


@router.post("/datasets")
async def create_dataset(req: _CreateDatasetRequest) -> dict[str, Any]:
    ds = get_lab_dataset_manager().create_dataset(
        name=req.name, description=req.description
    )
    return {
        "id": ds.id,
        "name": ds.name,
        "description": ds.description,
        "row_count": 0,
        "created_at": ds.created_at,
        "modified_at": ds.modified_at,
    }


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str) -> dict[str, Any]:
    """Returns the FULL dataset including rows."""
    try:
        return get_lab_dataset_manager().get_dataset(dataset_id).to_dict()
    except DatasetNotFound:
        raise HTTPException(404, "Dataset not found")
    except DatasetIntegrityError as e:
        raise HTTPException(409, f"Dataset integrity check failed: {e}")
    except LabError as e:
        raise HTTPException(400, str(e))


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str) -> dict[str, Any]:
    try:
        get_lab_dataset_manager().delete_dataset(dataset_id)
        return {"status": "deleted", "id": dataset_id}
    except LabError as e:
        raise HTTPException(400, str(e))


@router.post("/datasets/{dataset_id}/rows")
async def add_rows(dataset_id: str, req: _AddRowsRequest) -> dict[str, Any]:
    try:
        n = get_lab_dataset_manager().add_rows(dataset_id, req.rows)
        return {"added": n}
    except DatasetNotFound:
        raise HTTPException(404, "Dataset not found")
    except LabError as e:
        raise HTTPException(400, str(e))


@router.post("/datasets/{dataset_id}/import/csv")
async def import_csv(
    dataset_id: str,
    csv_body: str = Body(..., media_type="text/csv"),
    formula_col: str = Query(
        "formula",
        description="Name of the column that contains the chemical formula.",
    ),
) -> dict[str, Any]:
    """
    Send the CSV as the raw request body with ``Content-Type: text/csv``.
    Required column: ``formula`` (case-sensitive by default; override with
    ``?formula_col=Formula``).
    Recognised property columns (case-insensitive):
    band_gap_ev, conductivity_s_m, density_g_cm3, formation_energy_ev_per_atom,
    specific_capacitance_f_g, rs_ohm, rct_ohm, cdl_f, cdl_f_cm2,
    ionic_conductivity_s_cm. Anything else goes into ``conditions``.
    """
    try:
        n = get_lab_dataset_manager().import_csv(
            dataset_id, csv_body, formula_col=formula_col
        )
        return {"added": n}
    except DatasetNotFound:
        raise HTTPException(404, "Dataset not found")
    except ImportError_ as e:
        raise HTTPException(400, f"CSV import failed: {e}")
    except LabError as e:
        raise HTTPException(400, str(e))


@router.post("/datasets/{dataset_id}/import/json")
async def import_json(
    dataset_id: str,
    req: _ImportJSONRequest,
) -> dict[str, Any]:
    try:
        n = get_lab_dataset_manager().import_json(dataset_id, req.rows)
        return {"added": n}
    except DatasetNotFound:
        raise HTTPException(404, "Dataset not found")
    except ImportError_ as e:
        raise HTTPException(400, f"JSON import failed: {e}")
    except LabError as e:
        raise HTTPException(400, str(e))


@router.post("/datasets/{dataset_id}/import/xlsx")
async def import_xlsx(
    dataset_id: str,
    file: UploadFile = File(..., description="AnalyteX-style xlsx with CV / GCD / EIS sheets."),
    material: str = Form("AGV"),
    electrolyte: str = Form("unknown"),
    gcd_current_mA: float = Form(1.0),
    eis_fmax_Hz: float = Form(1.0e5),
    eis_fmin_Hz: float = Form(1.0e-2),
    electrode_area_cm2: Optional[float] = Form(None),
) -> dict[str, Any]:
    """
    Upload a multi-sheet AnalyteX xlsx (CV, GCD, EIS) directly. The
    server runs the importer and stores derived rows + the raw arrays
    into the encrypted dataset.

    All extras are form fields so the Swagger UI exposes them as a
    plain HTML form — no JSON wrapping needed.
    """
    try:
        data = await file.read()
        if not data:
            raise HTTPException(400, "uploaded file is empty")
        if len(data) > 50 * 1024 * 1024:
            raise HTTPException(413, "file > 50 MB; split or compress first")

        opts = XlsxImportOptions(
            material=material,
            electrolyte=electrolyte,
            gcd_current_mA=gcd_current_mA,
            eis_fmax_Hz=eis_fmax_Hz,
            eis_fmin_Hz=eis_fmin_Hz,
            electrode_area_cm2=electrode_area_cm2,
            source_filename=file.filename or "upload.xlsx",
        )
        result = import_xlsx_bytes(data, opts)
    except ValueError as e:
        raise HTTPException(400, f"xlsx import failed: {e}")
    except Exception as e:  # noqa: BLE001 — surface unexpected errors at the boundary
        raise HTTPException(400, f"xlsx import error: {type(e).__name__}: {e}")

    try:
        added = get_lab_dataset_manager().add_rows(dataset_id, result.rows)
    except DatasetNotFound:
        raise HTTPException(404, "Dataset not found")
    except LabError as e:
        raise HTTPException(400, str(e))

    return {
        "added": added,
        "n_cv": result.n_cv,
        "n_gcd": result.n_gcd,
        "has_eis": result.has_eis,
        "rs_fit": result.rs_fit,
    }


@router.get("/lookup")
async def lookup_formula(
    formula: str = Query(..., min_length=1, max_length=80),
) -> dict[str, Any]:
    """
    Look ``formula`` up across every dataset; return all matches with
    their dataset_id + dataset_name for provenance. Same lookup
    AlchemiBridge.estimate_properties uses internally.
    """
    matches = get_lab_dataset_manager().lookup(formula)
    return {
        "formula": formula,
        "match_count": len(matches),
        "matches": matches,
    }
