"""
Dataset Search & Filter Interface
=====================================
Query the research database by material, property, method, and application.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class DatasetSearch:
    """
    Search interface over the research paper dataset.

    Supports filtering by:
        - Material component
        - EIS property ranges
        - Synthesis method
        - Application domain
        - Year range
        - Free-text title/abstract search
    """

    def __init__(self, conn):
        self.conn = conn

    def search(
        self,
        material: Optional[str] = None,
        application: Optional[str] = None,
        method: Optional[str] = None,
        min_capacitance: Optional[float] = None,
        max_Rct: Optional[float] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        text_query: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search papers with filters.

        Args:
            material: Filter by material component (e.g. 'graphene', 'MnO2')
            application: Filter by application ('supercapacitor', 'biosensor', etc.)
            method: Filter by synthesis method ('hydrothermal', 'sol_gel', etc.)
            min_capacitance: Minimum specific capacitance (F/g)
            max_Rct: Maximum charge transfer resistance (ohm)
            year_from: Minimum publication year
            year_to: Maximum publication year
            text_query: Free-text search in title and abstract
            limit: Max results (default 50)

        Returns:
            List of paper dicts with associated extracted data
        """
        conditions = []
        params = []

        base_query = """
            SELECT DISTINCT p.id, p.title, p.authors, p.doi, p.year,
                   p.journal, p.application, p.source_api, p.url
            FROM papers p
        """
        joins = []

        # Material filter
        if material:
            joins.append("LEFT JOIN materials m ON m.paper_id = p.id")
            conditions.append("m.component LIKE ?")
            params.append(f"%{material}%")

        # Synthesis method filter
        if method:
            joins.append("LEFT JOIN synthesis s ON s.paper_id = p.id")
            conditions.append("s.method LIKE ?")
            params.append(f"%{method}%")

        # EIS property filters
        if min_capacitance is not None or max_Rct is not None:
            joins.append("LEFT JOIN eis_data e ON e.paper_id = p.id")
            if min_capacitance is not None:
                conditions.append("e.capacitance_F_g >= ?")
                params.append(min_capacitance)
            if max_Rct is not None:
                conditions.append("e.Rct_ohm <= ?")
                params.append(max_Rct)

        # Application filter
        if application:
            conditions.append("p.application = ?")
            params.append(application)

        # Year range
        if year_from:
            conditions.append("p.year >= ?")
            params.append(year_from)
        if year_to:
            conditions.append("p.year <= ?")
            params.append(year_to)

        # Text search
        if text_query:
            conditions.append("(p.title LIKE ? OR p.abstract LIKE ?)")
            params.extend([f"%{text_query}%", f"%{text_query}%"])

        # Build final query
        join_clause = " ".join(set(joins))
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"{base_query} {join_clause} WHERE {where_clause} ORDER BY p.year DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()

        # Enrich with extracted data
        results = []
        for row in rows:
            paper = dict(row)
            paper_id = row["id"]

            # Materials
            mat_rows = self.conn.execute(
                "SELECT component, ratio_value, ratio_unit, confidence "
                "FROM materials WHERE paper_id=?", (paper_id,)
            ).fetchall()
            paper["materials"] = [dict(r) for r in mat_rows]

            # Synthesis
            syn_rows = self.conn.execute(
                "SELECT method, temperature_C, duration_hours, confidence "
                "FROM synthesis WHERE paper_id=?", (paper_id,)
            ).fetchall()
            paper["synthesis"] = [dict(r) for r in syn_rows]

            # EIS
            eis_rows = self.conn.execute(
                "SELECT Rs_ohm, Rct_ohm, capacitance_F_g, electrolyte, confidence "
                "FROM eis_data WHERE paper_id=?", (paper_id,)
            ).fetchall()
            paper["eis_data"] = [dict(r) for r in eis_rows]

            results.append(paper)

        return results

    def list_materials(self) -> List[Dict[str, Any]]:
        """List all unique materials with paper counts."""
        rows = self.conn.execute("""
            SELECT component, COUNT(DISTINCT paper_id) as paper_count,
                   AVG(confidence) as avg_confidence
            FROM materials
            GROUP BY component
            ORDER BY paper_count DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def list_applications(self) -> List[Dict[str, Any]]:
        """List all applications with counts."""
        rows = self.conn.execute("""
            SELECT application, COUNT(*) as count
            FROM papers
            WHERE application IS NOT NULL
            GROUP BY application
            ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def list_methods(self) -> List[Dict[str, Any]]:
        """List all synthesis methods with counts."""
        rows = self.conn.execute("""
            SELECT method, COUNT(DISTINCT paper_id) as paper_count
            FROM synthesis
            WHERE method IS NOT NULL
            GROUP BY method
            ORDER BY paper_count DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_paper_detail(self, paper_id: int) -> Optional[Dict[str, Any]]:
        """Get full details for a single paper."""
        row = self.conn.execute(
            "SELECT * FROM papers WHERE id=?", (paper_id,)
        ).fetchone()

        if not row:
            return None

        paper = dict(row)

        # All materials
        paper["materials"] = [
            dict(r) for r in self.conn.execute(
                "SELECT * FROM materials WHERE paper_id=?", (paper_id,)
            ).fetchall()
        ]

        # All synthesis
        paper["synthesis"] = [
            dict(r) for r in self.conn.execute(
                "SELECT * FROM synthesis WHERE paper_id=?", (paper_id,)
            ).fetchall()
        ]

        # All EIS data
        paper["eis_data"] = [
            dict(r) for r in self.conn.execute(
                "SELECT * FROM eis_data WHERE paper_id=?", (paper_id,)
            ).fetchall()
        ]

        # Extraction provenance
        paper["extractions"] = [
            dict(r) for r in self.conn.execute(
                "SELECT * FROM extractions WHERE paper_id=?", (paper_id,)
            ).fetchall()
        ]

        return paper
