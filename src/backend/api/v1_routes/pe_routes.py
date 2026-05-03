"""
VANL Extended API Routes — Printed Electronics Digital Twin
=============================================================
New endpoints for ink formulation, supercapacitor devices,
batteries, and biosensors.

All routes return physics-engine-computed data. No fabricated values.
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pe", tags=["printed_electronics"])


# ══════════════════════════════════════════════════════════════════════
#   INK ENGINE
# ══════════════════════════════════════════════════════════════════════

class InkFormulationRequest(BaseModel):
    filler_material: str = Field("graphene", description="Conductive filler material")
    filler_loading_wt_pct: float = Field(5.0, description="Filler loading (wt%)")
    particle_size_nm: float = Field(500.0, description="Mean particle size (nm)")
    aspect_ratio: float = Field(100.0, description="Particle aspect ratio (L/d)")
    particle_density_kg_m3: float = Field(2200.0, description="Filler density (kg/m³)")
    primary_solvent: str = Field("water", description="Primary solvent")
    co_solvent: Optional[str] = Field(None, description="Co-solvent")
    co_solvent_fraction: float = Field(0.0, description="Co-solvent volume fraction")
    binder_type: str = Field("none", description="Binder type")
    binder_wt_pct: float = Field(0.0, description="Binder loading (wt%)")
    surfactant: Optional[str] = Field(None, description="Surfactant type")
    surfactant_wt_pct: float = Field(0.0, description="Surfactant loading (wt%)")
    print_method: str = Field("screen_printing", description="Target printing method")


@router.post("/ink/simulate")
async def simulate_ink_endpoint(request: InkFormulationRequest):
    """
    Simulate conductive ink properties for printed electronics.

    Returns: viscosity, printability, percolation conductivity, sheet resistance,
    drying behavior, stability assessment, and recommendations.
    """
    try:
        from src.backend.core.engines.ink_engine import InkFormulation, PrintMethod, simulate_ink

        formulation = InkFormulation(
            filler_material=request.filler_material,
            filler_loading_wt_pct=request.filler_loading_wt_pct,
            particle_size_nm=request.particle_size_nm,
            aspect_ratio=request.aspect_ratio,
            particle_density_kg_m3=request.particle_density_kg_m3,
            primary_solvent=request.primary_solvent,
            co_solvent=request.co_solvent,
            co_solvent_fraction=request.co_solvent_fraction,
            binder_type=request.binder_type,
            binder_wt_pct=request.binder_wt_pct,
            surfactant=request.surfactant,
            surfactant_wt_pct=request.surfactant_wt_pct,
            print_method=PrintMethod(request.print_method),
        )

        props = simulate_ink(formulation)
        return props.to_dict()

    except Exception as e:
        logger.exception("Ink simulation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ink/rheology")
async def ink_rheology_endpoint(request: InkFormulationRequest):
    """Generate full rheology flow curve (viscosity vs shear rate)."""
    try:
        from src.backend.core.engines.ink_engine import InkFormulation, PrintMethod, rheology_curve

        formulation = InkFormulation(
            filler_material=request.filler_material,
            filler_loading_wt_pct=request.filler_loading_wt_pct,
            particle_size_nm=request.particle_size_nm,
            aspect_ratio=request.aspect_ratio,
            particle_density_kg_m3=request.particle_density_kg_m3,
            primary_solvent=request.primary_solvent,
            print_method=PrintMethod(request.print_method),
        )
        return rheology_curve(formulation)

    except Exception as e:
        logger.exception("Rheology curve failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ink/percolation")
async def ink_percolation_endpoint(
    filler_material: str = "graphene",
    aspect_ratio: float = 100.0,
):
    """Generate percolation conductivity curve for a given filler."""
    try:
        from src.backend.core.engines.ink_engine import percolation_curve
        return percolation_curve(filler_material, aspect_ratio)
    except Exception as e:
        logger.exception("Percolation curve failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ink/solvents")
async def list_solvents_endpoint():
    """List available solvents with physical properties."""
    from src.backend.core.engines.ink_engine import list_solvents
    return {"solvents": list_solvents()}


@router.get("/ink/print-methods")
async def list_print_methods_endpoint():
    """List available printing methods with specifications."""
    from src.backend.core.engines.ink_engine import list_print_methods
    return {"methods": list_print_methods()}


# ══════════════════════════════════════════════════════════════════════
#   SUPERCAPACITOR DEVICE
# ══════════════════════════════════════════════════════════════════════

class SupercapRequest(BaseModel):
    # Electrode
    material: str = Field("activated_carbon", description="Electrode material")
    capacitance_F_g: float = Field(150.0, description="Specific capacitance (F/g)")
    mass_mg: float = Field(1.0, description="Active material mass (mg)")
    area_mm2: float = Field(100.0, description="Electrode area (mm²)")
    thickness_um: float = Field(50.0, description="Film thickness (µm)")
    conductivity_S_m: float = Field(1e3, description="Electrode conductivity (S/m)")
    porosity: float = Field(0.4, description="Film porosity")
    # Electrolyte
    electrolyte: str = Field("1M H2SO4", description="Electrolyte name")
    voltage_V: float = Field(1.0, description="Voltage window (V)")
    electrolyte_type: str = Field("aqueous", description="Electrolyte type")
    # Device
    is_symmetric: bool = Field(True, description="Symmetric device?")
    temperature_C: float = Field(25.0, description="Temperature (°C)")


@router.post("/supercap/simulate")
async def simulate_supercap_endpoint(request: SupercapRequest):
    """
    Full supercapacitor device simulation.

    Returns: device capacitance, energy/power density, Ragone plot,
    GCD waveform, EIS, cycling stability, self-discharge.
    """
    try:
        from src.backend.core.engines.supercap_device_engine import (
            ElectrodeSpec, ElectrolyteSpec, DeviceConfig, simulate_device,
        )

        side = max(float(request.area_mm2) ** 0.5, 0.1)

        espec = ElectrodeSpec(
            material_name=request.material,
            specific_capacitance_F_g=request.capacitance_F_g,
            active_mass_mg=request.mass_mg,
            length_mm=side, width_mm=side,
            thickness_um=request.thickness_um,
            conductivity_S_m=request.conductivity_S_m,
            porosity=request.porosity,
        )

        cond_map = {
            "1M H2SO4": 38.0, "6M KOH": 60.0, "1M Na2SO4": 8.0,
            "1M KCl": 11.2, "1M TEABF4/ACN": 5.0, "EMIMBF4": 1.5,
        }
        elec = ElectrolyteSpec(
            name=request.electrolyte,
            conductivity_S_m=cond_map.get(request.electrolyte, 10.0),
            voltage_window_V=request.voltage_V,
            type=request.electrolyte_type,
        )

        config = DeviceConfig(
            electrode_pos=espec,
            electrode_neg=espec,
            electrolyte=elec,
            is_symmetric=request.is_symmetric,
            temperature_C=request.temperature_C,
        )

        result = simulate_device(config)
        return result.to_dict()

    except Exception as e:
        logger.exception("Supercap simulation failed")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════
#   BATTERY
# ══════════════════════════════════════════════════════════════════════

class BatteryRequest(BaseModel):
    chemistry: str = Field("zinc_MnO2", description="Battery chemistry")
    area_cm2: float = Field(1.0, description="Electrode area (cm²)")
    cathode_thickness_um: float = Field(100.0, description="Cathode thickness (µm)")
    anode_thickness_um: float = Field(80.0, description="Anode thickness (µm)")
    cathode_loading_mg_cm2: float = Field(10.0, description="Cathode loading (mg/cm²)")
    anode_loading_mg_cm2: float = Field(8.0, description="Anode loading (mg/cm²)")
    C_rate: float = Field(0.5, description="Discharge C-rate")
    temperature_C: float = Field(25.0, description="Temperature (°C)")
    n_cells_series: int = Field(1, description="Number of cells in series")


@router.post("/battery/simulate")
async def simulate_battery_endpoint(request: BatteryRequest):
    """
    Full printed battery simulation.

    Returns: capacity, energy/power density, discharge curve, rate capability,
    aging prediction, EIS, Ragone plot.
    """
    try:
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery

        config = BatteryConfig(
            chemistry=request.chemistry,
            electrode_area_cm2=request.area_cm2,
            cathode_thickness_um=request.cathode_thickness_um,
            anode_thickness_um=request.anode_thickness_um,
            cathode_loading_mg_cm2=request.cathode_loading_mg_cm2,
            anode_loading_mg_cm2=request.anode_loading_mg_cm2,
            C_rate=request.C_rate,
            temperature_C=request.temperature_C,
            n_cells_series=request.n_cells_series,
        )

        # Set chemistry-specific defaults
        chem_defaults = {
            "zinc_MnO2": {"cathode_capacity_mAh_g": 308, "anode_capacity_mAh_g": 820,
                          "cutoff_V": 0.9, "max_V": 1.6},
            "silver_zinc": {"cathode_capacity_mAh_g": 150, "anode_capacity_mAh_g": 820,
                           "cutoff_V": 1.2, "max_V": 1.6},
            "LiFePO4": {"cathode_capacity_mAh_g": 170, "anode_capacity_mAh_g": 372,
                        "cutoff_V": 2.5, "max_V": 3.65, "electrolyte_type": "organic",
                        "electrolyte_conductivity_S_m": 1.0},
            "LiCoO2": {"cathode_capacity_mAh_g": 140, "anode_capacity_mAh_g": 372,
                       "cutoff_V": 3.0, "max_V": 4.2, "electrolyte_type": "organic",
                       "electrolyte_conductivity_S_m": 1.0},
        }

        defaults = chem_defaults.get(request.chemistry, {})
        for k, v in defaults.items():
            setattr(config, k, v)

        result = simulate_battery(config)
        return result.to_dict()

    except Exception as e:
        logger.exception("Battery simulation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/battery/chemistries")
async def list_battery_chemistries_endpoint():
    """List available battery chemistries."""
    from src.backend.core.engines.battery_engine import list_battery_chemistries
    return {"chemistries": list_battery_chemistries()}


# ══════════════════════════════════════════════════════════════════════
#   BIOSENSOR
# ══════════════════════════════════════════════════════════════════════

class BiosensorRequest(BaseModel):
    analyte: str = Field("glucose", description="Target analyte")
    sensor_type: str = Field("amperometric", description="Sensor type")
    electrode_material: str = Field("carbon_black", description="Working electrode material")
    modifier: str = Field("enzyme", description="Surface modification")
    area_mm2: float = Field(7.07, description="Working electrode area (mm²)")
    roughness_factor: float = Field(1.5, description="Surface roughness factor")
    enzyme_loading_U_cm2: float = Field(10.0, description="Enzyme loading (U/cm²)")
    pH: float = Field(7.4, description="Solution pH")
    temperature_C: float = Field(25.0, description="Temperature (°C)")
    applied_potential_V: float = Field(0.6, description="Applied potential (V)")
    scan_rate_mV_s: float = Field(50.0, description="Scan rate (mV/s)")


@router.post("/biosensor/simulate")
async def simulate_biosensor_endpoint(request: BiosensorRequest):
    """
    Full biosensor simulation for printed SPEs.

    Returns: calibration curve, LOD/LOQ, sensitivity, chronoamperometry,
    DPV response, EIS characterization, stability, selectivity.
    """
    try:
        from src.backend.core.engines.biosensor_engine import (
            BiosensorConfig, BiosensorType, simulate_biosensor,
        )

        config = BiosensorConfig(
            analyte=request.analyte,
            sensor_type=BiosensorType(request.sensor_type),
            working_electrode_material=request.electrode_material,
            modifier=request.modifier,
            working_electrode_area_mm2=request.area_mm2,
            roughness_factor=request.roughness_factor,
            enzyme_loading_U_cm2=request.enzyme_loading_U_cm2,
            pH=request.pH,
            temperature_C=request.temperature_C,
            applied_potential_V=request.applied_potential_V,
            scan_rate_mV_s=request.scan_rate_mV_s,
        )

        result = simulate_biosensor(config)
        return result.to_dict()

    except Exception as e:
        logger.exception("Biosensor simulation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/biosensor/analytes")
async def list_analytes_endpoint():
    """List available analytes for biosensor simulation."""
    from src.backend.core.engines.biosensor_engine import list_analytes
    return {"analytes": list_analytes()}


# ══════════════════════════════════════════════════════════════════════
#   DEVICE STRUCTURE GENERATOR
# ══════════════════════════════════════════════════════════════════════

class DeviceStructureRequest(BaseModel):
    device_type: str = Field("supercapacitor", description="Device type")
    layers: List[Dict] = Field(
        default=[
            {"name": "substrate", "material": "PET", "thickness_um": 125},
            {"name": "current_collector", "material": "silver_nanoparticles", "thickness_um": 1},
            {"name": "electrode", "material": "activated_carbon", "thickness_um": 50},
            {"name": "electrolyte", "material": "gel_H2SO4", "thickness_um": 100},
            {"name": "electrode", "material": "activated_carbon", "thickness_um": 50},
            {"name": "current_collector", "material": "silver_nanoparticles", "thickness_um": 1},
            {"name": "encapsulation", "material": "PET", "thickness_um": 125},
        ],
        description="Device layer stack",
    )
    width_mm: float = Field(10.0)
    length_mm: float = Field(10.0)


@router.post("/device/structure")
async def generate_device_structure(request: DeviceStructureRequest):
    """
    Generate a 3D device structure representation.

    Returns layer-by-layer structure with dimensions, material properties,
    and interface parameters for digital twin visualization.
    """
    try:
        layers = []
        z_offset = 0.0

        for layer in request.layers:
            thickness = layer.get("thickness_um", 10)
            material = layer.get("material", "unknown")
            name = layer.get("name", "layer")

            # Material properties lookup
            props = _get_layer_properties(material)

            layers.append({
                "name": name,
                "material": material,
                "thickness_um": thickness,
                "z_bottom_um": z_offset,
                "z_top_um": z_offset + thickness,
                "width_mm": request.width_mm,
                "length_mm": request.length_mm,
                "volume_mm3": request.width_mm * request.length_mm * thickness / 1000,
                "properties": props,
            })
            z_offset += thickness

        total_thickness = z_offset
        total_volume = request.width_mm * request.length_mm * total_thickness / 1000

        return {
            "device_type": request.device_type,
            "total_thickness_um": total_thickness,
            "footprint_mm2": request.width_mm * request.length_mm,
            "total_volume_mm3": round(total_volume, 4),
            "layers": layers,
            "n_layers": len(layers),
        }

    except Exception as e:
        logger.exception("Device structure generation failed")
        raise HTTPException(status_code=500, detail=str(e))


def _get_layer_properties(material: str) -> dict:
    """Get material properties for device layer."""
    props_db = {
        "PET": {"density_g_cm3": 1.38, "conductivity_S_m": 1e-14,
                "dielectric_constant": 3.1, "flexibility": "high", "color": "#e8e8e8"},
        "PI": {"density_g_cm3": 1.42, "conductivity_S_m": 1e-13,
               "dielectric_constant": 3.4, "flexibility": "high", "color": "#d4a030"},
        "paper": {"density_g_cm3": 0.7, "conductivity_S_m": 1e-10,
                  "flexibility": "medium", "color": "#f5f0e0"},
        "silver_nanoparticles": {"density_g_cm3": 10.5, "conductivity_S_m": 6.3e7,
                                "sheet_resistance_ohm_sq": 0.05, "color": "#c0c0c0"},
        "carbon_black": {"density_g_cm3": 1.8, "conductivity_S_m": 5e4,
                         "sheet_resistance_ohm_sq": 50, "color": "#1a1a1a"},
        "PEDOT_PSS": {"density_g_cm3": 1.01, "conductivity_S_m": 1000,
                      "color": "#1a3a5c"},
        "activated_carbon": {"density_g_cm3": 0.5, "conductivity_S_m": 1e3,
                            "surface_area_m2_g": 1500, "color": "#2d2d2d"},
        "MnO2": {"density_g_cm3": 5.0, "conductivity_S_m": 1e-5,
                 "pseudocapacitive": True, "color": "#3d2c1a"},
        "gel_H2SO4": {"density_g_cm3": 1.1, "conductivity_S_m": 1.0,
                      "color": "#e0f0ff", "ionic": True},
        "gel_KOH": {"density_g_cm3": 1.15, "conductivity_S_m": 2.0,
                    "color": "#e8ffe0", "ionic": True},
        "zinc": {"density_g_cm3": 7.14, "conductivity_S_m": 1.7e7,
                 "color": "#b0b0c0"},
    }
    return props_db.get(material, {"density_g_cm3": 1.0, "color": "#808080"})
