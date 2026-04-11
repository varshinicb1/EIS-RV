"""Test all printed electronics API endpoints."""
import requests

BASE = "http://localhost:8000/api/pe"

# 1. Supercap
print("=" * 50)
print("SUPERCAPACITOR DEVICE SIMULATION")
print("=" * 50)
r = requests.post(f"{BASE}/supercap/simulate", json={
    "material": "activated_carbon",
    "capacitance_F_g": 150,
    "mass_mg": 1.0,
    "area_mm2": 100,
    "thickness_um": 50,
    "electrolyte": "1M H2SO4",
    "voltage_V": 1.0,
})
d = r.json()
print(f"  C_device     = {d['C_device_mF']} mF")
print(f"  C_specific   = {d['C_specific_F_g']} F/g")
print(f"  C_areal      = {d['C_areal_mF_cm2']} mF/cm²")
print(f"  Energy       = {d['energy_Wh_kg']} Wh/kg")
print(f"  Power        = {d['power_W_kg']} W/kg")
print(f"  ESR          = {d['ESR_ohm']} ohm")
print(f"  Retention 1k = {d['retention_1000_cycles_pct']}%")
print(f"  Retention10k = {d['retention_10000_cycles_pct']}%")
print(f"  V after 24h  = {d['voltage_after_24h_pct']}%")
print(f"  Ragone pts   = {len(d.get('ragone', {}).get('E_Wh_kg', []))}")
print(f"  GCD pts      = {len(d.get('gcd', {}).get('time_s', []))}")
print(f"  EIS pts      = {len(d.get('eis', {}).get('frequencies', []))}")
print()

# 2. Battery
print("=" * 50)
print("PRINTED BATTERY SIMULATION")
print("=" * 50)
r = requests.post(f"{BASE}/battery/simulate", json={
    "chemistry": "zinc_MnO2",
    "area_cm2": 1.0,
    "C_rate": 0.5,
})
d = r.json()
print(f"  Capacity     = {d['delivered_capacity_mAh']} mAh")
print(f"  Utilization  = {d['utilization_pct']}%")
print(f"  Energy       = {d['energy_mWh']} mWh")
print(f"  Energy Dens. = {d['energy_density_Wh_kg']} Wh/kg")
print(f"  OCV          = {d['OCV_V']} V")
print(f"  Avg V        = {d['avg_discharge_V']} V")
print(f"  R_internal   = {d['internal_resistance_ohm']} Ω")
print(f"  Rate cap.    = {d.get('rate_capability', {})}")
print(f"  Discharge pts= {len(d.get('discharge_curve', {}).get('voltage_V', []))}")
print()

# 3. Biosensor
print("=" * 50)
print("BIOSENSOR SIMULATION")
print("=" * 50)
r = requests.post(f"{BASE}/biosensor/simulate", json={
    "analyte": "glucose",
    "sensor_type": "amperometric",
    "electrode_material": "carbon_black",
    "modifier": "enzyme",
    "area_mm2": 7.07,
})
d = r.json()
print(f"  Sensitivity  = {d['sensitivity_uA_mM']} µA/mM")
print(f"  LOD          = {d['LOD_uM']} µM")
print(f"  LOQ          = {d['LOQ_uM']} µM")
print(f"  Km           = {d['Km_mM']} mM")
print(f"  R²           = {d.get('calibration', {}).get('R_squared', 'N/A')}")
print(f"  Response t   = {d['response_time_s']} s")
print(f"  Rct change   = {d['Rct_change_pct']}%")
print(f"  Peak current = {d['peak_current_uA']} µA @ {d['peak_potential_V']}V")
print(f"  Op. stab.    = {d['operational_stability_hours']} h")
print(f"  Shelf life   = {d['shelf_life_days']} days")
print()

# 4. Ink Engine
print("=" * 50)
print("INK FORMULATION ENGINE")
print("=" * 50)
r = requests.post(f"{BASE}/ink/simulate", json={
    "filler_material": "carbon_black",
    "filler_loading_wt_pct": 10,
    "particle_size_nm": 500,
    "aspect_ratio": 10,
    "primary_solvent": "water",
    "print_method": "screen_printing",
})
d = r.json()
print(f"  Viscosity    = {d['viscosity_mPas']} mPa·s")
print(f"  Surf. Ten.   = {d['surface_tension_mN_m']} mN/m")
print(f"  Z-param      = {d['Z_parameter']}")
print(f"  Printability = {d['printability_score'] * 100:.0f}%")
print(f"  Sheet R      = {d['sheet_resistance_ohm_sq']} Ω/□")
print(f"  Conductivity = {d['conductivity_S_m']} S/m")
print(f"  Perc. thresh = {d['percolation_threshold_vol_pct']}%")
print(f"  Above perc.  = {d['above_percolation']}")
print(f"  Dry film     = {d['dry_film_thickness_um']} µm")
print(f"  Shelf life   = {d['shelf_life_days']} days")
print(f"  Coffee ring  = {d['coffee_ring_risk']}")
print()

# 5. Quick check other endpoints
print("=" * 50)
print("SUPPORTING ENDPOINTS")
print("=" * 50)
r = requests.get(f"{BASE}/battery/chemistries")
chems = r.json()["chemistries"]
print(f"  Battery chemistries: {len(chems)} ({', '.join(c['name'] for c in chems)})")

r = requests.get(f"{BASE}/biosensor/analytes")
analytes = r.json()["analytes"]
print(f"  Biosensor analytes: {len(analytes)} ({', '.join(a['name'] for a in analytes)})")

r = requests.get(f"{BASE}/ink/solvents")
solvents = r.json()["solvents"]
print(f"  Ink solvents: {len(solvents)} ({', '.join(s['name'] for s in solvents)})")

r = requests.get(f"{BASE}/ink/print-methods")
methods = r.json()["methods"]
print(f"  Print methods: {len(methods)} ({', '.join(m['method'] for m in methods)})")

print()
print("✅ ALL ENDPOINTS OPERATIONAL")
