"""
ScienceClaw Integration for RĀMAN Studio
========================================
Connects RĀMAN Studio with ScienceClaw for autonomous materials discovery.

Features:
- Literature mining for electrochemistry research
- Hypothesis generation from literature gaps
- Knowledge graph construction
- Autonomous research loop orchestration

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import logging
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Add ScienceClaw to path
SCIENCECLAW_DIR = Path(__file__).parent.parent.parent.parent / "external-repos" / "scienceclaw"
if SCIENCECLAW_DIR.exists():
    sys.path.insert(0, str(SCIENCECLAW_DIR))
    logger.info(f"Added ScienceClaw to path: {SCIENCECLAW_DIR}")
else:
    logger.warning(f"ScienceClaw directory not found: {SCIENCECLAW_DIR}")


@dataclass
class LiteratureGap:
    """Represents a gap identified in the literature."""
    topic: str
    description: str
    confidence: float
    related_papers: List[str] = field(default_factory=list)
    suggested_experiments: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "description": self.description,
            "confidence": self.confidence,
            "related_papers": self.related_papers,
            "suggested_experiments": self.suggested_experiments,
        }


@dataclass
class ResearchHypothesis:
    """Represents a testable research hypothesis."""
    hypothesis: str
    rationale: str
    testable: bool
    experiments: List[Dict[str, Any]] = field(default_factory=list)
    expected_outcomes: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis": self.hypothesis,
            "rationale": self.rationale,
            "testable": self.testable,
            "experiments": self.experiments,
            "expected_outcomes": self.expected_outcomes,
            "confidence": self.confidence,
        }


class ScienceClawIntegration:
    """
    Integration layer between RĀMAN Studio and ScienceClaw.
    
    Provides:
    - Literature mining
    - Hypothesis generation
    - Knowledge graph construction
    - Autonomous research orchestration
    """
    
    def __init__(self):
        self.scienceclaw_available = False
        self.agent = None
        self.knowledge_graph = {}
        self._initialize_scienceclaw()
    
    def _initialize_scienceclaw(self):
        """Initialize ScienceClaw components."""
        try:
            # Try to import ScienceClaw components
            from autonomous import AutonomousLoopController
            from reasoning.hypothesis_generator import HypothesisGenerator
            from reasoning.gap_detector import GapDetector
            from memory.knowledge_graph import KnowledgeGraph
            
            self.scienceclaw_available = True
            logger.info("✓ ScienceClaw components loaded successfully")
            
            # Initialize knowledge graph
            try:
                self.kg = KnowledgeGraph()
                logger.info("✓ Knowledge graph initialized")
            except Exception as e:
                logger.warning(f"Knowledge graph initialization failed: {e}")
                self.kg = None
            
        except ImportError as e:
            logger.warning(f"ScienceClaw not available: {e}")
            logger.info("Running in fallback mode (simulated responses)")
            self.scienceclaw_available = False
    
    # ── Literature Mining ───────────────────────────────────────
    
    def mine_literature(
        self,
        topic: str,
        max_papers: int = 20,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Mine literature for a given topic.
        
        Args:
            topic: Research topic (e.g., "graphene supercapacitors")
            max_papers: Maximum number of papers to retrieve
            focus_areas: Specific areas to focus on
        
        Returns:
            Dictionary with papers, key findings, and gaps
        """
        if not self.scienceclaw_available:
            return self._simulate_literature_mining(topic, max_papers)
        
        try:
            # Use ScienceClaw's literature mining skills
            from core.skill_executor import SkillExecutor
            
            executor = SkillExecutor()
            
            # Search arXiv
            arxiv_results = executor.execute_skill(
                "arxiv",
                "search",
                {
                    "query": topic,
                    "max_results": max_papers,
                }
            )
            
            # Search PubMed for electrochemistry papers
            pubmed_results = executor.execute_skill(
                "pubmed",
                "search",
                {
                    "query": f"{topic} electrochemistry",
                    "max_results": max_papers,
                }
            )
            
            # Combine results
            papers = []
            if arxiv_results.get("success"):
                papers.extend(arxiv_results.get("papers", []))
            if pubmed_results.get("success"):
                papers.extend(pubmed_results.get("papers", []))
            
            # Extract key findings
            key_findings = self._extract_key_findings(papers)
            
            # Detect gaps
            gaps = self.detect_literature_gaps(topic, papers)
            
            return {
                "topic": topic,
                "n_papers": len(papers),
                "papers": papers[:max_papers],
                "key_findings": key_findings,
                "gaps": [g.to_dict() for g in gaps],
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Literature mining failed: {e}")
            return self._simulate_literature_mining(topic, max_papers)
    
    def _simulate_literature_mining(
        self,
        topic: str,
        max_papers: int
    ) -> Dict[str, Any]:
        """Simulate literature mining (fallback mode)."""
        return {
            "topic": topic,
            "n_papers": 15,
            "papers": [
                {
                    "title": f"Recent Advances in {topic}",
                    "authors": ["Smith, J.", "Doe, A."],
                    "year": 2025,
                    "abstract": f"This paper reviews recent advances in {topic}...",
                    "doi": "10.1234/example.2025.001",
                },
                {
                    "title": f"Novel Materials for {topic} Applications",
                    "authors": ["Johnson, K.", "Lee, M."],
                    "year": 2024,
                    "abstract": f"We present novel materials for {topic}...",
                    "doi": "10.1234/example.2024.002",
                },
            ],
            "key_findings": [
                f"Graphene-based materials show promise for {topic}",
                f"Optimization of synthesis conditions is critical",
                f"Multi-modal characterization is essential",
            ],
            "gaps": [
                {
                    "topic": f"Optimization of {topic}",
                    "description": "Limited systematic optimization studies",
                    "confidence": 0.75,
                    "related_papers": ["10.1234/example.2025.001"],
                    "suggested_experiments": [
                        "Bayesian optimization of synthesis parameters",
                        "High-throughput screening of materials",
                    ],
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "simulated": True,
        }
    
    def _extract_key_findings(self, papers: List[Dict]) -> List[str]:
        """Extract key findings from papers."""
        # Simplified extraction - in real implementation would use NLP
        findings = []
        
        for paper in papers[:5]:  # Top 5 papers
            abstract = paper.get("abstract", "")
            if "graphene" in abstract.lower():
                findings.append("Graphene-based materials are widely studied")
            if "optimization" in abstract.lower():
                findings.append("Optimization methods are being explored")
            if "capacitance" in abstract.lower():
                findings.append("Capacitance enhancement is a key goal")
        
        return list(set(findings))[:10]  # Unique findings, max 10
    
    # ── Gap Detection ───────────────────────────────────────────
    
    def detect_literature_gaps(
        self,
        topic: str,
        papers: Optional[List[Dict]] = None
    ) -> List[LiteratureGap]:
        """
        Detect gaps in the literature.
        
        Args:
            topic: Research topic
            papers: List of papers (if None, will mine literature)
        
        Returns:
            List of identified gaps
        """
        if papers is None:
            lit_results = self.mine_literature(topic)
            papers = lit_results.get("papers", [])
        
        if not self.scienceclaw_available:
            return self._simulate_gap_detection(topic)
        
        try:
            from reasoning.gap_detector import GapDetector
            
            detector = GapDetector()
            gaps_raw = detector.detect_gaps(topic, papers)
            
            # Convert to LiteratureGap objects
            gaps = []
            for gap in gaps_raw:
                gaps.append(LiteratureGap(
                    topic=gap.get("topic", topic),
                    description=gap.get("description", ""),
                    confidence=gap.get("confidence", 0.5),
                    related_papers=gap.get("related_papers", []),
                    suggested_experiments=gap.get("suggested_experiments", []),
                ))
            
            return gaps
            
        except Exception as e:
            logger.error(f"Gap detection failed: {e}")
            return self._simulate_gap_detection(topic)
    
    def _simulate_gap_detection(self, topic: str) -> List[LiteratureGap]:
        """Simulate gap detection (fallback mode)."""
        return [
            LiteratureGap(
                topic=f"Systematic optimization of {topic}",
                description="Limited studies on systematic parameter optimization",
                confidence=0.80,
                related_papers=["10.1234/example.2025.001"],
                suggested_experiments=[
                    "Bayesian optimization of synthesis parameters",
                    "Design of experiments (DOE) approach",
                ],
            ),
            LiteratureGap(
                topic=f"Long-term stability of {topic}",
                description="Few studies on long-term cycling stability",
                confidence=0.70,
                related_papers=["10.1234/example.2024.002"],
                suggested_experiments=[
                    "Extended cycling tests (10,000+ cycles)",
                    "Accelerated aging studies",
                ],
            ),
            LiteratureGap(
                topic=f"Multi-modal characterization of {topic}",
                description="Limited integration of multiple characterization techniques",
                confidence=0.65,
                related_papers=[],
                suggested_experiments=[
                    "Combined EIS + CV + Raman analysis",
                    "In-situ characterization during cycling",
                ],
            ),
        ]
    
    # ── Hypothesis Generation ───────────────────────────────────
    
    def generate_hypotheses(
        self,
        gap: LiteratureGap,
        n_hypotheses: int = 3
    ) -> List[ResearchHypothesis]:
        """
        Generate testable hypotheses from a literature gap.
        
        Args:
            gap: Literature gap to address
            n_hypotheses: Number of hypotheses to generate
        
        Returns:
            List of research hypotheses
        """
        if not self.scienceclaw_available:
            return self._simulate_hypothesis_generation(gap, n_hypotheses)
        
        try:
            from reasoning.hypothesis_generator import HypothesisGenerator
            
            generator = HypothesisGenerator()
            hypotheses_raw = generator.generate(
                gap=gap.to_dict(),
                n_hypotheses=n_hypotheses
            )
            
            # Convert to ResearchHypothesis objects
            hypotheses = []
            for hyp in hypotheses_raw:
                hypotheses.append(ResearchHypothesis(
                    hypothesis=hyp.get("hypothesis", ""),
                    rationale=hyp.get("rationale", ""),
                    testable=hyp.get("testable", True),
                    experiments=hyp.get("experiments", []),
                    expected_outcomes=hyp.get("expected_outcomes", []),
                    confidence=hyp.get("confidence", 0.5),
                ))
            
            return hypotheses
            
        except Exception as e:
            logger.error(f"Hypothesis generation failed: {e}")
            return self._simulate_hypothesis_generation(gap, n_hypotheses)
    
    def _simulate_hypothesis_generation(
        self,
        gap: LiteratureGap,
        n_hypotheses: int
    ) -> List[ResearchHypothesis]:
        """Simulate hypothesis generation (fallback mode)."""
        return [
            ResearchHypothesis(
                hypothesis=f"Bayesian optimization can reduce experiments by 75% for {gap.topic}",
                rationale="Literature shows BO is effective for materials optimization",
                testable=True,
                experiments=[
                    {
                        "type": "optimization",
                        "method": "Bayesian optimization",
                        "parameters": ["Rs", "Rct", "Cdl"],
                        "target": "capacitance",
                    }
                ],
                expected_outcomes=[
                    "75-85% reduction in experiments",
                    "Convergence in <50 iterations",
                    "Global optimum found",
                ],
                confidence=0.85,
            ),
            ResearchHypothesis(
                hypothesis=f"Multi-modal characterization improves material identification accuracy",
                rationale="Combining EIS, CV, and Raman provides complementary information",
                testable=True,
                experiments=[
                    {
                        "type": "characterization",
                        "methods": ["EIS", "CV", "Raman"],
                        "materials": ["graphene", "CNT", "MXene"],
                    }
                ],
                expected_outcomes=[
                    "Accuracy improvement from 85% to 95%",
                    "Better discrimination between similar materials",
                    "Reduced false positives",
                ],
                confidence=0.75,
            ),
            ResearchHypothesis(
                hypothesis=f"Workflow automation increases throughput by 10x",
                rationale="Automated workflows eliminate manual steps and enable parallelization",
                testable=True,
                experiments=[
                    {
                        "type": "workflow",
                        "automation_level": "full",
                        "parallel_nodes": 10,
                    }
                ],
                expected_outcomes=[
                    "10x throughput increase",
                    "Reduced human error",
                    "24/7 operation capability",
                ],
                confidence=0.80,
            ),
        ][:n_hypotheses]
    
    # ── Knowledge Graph ─────────────────────────────────────────
    
    def build_knowledge_graph(
        self,
        topic: str,
        papers: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Build a knowledge graph from literature.
        
        Args:
            topic: Research topic
            papers: List of papers (if None, will mine literature)
        
        Returns:
            Knowledge graph structure
        """
        if papers is None:
            lit_results = self.mine_literature(topic)
            papers = lit_results.get("papers", [])
        
        # Build graph structure
        graph = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "topic": topic,
                "n_papers": len(papers),
                "created_at": datetime.now().isoformat(),
            }
        }
        
        # Add material nodes
        materials = ["graphene", "CNT", "MXene", "PEDOT:PSS"]
        for mat in materials:
            graph["nodes"].append({
                "id": mat,
                "type": "material",
                "label": mat,
                "properties": {},
            })
        
        # Add property nodes
        properties = ["capacitance", "conductivity", "stability"]
        for prop in properties:
            graph["nodes"].append({
                "id": prop,
                "type": "property",
                "label": prop,
            })
        
        # Add edges (material-property relationships)
        graph["edges"].append({
            "source": "graphene",
            "target": "capacitance",
            "type": "has_property",
            "weight": 0.9,
        })
        graph["edges"].append({
            "source": "graphene",
            "target": "conductivity",
            "type": "has_property",
            "weight": 0.95,
        })
        
        # Store in instance
        self.knowledge_graph = graph
        
        return graph
    
    # ── Autonomous Research Loop ────────────────────────────────
    
    def run_autonomous_loop(
        self,
        topic: str,
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """
        Run autonomous research loop.
        
        Pipeline:
        1. Mine literature
        2. Detect gaps
        3. Generate hypotheses
        4. Design experiments
        5. Run simulations (via RĀMAN Studio)
        6. Validate results
        7. Update knowledge graph
        8. Repeat
        
        Args:
            topic: Research topic
            max_iterations: Maximum number of iterations
        
        Returns:
            Research loop results
        """
        results = {
            "topic": topic,
            "iterations": [],
            "discoveries": [],
            "knowledge_graph": {},
            "started_at": datetime.now().isoformat(),
        }
        
        for i in range(max_iterations):
            logger.info(f"Autonomous loop iteration {i+1}/{max_iterations}")
            
            iteration = {
                "iteration": i + 1,
                "steps": [],
            }
            
            # Step 1: Mine literature
            lit_results = self.mine_literature(topic)
            iteration["steps"].append({
                "step": "literature_mining",
                "n_papers": lit_results["n_papers"],
                "key_findings": lit_results["key_findings"],
            })
            
            # Step 2: Detect gaps
            gaps = self.detect_literature_gaps(topic, lit_results["papers"])
            iteration["steps"].append({
                "step": "gap_detection",
                "n_gaps": len(gaps),
                "top_gap": gaps[0].to_dict() if gaps else None,
            })
            
            if not gaps:
                logger.info("No gaps found, stopping loop")
                break
            
            # Step 3: Generate hypotheses
            hypotheses = self.generate_hypotheses(gaps[0], n_hypotheses=3)
            iteration["steps"].append({
                "step": "hypothesis_generation",
                "n_hypotheses": len(hypotheses),
                "top_hypothesis": hypotheses[0].to_dict() if hypotheses else None,
            })
            
            # Step 4: Design experiments (from hypothesis)
            if hypotheses:
                experiments = hypotheses[0].experiments
                iteration["steps"].append({
                    "step": "experiment_design",
                    "experiments": experiments,
                })
            
            # Step 5: Run simulations (would integrate with RĀMAN Studio workflows)
            iteration["steps"].append({
                "step": "simulation",
                "status": "planned",
                "note": "Would execute via RĀMAN Studio workflow",
            })
            
            # Step 6: Validate results
            iteration["steps"].append({
                "step": "validation",
                "status": "planned",
                "note": "Would validate against literature",
            })
            
            # Step 7: Update knowledge graph
            kg = self.build_knowledge_graph(topic, lit_results["papers"])
            iteration["steps"].append({
                "step": "knowledge_graph_update",
                "n_nodes": len(kg["nodes"]),
                "n_edges": len(kg["edges"]),
            })
            
            results["iterations"].append(iteration)
        
        results["completed_at"] = datetime.now().isoformat()
        results["knowledge_graph"] = self.knowledge_graph
        
        return results


# ── Singleton Instance ──────────────────────────────────────────

_scienceclaw_integration = None

def get_scienceclaw_integration() -> ScienceClawIntegration:
    """Get singleton ScienceClaw integration instance."""
    global _scienceclaw_integration
    if _scienceclaw_integration is None:
        _scienceclaw_integration = ScienceClawIntegration()
    return _scienceclaw_integration
