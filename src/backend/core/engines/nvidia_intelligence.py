"""
NVIDIA Intelligence — honest replacement.

This used to be a 308-line module that called fabricated endpoints
(``/materials/predict``, ``/materials/crystal``, ``/literature/search``,
``/synthesis/optimize``, ``/chat/materials``) at
``integrate.api.nvidia.com``. None of those endpoints exist; every call
404'd and silently returned hand-typed fallback data.

This rewrite delegates to the honest ``src.ai_engine.nim_client`` /
``AlchemiBridge`` and refuses calls we cannot back up.

Surface preserved
-----------------
The methods invoked by ``src.backend.api.v1_routes.nvidia_routes`` —
``predict_material_properties``, ``generate_crystal_structure``,
``query_literature``, ``optimize_synthesis``, ``chat_materials_expert``,
plus the ``.enabled`` and ``.api_key`` attributes — keep their
signatures so the routes don't break.

Feature status
--------------
- predict_material_properties: REAL (curated DB + LLM estimate, clearly flagged).
- chat_materials_expert:       REAL (chat-completions to a real NIM).
- query_literature:            REDIRECTS to ``src.backend.research`` pipeline.
- generate_crystal_structure:  REFUSES (was a stub returning simple cubic).
- optimize_synthesis:          REFUSES (was a stub).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from src.ai_engine.alchemi_bridge import AlchemiBridge
from src.ai_engine.nim_client import NIMError, get_default_client  # noqa: F401

logger = logging.getLogger(__name__)


_REFUSAL_CRYSTAL = (
    "Crystal structure generation requires a dedicated NIM (e.g. DiffCSP) "
    "served by NVIDIA under a separate request shape, or a local model. "
    "It is not provided by integrate.api.nvidia.com/v1/chat/completions. "
    "Until we wire one up, this endpoint refuses rather than returns a "
    "fabricated cubic lattice."
)

_REFUSAL_OPTIMIZE = (
    "Synthesis-parameter optimisation as previously implemented was a "
    "stub. To do this honestly we would either (a) wrap a Bayesian "
    "optimiser locally over a small forward model or (b) call a "
    "domain-specific NIM. Neither is wired up yet."
)


class NVIDIAIntelligence:
    """Backward-compatible facade over the honest AlchemiBridge + NIM client."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        # Build a bridge; it picks up NVIDIA_API_KEY from env if api_key is None.
        self._bridge = AlchemiBridge(api_key=api_key)
        self._client = self._bridge.client

    # ---- Attributes some callers read directly ---------------------------

    @property
    def api_key(self) -> str:
        return self._client.api_key

    @property
    def enabled(self) -> bool:
        return self._client.configured

    @property
    def base_url(self) -> str:
        return self._client.base_url

    # ---- Surface (real) --------------------------------------------------

    def predict_material_properties(
        self,
        formula: str,
        properties: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Look up the formula in the curated 48-entry database; if missing,
        ask the chat model for a JSON-formatted estimate. Always indicates
        ``source`` so the caller can decide whether the values are
        trustworthy.
        """
        result = self._bridge.estimate_properties(formula)
        if properties and isinstance(result.get("properties"), dict):
            full = result["properties"]
            result["properties"] = {k: full.get(k) for k in properties}
        return result

    def chat_materials_expert(
        self,
        question: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Materials-science chat through a real NIM."""
        prompt = question
        if context:
            prompt = (
                f"Context (JSON):\n{context}\n\n"
                f"Question:\n{question}"
            )
        return self._bridge.ask(prompt)

    def query_literature(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Look papers up in the local research-pipeline cache (arXiv +
        Crossref + Semantic Scholar) instead of calling a NIM literature
        endpoint that doesn't exist. If the cache is empty we tell the
        caller — we do not fabricate results.
        """
        try:
            from src.backend.research.config import DB_PATH
            from src.backend.research.schema import get_connection
            from src.backend.research.search import DatasetSearch

            conn = get_connection(DB_PATH)
            try:
                search = DatasetSearch(conn)
                hits = search.search(text_query=query, limit=max_results) or []
                return [
                    {
                        "title":   h.get("title"),
                        "authors": h.get("authors"),
                        "doi":     h.get("doi"),
                        "url":     h.get("url"),
                        "year":    h.get("year"),
                        "source":  h.get("source"),
                        "abstract": (h.get("abstract") or "")[:500],
                    }
                    for h in hits
                ]
            finally:
                try:
                    conn.close()
                except Exception:
                    logger.warning("%s:%d swallowed exception", __name__, 146, exc_info=False)
        except Exception as e:
            logger.warning("Literature search failed: %s", e)
            return []

    # ---- Surface (honest refusals) --------------------------------------

    def generate_crystal_structure(
        self,
        formula: str,
        space_group: Optional[int] = None,  # noqa: ARG002 — kept for API
    ) -> dict[str, Any]:
        return {"ok": False, "error": _REFUSAL_CRYSTAL, "formula": formula}

    def optimize_synthesis(
        self,
        target_properties: dict[str, Any],
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "error": _REFUSAL_OPTIMIZE,
            "target_properties": target_properties,
            "constraints": constraints,
        }


# Process-wide singleton. ``nvidia_routes`` imports ``get_nvidia_intelligence``
# directly; preserve the name.
_singleton: Optional[NVIDIAIntelligence] = None


def get_nvidia_intelligence() -> NVIDIAIntelligence:
    global _singleton
    if _singleton is None:
        _singleton = NVIDIAIntelligence()
    return _singleton


def reset_nvidia_intelligence() -> None:
    """For tests."""
    global _singleton
    _singleton = None
