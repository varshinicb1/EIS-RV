"""
Autonomous experiment recommendation system.
Combines knowledge graph, vector store, and SQLite data to recommend experiments.
"""

import logging
from typing import List, Dict, Any, Optional
import sqlite3

logger = logging.getLogger(__name__)

class AutonomousExperimenter:
    def __init__(self, db_path: str, kg_client=None, vector_store=None):
        self.db_path = db_path
        self.kg_client = kg_client
        self.vector_store = vector_store
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def recommend_materials_for_analyte(self, analyte: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recommend materials to detect a specific analyte."""
        recommendations = []
        
        # Query knowledge graph for unexplored combinations
        if self.kg_client:
            try:
                unexplored = self.kg_client.find_unexplored_combinations(analyte)
                for item in unexplored[:limit]:
                    recommendations.append({
                        "material": item.get("material"),
                        "formula": item.get("formula"),
                        "rationale": f"Material has detected {len(item.get('detected_analytes', []))} other analytes",
                        "confidence": 0.7
                    })
            except Exception as e:
                logger.error(f"KG query failed: {e}")
        
        # Fallback: query SQLite for materials with similar analytes
        if not recommendations:
            query = """
            SELECT DISTINCT m.component, m.confidence
            FROM materials m
            JOIN papers p ON m.paper_id = p.id
            WHERE p.application LIKE ?
            ORDER BY m.confidence DESC
            LIMIT ?
            """
            rows = self.conn.execute(query, (f"%{analyte}%", limit)).fetchall()
            for row in rows:
                recommendations.append({
                    "material": row["component"],
                    "confidence": row["confidence"],
                    "rationale": "Found in similar application papers"
                })
        
        return recommendations
    
    def optimize_synthesis(self, material: str) -> Dict[str, Any]:
        """Suggest optimal synthesis parameters for a material."""
        optimization = {}
        
        # Query knowledge graph for synthesis trends
        if self.kg_client:
            try:
                trends = self.kg_client.get_synthesis_trends(material)
                if trends:
                    best_method = trends[0]
                    optimization = {
                        "recommended_method": best_method.get("method"),
                        "avg_temperature": best_method.get("avg_temp"),
                        "avg_ph": best_method.get("avg_ph"),
                        "frequency": best_method.get("frequency"),
                        "confidence": 0.8
                    }
            except Exception as e:
                logger.error(f"Synthesis trend query failed: {e}")
        
        # Fallback: query SQLite
        if not optimization:
            query = """
            SELECT method, AVG(temperature_C) as avg_temp, AVG(pH) as avg_ph, COUNT(*) as freq
            FROM synthesis
            JOIN materials m ON synthesis.paper_id = m.paper_id
            WHERE m.component = ?
            GROUP BY method
            ORDER BY freq DESC
            LIMIT 1
            """
            row = self.conn.execute(query, (material,)).fetchone()
            if row:
                optimization = {
                    "recommended_method": row["method"],
                    "avg_temperature": row["avg_temp"],
                    "avg_ph": row["avg_ph"],
                    "frequency": row["freq"],
                    "confidence": 0.6
                }
        
        return optimization
    
    def generate_recipe(self, materials: List[str], target_analyte: str) -> Dict[str, Any]:
        """Generate experimental recipe for material combination."""
        recipe = {
            "materials": materials,
            "target_analyte": target_analyte,
            "synthesis": {},
            "characterization": ["EIS", "CV"],
            "expected_performance": {}
        }
        
        # Get synthesis optimization for each material
        for material in materials:
            synthesis = self.optimize_synthesis(material)
            if synthesis:
                recipe["synthesis"][material] = synthesis
        
        # Estimate performance based on similar materials
        query = """
        SELECT AVG(eis_data.capacitance_F_g) as avg_cap, 
               AVG(eis_data.Rct_ohm) as avg_rct
        FROM eis_data
        JOIN materials m ON eis_data.paper_id = m.paper_id
        WHERE m.component IN ({})
        """.format(",".join(["?"] * len(materials)))
        
        row = self.conn.execute(query, materials).fetchone()
        if row:
            recipe["expected_performance"] = {
                "capacitance_F_g": row["avg_cap"],
                "Rct_ohm": row["avg_rct"]
            }
        
        return recipe
    
    def suggest_experiments(self, research_goal: str) -> List[Dict[str, Any]]:
        """Suggest experiments based on research goal using semantic search."""
        suggestions = []
        
        if self.vector_store:
            try:
                # Semantic search for similar experiments
                results = self.vector_store.semantic_search(research_goal, limit=5)
                
                for result in results:
                    paper_id = result.get("paper_id")
                    if paper_id:
                        # Get paper details
                        paper = self.conn.execute(
                            "SELECT title, abstract FROM papers WHERE id=?",
                            (paper_id,)
                        ).fetchone()
                        
                        if paper:
                            suggestions.append({
                                "title": paper["title"],
                                "abstract": paper["abstract"],
                                "relevance_score": result.get("score"),
                                "rationale": "Similar experiment found in literature"
                            })
            except Exception as e:
                logger.error(f"Semantic search failed: {e}")
        
        return suggestions
