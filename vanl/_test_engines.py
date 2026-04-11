"""Quick validation of new engines."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")

# Test 1: Material DB
print("=" * 60)
print("TEST 1: Materials Database")
print("=" * 60)
from vanl.backend.core.materials_db import MATERIALS_DB, get_categories
print(f"Total materials: {len(MATERIALS_DB)}")
for cat, count in sorted(get_categories().items()):
    print(f"  {cat:25s} {count}")

# Spot check a few
for name in ["graphene", "MnO2", "LiFePO4", "MXene_Ti3C2"]:
    m = MATERIALS_DB.get(name)
    if m:
        print(f"\n  {m.formula}: sigma={m.conductivity_S_m} S/m, "
              f"SA={m.theoretical_surface_area_m2_g} m2/g, "
              f"${m.cost_per_gram_USD}/g")

# Test 2: CV Engine
print("\n" + "=" * 60)
print("TEST 2: CV Simulation")
print("=" * 60)
from vanl.backend.core.cv_engine import CVParameters, simulate_cv
cv_params = CVParameters(
    E_formal_V=0.23,
    C_ox_bulk_M=5e-3,
    D_ox_cm2_s=7.6e-6,
    k0_cm_s=0.01,
    scan_rate_V_s=0.05,
)
cv_result = simulate_cv(cv_params, n_points=500)
d = cv_result.to_dict()
a = d["analysis"]
print(f"  Peak anodic:   E_pa = {a['E_pa_V']:.3f} V, i_pa = {a['i_pa_mA']:.4f} mA")
print(f"  Peak cathodic: E_pc = {a['E_pc_V']:.3f} V, i_pc = {a['i_pc_mA']:.4f} mA")
print(f"  ΔEp = {a['delta_Ep_mV']:.1f} mV")
print(f"  Reversibility: {a['reversibility']}")
print(f"  Randles-Sevcik ip = {d['randles_sevcik']['i_p_theoretical_A']:.6f} A")
print(f"  Data points: {len(d['E'])}")

# Test 3: GCD Engine
print("\n" + "=" * 60)
print("TEST 3: GCD Simulation")
print("=" * 60)
from vanl.backend.core.gcd_engine import GCDParameters, simulate_gcd
gcd_params = GCDParameters(
    Cdl_F=0.01,        # 10 mF
    C_pseudo_F=0.005,   # 5 mF pseudocap
    Rs_ohm=5.0,
    Rct_ohm=50.0,
    current_A=0.001,     # 1 mA
    active_mass_mg=1.0,
    V_max=1.0,
    n_cycles=3,
)
gcd_result = simulate_gcd(gcd_params)
d = gcd_result.to_dict()
s = d["summary"]
print(f"  Specific Capacitance: {s['specific_capacitance_F_g']:.1f} F/g")
print(f"  Energy Density: {s['energy_density_Wh_kg']:.2f} Wh/kg")
print(f"  Power Density: {s['power_density_W_kg']:.1f} W/kg")
print(f"  Coulombic Efficiency: {s['coulombic_efficiency_pct']:.1f}%")
print(f"  IR Drop: {s['IR_drop_V']:.4f} V")
print(f"  Cycles simulated: {len(d['cycle_data'])}")
for c in d["cycle_data"]:
    print(f"    Cycle {c['cycle']}: Cs={c['specific_capacitance_F_g']:.1f} F/g, "
          f"η={c['coulombic_efficiency_pct']:.1f}%")
print(f"  Data points: {len(d['time_s'])}")

print("\n✅ All engines operational.")
