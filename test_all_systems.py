import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'src/backend')

import numpy as np

# Test 1: GCD analyzer
from core.gcd_analyzer import get_gcd_analyzer
analyzer = get_gcd_analyzer()
t = np.linspace(0, 10, 200)
v = np.concatenate([np.linspace(0, 0.8, 100), np.linspace(0.8, 0.05, 100)])
res = analyzer.analyze(t, v, current_A=1e-3, mass_g=1e-3)
print(f"GCD OK: Cs={res.specific_capacitance_Fg:.1f} F/g, E={res.energy_density_Whkg:.2f} Wh/kg, P={res.power_density_Wkg:.1f} W/kg")

# Test 2: NVIDIA fallback
from research.nvidia_integration import discover_materials
candidates = discover_materials("Pb2+ detection biosensor")
print(f"NVIDIA OK: {len(candidates)} candidates, top={candidates[0].name}")

# Test 3: EIS with plot data
from core.chi_parser import get_analyzer
a = get_analyzer()
r = a.auto_analyze(r"Lab data\fog differet data\fog differet data\EIS FOG.xlsx")
eis = r["eis_analysis"]
pk = list(r["plot_data"].keys())
print(f"EIS OK: Rct={eis['Rct_ohm']}, plot_keys={pk}")

# Test 4: Raman with plot data
r2 = a.auto_analyze(r"Lab data\FO.txt")
mats = r2["raman_analysis"]["materials_detected"]
pk2 = list(r2["plot_data"].keys())
print(f"Raman OK: materials={mats}, plot_keys={pk2}")

print("ALL SYSTEMS GO")
