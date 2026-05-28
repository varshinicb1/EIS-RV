"""
ScienceClaw API Routes
======================
REST API endpoints for ScienceClaw integration.

Endpoints:
- Literature mining
- Gap detection
- Hypothesis generation
- Knowledge graph
- Autonomous research loop

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from src.backend.integrations.scienceclaw_integration import (
    get_scienceclaw_integration,
    LiteratureGap,
    ResearchHypothesis,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/scienceclaw", tags=["scienceclaw"])


# ── Request/Response Models ─────────────────────────────────────

class LiteratureMiningRequest(BaseModel):
    topic: str = Field(..., description="Research topic to mine")
    max_papers: int = Field(20, ge=1, le=100, description="Maximum papers to retrieve")
    focus_areas: Optional[List[str]] = Field(None, description="Specific focus areas")


class GapDetectionRequest(BaseModel):
    topic: str = Field(..., description="Research topic")
    papers: Optional[List[Dict[str, Any]]] = Field(None, description="Papers to analyze")


class HypothesisGenerationRequest(BaseModel):
    gap: Dict[str, Any] = Field(..., description="Literature gap to address")
    n_hypotheses: int = Field(3, ge=1, le=10, description="Number of hypotheses")


class KnowledgeGraphRequest(BaseModel):
    topic: str = Field(..., description="Research topic")
    papers: Optional[List[Dict[str, Any]]] = Field(None, description="Papers to analyze")


class AutonomousLoopRequest(BaseModel):
    topic: str = Field(..., description="Research topic")
    max_iterations: int = Field(5, ge=1, le=20, description="Maximum iterations")


# ── Status Endpoint ─────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """
    Get ScienceClaw integration status.
    
    Returns:
        Status information including availability and capabilities
    """
    integration = get_scienceclaw_integration()
    
    return {
        "scienceclaw_available": integration.scienceclaw_available,
        "knowledge_graph_nodes": len(integration.knowledge_graph.get("nodes", [])),
        "knowledge_graph_edges": len(integration.knowledge_graph.get("edges", [])),
        "capabilities": {
            "literature_mining": True,
            "gap_detection": True,
            "hypothesis_generation": True,
            "knowledge_graph": True,
            "autonomous_loop": True,
        },
        "mode": "full" if integration.scienceclaw_available else "simulated",
    }


# ── Literature Mining ───────────────────────────────────────────

@router.post("/literature/mine")
async def mine_literature(req: LiteratureMiningRequest):
    """
    Mine literature for a research topic.
    
    Searches arXiv, PubMed, and other sources for relevant papers.
    Extracts key findings and identifies research gaps.
    
    Returns:
        Papers, key findings, and identified gaps
    """
    integration = get_scienceclaw_integration()
    
    try:
        results = integration.mine_literature(
            topic=req.topic,
            max_papers=req.max_papers,
            focus_areas=req.focus_areas
        )
        
        return {
            "status": "success",
            "results": results,
        }
        
    except Exception as e:
        logger.error(f"Literature mining failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Gap Detection ───────────────────────────────────────────────

@router.post("/gaps/detect")
async def detect_gaps(req: GapDetectionRequest):
    """
    Detect gaps in the literature.
    
    Analyzes papers to identify under-explored areas,
    contradictions, and opportunities for new research.
    
    Returns:
        List of identified gaps with confidence scores
    """
    integration = get_scienceclaw_integration()
    
    try:
        gaps = integration.detect_literature_gaps(
            topic=req.topic,
            papers=req.papers
        )
        
        return {
            "status": "success",
            "n_gaps": len(gaps),
            "gaps": [g.to_dict() for g in gaps],
        }
        
    except Exception as e:
        logger.error(f"Gap detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Hypothesis Generation ───────────────────────────────────────

@router.post("/hypotheses/generate")
async def generate_hypotheses(req: HypothesisGenerationRequest):
    """
    Generate testable hypotheses from a literature gap.
    
    Uses AI reasoning to propose hypotheses that address
    identified gaps, with suggested experiments and expected outcomes.
    
    Returns:
        List of research hypotheses with experiments
    """
    integration = get_scienceclaw_integration()
    
    try:
        # Convert dict to LiteratureGap
        gap = LiteratureGap(
            topic=req.gap.get("topic", ""),
            description=req.gap.get("description", ""),
            confidence=req.gap.get("confidence", 0.5),
            related_papers=req.gap.get("related_papers", []),
            suggested_experiments=req.gap.get("suggested_experiments", []),
        )
        
        hypotheses = integration.generate_hypotheses(
            gap=gap,
            n_hypotheses=req.n_hypotheses
        )
        
        return {
            "status": "success",
            "n_hypotheses": len(hypotheses),
            "hypotheses": [h.to_dict() for h in hypotheses],
        }
        
    except Exception as e:
        logger.error(f"Hypothesis generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Knowledge Graph ─────────────────────────────────────────────

@router.post("/knowledge-graph/build")
async def build_knowledge_graph(req: KnowledgeGraphRequest):
    """
    Build a knowledge graph from literature.
    
    Extracts entities (materials, properties, methods) and
    relationships from papers to construct a knowledge graph.
    
    Returns:
        Knowledge graph with nodes and edges
    """
    integration = get_scienceclaw_integration()
    
    try:
        graph = integration.build_knowledge_graph(
            topic=req.topic,
            papers=req.papers
        )
        
        return {
            "status": "success",
            "graph": graph,
        }
        
    except Exception as e:
        logger.error(f"Knowledge graph building failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-graph/current")
async def get_current_knowledge_graph():
    """
    Get the current knowledge graph.
    
    Returns:
        Current knowledge graph state
    """
    integration = get_scienceclaw_integration()
    
    return {
        "status": "success",
        "graph": integration.knowledge_graph,
    }


# ── Autonomous Research Loop ────────────────────────────────────

@router.post("/autonomous/start")
async def start_autonomous_loop(req: AutonomousLoopRequest):
    """
    Start autonomous research loop.
    
    Runs a complete autonomous discovery pipeline:
    1. Mine literature
    2. Detect gaps
    3. Generate hypotheses
    4. Design experiments
    5. Run simulations
    6. Validate results
    7. Update knowledge graph
    8. Repeat
    
    Returns:
        Research loop results with discoveries
    """
    integration = get_scienceclaw_integration()
    
    try:
        results = integration.run_autonomous_loop(
            topic=req.topic,
            max_iterations=req.max_iterations
        )
        
        return {
            "status": "success",
            "results": results,
        }
        
    except Exception as e:
        logger.error(f"Autonomous loop failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Quick Actions ───────────────────────────────────────────────

@router.post("/quick/literature-to-hypothesis")
async def literature_to_hypothesis(req: LiteratureMiningRequest):
    """
    Quick action: Mine literature and generate hypotheses.
    
    Combines literature mining, gap detection, and hypothesis
    generation into a single endpoint for convenience.
    
    Returns:
        Papers, gaps, and hypotheses
    """
    integration = get_scienceclaw_integration()
    
    try:
        # Mine literature
        lit_results = integration.mine_literature(
            topic=req.topic,
            max_papers=req.max_papers,
            focus_areas=req.focus_areas
        )
        
        # Detect gaps
        gaps = integration.detect_literature_gaps(
            topic=req.topic,
            papers=lit_results.get("papers", [])
        )
        
        # Generate hypotheses for top gap
        hypotheses = []
        if gaps:
            hypotheses = integration.generate_hypotheses(
                gap=gaps[0],
                n_hypotheses=3
            )
        
        return {
            "status": "success",
            "literature": {
                "n_papers": lit_results["n_papers"],
                "key_findings": lit_results["key_findings"],
            },
            "gaps": [g.to_dict() for g in gaps],
            "hypotheses": [h.to_dict() for h in hypotheses],
        }
        
    except Exception as e:
        logger.error(f"Literature to hypothesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick/hypothesis-to-workflow")
async def hypothesis_to_workflow(req: HypothesisGenerationRequest):
    """
    Quick action: Convert hypothesis to workflow.
    
    Takes a hypothesis and generates a RĀMAN Studio workflow
    to test it experimentally.
    
    Returns:
        Workflow definition ready for execution
    """
    try:
        # Extract experiments from hypothesis
        hypothesis = req.gap  # Reusing gap field for hypothesis
        experiments = hypothesis.get("experiments", [])
        
        if not experiments:
            raise HTTPException(
                status_code=400,
                detail="Hypothesis must include experiments"
            )
        
        # Convert to workflow nodes
        nodes = []
        for i, exp in enumerate(experiments):
            exp_type = exp.get("type", "simulation")
            
            if exp_type == "optimization":
                nodes.append({
                    "node_id": f"opt_{i}",
                    "node_type": "optimization",
                    "name": f"Optimization {i+1}",
                    "action": "optimize_bayesian",
                    "parameters": exp,
                    "dependencies": [],
                })
            elif exp_type == "characterization":
                for method in exp.get("methods", []):
                    nodes.append({
                        "node_id": f"char_{method.lower()}_{i}",
                        "node_type": "simulation",
                        "name": f"{method} Characterization",
                        "action": f"simulate_{method.lower()}",
                        "parameters": {},
                        "dependencies": [],
                    })
            elif exp_type == "workflow":
                nodes.append({
                    "node_id": f"workflow_{i}",
                    "node_type": "workflow",
                    "name": f"Workflow {i+1}",
                    "action": "execute_workflow",
                    "parameters": exp,
                    "dependencies": [],
                })
        
        # Create workflow definition
        workflow = {
            "name": hypothesis.get("hypothesis", "Generated Workflow"),
            "description": hypothesis.get("rationale", ""),
            "nodes": nodes,
        }
        
        return {
            "status": "success",
            "workflow": workflow,
            "note": "Use POST /api/v2/workflows/create-custom to create this workflow",
        }
        
    except Exception as e:
        logger.error(f"Hypothesis to workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
