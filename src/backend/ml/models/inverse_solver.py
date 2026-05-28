"""
Inverse Problem Solver for Material Identification
===================================================
Given measured electrochemical/spectroscopic data, infer material properties
and composition using Bayesian inference and optimization.

This module solves the inverse problem:
    Measured Data → Material Properties → Material Identity

Approach:
1. **Feature Extraction**: Extract electrochemical fingerprints from raw data
2. **Bayesian Inference**: Use probabilistic models to infer material properties
3. **Database Matching**: Cross-reference against known materials
4. **Confidence Scoring**: Quantify uncertainty in predictions

Author: VidyuthLabs
Date: May 9, 2026
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm, multivariate_normal

from ..models.cross_modal_identifier import (
    CrossModalIdentifier,
    ElectrochemicalFingerprint,
    MaterialIdentification,
)
from ...core.engines.materials_db import MATERIALS_DB

# Optional imports - gracefully handle if not available
try:
    from ...core.engines.eis_engine import simulate_eis
except ImportError:
    simulate_eis = None

try:
    from ...core.engines.cv_engine import simulate_cv
except ImportError:
    simulate_cv = None

logger = logging.getLogger(__name__)


@dataclass
class InverseSolution:
    """Result of inverse problem solving."""
    material_candidates: List[MaterialIdentification]
    inferred_properties: Dict[str, Any]
    confidence: float
    method: str
    convergence_info: Dict[str, Any]
    synthesis_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "material_candidates": [m.to_dict() for m in self.material_candidates],
            "inferred_properties": self.inferred_properties,
            "confidence": float(self.confidence),
            "method": self.method,
            "convergence_info": self.convergence_info,
            "synthesis_suggestions": self.synthesis_suggestions,
        }


class InverseSolver:
    """
    Solves inverse problems to identify materials from measured data.
    
    Supports:
    - EIS data → Rct, Cdl, Warburg → material identification
    - CV data → peak positions, ΔEp, ipa/ipc → material identification
    - Raman data → peak positions → material identification
    - Multi-modal fusion for higher confidence
    """
    
    def __init__(self):
        self.identifier = CrossModalIdentifier()
        logger.info("InverseSolver initialized")
    
    def solve_from_eis(
        self,
        frequency_Hz: np.ndarray,
        Z_real_ohm: np.ndarray,
        Z_imag_ohm: np.ndarray,
        method: str = "circuit_fit",
    ) -> InverseSolution:
        """
        Solve inverse problem from EIS data.
        
        Args:
            frequency_Hz: Frequency array (Hz)
            Z_real_ohm: Real impedance (Ω)
            Z_imag_ohm: Imaginary impedance (Ω)
            method: "circuit_fit" or "bayesian"
        
        Returns:
            InverseSolution with material candidates and properties
        """
        logger.info(f"Solving inverse EIS problem using {method}")
        
        # Extract circuit parameters from measured data
        if method == "circuit_fit":
            params, convergence = self._fit_randles_circuit(
                frequency_Hz, Z_real_ohm, Z_imag_ohm
            )
        elif method == "bayesian":
            params, convergence = self._bayesian_eis_inference(
                frequency_Hz, Z_real_ohm, Z_imag_ohm
            )
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Extract electrochemical fingerprint
        fingerprint = ElectrochemicalFingerprint(
            modality="EIS",
            rct_ohm=params.get("Rct"),
            rs_ohm=params.get("Rs"),
            cdl_uF=params.get("Cdl", 0) * 1e6,  # F → µF
            warburg_coefficient=params.get("sigma_warburg"),
        )
        
        # Identify materials
        candidates = self.identifier._match_fingerprint(fingerprint)
        
        # Compute overall confidence
        confidence = self._compute_confidence(convergence, candidates)
        
        # Generate synthesis suggestions
        synthesis = self._suggest_synthesis(candidates)
        
        return InverseSolution(
            material_candidates=candidates,
            inferred_properties=params,
            confidence=confidence,
            method=method,
            convergence_info=convergence,
            synthesis_suggestions=synthesis,
        )
    
    def solve_from_cv(
        self,
        potential_V: np.ndarray,
        current_A: np.ndarray,
        scan_rate_V_s: float,
    ) -> InverseSolution:
        """
        Solve inverse problem from CV data.
        
        Args:
            potential_V: Potential array (V)
            current_A: Current array (A)
            scan_rate_V_s: Scan rate (V/s)
        
        Returns:
            InverseSolution with material candidates
        """
        logger.info("Solving inverse CV problem")
        
        # Extract CV features
        features = self._extract_cv_features(potential_V, current_A, scan_rate_V_s)
        
        # Create fingerprint
        fingerprint = ElectrochemicalFingerprint(
            modality="CV",
            anodic_peak_V=features.get("anodic_peak_V"),
            cathodic_peak_V=features.get("cathodic_peak_V"),
            peak_separation_mV=features.get("peak_separation_mV"),
            ipa_ipc_ratio=features.get("ipa_ipc_ratio"),
            scan_rate_mVs=scan_rate_V_s * 1000,
        )
        
        # Identify materials
        candidates = self.identifier._match_fingerprint(fingerprint)
        
        # Confidence based on peak quality
        confidence = features.get("peak_quality", 0.5)
        
        synthesis = self._suggest_synthesis(candidates)
        
        return InverseSolution(
            material_candidates=candidates,
            inferred_properties=features,
            confidence=confidence,
            method="cv_feature_extraction",
            convergence_info={"peak_quality": features.get("peak_quality", 0.5)},
            synthesis_suggestions=synthesis,
        )
    
    def solve_from_raman(
        self,
        wavenumber_cm: np.ndarray,
        intensity: np.ndarray,
    ) -> InverseSolution:
        """
        Solve inverse problem from Raman data.
        
        Args:
            wavenumber_cm: Wavenumber array (cm⁻¹)
            intensity: Intensity array (arbitrary units)
        
        Returns:
            InverseSolution with material candidates
        """
        logger.info("Solving inverse Raman problem")
        
        # Detect peaks using scipy
        from scipy.signal import find_peaks
        
        # Normalize intensity
        intensity_norm = (intensity - intensity.min()) / (intensity.max() - intensity.min() + 1e-10)
        
        # Find peaks
        peaks_idx, properties = find_peaks(
            intensity_norm,
            height=0.1,
            prominence=0.05,
            distance=10
        )
        
        peaks = []
        for idx in peaks_idx:
            peaks.append({
                "position_cm": wavenumber_cm[idx],
                "intensity": intensity[idx],
                "snr": properties["peak_heights"][list(peaks_idx).index(idx)] / (np.std(intensity_norm) + 1e-10)
            })
        
        # Extract D/G ratio if carbon material
        d_g_ratio = None
        d_peak = next((p for p in peaks if 1300 <= p["position_cm"] <= 1400), None)
        g_peak = next((p for p in peaks if 1550 <= p["position_cm"] <= 1620), None)
        if d_peak and g_peak:
            d_g_ratio = d_peak["intensity"] / g_peak["intensity"]
        
        # Create fingerprint
        fingerprint = ElectrochemicalFingerprint(
            modality="Raman",
            raman_peaks_cm=[p["position_cm"] for p in peaks],
            raman_d_g_ratio=d_g_ratio,
        )
        
        # Identify materials
        candidates = self.identifier._match_fingerprint(fingerprint)
        
        # Confidence based on peak count and SNR
        avg_snr = np.mean([p.get("snr", 1.0) for p in peaks]) if peaks else 0.5
        confidence = min(1.0, len(peaks) / 5.0 * min(1.0, avg_snr / 10.0))
        
        synthesis = self._suggest_synthesis(candidates)
        
        return InverseSolution(
            material_candidates=candidates,
            inferred_properties={
                "peaks": peaks,
                "d_g_ratio": d_g_ratio,
                "num_peaks": len(peaks),
            },
            confidence=confidence,
            method="raman_peak_matching",
            convergence_info={"avg_snr": avg_snr, "num_peaks": len(peaks)},
            synthesis_suggestions=synthesis,
        )
    
    def solve_multimodal(
        self,
        eis_data: Optional[Dict[str, np.ndarray]] = None,
        cv_data: Optional[Dict[str, Any]] = None,
        raman_data: Optional[Dict[str, np.ndarray]] = None,
    ) -> InverseSolution:
        """
        Solve inverse problem using multiple modalities for higher confidence.
        
        Args:
            eis_data: {"frequency_Hz", "Z_real_ohm", "Z_imag_ohm"}
            cv_data: {"potential_V", "current_A", "scan_rate_V_s"}
            raman_data: {"wavenumber_cm", "intensity"}
        
        Returns:
            InverseSolution with fused results
        """
        logger.info("Solving multimodal inverse problem")
        
        solutions = []
        
        if eis_data:
            sol = self.solve_from_eis(**eis_data)
            solutions.append(sol)
        
        if cv_data:
            sol = self.solve_from_cv(**cv_data)
            solutions.append(sol)
        
        if raman_data:
            sol = self.solve_from_raman(**raman_data)
            solutions.append(sol)
        
        if not solutions:
            raise ValueError("No data provided")
        
        # Fuse results
        all_candidates = []
        for sol in solutions:
            all_candidates.extend(sol.material_candidates)
        
        # Group by material formula
        material_groups: Dict[str, List[MaterialIdentification]] = {}
        for cand in all_candidates:
            key = cand.formula
            if key not in material_groups:
                material_groups[key] = []
            material_groups[key].append(cand)
        
        # Compute fused confidence
        fused_candidates = []
        for formula, cands in material_groups.items():
            modalities = [c.modality_used for c in cands]
            avg_conf = sum(c.confidence for c in cands) / len(cands)
            
            # Multi-modal bonus: +15% per additional modality
            boost = min(0.45, 0.15 * (len(modalities) - 1))
            final_conf = min(1.0, avg_conf + boost)
            
            merged_features = {}
            for c in cands:
                merged_features.update(c.matching_features)
            
            fused_candidates.append(MaterialIdentification(
                material_name=cands[0].material_name,
                formula=formula,
                category=cands[0].category,
                confidence=final_conf,
                modality_used="+".join(modalities),
                matching_features=merged_features,
                suggested_applications=cands[0].suggested_applications,
                rationale=f"Multi-modal fusion from {', '.join(modalities)}. "
                          f"Base confidence {avg_conf:.2f} → {final_conf:.2f}",
            ))
        
        fused_candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        # Merge properties
        merged_props = {}
        for sol in solutions:
            merged_props.update(sol.inferred_properties)
        
        # Overall confidence
        overall_conf = max(sol.confidence for sol in solutions)
        
        synthesis = self._suggest_synthesis(fused_candidates)
        
        return InverseSolution(
            material_candidates=fused_candidates,
            inferred_properties=merged_props,
            confidence=overall_conf,
            method="multimodal_fusion",
            convergence_info={
                "modalities": len(solutions),
                "individual_confidences": [sol.confidence for sol in solutions],
            },
            synthesis_suggestions=synthesis,
        )
    
    # ═══════════════════════════════════════════════════════════════
    # PRIVATE METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def _fit_randles_circuit(
        self,
        freq: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Fit Randles circuit to EIS data using least-squares."""
        
        def randles_model(params, f):
            """Randles circuit: Rs + Rct/(1 + jωRctCdl) + σ/√ω"""
            Rs, Rct, Cdl, sigma = params
            omega = 2 * np.pi * f
            
            # Charge transfer branch
            Z_ct = Rct / (1 + 1j * omega * Rct * Cdl)
            
            # Warburg impedance
            Z_w = sigma / np.sqrt(omega) * (1 - 1j)
            
            return Rs + Z_ct + Z_w
        
        def objective(params):
            """Least-squares objective."""
            if any(p <= 0 for p in params):
                return 1e10
            
            Z_model = randles_model(params, freq)
            Z_meas = Z_real + 1j * Z_imag
            
            residual = np.abs(Z_model - Z_meas)
            return np.sum(residual**2)
        
        # Initial guess from data
        Rs_init = Z_real[-1]  # High-frequency intercept
        Rct_init = Z_real[0] - Rs_init  # Low-frequency - Rs
        Cdl_init = 1e-5  # 10 µF typical
        sigma_init = 100  # Typical Warburg
        
        x0 = [Rs_init, Rct_init, Cdl_init, sigma_init]
        
        # Bounds
        bounds = [
            (0.1, 1e6),    # Rs
            (0.1, 1e6),    # Rct
            (1e-9, 1e-2),  # Cdl
            (0.1, 1e6),    # sigma
        ]
        
        # Optimize
        result = minimize(
            objective,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
        )
        
        Rs, Rct, Cdl, sigma = result.x
        
        params = {
            "Rs": Rs,
            "Rct": Rct,
            "Cdl": Cdl,
            "sigma_warburg": sigma,
        }
        
        convergence = {
            "success": result.success,
            "residual": result.fun,
            "iterations": result.nit,
            "message": result.message,
        }
        
        logger.info(f"Circuit fit: Rs={Rs:.1f}Ω, Rct={Rct:.1f}Ω, Cdl={Cdl*1e6:.1f}µF")
        
        return params, convergence
    
    def _bayesian_eis_inference(
        self,
        freq: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Bayesian inference for EIS parameters with uncertainty quantification."""
        
        # Use differential evolution for global optimization
        def neg_log_likelihood(params):
            """Negative log-likelihood for Bayesian inference."""
            Rs, Rct, Cdl, sigma, noise_std = params
            
            if any(p <= 0 for p in params):
                return 1e10
            
            # Forward model
            omega = 2 * np.pi * freq
            Z_ct = Rct / (1 + 1j * omega * Rct * Cdl)
            Z_w = sigma / np.sqrt(omega) * (1 - 1j)
            Z_model = Rs + Z_ct + Z_w
            
            Z_meas = Z_real + 1j * Z_imag
            
            # Likelihood: Gaussian noise model
            residual = np.abs(Z_model - Z_meas)
            log_lik = -0.5 * np.sum((residual / noise_std)**2)
            log_lik -= len(residual) * np.log(noise_std)
            
            return -log_lik
        
        # Bounds
        bounds = [
            (0.1, 1e6),    # Rs
            (0.1, 1e6),    # Rct
            (1e-9, 1e-2),  # Cdl
            (0.1, 1e6),    # sigma
            (0.01, 100),   # noise_std
        ]
        
        # Global optimization
        result = differential_evolution(
            neg_log_likelihood,
            bounds,
            maxiter=100,
            seed=42,
        )
        
        Rs, Rct, Cdl, sigma, noise_std = result.x
        
        params = {
            "Rs": Rs,
            "Rct": Rct,
            "Cdl": Cdl,
            "sigma_warburg": sigma,
            "noise_std": noise_std,
        }
        
        convergence = {
            "success": result.success,
            "neg_log_likelihood": result.fun,
            "iterations": result.nit,
            "message": result.message,
        }
        
        logger.info(f"Bayesian EIS: Rs={Rs:.1f}Ω, Rct={Rct:.1f}Ω, Cdl={Cdl*1e6:.1f}µF")
        
        return params, convergence
    
    def _extract_cv_features(
        self,
        potential: np.ndarray,
        current: np.ndarray,
        scan_rate: float,
    ) -> Dict[str, Any]:
        """Extract electrochemical features from CV data."""
        
        # Find peaks (simple approach: local maxima/minima)
        from scipy.signal import find_peaks
        
        # Anodic peaks (positive current)
        anodic_peaks, _ = find_peaks(current, height=0, prominence=np.std(current)*0.5)
        
        # Cathodic peaks (negative current)
        cathodic_peaks, _ = find_peaks(-current, height=0, prominence=np.std(current)*0.5)
        
        features = {}
        
        if len(anodic_peaks) > 0:
            ipa_idx = anodic_peaks[np.argmax(current[anodic_peaks])]
            features["anodic_peak_V"] = potential[ipa_idx]
            features["ipa"] = current[ipa_idx]
        
        if len(cathodic_peaks) > 0:
            ipc_idx = cathodic_peaks[np.argmax(-current[cathodic_peaks])]
            features["cathodic_peak_V"] = potential[ipc_idx]
            features["ipc"] = current[ipc_idx]
        
        if "anodic_peak_V" in features and "cathodic_peak_V" in features:
            features["peak_separation_mV"] = abs(
                features["anodic_peak_V"] - features["cathodic_peak_V"]
            ) * 1000
            
            if features["ipc"] != 0:
                features["ipa_ipc_ratio"] = abs(features["ipa"] / features["ipc"])
        
        # Peak quality score
        if len(anodic_peaks) > 0 and len(cathodic_peaks) > 0:
            features["peak_quality"] = min(1.0, (len(anodic_peaks) + len(cathodic_peaks)) / 4.0)
        else:
            features["peak_quality"] = 0.3
        
        return features
    
    def _compute_confidence(
        self,
        convergence: Dict[str, Any],
        candidates: List[MaterialIdentification],
    ) -> float:
        """Compute overall confidence score."""
        
        # Convergence quality
        conv_score = 1.0 if convergence.get("success", False) else 0.5
        
        # Candidate quality
        if candidates:
            cand_score = candidates[0].confidence
        else:
            cand_score = 0.0
        
        # Combined
        return (conv_score + cand_score) / 2.0
    
    def _suggest_synthesis(
        self,
        candidates: List[MaterialIdentification],
    ) -> List[Dict[str, Any]]:
        """Suggest synthesis routes for identified materials."""
        
        suggestions = []
        
        for cand in candidates[:3]:  # Top 3 candidates
            mat_name = cand.material_name
            
            # Look up in materials database
            if mat_name in MATERIALS_DB:
                mat = MATERIALS_DB[mat_name]
                
                for method in mat.common_synthesis_methods:
                    suggestions.append({
                        "material": mat_name,
                        "formula": cand.formula,
                        "method": method,
                        "confidence": cand.confidence,
                        "estimated_cost_per_gram": mat.cost_per_gram_USD,
                        "typical_electrolytes": mat.common_electrolytes,
                    })
        
        return suggestions


# ═══════════════════════════════════════════════════════════════════
# MODULE-LEVEL INSTANCE
# ═══════════════════════════════════════════════════════════════════

_solver_instance: Optional[InverseSolver] = None


def get_solver() -> InverseSolver:
    """Get or create the singleton solver instance."""
    global _solver_instance
    if _solver_instance is None:
        _solver_instance = InverseSolver()
    return _solver_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    solver = InverseSolver()
    
    # Test with synthetic EIS data
    print("="*70)
    print("  Inverse Problem Solver Test")
    print("="*70)
    
    # Generate synthetic EIS data for graphene
    freq = np.logspace(-2, 5, 50)
    omega = 2 * np.pi * freq
    
    # True parameters (graphene-like)
    Rs_true = 10.0
    Rct_true = 50.0
    Cdl_true = 200e-6  # 200 µF
    sigma_true = 150.0
    
    # Forward model
    Z_ct = Rct_true / (1 + 1j * omega * Rct_true * Cdl_true)
    Z_w = sigma_true / np.sqrt(omega) * (1 - 1j)
    Z = Rs_true + Z_ct + Z_w
    
    # Add noise
    noise = np.random.normal(0, 2, len(freq)) + 1j * np.random.normal(0, 2, len(freq))
    Z_noisy = Z + noise
    
    # Solve inverse problem
    solution = solver.solve_from_eis(
        frequency_Hz=freq,
        Z_real_ohm=Z_noisy.real,
        Z_imag_ohm=Z_noisy.imag,
        method="circuit_fit",
    )
    
    print("\n--- Inferred Properties ---")
    for key, val in solution.inferred_properties.items():
        print(f"  {key}: {val:.3e}")
    
    print(f"\n--- Material Candidates (confidence: {solution.confidence:.2f}) ---")
    for i, cand in enumerate(solution.material_candidates[:3], 1):
        print(f"{i}. {cand.material_name} ({cand.formula})")
        print(f"   Confidence: {cand.confidence:.3f}")
        print(f"   Modality: {cand.modality_used}")
    
    print("\n--- Synthesis Suggestions ---")
    for i, sug in enumerate(solution.synthesis_suggestions[:3], 1):
        print(f"{i}. {sug['material']} via {sug['method']}")
        print(f"   Cost: ${sug['estimated_cost_per_gram']:.2f}/g")
    
    print("\nTest completed.")
