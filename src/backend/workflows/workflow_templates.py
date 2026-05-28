"""
Workflow Templates for RĀMAN Studio
===================================
Pre-built workflow templates for common autonomous experiment patterns.

Templates:
- Full Material Characterization (EIS + CV + Raman)
- Optimization Loop (CAMD + Simulation + Validation)
- Autonomous Discovery (Literature + Hypothesis + Optimization)
- Quality Control (Simulate + Validate + Report)
- Parallel Screening (Multiple materials in parallel)

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import uuid
from typing import Dict, Any, List
from src.backend.workflows.workflow_engine import (
    Workflow,
    WorkflowNode,
    NodeType,
)


class WorkflowTemplates:
    """Pre-built workflow templates."""
    
    @staticmethod
    def full_characterization(
        material_params: Dict[str, Any],
        workflow_name: str = "Full Material Characterization"
    ) -> Workflow:
        """
        Full material characterization workflow.
        
        Steps:
        1. Run EIS simulation
        2. Run CV simulation
        3. Run GCD simulation
        4. Identify material from combined data
        5. Generate report
        
        Args:
            material_params: Material parameters (Rs, Rct, Cdl, etc.)
            workflow_name: Custom workflow name
            
        Returns:
            Workflow ready for execution
        """
        workflow = Workflow(
            workflow_id=f"char_{uuid.uuid4().hex[:8]}",
            name=workflow_name,
            description="Complete electrochemical characterization with EIS, CV, and GCD",
            metadata={"template": "full_characterization", "material_params": material_params}
        )
        
        # Node 1: EIS Simulation
        eis_node = WorkflowNode(
            node_id="eis_sim",
            node_type=NodeType.SIMULATION,
            name="EIS Simulation",
            action="simulate_eis",
            parameters={
                "Rs": material_params.get("Rs", 10.0),
                "Rct": material_params.get("Rct", 100.0),
                "Cdl": material_params.get("Cdl", 1e-5),
                "sigma_w": material_params.get("sigma_w", 50.0),
                "n_cpe": material_params.get("n_cpe", 0.9),
                "f_min": 0.01,
                "f_max": 1e6,
                "n_points": 100,
            },
            dependencies=[],
        )
        workflow.add_node(eis_node)
        
        # Node 2: CV Simulation
        cv_node = WorkflowNode(
            node_id="cv_sim",
            node_type=NodeType.SIMULATION,
            name="CV Simulation",
            action="simulate_cv",
            parameters={
                "area_cm2": material_params.get("area_cm2", 0.0707),
                "E_formal_V": material_params.get("E_formal_V", 0.23),
                "n_electrons": material_params.get("n_electrons", 1),
                "C_ox_M": material_params.get("C_ox_M", 5e-3),
                "D_ox_cm2s": material_params.get("D_ox_cm2s", 7.6e-6),
                "k0_cm_s": material_params.get("k0_cm_s", 0.01),
                "alpha": 0.5,
                "E_start_V": -0.3,
                "E_vertex_V": 0.8,
                "scan_rate_V_s": 0.05,
                "n_points": 2000,
            },
            dependencies=[],
        )
        workflow.add_node(cv_node)
        
        # Node 3: GCD Simulation
        gcd_node = WorkflowNode(
            node_id="gcd_sim",
            node_type=NodeType.SIMULATION,
            name="GCD Simulation",
            action="simulate_gcd",
            parameters={
                "Cdl_F": material_params.get("Cdl", 1e-5),
                "C_pseudo_F": material_params.get("C_pseudo_F", 0),
                "Rs_ohm": material_params.get("Rs", 10.0),
                "Rct_ohm": material_params.get("Rct", 100.0),
                "current_mA": 1.0,
                "V_min": 0,
                "V_max": 1.0,
                "n_cycles": 5,
                "active_mass_mg": 1.0,
            },
            dependencies=[],
        )
        workflow.add_node(gcd_node)
        
        # Node 4: Material Identification
        identify_node = WorkflowNode(
            node_id="identify",
            node_type=NodeType.ANALYSIS,
            name="Identify Material",
            action="identify_material_ml",
            parameters={
                "frequencies": "${eis_sim.result.frequencies}",
                "Z_real": "${eis_sim.result.Z_real}",
                "Z_imag": "${eis_sim.result.Z_imag}",
                "top_k": 3,
            },
            dependencies=["eis_sim", "cv_sim", "gcd_sim"],
        )
        workflow.add_node(identify_node)
        
        return workflow
    
    @staticmethod
    def optimization_loop(
        target_metric: str = "capacitance",
        max_iterations: int = 50,
        workflow_name: str = "Bayesian Optimization Loop"
    ) -> Workflow:
        """
        Bayesian optimization workflow.
        
        Steps:
        1. Initialize candidate space
        2. Run optimization loop:
           a. Suggest next candidate (CAMD)
           b. Simulate candidate (VANL)
           c. Evaluate performance
           d. Update model
        3. Return best candidate
        
        Args:
            target_metric: Metric to optimize (capacitance, conductivity, etc.)
            max_iterations: Maximum optimization iterations
            workflow_name: Custom workflow name
            
        Returns:
            Workflow ready for execution
        """
        workflow = Workflow(
            workflow_id=f"opt_{uuid.uuid4().hex[:8]}",
            name=workflow_name,
            description=f"Bayesian optimization to maximize {target_metric}",
            metadata={
                "template": "optimization_loop",
                "target_metric": target_metric,
                "max_iterations": max_iterations
            }
        )
        
        # Node 1: Start Optimization Campaign
        opt_node = WorkflowNode(
            node_id="optimize",
            node_type=NodeType.ANALYSIS,
            name="Bayesian Optimization",
            action="optimize_bayesian",
            parameters={
                "target_metric": target_metric,
                "objective": "maximize",
                "max_iterations": max_iterations,
                "candidate_space": [],  # Will be populated from materials database
                "objective_fn": "eis_capacitance",  # Predefined objective function
            },
            dependencies=[],
            timeout_seconds=600,  # 10 minutes
        )
        workflow.add_node(opt_node)
        
        return workflow
    
    @staticmethod
    def autonomous_discovery(
        application: str = "supercapacitor electrode",
        workflow_name: str = "Autonomous Materials Discovery"
    ) -> Workflow:
        """
        Full autonomous discovery workflow.
        
        Steps:
        1. Discover candidate materials (NVIDIA NIM)
        2. Generate synthesis routes
        3. Simulate top candidates
        4. Optimize best candidate
        5. Validate results
        6. Generate report
        
        Args:
            application: Target application
            workflow_name: Custom workflow name
            
        Returns:
            Workflow ready for execution
        """
        workflow = Workflow(
            workflow_id=f"disc_{uuid.uuid4().hex[:8]}",
            name=workflow_name,
            description=f"Autonomous discovery for {application}",
            metadata={
                "template": "autonomous_discovery",
                "application": application
            }
        )
        
        # Node 1: Discover Materials
        discover_node = WorkflowNode(
            node_id="discover",
            node_type=NodeType.EXTERNAL_API,
            name="Discover Materials",
            action="discover_materials",
            parameters={
                "application": application,
                "max_candidates": 5,
            },
            dependencies=[],
        )
        workflow.add_node(discover_node)
        
        # Node 2: Simulate Top Candidate
        simulate_node = WorkflowNode(
            node_id="simulate_top",
            node_type=NodeType.SIMULATION,
            name="Simulate Top Candidate",
            action="simulate_eis",
            parameters={
                "Rs": "${discover.result.candidates[0].predicted_Rs}",
                "Rct": "${discover.result.candidates[0].predicted_Rct}",
                "Cdl": "${discover.result.candidates[0].predicted_Cdl}",
                "f_min": 0.01,
                "f_max": 1e6,
                "n_points": 100,
            },
            dependencies=["discover"],
        )
        workflow.add_node(simulate_node)
        
        # Node 3: Validate Performance
        validate_node = WorkflowNode(
            node_id="validate",
            node_type=NodeType.DECISION,
            name="Validate Performance",
            action="decision_gate",
            parameters={
                "condition": "greater_than",
                "value": "${simulate_top.result.capacitance}",
                "threshold": 100.0,  # Minimum capacitance threshold
            },
            dependencies=["simulate_top"],
        )
        workflow.add_node(validate_node)
        
        return workflow
    
    @staticmethod
    def quality_control(
        reference_data: Dict[str, Any],
        tolerance: float = 0.1,
        workflow_name: str = "Quality Control Check"
    ) -> Workflow:
        """
        Quality control workflow.
        
        Steps:
        1. Run simulation with test parameters
        2. Compare against reference data
        3. Calculate deviation
        4. Pass/fail decision
        5. Generate QC report
        
        Args:
            reference_data: Reference data for comparison
            tolerance: Acceptable deviation (0.1 = 10%)
            workflow_name: Custom workflow name
            
        Returns:
            Workflow ready for execution
        """
        workflow = Workflow(
            workflow_id=f"qc_{uuid.uuid4().hex[:8]}",
            name=workflow_name,
            description="Quality control validation against reference data",
            metadata={
                "template": "quality_control",
                "reference_data": reference_data,
                "tolerance": tolerance
            }
        )
        
        # Node 1: Run Test Simulation
        test_node = WorkflowNode(
            node_id="test_sim",
            node_type=NodeType.SIMULATION,
            name="Test Simulation",
            action="simulate_eis",
            parameters=reference_data.get("parameters", {}),
            dependencies=[],
        )
        workflow.add_node(test_node)
        
        # Node 2: Compare Results
        compare_node = WorkflowNode(
            node_id="compare",
            node_type=NodeType.ANALYSIS,
            name="Compare Results",
            action="data_transform",
            parameters={
                "operation": "compare",
                "test_data": "${test_sim.result}",
                "reference_data": reference_data.get("expected_results", {}),
                "tolerance": tolerance,
            },
            dependencies=["test_sim"],
        )
        workflow.add_node(compare_node)
        
        # Node 3: Pass/Fail Decision
        decision_node = WorkflowNode(
            node_id="decision",
            node_type=NodeType.DECISION,
            name="QC Decision",
            action="decision_gate",
            parameters={
                "condition": "less_than",
                "value": "${compare.result.deviation}",
                "threshold": tolerance,
            },
            dependencies=["compare"],
        )
        workflow.add_node(decision_node)
        
        return workflow
    
    @staticmethod
    def parallel_screening(
        materials: List[Dict[str, Any]],
        workflow_name: str = "Parallel Material Screening"
    ) -> Workflow:
        """
        Parallel screening workflow.
        
        Simulates multiple materials in parallel and ranks them.
        
        Steps:
        1. Simulate all materials in parallel
        2. Extract key metrics
        3. Rank by performance
        4. Generate comparison report
        
        Args:
            materials: List of material parameters to screen
            workflow_name: Custom workflow name
            
        Returns:
            Workflow ready for execution
        """
        workflow = Workflow(
            workflow_id=f"screen_{uuid.uuid4().hex[:8]}",
            name=workflow_name,
            description=f"Parallel screening of {len(materials)} materials",
            metadata={
                "template": "parallel_screening",
                "n_materials": len(materials)
            }
        )
        
        # Create simulation node for each material
        sim_node_ids = []
        for i, material in enumerate(materials):
            node_id = f"sim_{i}"
            sim_node = WorkflowNode(
                node_id=node_id,
                node_type=NodeType.SIMULATION,
                name=f"Simulate Material {i+1}",
                action="simulate_eis",
                parameters=material,
                dependencies=[],
            )
            workflow.add_node(sim_node)
            sim_node_ids.append(node_id)
        
        # Node: Rank Results
        rank_node = WorkflowNode(
            node_id="rank",
            node_type=NodeType.ANALYSIS,
            name="Rank Materials",
            action="data_transform",
            parameters={
                "operation": "rank",
                "results": [f"${{{node_id}.result}}" for node_id in sim_node_ids],
                "metric": "capacitance",
            },
            dependencies=sim_node_ids,
        )
        workflow.add_node(rank_node)
        
        return workflow
    
    @staticmethod
    def list_templates() -> List[Dict[str, Any]]:
        """List all available workflow templates."""
        return [
            {
                "id": "full_characterization",
                "name": "Full Material Characterization",
                "description": "Complete electrochemical characterization with EIS, CV, and GCD",
                "parameters": ["material_params"],
                "estimated_duration": "5-10 minutes",
            },
            {
                "id": "optimization_loop",
                "name": "Bayesian Optimization Loop",
                "description": "Autonomous optimization using CAMD and VANL",
                "parameters": ["target_metric", "max_iterations"],
                "estimated_duration": "10-30 minutes",
            },
            {
                "id": "autonomous_discovery",
                "name": "Autonomous Materials Discovery",
                "description": "Full discovery pipeline from hypothesis to validation",
                "parameters": ["application"],
                "estimated_duration": "15-45 minutes",
            },
            {
                "id": "quality_control",
                "name": "Quality Control Check",
                "description": "Validate simulation against reference data",
                "parameters": ["reference_data", "tolerance"],
                "estimated_duration": "2-5 minutes",
            },
            {
                "id": "parallel_screening",
                "name": "Parallel Material Screening",
                "description": "Screen multiple materials in parallel",
                "parameters": ["materials"],
                "estimated_duration": "5-15 minutes",
            },
        ]


def get_template(template_id: str, **kwargs) -> Workflow:
    """
    Get a workflow template by ID.
    
    Args:
        template_id: Template identifier
        **kwargs: Template-specific parameters
        
    Returns:
        Workflow instance ready for execution
    """
    templates = {
        "full_characterization": WorkflowTemplates.full_characterization,
        "optimization_loop": WorkflowTemplates.optimization_loop,
        "autonomous_discovery": WorkflowTemplates.autonomous_discovery,
        "quality_control": WorkflowTemplates.quality_control,
        "parallel_screening": WorkflowTemplates.parallel_screening,
    }
    
    template_fn = templates.get(template_id)
    if not template_fn:
        raise ValueError(f"Unknown template: {template_id}")
    
    return template_fn(**kwargs)
