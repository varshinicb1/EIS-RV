"""
AI-Powered Material Identification System
==========================================
Combines RDKit molecular fingerprints with ML models to identify materials
from electrochemical data (EIS, CV, Raman).

Architecture:
    User Data → Feature Extraction → RDKit Fingerprint Prediction →
    Similarity Search → ML Ensemble → Top Candidates + Confidence

Cleanup (2026-05-20):
    - Removed _generate_synthetic_features (hashlib-seeded random numbers).
    - Added _generate_physics_features: extracts real physical properties
      (Rs, Rct, Cdl, warburg_coeff, conductivity, surface_area) from the
      materials database entries.
    - Added _generate_training_samples: creates N noisy copies of real
      features using Gaussian noise (5-10% RSD) to simulate experimental
      variability for ML training.
    - Replaced _rule_based_identification (constant 0.5 scores) with
      _physics_based_identification: normalised Euclidean distance between
      input features and each material's reference features, converted to
      confidence via  confidence = 1 / (1 + distance).
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
from scipy import signal
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)

# Try to import ML dependencies
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not available - ML features disabled")

# Import RDKit integration
from src.backend.integrations.rdkit_integration import get_rdkit_integration


@dataclass
class MaterialPrediction:
    """Result from material identification."""
    material_name: str
    confidence: float
    smiles: str
    synthesis_route: Optional[str]
    properties: Dict[str, Any]
    alternatives: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "material_name": self.material_name,
            "confidence": round(self.confidence, 4),
            "smiles": self.smiles,
            "synthesis_route": self.synthesis_route,
            "properties": self.properties,
            "alternatives": self.alternatives,
        }


@dataclass
class SpectralFeatures:
    """Extracted features from electrochemical data."""
    # EIS features
    Rs: Optional[float] = None
    Rct: Optional[float] = None
    Cdl: Optional[float] = None
    warburg_coeff: Optional[float] = None
    
    # CV features
    peak_current_anodic: Optional[float] = None
    peak_current_cathodic: Optional[float] = None
    peak_separation: Optional[float] = None
    reversibility: Optional[float] = None
    
    # Raman features
    d_band_position: Optional[float] = None
    g_band_position: Optional[float] = None
    id_ig_ratio: Optional[float] = None
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for ML model."""
        features = [
            self.Rs or 0,
            self.Rct or 0,
            self.Cdl or 0,
            self.warburg_coeff or 0,
            self.peak_current_anodic or 0,
            self.peak_current_cathodic or 0,
            self.peak_separation or 0,
            self.reversibility or 0,
            self.d_band_position or 0,
            self.g_band_position or 0,
            self.id_ig_ratio or 0,
        ]
        return np.array(features)


class MaterialIdentifier:
    """
    AI-powered material identification system.
    
    Workflow:
        1. Extract features from uploaded data (EIS/CV/Raman)
        2. Predict molecular fingerprint using ML model
        3. Search materials database using RDKit similarity
        4. Ensemble prediction from multiple models
        5. Return top candidates with confidence scores
    
    Usage:
        identifier = MaterialIdentifier()
        identifier.load_materials_database("materials_db.json")
        identifier.train_model()
        
        # Identify material from EIS data
        prediction = identifier.identify_from_eis(
            frequencies=[...],
            Z_real=[...],
            Z_imag=[...]
        )
        print(f"Material: {prediction.material_name}")
        print(f"Confidence: {prediction.confidence}")
    """
    
    def __init__(self):
        self.rdkit = get_rdkit_integration()
        self.materials_db: List[Dict[str, Any]] = []
        self.ml_model = None
        self.scaler = None
        self.trained = False
        
    def load_materials_database(self, db_path: str) -> int:
        """
        Load materials database from JSON file.
        
        Args:
            db_path: Path to materials database JSON
            
        Returns:
            Number of materials loaded
        """
        try:
            with open(db_path, 'r') as f:
                data = json.load(f)
            
            # Handle both formats: direct list or {"materials": [...]}
            if isinstance(data, list):
                self.materials_db = data
            elif isinstance(data, dict) and 'materials' in data:
                self.materials_db = data['materials']
            else:
                logger.error(f"Invalid database format. Expected list or dict with 'materials' key")
                return 0
            
            # Calculate RDKit descriptors for each material
            if self.rdkit.is_available():
                for material in self.materials_db:
                    if 'smiles' in material:
                        descriptors = self.rdkit.calculate_descriptors(material['smiles'])
                        if descriptors:
                            material['rdkit_descriptors'] = descriptors.to_dict()
            
            logger.info(f"Loaded {len(self.materials_db)} materials from database")
            return len(self.materials_db)
            
        except Exception as e:
            logger.error(f"Failed to load materials database: {e}")
            return 0
    
    def extract_eis_features(
        self,
        frequencies: List[float],
        Z_real: List[float],
        Z_imag: List[float]
    ) -> SpectralFeatures:
        """
        Extract features from EIS data using proper circuit analysis.
        
        Args:
            frequencies: Frequency array (Hz)
            Z_real: Real impedance (Ω)
            Z_imag: Imaginary impedance (Ω)
            
        Returns:
            SpectralFeatures object
        """
        freq = np.array(frequencies)
        Zr = np.array(Z_real)
        Zi = np.array(Z_imag)
        
        # Sort by frequency (high to low)
        sort_idx = np.argsort(freq)[::-1]
        freq = freq[sort_idx]
        Zr = Zr[sort_idx]
        Zi = Zi[sort_idx]
        
        # Extract Rs (high-frequency real axis intercept)
        # Use the last few points and extrapolate
        high_freq_mask = freq > np.percentile(freq, 90)
        if np.sum(high_freq_mask) > 2:
            Rs = np.mean(Zr[high_freq_mask])
        else:
            Rs = Zr[-1]
        
        # Extract Rct (charge transfer resistance)
        # Find semicircle diameter in Nyquist plot
        # Rct = (max(Zr) - Rs)
        Rct = np.max(Zr) - Rs
        
        # Estimate Cdl (double layer capacitance)
        # From the frequency at maximum -Zi (semicircle peak)
        peak_idx = np.argmin(Zi)  # Most negative Zi
        if peak_idx > 0 and peak_idx < len(freq) - 1:
            omega_peak = 2 * np.pi * freq[peak_idx]
            # For RC circuit: ω_peak = 1/(Rct * Cdl)
            if Rct > 0:
                Cdl = 1 / (omega_peak * Rct)
            else:
                Cdl = 0
        else:
            # Fallback: estimate from mid-frequency
            mid_idx = len(freq) // 2
            omega_mid = 2 * np.pi * freq[mid_idx]
            Cdl = -1 / (omega_mid * Zi[mid_idx]) if Zi[mid_idx] != 0 else 0
        
        # Warburg coefficient (diffusion)
        # Fit Z' vs ω^(-0.5) at low frequencies
        low_freq_mask = freq < np.percentile(freq, 30)
        if np.sum(low_freq_mask) > 3:
            omega_low = 2 * np.pi * freq[low_freq_mask]
            omega_sqrt_inv = 1 / np.sqrt(omega_low)
            Zr_low = Zr[low_freq_mask]
            
            try:
                # Linear fit: Z' = A + σ * ω^(-0.5)
                coeffs = np.polyfit(omega_sqrt_inv, Zr_low, 1)
                warburg_coeff = coeffs[0]  # Slope = σ (Warburg coefficient)
            except:
                warburg_coeff = 0
        else:
            warburg_coeff = 0
        
        return SpectralFeatures(
            Rs=float(Rs),
            Rct=float(max(Rct, 0)),  # Ensure positive
            Cdl=float(abs(Cdl)),
            warburg_coeff=float(abs(warburg_coeff))
        )
    
    def extract_cv_features(
        self,
        potential: List[float],
        current: List[float]
    ) -> SpectralFeatures:
        """
        Extract features from CV data using proper peak detection.
        
        Args:
            potential: Potential array (V)
            current: Current array (A)
            
        Returns:
            SpectralFeatures object
        """
        E = np.array(potential)
        i = np.array(current)
        
        # Detect turning points
        dE = np.diff(E)
        sign_changes = np.where(np.diff(np.sign(dE)))[0] + 1
        
        if len(sign_changes) >= 1:
            mid_idx = sign_changes[0]
        else:
            mid_idx = len(E) // 2
        
        # Forward scan (anodic)
        E_forward = E[:mid_idx]
        i_forward = i[:mid_idx]
        
        # Reverse scan (cathodic)
        E_reverse = E[mid_idx:]
        i_reverse = i[mid_idx:]
        
        # Find anodic peaks using scipy.signal.find_peaks
        try:
            peaks_anodic, properties_anodic = signal.find_peaks(
                i_forward,
                prominence=np.std(i_forward) * 0.5,
                distance=len(i_forward) // 10
            )
            
            if len(peaks_anodic) > 0:
                # Use the most prominent peak
                peak_current_anodic = i_forward[peaks_anodic[0]]
                peak_potential_anodic = E_forward[peaks_anodic[0]]
            else:
                # Fallback to maximum
                peak_current_anodic = np.max(i_forward)
                peak_potential_anodic = E_forward[np.argmax(i_forward)]
        except:
            peak_current_anodic = np.max(i_forward)
            peak_potential_anodic = E_forward[np.argmax(i_forward)]
        
        # Find cathodic peaks (negative peaks)
        try:
            peaks_cathodic, properties_cathodic = signal.find_peaks(
                -i_reverse,
                prominence=np.std(i_reverse) * 0.5,
                distance=len(i_reverse) // 10
            )
            
            if len(peaks_cathodic) > 0:
                peak_current_cathodic = abs(i_reverse[peaks_cathodic[0]])
                peak_potential_cathodic = E_reverse[peaks_cathodic[0]]
            else:
                peak_current_cathodic = abs(np.min(i_reverse))
                peak_potential_cathodic = E_reverse[np.argmin(i_reverse)]
        except:
            peak_current_cathodic = abs(np.min(i_reverse))
            peak_potential_cathodic = E_reverse[np.argmin(i_reverse)]
        
        # Peak separation (ΔEp)
        peak_separation = abs(peak_potential_anodic - peak_potential_cathodic)
        
        # Reversibility (peak current ratio)
        if peak_current_anodic > 0 and peak_current_cathodic > 0:
            reversibility = min(peak_current_anodic, peak_current_cathodic) / \
                           max(peak_current_anodic, peak_current_cathodic)
        else:
            reversibility = 0.0
        
        return SpectralFeatures(
            peak_current_anodic=float(peak_current_anodic),
            peak_current_cathodic=float(peak_current_cathodic),
            peak_separation=float(peak_separation),
            reversibility=float(reversibility)
        )
    
    def extract_raman_features(
        self,
        wavenumber: List[float],
        intensity: List[float]
    ) -> SpectralFeatures:
        """
        Extract features from Raman data.
        
        Args:
            wavenumber: Raman shift (cm^-1)
            intensity: Raman intensity (a.u.)
            
        Returns:
            SpectralFeatures object
        """
        wn = np.array(wavenumber)
        I = np.array(intensity)
        
        # Find D and G band positions (typical for carbon materials)
        # D band: ~1350 cm^-1, G band: ~1580 cm^-1
        d_band_mask = (wn > 1300) & (wn < 1400)
        g_band_mask = (wn > 1550) & (wn < 1650)
        
        if np.sum(d_band_mask) > 0:
            d_band_position = wn[d_band_mask][np.argmax(I[d_band_mask])]
            d_band_intensity = np.max(I[d_band_mask])
        else:
            d_band_position = 0
            d_band_intensity = 0
        
        if np.sum(g_band_mask) > 0:
            g_band_position = wn[g_band_mask][np.argmax(I[g_band_mask])]
            g_band_intensity = np.max(I[g_band_mask])
        else:
            g_band_position = 0
            g_band_intensity = 0
        
        # I_D/I_G ratio (disorder/graphitization)
        id_ig_ratio = d_band_intensity / g_band_intensity \
                     if g_band_intensity > 0 else 0
        
        return SpectralFeatures(
            d_band_position=float(d_band_position),
            g_band_position=float(g_band_position),
            id_ig_ratio=float(id_ig_ratio)
        )
    
    def train_model(self, test_size: float = 0.2, samples_per_material: int = 20) -> Dict[str, float]:
        """
        Train ML model on materials database.

        Training data is generated from **real** physical properties stored
        in the materials database.  For each material, ``samples_per_material``
        noisy copies are created by adding Gaussian noise (5-10 % relative
        standard deviation) to simulate experimental variability.

        Args:
            test_size: Fraction of data for testing.
            samples_per_material: Number of noisy training samples to
                generate per material (default 20).

        Returns:
            Training metrics (accuracy, etc.)
        """
        if not ML_AVAILABLE:
            logger.warning("scikit-learn not available - cannot train model")
            return {"error": "ML not available"}

        if len(self.materials_db) < 10:
            logger.warning("Insufficient training data (need at least 10 materials)")
            return {"error": "Insufficient data"}

        # Prepare training data from real physics features
        X = []
        y = []

        for material in self.materials_db:
            # Extract real physics-based features from the database entry
            base_features = self._generate_physics_features(
                material['name'], material
            )
            # Generate multiple noisy training samples
            noisy_samples = self._generate_training_samples(
                base_features, n_samples=samples_per_material
            )
            for sample in noisy_samples:
                X.append(sample.to_array())
                y.append(material['name'])

        X = np.array(X)
        y = np.array(y)

        logger.info(
            "Physics-based training: %d samples from %d materials",
            len(X), len(self.materials_db),
        )
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train ensemble model
        self.ml_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.ml_model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.ml_model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        self.trained = True
        logger.info(f"Model trained with accuracy: {accuracy:.4f}")
        
        return {
            "accuracy": float(accuracy),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "n_materials": len(self.materials_db),
        }
    
    def identify_from_eis(
        self,
        frequencies: List[float],
        Z_real: List[float],
        Z_imag: List[float],
        top_k: int = 3
    ) -> MaterialPrediction:
        """
        Identify material from EIS data.
        
        Args:
            frequencies: Frequency array (Hz)
            Z_real: Real impedance (Ω)
            Z_imag: Imaginary impedance (Ω)
            top_k: Number of top candidates to return
            
        Returns:
            MaterialPrediction with top candidate and alternatives
        """
        # Extract features
        features = self.extract_eis_features(frequencies, Z_real, Z_imag)
        
        # Predict using ML model
        if self.trained and self.ml_model is not None:
            X = features.to_array().reshape(1, -1)
            X_scaled = self.scaler.transform(X)
            
            # Get prediction probabilities
            proba = self.ml_model.predict_proba(X_scaled)[0]
            classes = self.ml_model.classes_
            
            # Sort by probability
            top_indices = np.argsort(proba)[::-1][:top_k]
            
            # Build prediction
            best_idx = top_indices[0]
            best_material_name = classes[best_idx]
            best_confidence = proba[best_idx]
            
            # Find material in database
            best_material = next(
                (m for m in self.materials_db if m['name'] == best_material_name),
                None
            )
            
            if best_material is None:
                # Fallback to first material
                best_material = self.materials_db[0]
            
            # Build alternatives
            alternatives = []
            for idx in top_indices[1:]:
                alt_name = classes[idx]
                alt_conf = proba[idx]
                alt_material = next(
                    (m for m in self.materials_db if m['name'] == alt_name),
                    None
                )
                if alt_material:
                    alternatives.append({
                        "material_name": alt_name,
                        "confidence": float(alt_conf),
                        "smiles": alt_material.get('smiles', ''),
                    })
            
            return MaterialPrediction(
                material_name=best_material_name,
                confidence=float(best_confidence),
                smiles=best_material.get('smiles', ''),
                synthesis_route=best_material.get('synthesis_route'),
                properties=best_material.get('properties', {}),
                alternatives=alternatives,
            )
        
        else:
            # Fallback: physics-based distance identification
            logger.info("Using physics-based similarity identification (ML model not trained)")
            return self._physics_based_identification(features, top_k)

    # ── Physics-based feature helpers ────────────────────────────────

    # Map of conductivity text labels → approximate numeric values (S/m)
    _CONDUCTIVITY_MAP: Dict[str, float] = {
        "very_high": 1e6,
        "high": 1e4,
        "medium": 1e2,
        "low": 1.0,
        "very_low": 0.01,
    }

    def _generate_physics_features(
        self, material_name: str, material_data: dict
    ) -> SpectralFeatures:
        """
        Extract **real** physical properties from a materials-database entry
        and return them as a ``SpectralFeatures`` object.

        Looked-up keys (in order of preference):
            - ``features.Rs`` / ``eis_params.Rs_ohm``
            - ``features.Rct`` / ``eis_params.Rct_ohm``
            - ``features.Cdl`` / ``eis_params.Cdl_F``
            - ``features.warburg_coeff``
            - ``properties.conductivity`` (numeric or categorical)
            - ``properties.surface_area_m2_g`` / ``morphology.surface_area_m2_g``
            - ``properties.capacitance_F_g``

        If a property is missing the field defaults to ``0``.

        Args:
            material_name: Human-readable material name (for logging).
            material_data: Full dict entry from ``materials_database.json``.

        Returns:
            ``SpectralFeatures`` populated from real database values.
        """
        feats = material_data.get('features', {})
        eis   = material_data.get('eis_params', {})
        props = material_data.get('properties', {})
        morph = material_data.get('morphology', {})

        # Rs — solution resistance (Ω)
        Rs = feats.get('Rs', eis.get('Rs_ohm', 0.0))

        # Rct — charge-transfer resistance (Ω)
        Rct = feats.get('Rct', eis.get('Rct_ohm', 0.0))

        # Cdl — double-layer capacitance (F)
        Cdl = feats.get('Cdl', eis.get('Cdl_F', 0.0))

        # Warburg coefficient
        warburg_coeff = feats.get('warburg_coeff', 0.0)

        # ── Additional physical features encoded in the unused
        #    SpectralFeatures slots (peak_current_anodic, etc.) so that
        #    the existing 11-element feature vector carries more
        #    discriminative information without changing the dataclass.
        # slot: peak_current_anodic  → conductivity (S/m)
        cond_raw = props.get('conductivity', material_data.get('conductivity_S_m', 0))
        if isinstance(cond_raw, str):
            conductivity = self._CONDUCTIVITY_MAP.get(cond_raw, 1.0)
        else:
            conductivity = float(cond_raw)

        # slot: peak_current_cathodic → surface area (m²/g)
        surface_area = float(
            props.get('surface_area_m2_g',
                       morph.get('surface_area_m2_g', 0.0))
        )

        # slot: peak_separation → capacitance (F/g)
        capacitance = float(props.get('capacitance_F_g', 0.0))

        # slot: reversibility → band gap (eV), 0 if absent
        band_gap = float(material_data.get('band_gap_eV', 0.0))

        logger.debug(
            "Physics features for '%s': Rs=%.2f Rct=%.2f Cdl=%.2e "
            "warburg=%.2f cond=%.1f SA=%.1f cap=%.1f bg=%.2f",
            material_name, Rs, Rct, Cdl, warburg_coeff,
            conductivity, surface_area, capacitance, band_gap,
        )

        return SpectralFeatures(
            Rs=float(Rs),
            Rct=float(Rct),
            Cdl=float(Cdl),
            warburg_coeff=float(warburg_coeff),
            peak_current_anodic=conductivity,
            peak_current_cathodic=surface_area,
            peak_separation=capacitance,
            reversibility=band_gap,
        )

    def _generate_training_samples(
        self,
        base_features: SpectralFeatures,
        n_samples: int = 20,
        rsd_low: float = 0.05,
        rsd_high: float = 0.10,
    ) -> List[SpectralFeatures]:
        """
        Create *n_samples* noisy copies of ``base_features`` to simulate
        experimental variability for ML training.

        Each feature value is perturbed independently by
        ``value * (1 + N(0, rsd))`` where *rsd* is drawn uniformly from
        [``rsd_low``, ``rsd_high``] (5-10 % relative standard deviation by
        default).

        Args:
            base_features: Reference feature vector from the database.
            n_samples: Number of noisy copies to generate.
            rsd_low: Minimum relative standard deviation (default 0.05).
            rsd_high: Maximum relative standard deviation (default 0.10).

        Returns:
            List of ``SpectralFeatures`` with added Gaussian noise.
        """
        rng = np.random.default_rng()  # non-seeded, non-global RNG
        base_arr = base_features.to_array()
        field_names = [
            'Rs', 'Rct', 'Cdl', 'warburg_coeff',
            'peak_current_anodic', 'peak_current_cathodic',
            'peak_separation', 'reversibility',
            'd_band_position', 'g_band_position', 'id_ig_ratio',
        ]

        samples: List[SpectralFeatures] = []
        for _ in range(n_samples):
            rsd = rng.uniform(rsd_low, rsd_high)
            noise = rng.normal(loc=0.0, scale=rsd, size=base_arr.shape)
            noisy = base_arr * (1.0 + noise)
            # Ensure non-negative values for physical quantities
            noisy = np.abs(noisy)
            kwargs = {name: float(noisy[i]) for i, name in enumerate(field_names)}
            samples.append(SpectralFeatures(**kwargs))

        return samples

    # ── Physics-based fallback identification ────────────────────────

    def _physics_based_identification(
        self,
        features: SpectralFeatures,
        top_k: int,
    ) -> MaterialPrediction:
        """
        Identify materials using normalised Euclidean distance between the
        input feature vector and each material's reference features.

        For every material in the database the reference feature vector is
        obtained via ``_generate_physics_features``.  The distance is then
        converted to a bounded confidence score:

            confidence = 1 / (1 + d)

        where *d* is the Euclidean distance in standardised feature space
        (each dimension is normalised by the range across all materials so
        that no single feature dominates).

        Args:
            features: Extracted ``SpectralFeatures`` from user data.
            top_k: Number of top candidates to return.

        Returns:
            ``MaterialPrediction`` with top candidate and alternatives.
        """
        if len(self.materials_db) == 0:
            # Edge case: empty database
            return MaterialPrediction(
                material_name="Unknown",
                confidence=0.0,
                smiles="",
                synthesis_route=None,
                properties={},
                alternatives=[],
            )

        input_vec = features.to_array()  # shape (11,)

        # Build reference matrix (N_materials × 11)
        ref_vecs = []
        for mat in self.materials_db:
            ref_feat = self._generate_physics_features(mat['name'], mat)
            ref_vecs.append(ref_feat.to_array())
        ref_matrix = np.array(ref_vecs)  # (N, 11)

        # Normalise each feature dimension by its range across all
        # materials so that no single dimension dominates the distance.
        feat_range = ref_matrix.max(axis=0) - ref_matrix.min(axis=0)
        # Avoid division by zero for constant features
        feat_range[feat_range == 0] = 1.0

        norm_input = (input_vec - ref_matrix.min(axis=0)) / feat_range
        norm_refs  = (ref_matrix - ref_matrix.min(axis=0)) / feat_range

        # Euclidean distances
        distances = np.linalg.norm(norm_refs - norm_input, axis=1)

        # Convert to confidence: confidence = 1 / (1 + distance)
        confidences = 1.0 / (1.0 + distances)

        # Sort descending by confidence
        sorted_indices = np.argsort(confidences)[::-1][:top_k]

        best_idx = sorted_indices[0]
        best_material = self.materials_db[best_idx]

        logger.info(
            "Physics-based identification: best match '%s' "
            "(confidence=%.4f, distance=%.4f)",
            best_material['name'], confidences[best_idx], distances[best_idx],
        )

        alternatives = [
            {
                "material_name": self.materials_db[idx]['name'],
                "confidence": float(confidences[idx]),
                "smiles": self.materials_db[idx].get('smiles', ''),
            }
            for idx in sorted_indices[1:]
        ]

        return MaterialPrediction(
            material_name=best_material['name'],
            confidence=float(confidences[best_idx]),
            smiles=best_material.get('smiles', ''),
            synthesis_route=best_material.get('synthesis_route'),
            properties=best_material.get('properties', {}),
            alternatives=alternatives,
        )


# Global singleton instance
_identifier_instance = None

def get_material_identifier() -> MaterialIdentifier:
    """Get the global material identifier instance."""
    global _identifier_instance
    if _identifier_instance is None:
        _identifier_instance = MaterialIdentifier()
    return _identifier_instance
