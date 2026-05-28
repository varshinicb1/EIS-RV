"""
Knowledge Graph using Neo4j for material relationships.
Builds and queries material-analyte-performance relationships.
"""

import logging
from typing import List, Dict, Optional, Any
from neo4j import GraphDatabase
import os

logger = logging.getLogger(__name__)

class KnowledgeGraph:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = None
    ):
        if password is None:
            password = os.environ.get("NEO4J_PASSWORD", "changeme123")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._ensure_constraints()
    
    def close(self):
        self.driver.close()
    
    def _ensure_constraints(self):
        """Create uniqueness constraints."""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Material) REQUIRE m.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Analyte) REQUIRE a.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE")
    
    def add_material(self, name: str, formula: Optional[str] = None, paper_id: Optional[int] = None):
        """Add material node."""
        with self.driver.session() as session:
            query = """
            MERGE (m:Material {name: $name})
            SET m.formula = $formula
            """
            session.run(query, name=name, formula=formula)
            
            if paper_id:
                session.run("""
                MATCH (m:Material {name: $name})
                MERGE (p:Paper {id: $paper_id})
                MERGE (m)-[:MENTIONED_IN]->(p)
                """, name=name, paper_id=paper_id)
    
    def add_analyte(self, name: str, paper_id: Optional[int] = None):
        """Add analyte node."""
        with self.driver.session() as session:
            session.run("MERGE (a:Analyte {name: $name})", name=name)
            
            if paper_id:
                session.run("""
                MATCH (a:Analyte {name: $name})
                MERGE (p:Paper {id: $paper_id})
                MERGE (a)-[:DETECTED_IN]->(p)
                """, name=name, paper_id=paper_id)
    
    def add_detects_relationship(
        self,
        material: str,
        analyte: str,
        lod: Optional[str] = None,
        sensitivity: Optional[str] = None,
        paper_id: Optional[int] = None,
        confidence: float = 0.5
    ):
        """Add 'detects' relationship between material and analyte."""
        with self.driver.session() as session:
            query = """
            MATCH (m:Material {name: $material})
            MATCH (a:Analyte {name: $analyte})
            MERGE (m)-[r:DETECTS]->(a)
            SET r.lod = $lod, r.sensitivity = $sensitivity, r.confidence = $confidence
            """
            session.run(query, material=material, analyte=analyte, lod=lod, sensitivity=sensitivity, confidence=confidence)
            
            if paper_id:
                session.run("""
                MATCH (m:Material {name: $material})-[r:DETECTS]->(a:Analyte {name: $analyte})
                MERGE (p:Paper {id: $paper_id})
                MERGE (r)-[:REPORTED_IN]->(p)
                """, material=material, analyte=analyte, paper_id=paper_id)
    
    def add_synthesis_relationship(
        self,
        material: str,
        method: str,
        temperature: Optional[float] = None,
        ph: Optional[float] = None,
        paper_id: Optional[int] = None
    ):
        """Add 'synthesized_by' relationship."""
        with self.driver.session() as session:
            query = """
            MATCH (m:Material {name: $material})
            MERGE (s:SynthesisMethod {name: $method})
            MERGE (m)-[r:SYNTHESIZED_BY]->(s)
            SET r.temperature_C = $temperature, r.pH = $ph
            """
            session.run(query, material=material, method=method, temperature=temperature, ph=ph)
    
    def add_composite_relationship(
        self,
        material1: str,
        material2: str,
        relationship_type: str = "COMBINED_WITH",
        paper_id: Optional[int] = None
    ):
        """Add composite material relationship."""
        with self.driver.session() as session:
            query = f"""
            MATCH (m1:Material {{name: $material1}})
            MATCH (m2:Material {{name: $material2}})
            MERGE (m1)-[r:{relationship_type}]->(m2)
            """
            session.run(query, material1=material1, material2=material2)
    
    def find_related_materials(self, material: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Find materials related through composites or similar detection."""
        with self.driver.session() as session:
            query = """
            MATCH (m:Material {name: $material})-[*1..2]-(related:Material)
            RETURN DISTINCT related.name as name, related.formula as formula
            LIMIT 20
            """
            result = session.run(query, material=material)
            return [record.data() for record in result]
    
    def find_unexplored_combinations(self, analyte: str) -> List[Dict[str, Any]]:
        """Find materials that could detect the analyte but haven't been tested."""
        with self.driver.session() as session:
            query = """
            MATCH (m:Material)
            WHERE NOT (m)-[:DETECTS]->(:Analyte {name: $analyte})
            MATCH (m)-[:DETECTS]->(a:Analyte)
            WITH m, collect(DISTINCT a.name) as detected_analytes
            RETURN m.name as material, m.formula as formula, detected_analytes
            ORDER BY size(detected_analytes) DESC
            LIMIT 10
            """
            result = session.run(query, analyte=analyte)
            return [record.data() for record in result]
    
    def get_synthesis_trends(self, material: str) -> List[Dict[str, Any]]:
        """Get synthesis method trends for a material."""
        with self.driver.session() as session:
            query = """
            MATCH (m:Material {name: $material})-[r:SYNTHESIZED_BY]->(s:SynthesisMethod)
            RETURN s.name as method, avg(r.temperature_C) as avg_temp, 
                   avg(r.pH) as avg_ph, count(*) as frequency
            ORDER BY frequency DESC
            """
            result = session.run(query, material=material)
            return [record.data() for record in result]
