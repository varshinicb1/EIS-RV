"""
NVIDIA Alchemi bridge — honest replacement.

This module exists for backward compatibility with the older
``AlchemiBridge`` API surface. The original implementation called
fabricated NVIDIA endpoints (``/optimize``, ``/predict``, ``/properties``,
``/md``) that do not exist on ``integrate.api.nvidia.com``; every call
silently fell through to a hand-typed 13-row dictionary with a buggy
formula key. That has been removed.

What you get now
----------------
- ``ask`` — materials-Q&A against a real chat model. Uses
  ``src.ai_engine.nim_client`` against the OpenAI-compatible endpoint.
- ``estimate_properties`` — looks up the material in the curated 48-entry
  ``materials_db`` first, and only if it is unknown asks the chat model
  for a JSON-formatted estimate. LLM-estimated values are clearly
  flagged with ``"source": "llm_estimate"`` and never claimed to be
  computational chemistry.
- ``optimize_geometry``, ``run_molecular_dynamics``: kept as no-op stubs
  that raise ``NotImplementedError`` with a clear message. NVIDIA does
  host MLIP-based microservices (MACE-MP, ORB, SevenNet, MatterSim) but
  they are NOT served by the OpenAI-compatible chat endpoint, and we
  haven't wired up their separate request shapes yet. Until we do, we
  refuse rather than fabricate.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from src.ai_engine.nim_client import NIMClient, NIMError, get_default_client

logger = logging.getLogger(__name__)


# Materials we know about with curated data — derived from the 48-entry
# materials_db.py. Imported lazily to avoid a hard dependency at import time.
def _load_curated_db() -> dict[str, dict[str, Any]]:
    try:
        from src.backend.core.engines.materials_db import MATERIALS_DB
        return MATERIALS_DB
    except Exception:  # pragma: no cover — DB is bundled with the app
        logger.warning("materials_db not importable; alchemi will rely on NIM only")
        return {}


_MATERIALS_QA_SYSTEM = (
    "You are an expert in electrochemical materials science. You answer "
    "concisely (under 250 words), cite mechanism when relevant, and refuse "
    "to fabricate numerical values. When asked for a specific quantitative "
    "property you do not know precisely, say so and suggest a reasonable "
    "range, marking it as an estimate."
)


_PROPERTY_SCHEMA_HINT = (
    '{"formula": str, "band_gap_eV": float|null, '
    '"formation_energy_eV_per_atom": float|null, '
    '"density_g_cm3": float|null, '
    '"crystal_system": str|null, '
    '"notes": str}'
)


class AlchemiBridge:
    """Backward-compatible facade over the honest NIM client + materials DB."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        # If a key was passed explicitly, build a dedicated client; otherwise
        # share the process-wide singleton.
        if api_key is not None:
            self.client = NIMClient(api_key=api_key, default_model=model)
        else:
            self.client = get_default_client()
            if model:
                # User specified a model but reused the singleton — respect it
                # for this instance only.
                self.client.default_model = self.client._resolve_model(model)  # type: ignore[attr-defined]

        self._db: Optional[dict[str, dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # Methods expected by older callers
    # ------------------------------------------------------------------

    def ask(self, prompt: str, *, system: Optional[str] = None,
            temperature: float = 0.4) -> dict[str, Any]:
        """Free-form materials-science question. Returns dict with answer + usage."""
        try:
            sys_prompt = system or _MATERIALS_QA_SYSTEM
            completion = self.client.chat(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user",   "content": prompt},
                ],
                temperature=temperature,
                max_tokens=1024,
            )
            return {
                "ok": True,
                "answer": completion.text,
                "model": completion.model,
                "tokens": completion.total_tokens,
            }
        except NIMError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": e.status,
                "retryable": e.retryable,
            }

    def estimate_properties(self, formula: str) -> dict[str, Any]:
        """
        Return material properties, with provenance.

        Resolution order — highest-trust first:

        1. **User lab data** (``LabDatasetManager``). Returned as
           ``"source": "lab_dataset"`` with the originating dataset id
           and name. Multiple matches → all returned in ``matches``.
        2. **Curated 48-entry reference DB**. ``"source": "curated_db"``.
           Trustworthy reference values.
        3. **LLM JSON estimate** via NIM chat. ``"source": "llm_estimate"``.
           Plausible but not computational chemistry; flagged.
        4. **Unavailable** — no source had data; returned with the error.
           We never fabricate.
        """
        formula = (formula or "").strip()
        if not formula:
            return {"source": "error", "error": "empty formula"}

        # 1. User lab data takes priority — these are the user's own
        # measurements and are the most relevant data point.
        try:
            from src.backend.lab.dataset_manager import get_lab_dataset_manager
            lab = get_lab_dataset_manager().lookup(formula)
        except Exception as e:  # noqa: BLE001 — lab store is best-effort
            logger.debug("lab dataset lookup failed: %s", e)
            lab = []
        if lab:
            # Merge properties across matches (latest non-null wins).
            merged: dict[str, Any] = {}
            for row in lab:
                for k, v in (row.get("properties") or {}).items():
                    if v is not None:
                        merged[k] = v
            return {
                "source": "lab_dataset",
                "formula": formula,
                "properties": merged,
                "matches": lab,
                "match_count": len(lab),
            }

        # 2. Curated DB lookup.
        if self._db is None:
            self._db = _load_curated_db()
        for key in (formula, formula.lower(), formula.replace(" ", "")):
            if key in self._db:
                entry = self._db[key]
                if is_dataclass(entry):
                    props = asdict(entry)
                elif isinstance(entry, dict):
                    props = dict(entry)
                else:
                    props = {k: v for k, v in vars(entry).items()
                             if not k.startswith("_")}
                return {
                    "source": "curated_db",
                    "formula": formula,
                    "properties": props,
                }

        # 3. LLM estimate.
        try:
            data = self.client.chat_json(
                f"Give your best estimate of the bulk material properties of "
                f"`{formula}`. Use null for any value you do not know to "
                f"within an order of magnitude.",
                schema_hint=_PROPERTY_SCHEMA_HINT,
                system=_MATERIALS_QA_SYSTEM,
                temperature=0.2,
                max_tokens=512,
            )
            return {
                "source": "llm_estimate",
                "formula": formula,
                "properties": data if isinstance(data, dict) else {},
                "warning": (
                    "These values are LLM-generated estimates, not "
                    "computational-chemistry results. Use only as a first-"
                    "pass guess."
                ),
            }
        except NIMError as e:
            return {
                "source": "unavailable",
                "formula": formula,
                "error": str(e),
                "status": e.status,
            }

    # ------------------------------------------------------------------
    # Stubs we used to fake — now refuse honestly
    # ------------------------------------------------------------------

    @staticmethod
    def _refuse_unimplemented(method: str) -> dict[str, Any]:
        return {
            "ok": False,
            "error": (
                f"{method} is not implemented. The OpenAI-compatible NIM "
                f"endpoint does not provide this; NVIDIA does host MLIP "
                f"microservices (e.g. MACE-MP, ORB) under separate request "
                f"shapes that we have not wired up yet. Either run a local "
                f"MLIP via ASE+pyace, or wait for the dedicated NIM client."
            ),
        }

    def optimize_geometry(self, _params: dict[str, Any]) -> dict[str, Any]:
        return self._refuse_unimplemented("optimize_geometry")

    def calculate_band_gap(self, params: dict[str, Any]) -> dict[str, Any]:
        # Route through estimate_properties — the band gap is one of the
        # fields we ask for and it's the only thing the old API returned.
        species = params.get("species") or params.get("formula") or []
        formula = species if isinstance(species, str) else "".join(species)
        result = self.estimate_properties(formula)
        if result.get("source") in ("curated_db", "llm_estimate"):
            props = result.get("properties") or {}
            return {
                **result,
                "band_gap_eV": props.get("band_gap_eV"),
            }
        return result

    def calculate_properties(self, params: dict[str, Any]) -> dict[str, Any]:
        species = params.get("species") or params.get("formula") or []
        formula = species if isinstance(species, str) else "".join(species)
        return self.estimate_properties(formula)

    def run_molecular_dynamics(self, _params: dict[str, Any]) -> dict[str, Any]:
        return self._refuse_unimplemented("run_molecular_dynamics")

    def get_status(self) -> dict[str, Any]:
        if self._db is None:
            self._db = _load_curated_db()
        return {
            "configured": self.client.configured,
            "model": self.client.default_model,
            "base_url": self.client.base_url,
            "curated_materials": len(self._db),
            "mode": "online" if self.client.configured else "offline",
        }
