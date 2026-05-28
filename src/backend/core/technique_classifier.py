"""
Enhanced electrochemical technique detection using ML and signal analysis.
Fixes DPV/EIS misclassification issue.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)

class TechniqueClassifier:
    def __init__(self):
        self.technique_patterns = {
            "EIS": [
                r"zreal|zre|z'|z_real|z'",
                r"zimag|zim|z''|z_imag",
                r"impedance|nyquist|bode",
                r"freq.*z|z.*freq"
            ],
            "DPV": [
                r"differential\s*pulse|diff\s*pulse",
                r"pulse\s*voltammetry",
                r"dpv",
                r"pulse.*current|current.*pulse"
            ],
            "CV": [
                r"cyclic\s*voltammetry",
                r"cv",
                r"potential.*current|current.*potential",
                r"scan\s*rate"
            ],
            "SWV": [
                r"square\s*wave",
                r"swv"
            ],
            "CA": [
                r"chronoamperometry|ca",
                r"chrono"
            ],
            "GCD": [
                r"galvanostatic|charge.*discharge|gcd",
                r"chronopotentiometry"
            ],
            "LSV": [
                r"linear\s*sweep|lsv"
            ]
        }
    
    def analyze_filename(self, filename: str) -> Dict[str, float]:
        """Analyze filename for technique hints."""
        scores = {}
        filename_lower = filename.lower()
        
        for technique, patterns in self.technique_patterns.items():
            score = 0.0
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    score += 0.3
            scores[technique] = min(score, 1.0)
        
        return scores
    
    def analyze_headers(self, headers: List[str]) -> Dict[str, float]:
        """Analyze column headers for technique hints."""
        scores = {}
        headers_lower = [h.lower() for h in headers]
        headers_text = " ".join(headers_lower)
        
        for technique, patterns in self.technique_patterns.items():
            score = 0.0
            for pattern in patterns:
                if re.search(pattern, headers_text):
                    score += 0.4
            scores[technique] = min(score, 1.0)
        
        return scores
    
    def analyze_signal_shape(self, columns: Dict[str, np.ndarray]) -> Dict[str, float]:
        """Analyze signal shape to distinguish techniques."""
        scores = {}
        
        # Check for Nyquist semicircle (EIS)
        if 'zreal' in columns or 'zre' in columns or 'z_real' in columns:
            zreal_key = next((k for k in columns if 'zreal' in k.lower() or 'zre' in k.lower()), None)
            zimag_key = next((k for k in columns if 'zimag' in k.lower() or 'zim' in k.lower()), None)
            
            if zreal_key and zimag_key:
                zreal = columns[zreal_key]
                zimag = columns[zimag_key]
                
                # Check for semicircle pattern
                if self._has_semicircle_shape(zreal, zimag):
                    scores["EIS"] = 0.9
                # Check for DPV pulse pattern
                elif self._has_pulse_pattern(columns):
                    scores["DPV"] = 0.85
        
        # Check for CV peaks
        if 'current' in columns or 'i_' in str(columns).lower():
            current_key = next((k for k in columns if 'current' in k.lower() or k.startswith('i_')), None)
            potential_key = next((k for k in columns if 'potential' in k.lower() or 'e_v' in k.lower() or 'ewe' in k.lower()), None)
            
            if current_key and potential_key:
                current = columns[current_key]
                if self._has_peaks(current):
                    scores["CV"] = 0.8
        
        return scores
    
    def _has_semicircle_shape(self, zreal: np.ndarray, zimag: np.ndarray) -> bool:
        """Check if data forms a Nyquist semicircle."""
        if len(zreal) < 10:
            return False
        
        # Simple heuristic: check for monotonic decrease in real part
        # and peak in imaginary part
        zreal_diff = np.diff(zreal)
        if np.all(zreal_diff < 0):  # Monotonically decreasing
            # Check for peak in imaginary part
            zimag_abs = np.abs(zimag)
            peak_idx = np.argmax(zimag_abs)
            if 0.2 * len(zimag) < peak_idx < 0.8 * len(zimag):
                return True
        
        return False
    
    def _has_pulse_pattern(self, columns: Dict[str, np.ndarray]) -> bool:
        """Check for DPV pulse pattern in data."""
        # DPV typically has step-like current changes
        for col_name, col_data in columns.items():
            if 'current' in col_name.lower():
                # Check for step changes
                diffs = np.abs(np.diff(col_data))
                if np.any(diffs > 3 * np.std(diffs)):
                    return True
        return False
    
    def _has_peaks(self, data: np.ndarray) -> bool:
        """Check for oxidation/reduction peaks."""
        if len(data) < 10:
            return False
        
        # Simple peak detection
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(data, height=np.std(data))
        return len(peaks) >= 1
    
    def classify(
        self,
        filename: str,
        headers: List[str],
        columns: Dict[str, np.ndarray]
    ) -> Tuple[str, float]:
        """Classify technique using ensemble of all methods."""
        filename_scores = self.analyze_filename(filename)
        header_scores = self.analyze_headers(headers)
        signal_scores = self.analyze_signal_shape(columns)
        
        # Ensemble: weighted sum
        weights = {"filename": 0.2, "header": 0.4, "signal": 0.4}
        
        final_scores = {}
        for technique in self.technique_patterns.keys():
            final_scores[technique] = (
                weights["filename"] * filename_scores.get(technique, 0) +
                weights["header"] * header_scores.get(technique, 0) +
                weights["signal"] * signal_scores.get(technique, 0)
            )
        
        # Return highest scoring technique
        best_technique = max(final_scores, key=final_scores.get)
        confidence = final_scores[best_technique]
        
        # Fallback to Unknown if confidence is too low
        if confidence < 0.3:
            return "Unknown", confidence
        
        return best_technique, confidence
