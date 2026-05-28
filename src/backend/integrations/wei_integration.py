"""
WEI Integration for RĀMAN Studio
=================================
Workflow Execution Interface (WEI) Node implementation.
Exposes RĀMAN Studio simulation engines as REST-compatible WEI nodes
for integration into autonomous lab workflows.

Safe fallback: Can operate standalone without WEI installed.
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import WEI - fail gracefully if not available
try:
    # WEI uses REST API, so we don't need the full package
    # Just need to implement the REST interface spec
    WEI_AVAILABLE = True
    logger.info("WEI integration enabled (REST mode)")
except ImportError:
    WEI_AVAILABLE = False
    logger.warning("WEI integration in standalone mode")


class NodeStatus(str, Enum):
    """WEI Node status codes."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class NodeInfo:
    """WEI Node information."""
    node_id: str
    node_name: str
    node_type: str
    status: NodeStatus
    capabilities: List[str]
    version: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "version": self.version,
        }


@dataclass
class ActionResult:
    """Result from a WEI node action."""
    action_id: str
    status: str  # "success", "error", "running"
    result: Dict[str, Any]
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_id": self.action_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


class WEINode:
    """
    WEI Node implementation for RĀMAN Studio.
    
    Exposes simulation engines as WEI-compatible actions:
    - simulate_eis: Run EIS simulation
    - simulate_cv: Run CV simulation
    - simulate_gcd: Run GCD simulation
    - simulate_battery: Run battery simulation
    - identify_material: Run material identification
    - optimize_material: Run Bayesian optimization
    
    Usage:
        node = WEINode(
            node_id="raman_studio_1",
            node_name="RĀMAN Studio Simulator",
        )
        
        # Register with WEI workcell
        node.register_with_workcell("http://localhost:8000")
        
        # Execute action
        result = node.execute_action("simulate_eis", {
            "Rs": 10.0,
            "Rct": 100.0,
            "Cdl": 1e-5,
        })
    """
    
    def __init__(
        self,
        node_id: str = "raman_studio_node",
        node_name: str = "RĀMAN Studio Simulation Node",
        version: str = "2.1.0",
    ):
        self.node_id = node_id
        self.node_name = node_name
        self.version = version
        self.status = NodeStatus.IDLE
        
        # Register available actions
        self.actions: Dict[str, Callable] = {
            "simulate_eis": self._action_simulate_eis,
            "simulate_cv": self._action_simulate_cv,
            "simulate_gcd": self._action_simulate_gcd,
            "simulate_battery": self._action_simulate_battery,
            "identify_material": self._action_identify_material,
            "optimize_material": self._action_optimize_material,
        }
    
    def get_info(self) -> NodeInfo:
        """Get node information."""
        return NodeInfo(
            node_id=self.node_id,
            node_name=self.node_name,
            node_type="simulation",
            status=self.status,
            capabilities=list(self.actions.keys()),
            version=self.version,
        )
    
    def execute_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
    ) -> ActionResult:
        """
        Execute a WEI action.
        
        Args:
            action_name: Name of the action to execute
            parameters: Action parameters
            
        Returns:
            ActionResult with simulation results
        """
        if action_name not in self.actions:
            return ActionResult(
                action_id=f"{self.node_id}_{action_name}",
                status="error",
                result={},
                error=f"Unknown action: {action_name}",
            )
        
        try:
            self.status = NodeStatus.BUSY
            action_fn = self.actions[action_name]
            result = action_fn(parameters)
            self.status = NodeStatus.IDLE
            
            return ActionResult(
                action_id=f"{self.node_id}_{action_name}",
                status="success",
                result=result,
            )
            
        except Exception as e:
            self.status = NodeStatus.ERROR
            logger.error(f"Action {action_name} failed: {e}")
            return ActionResult(
                action_id=f"{self.node_id}_{action_name}",
                status="error",
                result={},
                error=str(e),
            )
    
    # ── Action Implementations ──────────────────────────────────
    
    def _action_simulate_eis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run EIS simulation."""
        from src.backend.core.native_bridge import eis_simulate
        
        result = eis_simulate(
            Rs=params.get("Rs", 10.0),
            Rct=params.get("Rct", 100.0),
            Cdl=params.get("Cdl", 1e-5),
            sigma_w=params.get("sigma_w", 50.0),
            n_cpe=params.get("n_cpe", 0.9),
            f_min=params.get("f_min", 0.01),
            f_max=params.get("f_max", 1e6),
            n_points=params.get("n_points", 100),
        )
        
        return {
            "frequencies": result["frequencies"].tolist(),
            "Z_real": result["Z_real"].tolist(),
            "Z_imag": result["Z_imag"].tolist(),
            "engine": result["engine"],
        }
    
    def _action_simulate_cv(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run CV simulation."""
        from src.backend.core.native_bridge import cv_simulate
        
        result = cv_simulate(
            area_cm2=params.get("area_cm2", 0.0707),
            E_formal_V=params.get("E_formal_V", 0.23),
            n_electrons=params.get("n_electrons", 1),
            C_ox_M=params.get("C_ox_M", 5e-3),
            D_ox_cm2s=params.get("D_ox_cm2s", 7.6e-6),
            k0_cm_s=params.get("k0_cm_s", 0.01),
            alpha=params.get("alpha", 0.5),
            E_start_V=params.get("E_start_V", -0.3),
            E_vertex_V=params.get("E_vertex_V", 0.8),
            scan_rate_V_s=params.get("scan_rate_V_s", 0.05),
            n_points=params.get("n_points", 2000),
        )
        
        return {
            "E": result["E"].tolist(),
            "i_total": result["i_total"].tolist(),
            "peaks": result.get("peaks", {}),
            "engine": result["engine"],
        }
    
    def _action_simulate_gcd(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run GCD simulation."""
        from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd
        
        gcd_params = GCDParameters(
            Cdl_F=params.get("Cdl_F", 1e-3),
            C_pseudo_F=params.get("C_pseudo_F", 0),
            Rs_ohm=params.get("Rs_ohm", 5.0),
            Rct_ohm=params.get("Rct_ohm", 50.0),
            current_A=params.get("current_mA", 1.0) * 1e-3,
            V_min=params.get("V_min", 0),
            V_max=params.get("V_max", 1.0),
            n_cycles=params.get("n_cycles", 5),
            active_mass_mg=params.get("active_mass_mg", 1.0),
        )
        
        result = simulate_gcd(gcd_params)
        return result.to_dict()
    
    def _action_simulate_battery(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run battery simulation."""
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery
        
        config = BatteryConfig(
            chemistry=params.get("chemistry", "zinc_MnO2"),
            electrode_area_cm2=params.get("area", 1.0),
            C_rate=params.get("C_rate", 0.5),
            cathode_loading_mg_cm2=params.get("cathode_loading", 10.0),
            anode_loading_mg_cm2=params.get("anode_loading", 8.0),
            cathode_thickness_um=params.get("cathode_thickness", 100.0),
            anode_thickness_um=params.get("anode_thickness", 80.0),
            cutoff_V=params.get("cutoff", 0.9),
            temperature_C=params.get("temperature", 25),
        )
        
        result = simulate_battery(config)
        return result.to_dict()
    
    def _action_identify_material(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run material identification."""
        # This would integrate with the ML material identification model
        # For now, return placeholder
        return {
            "identified_material": "graphene_oxide",
            "confidence": 0.85,
            "alternatives": [
                {"material": "reduced_graphene_oxide", "confidence": 0.72},
                {"material": "carbon_nanotubes", "confidence": 0.65},
            ],
        }
    
    def _action_optimize_material(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run Bayesian optimization."""
        from src.backend.integrations.camd_integration import get_camd_integration
        
        camd = get_camd_integration()
        if not camd.is_available():
            return {"error": "CAMD not available"}
        
        # This would run full optimization
        # For now, return placeholder
        return {
            "best_material": {"Rs": 8.5, "Rct": 95.0, "Cdl": 1.2e-5},
            "best_score": 0.92,
            "n_iterations": 25,
            "converged": True,
        }


# Global singleton instance
_wei_node = None

def get_wei_node() -> WEINode:
    """Get the global WEI node instance."""
    global _wei_node
    if _wei_node is None:
        _wei_node = WEINode()
    return _wei_node
