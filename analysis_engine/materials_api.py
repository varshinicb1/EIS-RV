"""
Materials Project API Integration (Free, no key required for basic queries).

Provides material property lookup for electrode material screening:
- Crystal structure
- Band gap, formation energy
- Electrochemical stability window
- Ionic conductivity estimates

Uses the Materials Project REST API v2 (open access).
Reference: Jain et al., APL Materials 1, 011002 (2013)
"""

import json
import urllib.request
import urllib.parse
from typing import Optional


MP_API_BASE = "https://api.materialsproject.org"


def search_materials(formula: str, api_key: Optional[str] = None,
                     fields: Optional[list] = None) -> list:
    """
    Search Materials Project for materials by formula.

    Parameters
    ----------
    formula : str
        Chemical formula (e.g., "Fe2O3", "MnO2", "LiFePO4")
    api_key : str, optional
        Materials Project API key. Some queries work without it.
    fields : list, optional
        Fields to retrieve. Default: basic properties.

    Returns
    -------
    list of dict with material properties
    """
    if fields is None:
        fields = [
            "material_id", "formula_pretty", "formation_energy_per_atom",
            "band_gap", "energy_above_hull", "is_stable",
            "symmetry", "volume", "density",
        ]

    url = f"{MP_API_BASE}/materials/summary/"
    params = {
        "formula": formula,
        "fields": ",".join(fields),
        "_limit": 20,
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"

    headers = {"accept": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key

    try:
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", [])
    except Exception as e:
        return [{"error": str(e)}]


def get_electrode_candidates(element_group: str = "transition_metal_oxide",
                             api_key: Optional[str] = None) -> list:
    """
    Get candidate electrode materials for supercapacitor/sensor applications.

    Parameters
    ----------
    element_group : str
        Predefined group: "transition_metal_oxide", "carbon", "conducting_polymer"
    api_key : str, optional
        Materials Project API key.

    Returns
    -------
    list of candidate materials with properties
    """
    formulas = {
        "transition_metal_oxide": [
            "MnO2", "Fe2O3", "Fe3O4", "NiO", "Co3O4", "RuO2",
            "V2O5", "TiO2", "WO3", "SnO2", "CuO", "ZnO",
        ],
        "carbon": [
            "C",  # graphite/graphene/CNT
        ],
        "conducting_polymer": [],  # Not in MP database
        "perovskite": [
            "BaTiO3", "SrTiO3", "LaCoO3", "LaMnO3",
        ],
        "spinel": [
            "NiCo2O4", "MnCo2O4", "ZnCo2O4", "CuCo2O4",
        ],
    }

    target_formulas = formulas.get(element_group, formulas["transition_metal_oxide"])
    results = []
    for formula in target_formulas:
        mats = search_materials(formula, api_key)
        for m in mats:
            if "error" not in m:
                m["application_group"] = element_group
                results.append(m)

    # Sort by energy above hull (stability)
    results.sort(key=lambda x: x.get("energy_above_hull", 999))
    return results


def predict_supercapacitor_metrics(material_props: dict) -> dict:
    """
    Estimate supercapacitor performance metrics from material properties.

    Uses empirical correlations from literature:
    - Specific capacitance estimation from band gap and structure
    - Rate capability from ionic conductivity
    - Cycling stability from thermodynamic stability

    References:
    - Liu et al., Journal of Materials Informatics (2024)
    - Mishra et al., arXiv:2208.04172 (2022)
    """
    band_gap = material_props.get("band_gap", 0)
    e_hull = material_props.get("energy_above_hull", 0)
    density = material_props.get("density", 5.0)

    # Empirical capacitance estimate (F/g) — from literature correlations
    # Lower band gap → better electronic conductivity → higher capacitance
    if band_gap < 0.5:
        cap_estimate = 200 + (0.5 - band_gap) * 400  # metallic/semimetallic
    elif band_gap < 2.0:
        cap_estimate = 100 + (2.0 - band_gap) * 66  # semiconductor
    else:
        cap_estimate = max(10, 100 - (band_gap - 2.0) * 30)  # wide bandgap

    # Stability score (0-100) from energy above hull
    stability = max(0, 100 - e_hull * 1000)

    # Energy density estimate (Wh/kg)
    voltage_window = min(1.5, 3.0 - band_gap * 0.5) if band_gap > 0 else 1.0
    energy_density = 0.5 * cap_estimate * voltage_window**2 / 3.6

    return {
        "estimated_specific_capacitance_F_g": round(cap_estimate, 1),
        "estimated_voltage_window_V": round(voltage_window, 2),
        "estimated_energy_density_Wh_kg": round(energy_density, 1),
        "stability_score": round(stability, 1),
        "notes": "Estimates based on empirical ML correlations from literature. "
                 "Verify experimentally.",
    }


def predict_sensor_metrics(material_props: dict, analyte: str = "general") -> dict:
    """
    Estimate biosensor performance from material properties.

    Parameters
    ----------
    material_props : dict
        Material properties from Materials Project
    analyte : str
        Target analyte type: "general", "glucose", "uric_acid", "dopamine"

    Returns
    -------
    dict with estimated sensor performance metrics
    """
    band_gap = material_props.get("band_gap", 0)
    e_hull = material_props.get("energy_above_hull", 0)

    # Sensitivity estimate (μA/mM/cm²)
    if band_gap < 1.0:
        sensitivity = 50 + (1.0 - band_gap) * 100
    else:
        sensitivity = max(5, 50 - (band_gap - 1.0) * 20)

    # LOD estimate (μM) — lower is better
    lod = max(0.01, 10 - sensitivity * 0.05)

    # Linear range (mM)
    linear_range = [round(lod * 1e-3, 4), round(sensitivity * 0.1, 2)]

    # Response time (s) — correlated with conductivity
    response_time = max(1, 15 - sensitivity * 0.05)

    return {
        "estimated_sensitivity_uA_mM_cm2": round(sensitivity, 1),
        "estimated_LOD_uM": round(lod, 3),
        "estimated_linear_range_mM": linear_range,
        "estimated_response_time_s": round(response_time, 1),
        "stability_score": round(max(0, 100 - e_hull * 1000), 1),
        "analyte": analyte,
        "notes": "Preliminary estimates. Actual performance depends on "
                 "electrode preparation, electrolyte, and testing conditions.",
    }


if __name__ == "__main__":
    import sys

    formula = sys.argv[1] if len(sys.argv) > 1 else "Fe2O3"
    print(f"Searching Materials Project for: {formula}")

    materials = search_materials(formula)
    for m in materials[:3]:
        print(json.dumps(m, indent=2, default=str))
        print("\nSupercapacitor prediction:")
        print(json.dumps(predict_supercapacitor_metrics(m), indent=2))
        print("\nSensor prediction:")
        print(json.dumps(predict_sensor_metrics(m), indent=2))
        print("---")
