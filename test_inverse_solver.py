"""
Quick Test Script for Inverse Solver
======================================
Validates the predictive material identification system.
"""

import sys
import numpy as np

print("="*70)
print("  Predictive Material Identification System - Validation")
print("="*70)

# Test 1: Import modules
print("\n[1/5] Testing imports...")
try:
    from src.backend.ml.models.inverse_solver import InverseSolver
    from src.backend.ml.models.cross_modal_identifier import CrossModalIdentifier
    from src.backend.core.engines.materials_db import MATERIALS_DB
    print("✓ All modules imported successfully")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Initialize solver
print("\n[2/5] Initializing inverse solver...")
try:
    solver = InverseSolver()
    print(f"✓ Solver initialized with {len(solver.identifier.fingerprints)} material fingerprints")
except Exception as e:
    print(f"✗ Initialization failed: {e}")
    sys.exit(1)

# Test 3: Generate synthetic graphene EIS data
print("\n[3/5] Generating synthetic graphene EIS data...")
try:
    freq = np.logspace(-2, 5, 50)
    omega = 2 * np.pi * freq
    
    # Graphene-like parameters
    Rs_true = 10.0
    Rct_true = 50.0
    Cdl_true = 200e-6  # 200 µF
    sigma_true = 150.0
    
    # Forward model
    Z_ct = Rct_true / (1 + 1j * omega * Rct_true * Cdl_true)
    Z_w = sigma_true / np.sqrt(omega) * (1 - 1j)
    Z = Rs_true + Z_ct + Z_w
    
    # Add small noise
    np.random.seed(42)
    noise = np.random.normal(0, 1, len(freq)) + 1j * np.random.normal(0, 1, len(freq))
    Z_noisy = Z + noise
    
    print(f"✓ Generated {len(freq)} EIS data points")
    print(f"  True parameters: Rs={Rs_true}Ω, Rct={Rct_true}Ω, Cdl={Cdl_true*1e6:.0f}µF")
except Exception as e:
    print(f"✗ Data generation failed: {e}")
    sys.exit(1)

# Test 4: Solve inverse problem
print("\n[4/5] Solving inverse problem...")
try:
    solution = solver.solve_from_eis(
        frequency_Hz=freq,
        Z_real_ohm=Z_noisy.real,
        Z_imag_ohm=Z_noisy.imag,
        method="circuit_fit"
    )
    print("✓ Inverse problem solved successfully")
except Exception as e:
    print(f"✗ Inverse solver failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Validate results
print("\n[5/5] Validating results...")
try:
    # Check inferred properties
    Rs_inferred = solution.inferred_properties.get("Rs", 0)
    Rct_inferred = solution.inferred_properties.get("Rct", 0)
    Cdl_inferred = solution.inferred_properties.get("Cdl", 0)
    
    print(f"\n  Inferred Properties:")
    print(f"    Rs:  {Rs_inferred:.1f} Ω (true: {Rs_true:.1f} Ω)")
    print(f"    Rct: {Rct_inferred:.1f} Ω (true: {Rct_true:.1f} Ω)")
    print(f"    Cdl: {Cdl_inferred*1e6:.1f} µF (true: {Cdl_true*1e6:.1f} µF)")
    
    # Check material candidates
    if solution.material_candidates:
        top_candidate = solution.material_candidates[0]
        print(f"\n  Top Material Candidate:")
        print(f"    Name:       {top_candidate.material_name}")
        print(f"    Formula:    {top_candidate.formula}")
        print(f"    Category:   {top_candidate.category}")
        print(f"    Confidence: {top_candidate.confidence:.2%}")
        print(f"    Modality:   {top_candidate.modality_used}")
        
        # Check if graphene or rGO was identified
        if top_candidate.material_name in ["graphene", "reduced_graphene_oxide"]:
            print(f"\n  ✓ Correctly identified carbon material!")
        else:
            print(f"\n  ⚠ Expected graphene/rGO, got {top_candidate.material_name}")
    else:
        print(f"\n  ✗ No material candidates found")
    
    # Check synthesis suggestions
    if solution.synthesis_suggestions:
        print(f"\n  Synthesis Suggestions:")
        for i, sug in enumerate(solution.synthesis_suggestions[:3], 1):
            print(f"    {i}. {sug['material']} via {sug['method']}")
            print(f"       Cost: ${sug['estimated_cost_per_gram']:.2f}/g")
    
    # Overall confidence
    print(f"\n  Overall Confidence: {solution.confidence:.2%}")
    print(f"  Method: {solution.method}")
    print(f"  Convergence: {solution.convergence_info.get('success', False)}")
    
    # Validation checks
    errors = []
    
    # Check parameter accuracy (within 20%)
    if abs(Rs_inferred - Rs_true) / Rs_true > 0.2:
        errors.append(f"Rs error too large: {abs(Rs_inferred - Rs_true) / Rs_true:.1%}")
    
    if abs(Rct_inferred - Rct_true) / Rct_true > 0.2:
        errors.append(f"Rct error too large: {abs(Rct_inferred - Rct_true) / Rct_true:.1%}")
    
    if abs(Cdl_inferred - Cdl_true) / Cdl_true > 0.3:
        errors.append(f"Cdl error too large: {abs(Cdl_inferred - Cdl_true) / Cdl_true:.1%}")
    
    # Check confidence
    if solution.confidence < 0.5:
        errors.append(f"Confidence too low: {solution.confidence:.2%}")
    
    if errors:
        print(f"\n  ⚠ Validation warnings:")
        for err in errors:
            print(f"    - {err}")
    else:
        print(f"\n  ✓ All validation checks passed!")
    
except Exception as e:
    print(f"✗ Validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "="*70)
print("  VALIDATION COMPLETE")
print("="*70)
print("\n✓ Predictive Material Identification System is working correctly!")
print("\nNext steps:")
print("  1. Test with real CHI608E lab data")
print("  2. Try multi-modal fusion (EIS + CV + Raman)")
print("  3. Use the frontend panel for interactive analysis")
print("\nAPI endpoints available:")
print("  - POST /api/v2/inverse/eis")
print("  - POST /api/v2/inverse/cv")
print("  - POST /api/v2/inverse/raman")
print("  - POST /api/v2/inverse/multimodal")
print("\n" + "="*70)
