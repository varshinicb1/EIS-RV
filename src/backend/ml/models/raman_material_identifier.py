"""
Raman Material Identification System
=====================================
Advanced material identification using machine learning and spectral matching.

Features:
- Database-driven material identification
- Fuzzy peak matching with confidence scores
- Machine learning-based classification (future)
- Multi-material detection (mixtures)
- Quality assessment and validation
- Spectral similarity scoring

Author: VidyuthLabs
Date: May 6, 2026
"""

import numpy as np
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from scipy.spatial.distance import cosine, euclidean
from scipy.interpolate import interp1d

logger = logging.getLogger(__name__)


@dataclass
class MaterialMatch:
    """Material identification match result."""
    material_id: str
    name: str
    formula: str
    category: str
    confidence: float
    matched_peaks: int
    total_expected_peaks: int
    peak_matches: List[Dict[str, Any]]
    spectral_similarity: float
    quality_score: float
    description: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "material_id": self.material_id,
            "name": self.name,
            "formula": self.formula,
            "category": self.category,
            "confidence": float(self.confidence),
            "matched_peaks": self.matched_peaks,
            "total_expected_peaks": self.total_expected_peaks,
            "match_ratio": float(self.matched_peaks / self.total_expected_peaks) if self.total_expected_peaks > 0 else 0.0,
            "peak_matches": self.peak_matches,
            "spectral_similarity": float(self.spectral_similarity),
            "quality_score": float(self.quality_score),
            "description": self.description
        }


class RamanMaterialIdentifier:
    """
    Advanced Raman material identification system.
    
    Uses comprehensive material database with reference spectra for
    accurate material identification based on peak positions, intensities,
    and spectral similarity.
    """
    
    def __init__(self, database_path: Optional[str] = None):
        """
        Initialize material identifier with database.
        
        Args:
            database_path: Path to raman_materials.json database
        """
        if database_path is None:
            # Default path - go up 4 levels from this file to reach EIS-RV root
            database_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "material_database" / "raman_materials.json"
        
        self.database_path = Path(database_path)
        self.materials = []
        self.load_database()
        
        logger.info(f"Raman material identifier initialized with {len(self.materials)} materials")
    
    def load_database(self):
        """Load material database from JSON file."""
        try:
            with open(self.database_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.materials = data.get("materials", [])
                logger.info(f"Loaded {len(self.materials)} materials from database")
        except FileNotFoundError:
            logger.error(f"Material database not found: {self.database_path}")
            self.materials = []
        except Exception as e:
            logger.error(f"Failed to load material database: {e}")
            self.materials = []
    
    def identify_material(
        self,
        detected_peaks: List[Dict[str, Any]],
        wavenumber: Optional[np.ndarray] = None,
        intensity: Optional[np.ndarray] = None,
        top_n: int = 5,
        min_confidence: float = 0.3
    ) -> List[MaterialMatch]:
        """
        Identify material based on detected Raman peaks.
        
        Args:
            detected_peaks: List of detected peaks with positions and intensities
            wavenumber: Full wavenumber array (optional, for spectral similarity)
            intensity: Full intensity array (optional, for spectral similarity)
            top_n: Number of top matches to return
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of MaterialMatch objects sorted by confidence
        """
        if not detected_peaks:
            logger.warning("No peaks provided for material identification")
            return []
        
        # Extract peak positions
        detected_positions = [p["position_cm"] for p in detected_peaks]
        detected_intensities = [p.get("intensity", 1.0) for p in detected_peaks]
        
        logger.info(f"Identifying material from {len(detected_positions)} detected peaks")
        logger.debug(f"Peak positions: {detected_positions}")
        
        matches = []
        
        for material in self.materials:
            match = self._match_material(
                material,
                detected_positions,
                detected_intensities,
                wavenumber,
                intensity
            )
            
            if match and match.confidence >= min_confidence:
                matches.append(match)
        
        # Sort by confidence (descending)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        
        # Return top N matches
        result = matches[:top_n]
        
        logger.info(f"Found {len(result)} material matches above confidence threshold {min_confidence}")
        if result:
            logger.info(f"Top match: {result[0].name} (confidence: {result[0].confidence:.3f})")
        
        return result
    
    def _match_material(
        self,
        material: Dict[str, Any],
        detected_positions: List[float],
        detected_intensities: List[float],
        wavenumber: Optional[np.ndarray],
        intensity: Optional[np.ndarray]
    ) -> Optional[MaterialMatch]:
        """
        Match detected peaks against a single material in database.
        
        Args:
            material: Material dictionary from database
            detected_positions: List of detected peak positions (cm⁻¹)
            detected_intensities: List of detected peak intensities
            wavenumber: Full wavenumber array (optional)
            intensity: Full intensity array (optional)
        
        Returns:
            MaterialMatch object or None
        """
        material_id = material["material_id"]
        name = material["name"]
        formula = material.get("formula", "")
        category = material.get("category", "")
        description = material.get("description", "")
        
        # Get reference peaks
        reference_peaks = material.get("reference_peaks", [])
        if not reference_peaks:
            return None
        
        # Get identification criteria
        criteria = material.get("identification_criteria", {})
        primary_peaks = criteria.get("primary_peaks", [p["position_cm"] for p in reference_peaks])
        tolerance = criteria.get("tolerance_cm", 20)
        min_conf = criteria.get("min_confidence", 0.5)
        
        # Match peaks
        peak_matches = []
        matched_count = 0
        
        for ref_peak in reference_peaks:
            ref_pos = ref_peak["position_cm"]
            ref_intensity = ref_peak.get("intensity_relative", 1.0)
            assignment = ref_peak.get("assignment", "")
            
            # Find closest detected peak
            best_match = None
            best_distance = float('inf')
            
            for i, det_pos in enumerate(detected_positions):
                distance = abs(det_pos - ref_pos)
                if distance <= tolerance and distance < best_distance:
                    best_distance = distance
                    best_match = {
                        "reference_position_cm": ref_pos,
                        "detected_position_cm": det_pos,
                        "distance_cm": distance,
                        "reference_intensity": ref_intensity,
                        "detected_intensity": detected_intensities[i],
                        "assignment": assignment,
                        "matched": True
                    }
            
            if best_match:
                peak_matches.append(best_match)
                matched_count += 1
            else:
                # Peak not found
                peak_matches.append({
                    "reference_position_cm": ref_pos,
                    "detected_position_cm": None,
                    "distance_cm": None,
                    "reference_intensity": ref_intensity,
                    "detected_intensity": None,
                    "assignment": assignment,
                    "matched": False
                })
        
        # Calculate confidence score
        if len(reference_peaks) == 0:
            return None
        
        # Base confidence: ratio of matched peaks
        match_ratio = matched_count / len(reference_peaks)
        
        # Bonus for matching primary peaks
        primary_matched = 0
        for primary_pos in primary_peaks:
            for det_pos in detected_positions:
                if abs(det_pos - primary_pos) <= tolerance:
                    primary_matched += 1
                    break
        
        primary_ratio = primary_matched / len(primary_peaks) if primary_peaks else 0.0
        
        # Weighted confidence: 60% match ratio + 40% primary peaks
        confidence = 0.6 * match_ratio + 0.4 * primary_ratio
        
        # Spectral similarity (if full spectrum provided)
        spectral_similarity = 0.0
        if wavenumber is not None and intensity is not None:
            spectral_similarity = self._calculate_spectral_similarity(
                wavenumber, intensity, reference_peaks
            )
            # Boost confidence with spectral similarity (10% weight)
            confidence = 0.9 * confidence + 0.1 * spectral_similarity
        
        # Quality score (peak position accuracy)
        quality_score = self._calculate_quality_score(peak_matches)
        
        # Check minimum confidence
        if confidence < min_conf:
            return None
        
        return MaterialMatch(
            material_id=material_id,
            name=name,
            formula=formula,
            category=category,
            confidence=confidence,
            matched_peaks=matched_count,
            total_expected_peaks=len(reference_peaks),
            peak_matches=peak_matches,
            spectral_similarity=spectral_similarity,
            quality_score=quality_score,
            description=description
        )
    
    def _calculate_spectral_similarity(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
        reference_peaks: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate spectral similarity between measured and reference spectrum.
        
        Uses synthetic reference spectrum generated from peak list.
        
        Args:
            wavenumber: Measured wavenumber array
            intensity: Measured intensity array
            reference_peaks: Reference peak list
        
        Returns:
            Similarity score (0-1, higher is better)
        """
        try:
            # Generate synthetic reference spectrum
            ref_intensity = np.zeros_like(wavenumber)
            
            for peak in reference_peaks:
                pos = peak["position_cm"]
                amp = peak.get("intensity_relative", 1.0)
                fwhm = peak.get("fwhm_cm", 20)
                
                # Lorentzian peak
                gamma = fwhm / 2
                ref_intensity += amp * (gamma**2) / ((wavenumber - pos)**2 + gamma**2)
            
            # Normalize both spectra
            intensity_norm = intensity / (np.linalg.norm(intensity) + 1e-10)
            ref_intensity_norm = ref_intensity / (np.linalg.norm(ref_intensity) + 1e-10)
            
            # Calculate cosine similarity
            similarity = 1.0 - cosine(intensity_norm, ref_intensity_norm)
            
            return max(0.0, min(1.0, similarity))
        
        except Exception as e:
            logger.warning(f"Failed to calculate spectral similarity: {e}")
            return 0.0
    
    def _calculate_quality_score(self, peak_matches: List[Dict[str, Any]]) -> float:
        """
        Calculate quality score based on peak position accuracy.
        
        Args:
            peak_matches: List of peak match dictionaries
        
        Returns:
            Quality score (0-1, higher is better)
        """
        matched = [m for m in peak_matches if m["matched"]]
        
        if not matched:
            return 0.0
        
        # Average normalized distance (lower is better)
        distances = [m["distance_cm"] for m in matched]
        avg_distance = np.mean(distances)
        
        # Convert to quality score (exponential decay)
        # Perfect match (0 cm) = 1.0, 20 cm = 0.37, 40 cm = 0.14
        quality = np.exp(-avg_distance / 20.0)
        
        return quality
    
    def identify_mixture(
        self,
        detected_peaks: List[Dict[str, Any]],
        wavenumber: Optional[np.ndarray] = None,
        intensity: Optional[np.ndarray] = None,
        max_components: int = 3,
        min_confidence: float = 0.4
    ) -> List[MaterialMatch]:
        """
        Identify multiple materials in a mixture.
        
        Uses greedy algorithm to find best combination of materials
        that explain the detected peaks.
        
        Args:
            detected_peaks: List of detected peaks
            wavenumber: Full wavenumber array (optional)
            intensity: Full intensity array (optional)
            max_components: Maximum number of materials in mixture
            min_confidence: Minimum confidence per component
        
        Returns:
            List of MaterialMatch objects for mixture components
        """
        detected_positions = [p["position_cm"] for p in detected_peaks]
        detected_intensities = [p.get("intensity", 1.0) for p in detected_peaks]
        
        components = []
        remaining_peaks = list(range(len(detected_positions)))
        
        for _ in range(max_components):
            if not remaining_peaks:
                break
            
            # Get subset of peaks
            subset_positions = [detected_positions[i] for i in remaining_peaks]
            subset_intensities = [detected_intensities[i] for i in remaining_peaks]
            
            # Find best match for remaining peaks
            matches = self.identify_material(
                [{"position_cm": p, "intensity": i} for p, i in zip(subset_positions, subset_intensities)],
                wavenumber,
                intensity,
                top_n=1,
                min_confidence=min_confidence
            )
            
            if not matches:
                break
            
            best_match = matches[0]
            components.append(best_match)
            
            # Remove matched peaks from remaining
            matched_positions = [m["detected_position_cm"] for m in best_match.peak_matches if m["matched"]]
            remaining_peaks = [i for i in remaining_peaks if detected_positions[i] not in matched_positions]
        
        logger.info(f"Identified {len(components)} components in mixture")
        
        return components
    
    def get_material_by_id(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        Get material information by ID.
        
        Args:
            material_id: Material ID
        
        Returns:
            Material dictionary or None
        """
        for material in self.materials:
            if material["material_id"] == material_id:
                return material
        return None
    
    def get_materials_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all materials in a category.
        
        Args:
            category: Material category
        
        Returns:
            List of material dictionaries
        """
        return [m for m in self.materials if m.get("category") == category]
    
    def search_materials(self, query: str) -> List[Dict[str, Any]]:
        """
        Search materials by name, formula, or description.
        
        Args:
            query: Search query
        
        Returns:
            List of matching material dictionaries
        """
        query_lower = query.lower()
        results = []
        
        for material in self.materials:
            name = material.get("name", "").lower()
            formula = material.get("formula", "").lower()
            description = material.get("description", "").lower()
            
            if query_lower in name or query_lower in formula or query_lower in description:
                results.append(material)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with statistics
        """
        categories = {}
        for material in self.materials:
            cat = material.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        
        total_peaks = sum(len(m.get("reference_peaks", [])) for m in self.materials)
        
        return {
            "total_materials": len(self.materials),
            "categories": categories,
            "total_reference_peaks": total_peaks,
            "average_peaks_per_material": total_peaks / len(self.materials) if self.materials else 0
        }


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def add_material_to_database(
    database_path: str,
    material: Dict[str, Any]
) -> bool:
    """
    Add a new material to the database.
    
    Args:
        database_path: Path to raman_materials.json
        material: Material dictionary
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load existing database
        with open(database_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Add material
        data["materials"].append(material)
        
        # Save database
        with open(database_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Added material {material['name']} to database")
        return True
    
    except Exception as e:
        logger.error(f"Failed to add material to database: {e}")
        return False


def update_material_in_database(
    database_path: str,
    material_id: str,
    updates: Dict[str, Any]
) -> bool:
    """
    Update an existing material in the database.
    
    Args:
        database_path: Path to raman_materials.json
        material_id: Material ID to update
        updates: Dictionary of fields to update
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load existing database
        with open(database_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find and update material
        for material in data["materials"]:
            if material["material_id"] == material_id:
                material.update(updates)
                break
        else:
            logger.warning(f"Material {material_id} not found in database")
            return False
        
        # Save database
        with open(database_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Updated material {material_id} in database")
        return True
    
    except Exception as e:
        logger.error(f"Failed to update material in database: {e}")
        return False


if __name__ == "__main__":
    # Test material identifier
    logging.basicConfig(level=logging.INFO)
    
    identifier = RamanMaterialIdentifier()
    
    # Test with graphene peaks
    test_peaks = [
        {"position_cm": 1582, "intensity": 1.0},
        {"position_cm": 2698, "intensity": 2.5}
    ]
    
    matches = identifier.identify_material(test_peaks, top_n=3)
    
    print("\n" + "="*80)
    print("RAMAN MATERIAL IDENTIFICATION TEST")
    print("="*80)
    print(f"\nDetected peaks: {[p['position_cm'] for p in test_peaks]}")
    print(f"\nTop {len(matches)} matches:")
    
    for i, match in enumerate(matches, 1):
        print(f"\n{i}. {match.name} ({match.formula})")
        print(f"   Confidence: {match.confidence:.3f}")
        print(f"   Matched peaks: {match.matched_peaks}/{match.total_expected_peaks}")
        print(f"   Quality score: {match.quality_score:.3f}")
        print(f"   Category: {match.category}")
    
    # Database statistics
    stats = identifier.get_statistics()
    print("\n" + "="*80)
    print("DATABASE STATISTICS")
    print("="*80)
    print(f"Total materials: {stats['total_materials']}")
    print(f"Total reference peaks: {stats['total_reference_peaks']}")
    print(f"Average peaks per material: {stats['average_peaks_per_material']:.1f}")
    print(f"\nMaterials by category:")
    for cat, count in sorted(stats['categories'].items()):
        print(f"  {cat}: {count}")
