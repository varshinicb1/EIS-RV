"""
Material Representation Layer
===============================
Extensible schema for nanomaterial compositions, synthesis parameters,
and structural descriptors.

Scientific basis:
    - Composition vectors represent multi-material blends (mass fractions)
    - Synthesis parameters capture process conditions affecting nanostructure
    - Structural descriptors are the bridge between processing and properties

All units follow SI + electrochemistry conventions:
    - Length: nm, µm, mm
    - Temperature: °C (user-facing), K (internal calculations)
    - Conductivity: S/m
    - Surface area: m²/g (BET-equivalent)
    - Capacitance: F (Farads)
    - Resistance: Ω (Ohms)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import numpy as np
import uuid
from datetime import datetime


# ---------------------------------------------------------------------------
#   Enumerations
# ---------------------------------------------------------------------------

class SynthesisMethod(str, Enum):
    """
    Common nanomaterial synthesis methods, each producing distinct
    nanostructures due to different nucleation/growth kinetics.
    """
    HYDROTHERMAL = "hydrothermal"           # High crystallinity, controlled morphology
    ELECTRODEPOSITION = "electrodeposition" # Thin films, good substrate adhesion
    DROP_CASTING = "drop_casting"           # Simple, variable thickness
    SPIN_COATING = "spin_coating"           # Uniform thin films
    CVD = "cvd"                             # Chemical vapor deposition
    SOLVOTHERMAL = "solvothermal"           # Non-aqueous hydrothermal variant
    SOL_GEL = "sol_gel"                     # Metal oxide nanoparticles
    COPRECIPITATION = "coprecipitation"     # Mixed oxides


class Solvent(str, Enum):
    WATER = "water"
    DMF = "dimethylformamide"
    NMP = "n_methyl_pyrrolidone"
    ETHANOL = "ethanol"
    ISOPROPANOL = "isopropanol"
    DMSO = "dimethyl_sulfoxide"


class ElectrodeType(str, Enum):
    SUPERCAPACITOR = "supercapacitor"
    BIOSENSOR = "biosensor"
    BATTERY_ANODE = "battery_anode"
    BATTERY_CATHODE = "battery_cathode"
    FUEL_CELL = "fuel_cell"
    ELECTROCATALYST = "electrocatalyst"


# ---------------------------------------------------------------------------
#   Material Database — Intrinsic Properties
# ---------------------------------------------------------------------------

# Base material properties (bulk/theoretical values)
# These serve as anchors for the physics-informed surrogate model.
MATERIAL_DATABASE: Dict[str, dict] = {
    "graphene": {
        "formula": "C",
        "type": "2D_carbon",
        "bulk_conductivity": 1e6,       # S/m (in-plane)
        "theoretical_surface_area": 2630, # m²/g (single layer graphene)
        "density": 2.267,                # g/cm³
        "cost_factor": 0.8,              # relative cost
        "pseudocapacitive": False,
        "electrochemical_window": 1.2,   # V
        "typical_Cdl": 21e-6,            # F/cm² (EDLC)
    },
    "reduced_graphene_oxide": {
        "formula": "C (rGO)",
        "type": "2D_carbon",
        "bulk_conductivity": 1e4,
        "theoretical_surface_area": 1500,
        "density": 2.1,
        "cost_factor": 0.6,
        "pseudocapacitive": False,
        "electrochemical_window": 1.0,
        "typical_Cdl": 15e-6,
    },
    "MnO2": {
        "formula": "MnO₂",
        "type": "transition_metal_oxide",
        "bulk_conductivity": 1e-5,
        "theoretical_surface_area": 300,
        "density": 5.026,
        "cost_factor": 0.3,
        "pseudocapacitive": True,
        "electrochemical_window": 0.9,
        "typical_capacitance": 1370,     # F/g (theoretical)
    },
    "PEDOT_PSS": {
        "formula": "PEDOT:PSS",
        "type": "conducting_polymer",
        "bulk_conductivity": 1000,
        "theoretical_surface_area": 100,
        "density": 1.01,
        "cost_factor": 0.7,
        "pseudocapacitive": True,
        "electrochemical_window": 1.3,
        "typical_capacitance": 92,
    },
    "carbon_black": {
        "formula": "C (CB)",
        "type": "carbon",
        "bulk_conductivity": 5e4,
        "theoretical_surface_area": 1500,
        "density": 1.8,
        "cost_factor": 0.1,
        "pseudocapacitive": False,
        "electrochemical_window": 1.0,
        "typical_Cdl": 10e-6,
    },
    "CNT": {
        "formula": "C (MWCNT)",
        "type": "1D_carbon",
        "bulk_conductivity": 1e5,
        "theoretical_surface_area": 1315,
        "density": 1.3,
        "cost_factor": 0.9,
        "pseudocapacitive": False,
        "electrochemical_window": 1.1,
        "typical_Cdl": 18e-6,
    },
    "Fe2O3": {
        "formula": "Fe₂O₃",
        "type": "transition_metal_oxide",
        "bulk_conductivity": 1e-4,
        "theoretical_surface_area": 200,
        "density": 5.24,
        "cost_factor": 0.2,
        "pseudocapacitive": True,
        "electrochemical_window": 0.8,
        "typical_capacitance": 1007,
    },
    "NiO": {
        "formula": "NiO",
        "type": "transition_metal_oxide",
        "bulk_conductivity": 1e-2,
        "theoretical_surface_area": 250,
        "density": 6.67,
        "cost_factor": 0.4,
        "pseudocapacitive": True,
        "electrochemical_window": 0.5,
        "typical_capacitance": 2584,
    },
    "polyaniline": {
        "formula": "PANI",
        "type": "conducting_polymer",
        "bulk_conductivity": 10,
        "theoretical_surface_area": 50,
        "density": 1.36,
        "cost_factor": 0.3,
        "pseudocapacitive": True,
        "electrochemical_window": 0.7,
        "typical_capacitance": 750,
    },
    "gold_nanoparticles": {
        "formula": "Au NP",
        "type": "noble_metal",
        "bulk_conductivity": 4.1e7,
        "theoretical_surface_area": 50,
        "density": 19.3,
        "cost_factor": 5.0,
        "pseudocapacitive": False,
        "electrochemical_window": 1.5,
        "typical_Cdl": 30e-6,
    },
    "NiMoO4": {
        "formula": "α-NiMoO₄",
        "type": "transition_metal_oxide",
        "bulk_conductivity": 1e-4,
        "theoretical_surface_area": 82.0,  # BET surface area from paper
        "density": 1.23,                 # X-ray density
        "cost_factor": 0.4,
        "pseudocapacitive": True,
        "electrochemical_window": 0.65,  # 3-electrode window
        "typical_capacitance": 548,      # F/g from paper
    },
}


# ---------------------------------------------------------------------------
#   Data Classes
# ---------------------------------------------------------------------------

@dataclass
class MaterialComposition:
    """
    Multi-material composition vector.
    Components are mass fractions that sum to 1.0.

    Example:
        Graphene (60%) + MnO2 (30%) + Carbon Black (10%)
        components = {"graphene": 0.6, "MnO2": 0.3, "carbon_black": 0.1}
    """
    components: Dict[str, float] = field(default_factory=lambda: {"graphene": 1.0})

    def __post_init__(self):
        self._normalize()

    def _normalize(self):
        """Ensure mass fractions sum to 1.0."""
        total = sum(self.components.values())
        if total > 0:
            self.components = {k: v / total for k, v in self.components.items()}

    def to_vector(self, material_order: Optional[List[str]] = None) -> np.ndarray:
        """Convert to fixed-length feature vector."""
        if material_order is None:
            material_order = sorted(MATERIAL_DATABASE.keys())
        return np.array([
            self.components.get(m, 0.0) for m in material_order
        ], dtype=np.float64)

    @staticmethod
    def from_vector(vec: np.ndarray, material_order: Optional[List[str]] = None):
        """Reconstruct from feature vector."""
        if material_order is None:
            material_order = sorted(MATERIAL_DATABASE.keys())
        components = {m: float(v) for m, v in zip(material_order, vec) if v > 1e-6}
        return MaterialComposition(components=components)

    @property
    def effective_conductivity(self) -> float:
        """
        Estimate effective conductivity using logarithmic mixing rule.
        This is more physically realistic than linear mixing for
        percolation-dominated conduction in nanocomposites.

        log(σ_eff) = Σ φᵢ × log(σᵢ)
        """
        log_sigma = 0.0
        for mat, frac in self.components.items():
            if mat in MATERIAL_DATABASE:
                sigma = max(MATERIAL_DATABASE[mat]["bulk_conductivity"], 1e-10)
                log_sigma += frac * np.log10(sigma)
        return 10 ** log_sigma

    @property
    def weighted_surface_area(self) -> float:
        """
        Estimate accessible surface area.
        Real surface area depends on nanostructure — this gives
        a composition-weighted theoretical upper bound.
        """
        sa = 0.0
        for mat, frac in self.components.items():
            if mat in MATERIAL_DATABASE:
                sa += frac * MATERIAL_DATABASE[mat]["theoretical_surface_area"]
        return sa

    @property
    def cost_index(self) -> float:
        """Weighted cost factor for the composition."""
        cost = 0.0
        for mat, frac in self.components.items():
            if mat in MATERIAL_DATABASE:
                cost += frac * MATERIAL_DATABASE[mat]["cost_factor"]
        return cost

    @property
    def has_pseudocapacitive(self) -> bool:
        """Check if composition includes pseudocapacitive materials."""
        for mat, frac in self.components.items():
            if frac > 0.05 and mat in MATERIAL_DATABASE:
                if MATERIAL_DATABASE[mat].get("pseudocapacitive", False):
                    return True
        return False

    def to_dict(self) -> dict:
        return {"components": self.components}


@dataclass
class SynthesisParameters:
    """
    Process conditions for nanomaterial synthesis.

    Scientific rationale:
        - Temperature controls nucleation rate and crystallinity
        - Duration affects grain size (Ostwald ripening)
        - pH influences surface charge and morphology
        - Solvent affects precursor solubility and reaction kinetics
    """
    method: SynthesisMethod = SynthesisMethod.HYDROTHERMAL
    temperature_C: float = 120.0    # Celsius
    duration_hours: float = 6.0     # Hours
    pH: float = 7.0                 # Solution pH
    solvent: Solvent = Solvent.WATER
    pressure_atm: float = 1.0       # For hydrothermal reactions
    concentration_mM: float = 50.0  # Precursor concentration

    def to_vector(self) -> np.ndarray:
        """Convert to numerical feature vector for ML models."""
        method_onehot = [0.0] * len(SynthesisMethod)
        method_list = list(SynthesisMethod)
        method_onehot[method_list.index(self.method)] = 1.0

        return np.array([
            self.temperature_C / 200.0,     # Normalize to ~[0, 1]
            self.duration_hours / 24.0,
            self.pH / 14.0,
            self.pressure_atm / 10.0,
            self.concentration_mM / 100.0,
        ] + method_onehot, dtype=np.float64)

    def to_dict(self) -> dict:
        return {
            "method": self.method.value,
            "temperature_C": self.temperature_C,
            "duration_hours": self.duration_hours,
            "pH": self.pH,
            "solvent": self.solvent.value,
            "pressure_atm": self.pressure_atm,
            "concentration_mM": self.concentration_mM,
        }


@dataclass
class StructuralDescriptors:
    """
    Structural properties of the synthesized nanomaterial.
    These bridge the gap between processing and electrochemistry.

    Scientific meaning:
        - porosity: fraction of void space (0-1). Higher porosity = more
          electrolyte access but potentially lower electronic conductivity.
        - surface_area_m2_g: BET-equivalent specific surface area.
          Determines double-layer capacitance.
        - conductivity_S_m: Electronic conductivity of the electrode.
          Determines solution resistance contribution.
        - defect_density: Fraction of defective sites (0-1).
          Defects create active sites but also degradation pathways.
        - layer_thickness_nm: For thin film electrodes.
        - crystallinity: Degree of crystalline order (0-1).
          Higher crystallinity = better electron transport.
        - particle_size_nm: Average nanoparticle or grain size.
          Small particles = high surface area but potential agglomeration.
    """
    porosity: float = 0.4
    surface_area_m2_g: float = 500.0
    conductivity_S_m: float = 1000.0
    defect_density: float = 0.1
    layer_thickness_nm: float = 200.0
    crystallinity: float = 0.7
    particle_size_nm: float = 20.0

    def to_vector(self) -> np.ndarray:
        """Convert to feature vector for EIS prediction model."""
        return np.array([
            self.porosity,
            np.log10(self.surface_area_m2_g + 1) / 4.0,  # Log-scale normalization
            np.log10(self.conductivity_S_m + 1) / 7.0,
            self.defect_density,
            np.log10(self.layer_thickness_nm + 1) / 4.0,
            self.crystallinity,
            np.log10(self.particle_size_nm + 1) / 3.0,
        ], dtype=np.float64)

    def to_dict(self) -> dict:
        return {
            "porosity": round(self.porosity, 4),
            "surface_area_m2_g": round(self.surface_area_m2_g, 2),
            "conductivity_S_m": round(self.conductivity_S_m, 2),
            "defect_density": round(self.defect_density, 4),
            "layer_thickness_nm": round(self.layer_thickness_nm, 1),
            "crystallinity": round(self.crystallinity, 4),
            "particle_size_nm": round(self.particle_size_nm, 1),
        }


@dataclass
class EISParameters:
    """
    Electrochemical Impedance Spectroscopy output parameters.

    Scientific meaning (Randles circuit: Rs + (Cdl || (Rct + Zw))):
        - Rs: Solution/ohmic resistance (Ω).
              Depends on electrolyte conductivity + electrode resistance.
        - Rct: Charge transfer resistance (Ω).
              Inversely proportional to exchange current density.
              Lower Rct = faster electron transfer kinetics.
        - Cdl: Double-layer capacitance (F).
              Proportional to electrochemically active surface area.
        - sigma_warburg: Warburg coefficient (Ω·s^(-1/2)).
              Related to diffusion coefficient of redox species.
              Higher σ = more diffusion-limited behavior.
        - n_cpe: CPE exponent (0.5-1.0).
              1.0 = ideal capacitor. <1.0 = distributed time constants
              due to surface roughness/heterogeneity.
    """
    Rs: float = 10.0            # Ohms
    Rct: float = 100.0          # Ohms
    Cdl: float = 1e-5           # Farads
    sigma_warburg: float = 50.0 # Ω·s^(-1/2)
    n_cpe: float = 0.9          # CPE exponent

    def to_vector(self) -> np.ndarray:
        return np.array([
            np.log10(self.Rs + 0.1),
            np.log10(self.Rct + 0.1),
            np.log10(self.Cdl + 1e-10),
            np.log10(self.sigma_warburg + 0.1),
            self.n_cpe,
        ], dtype=np.float64)

    @staticmethod
    def from_vector(vec: np.ndarray) -> 'EISParameters':
        return EISParameters(
            Rs=10 ** vec[0],
            Rct=10 ** vec[1],
            Cdl=10 ** vec[2],
            sigma_warburg=10 ** vec[3],
            n_cpe=float(np.clip(vec[4], 0.5, 1.0)),
        )

    @property
    def specific_capacitance_F_g(self) -> float:
        """Estimate specific capacitance (rough approximation)."""
        return self.Cdl * 1000  # Very rough F/g estimate

    def to_dict(self) -> dict:
        return {
            "Rs_ohm": round(self.Rs, 4),
            "Rct_ohm": round(self.Rct, 4),
            "Cdl_F": float(f"{self.Cdl:.6e}"),
            "sigma_warburg": round(self.sigma_warburg, 4),
            "n_cpe": round(self.n_cpe, 4),
        }


@dataclass
class ExperimentRecord:
    """Complete record of a virtual experiment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    composition: MaterialComposition = field(default_factory=MaterialComposition)
    synthesis: SynthesisParameters = field(default_factory=SynthesisParameters)
    descriptors: Optional[StructuralDescriptors] = None
    eis_params: Optional[EISParameters] = None
    objective_value: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "composition": self.composition.to_dict(),
            "synthesis": self.synthesis.to_dict(),
            "notes": self.notes,
        }
        if self.descriptors:
            d["descriptors"] = self.descriptors.to_dict()
        if self.eis_params:
            d["eis_params"] = self.eis_params.to_dict()
        if self.objective_value is not None:
            d["objective_value"] = round(self.objective_value, 6)
        return d
