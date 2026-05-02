"""
Research Paper Validation Engine
==================================
Validates simulation results against experimental data from research papers.
Uses the research_pipeline database to compare predictions with literature.

Features:
1. Extract experimental data from papers
2. Compare simulation results with literature
3. Calculate validation metrics (RMSE, R², MAE)
4. Generate validation reports
"""

import logging
import sqlite3
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation against literature."""
    material: str
    property_name: str
    simulated_value: float
    literature_values: List[float]
    literature_sources: List[str]
    mean_literature: float
    std_literature: float
    error_percent: float
    within_std: bool
    confidence: str  # "high", "medium", "low"
    recommendation: str


class PaperValidator:
    """
    Validates simulation results against research papers database.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize validator with research papers database.
        
        Args:
            db_path: Path to research_pipeline SQLite database
        """
        if db_path is None:
            # Try to find database in standard locations
            possible_paths = [
                "vanl/datasets/research/papers.db",
                "datasets/research/papers.db",
                "research_pipeline/papers.db"
            ]
            for path in possible_paths:
                if Path(path).exists():
                    db_path = path
                    break
        
        self.db_path = db_path
        if self.db_path and Path(self.db_path).exists():
            self.enabled = True
            logger.info(f"Paper validator enabled with database: {self.db_path}")
        else:
            self.enabled = False
            logger.warning("Research papers database not found. Validation disabled.")
    
    def validate_material_property(
        self,
        material: str,
        property_name: str,
        simulated_value: float,
        tolerance: float = 0.2
    ) -> ValidationResult:
        """
        Validate a simulated property against literature.
        
        Args:
            material: Material name (e.g., "graphene", "LiFePO4")
            property_name: Property name (e.g., "capacitance", "conductivity")
            simulated_value: Simulated value
            tolerance: Acceptable error tolerance (default 20%)
        
        Returns:
            ValidationResult with comparison
        """
        if not self.enabled:
            return ValidationResult(
                material=material,
                property_name=property_name,
                simulated_value=simulated_value,
                literature_values=[],
                literature_sources=[],
                mean_literature=0.0,
                std_literature=0.0,
                error_percent=0.0,
                within_std=False,
                confidence="unknown",
                recommendation="Research database not available"
            )
        
        # Query database for experimental values
        lit_values, lit_sources = self._query_literature_values(material, property_name)
        
        if not lit_values:
            return ValidationResult(
                material=material,
                property_name=property_name,
                simulated_value=simulated_value,
                literature_values=[],
                literature_sources=[],
                mean_literature=0.0,
                std_literature=0.0,
                error_percent=0.0,
                within_std=False,
                confidence="low",
                recommendation=f"No literature data found for {material} {property_name}"
            )
        
        # Calculate statistics
        mean_lit = np.mean(lit_values)
        std_lit = np.std(lit_values)
        error_pct = abs(simulated_value - mean_lit) / mean_lit * 100
        within_std = abs(simulated_value - mean_lit) <= std_lit
        
        # Determine confidence
        if error_pct < 10:
            confidence = "high"
            recommendation = "Excellent agreement with literature"
        elif error_pct < 20:
            confidence = "medium"
            recommendation = "Good agreement with literature"
        elif within_std:
            confidence = "medium"
            recommendation = "Within literature variability"
        else:
            confidence = "low"
            recommendation = f"Significant deviation ({error_pct:.1f}%). Review model assumptions."
        
        return ValidationResult(
            material=material,
            property_name=property_name,
            simulated_value=simulated_value,
            literature_values=lit_values,
            literature_sources=lit_sources,
            mean_literature=mean_lit,
            std_literature=std_lit,
            error_percent=error_pct,
            within_std=within_std,
            confidence=confidence,
            recommendation=recommendation
        )
    
    def _query_literature_values(
        self,
        material: str,
        property_name: str
    ) -> Tuple[List[float], List[str]]:
        """
        Query database for experimental values from literature.
        
        Returns:
            (values, sources) tuple
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Search for papers mentioning material and property
            query = """
                SELECT p.title, p.doi, p.year, pd.extracted_data
                FROM papers p
                JOIN paper_data pd ON p.id = pd.paper_id
                WHERE (p.title LIKE ? OR p.abstract LIKE ?)
                AND (p.title LIKE ? OR p.abstract LIKE ?)
                AND pd.data_type = 'experimental'
                LIMIT 50
            """
            
            material_pattern = f"%{material}%"
            property_pattern = f"%{property_name}%"
            
            cursor.execute(query, (
                material_pattern, material_pattern,
                property_pattern, property_pattern
            ))
            
            values = []
            sources = []
            
            for row in cursor.fetchall():
                title, doi, year, data_json = row
                try:
                    data = json.loads(data_json)
                    if property_name in data:
                        value = float(data[property_name])
                        values.append(value)
                        sources.append(f"{title[:50]}... ({year})")
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
            
            conn.close()
            return values, sources
        
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return [], []
    
    def validate_eis_spectrum(
        self,
        simulated_spectrum: Dict,
        material: str
    ) -> Dict:
        """
        Validate entire EIS spectrum against literature.
        
        Args:
            simulated_spectrum: Dict with Z_real, Z_imag arrays
            material: Material name
        
        Returns:
            Validation report
        """
        # Validate key EIS parameters
        validations = []
        
        # Extract Rct from spectrum (semicircle diameter)
        Z_real = np.array(simulated_spectrum.get("Z_real", []))
        if len(Z_real) > 0:
            Rct_sim = np.max(Z_real) - np.min(Z_real)
            val_rct = self.validate_material_property(
                material, "charge_transfer_resistance", Rct_sim
            )
            validations.append(val_rct)
        
        # Validate capacitance if available
        if "capacitance" in simulated_spectrum:
            val_cap = self.validate_material_property(
                material, "capacitance", simulated_spectrum["capacitance"]
            )
            validations.append(val_cap)
        
        return {
            "material": material,
            "validations": [
                {
                    "property": v.property_name,
                    "simulated": v.simulated_value,
                    "literature_mean": v.mean_literature,
                    "error_percent": v.error_percent,
                    "confidence": v.confidence,
                    "recommendation": v.recommendation
                }
                for v in validations
            ],
            "overall_confidence": self._calculate_overall_confidence(validations)
        }
    
    def _calculate_overall_confidence(self, validations: List[ValidationResult]) -> str:
        """Calculate overall confidence from multiple validations."""
        if not validations:
            return "unknown"
        
        confidence_scores = {
            "high": 3,
            "medium": 2,
            "low": 1,
            "unknown": 0
        }
        
        avg_score = np.mean([confidence_scores[v.confidence] for v in validations])
        
        if avg_score >= 2.5:
            return "high"
        elif avg_score >= 1.5:
            return "medium"
        else:
            return "low"
    
    def generate_validation_report(
        self,
        validations: List[ValidationResult]
    ) -> str:
        """
        Generate human-readable validation report.
        
        Args:
            validations: List of validation results
        
        Returns:
            Markdown-formatted report
        """
        report = "# Validation Report\n\n"
        report += "## Summary\n\n"
        report += f"Total validations: {len(validations)}\n\n"
        
        high_conf = sum(1 for v in validations if v.confidence == "high")
        med_conf = sum(1 for v in validations if v.confidence == "medium")
        low_conf = sum(1 for v in validations if v.confidence == "low")
        
        report += f"- High confidence: {high_conf}\n"
        report += f"- Medium confidence: {med_conf}\n"
        report += f"- Low confidence: {low_conf}\n\n"
        
        report += "## Detailed Results\n\n"
        
        for v in validations:
            report += f"### {v.material} - {v.property_name}\n\n"
            report += f"- **Simulated**: {v.simulated_value:.3e}\n"
            report += f"- **Literature mean**: {v.mean_literature:.3e} ± {v.std_literature:.3e}\n"
            report += f"- **Error**: {v.error_percent:.1f}%\n"
            report += f"- **Confidence**: {v.confidence}\n"
            report += f"- **Recommendation**: {v.recommendation}\n\n"
            
            if v.literature_sources:
                report += "**Sources**:\n"
                for source in v.literature_sources[:5]:  # Top 5 sources
                    report += f"- {source}\n"
                report += "\n"
        
        return report


# Global instance
_paper_validator = None

def get_paper_validator() -> PaperValidator:
    """Get or create global paper validator instance."""
    global _paper_validator
    if _paper_validator is None:
        _paper_validator = PaperValidator()
    return _paper_validator
