import sys
sys.path.insert(0, r'C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV\engine_core\raman_core_rs')
import raman_core_rs
import numpy as np

print("Module loaded: raman_core_rs v" + raman_core_rs.__version__)

# Test EIS
p = raman_core_rs.PyEISParams()
p.Rs = 10.0
p.Rct = 100.0
p.Cdl = 1e-5
p.sigma_w = 50.0
p.n_cpe = 0.9

res = raman_core_rs.simulate_eis_py(p, 0.01, 1e6, 100)
print("EIS:", len(res.frequencies), "freq points, Z_real[0]=", res.Z_real[0])

# Test CV
cv = raman_core_rs.PyCVParams()
cv.E_start_V = -0.3
cv.E_vertex_V = 0.8
cv.scan_rate_V_s = 0.05

cv_res = raman_core_rs.simulate_cv_py(cv, 500)
print("CV:", len(cv_res.E), "points, i_pa=", cv_res.i_pa, "i_pc=", cv_res.i_pc)

# Test DRT
freqs = np.logspace(-2, 6, 80)
zr = np.ones(80) * 110
zi = -np.ones(80) * 50

drt_p = raman_core_rs.PyDRTParams()
drt_res = raman_core_rs.compute_drt_py(freqs, zr, zi, drt_p)
print("DRT: gamma max=", np.max(drt_res.gamma), "R_inf=", drt_res.R_inf)

# Test circuit fit
fp = raman_core_rs.PyFitParams()
fit_res = raman_core_rs.fit_circuit_py(freqs, zr, zi, np.array([10.0, 100.0, 1e-5, 0.9, 50.0]), fp)
print("Fit: converged=", fit_res.converged, "chi2=", fit_res.chi_squared)

# Test KK
kk = raman_core_rs.kramers_kronig_test_py(freqs, zr, zi, 0)
print("KK: is_valid=", kk.is_valid, "mu=", kk.mu)

print("ALL RUST ENGINE TESTS PASSED")
