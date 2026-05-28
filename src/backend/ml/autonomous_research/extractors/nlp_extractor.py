"""
Advanced NLP extraction for scientific literature.
Uses spaCy and regex patterns to extract materials, synthesis, and electrochemical parameters.
"""

import logging
import re
from typing import Dict, Any, Optional, List
from .base_extractor import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)

class NLPExtractor(BaseExtractor):
    """Extract scientific data using NLP techniques."""
    
    def __init__(self, name: str = "NLPExtractor"):
        """Initialize NLP extractor."""
        super().__init__(name)
        self.material_patterns = [
            r'\b(graphene|carbon\s*nanotube|CNT|MoS2|MnO2|PEDOT|PSS|PEDOT:PSS|polypyrrole|polyaniline|TiO2|ZnO|NiO|Co3O4|Fe2O3|CuO|Ag|Au|Pt|Pd|Ru|Ir)\b',
            r'\b(polymer|composite|nanostructure|nanoparticle|nanowire|nanosheet|nanorod)\b'
        ]
        self.synthesis_patterns = {
            'method': r'(hydrothermal|sol-gel|electrodeposition|chemical\s*vapor|CVD|atomic\s*layer|ALD|drop\s*casting|spin\s*coating|spray\s*pyrolysis)',
            'temperature': r'(\d+)\s*[°C]?',
            'duration': r'(\d+)\s*(hour|h|min|minute)',
            'ph': r'pH\s*[:=]?\s*(\d+\.?\d*)'
        }
        self.eis_patterns = {
            'Rs': r'R[sS]\s*[:=]?\s*(\d+\.?\d*)\s*Ω?',
            'Rct': r'Rct\s*[:=]?\s*(\d+\.?\d*)\s*Ω?',
            'Cdl': r'Cdl\s*[:=]?\s*(\d+\.?\d*[eE][-+]?\d*)\s*F?',
            'capacitance': r'capacitance\s*[:=]?\s*(\d+\.?\d*)\s*(F/g|mF/cm2|F/cm2)',
            'electrolyte': r'(?:in|with)\s+(?:a\s+)?(\d+\.?\d*\s*[Mm]?\s*(?:KOH|H2SO4|NaOH|NaCl|LiPF6|LiClO4))'
        }
    
    def extract(self, paper: Dict[str, Any]) -> ExtractionResult:
        """Extract data using NLP."""
        try:
            text = paper.get("full_text", "") or paper.get("abstract", "") or ""
            
            if not text:
                return ExtractionResult(
                    success=False,
                    error="No text available for extraction",
                    method='nlp_extractor'
                )
            
            extracted_data = {
                "materials": self._extract_materials(text),
                "synthesis": self._extract_synthesis(text),
                "eis_parameters": self._extract_eis_parameters(text),
                "analytes": self._extract_analytes(text)
            }
            
            return ExtractionResult(
                success=True,
                data=extracted_data,
                method='nlp_extractor'
            )
            
        except Exception as e:
            logger.error(f"NLP extraction failed: {e}")
            return ExtractionResult(
                success=False,
                error=str(e),
                method='nlp_extractor'
            )
    
    def _extract_materials(self, text: str) -> List[Dict[str, Any]]:
        """Extract material names and ratios."""
        materials = []
        text_lower = text.lower()
        
        for pattern in self.material_patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                material = match.group(1)
                # Look for ratio in nearby context
                context = text[max(0, match.start()-50):min(len(text), match.end()+50)]
                ratio_match = re.search(r'(\d+\.?\d*)\s*(wt%|mol%|vol%|mg/mL)', context)
                
                materials.append({
                    "name": material,
                    "ratio": ratio_match.group(1) if ratio_match else None,
                    "unit": ratio_match.group(2) if ratio_match else None,
                    "confidence": 0.7
                })
        
        return materials
    
    def _extract_synthesis(self, text: str) -> Dict[str, Any]:
        """Extract synthesis parameters."""
        synthesis = {}
        
        for key, pattern in self.synthesis_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                synthesis[key] = match.group(1)
        
        return synthesis
    
    def _extract_eis_parameters(self, text: str) -> Dict[str, Any]:
        """Extract EIS parameters."""
        eis_params = {}
        
        for key, pattern in self.eis_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                eis_params[key] = match.group(1)
        
        return eis_params
    
    def _extract_analytes(self, text: str) -> List[str]:
        """Extract detected analytes."""
        analyte_patterns = [
            r'\b(glucose|dopamine|ascorbic\s*acid|uric\s*acid|H2O2|O2|NO|CO|NH3|ethanol|methanol)\b',
            r'\b(heavy\s*metal|Pb2+|Cd2+|Hg2+|As3+|Cr6+)\b'
        ]
        
        analytes = []
        for pattern in analyte_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            analytes.extend(matches)
        
        return list(set(analytes))
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate extracted NLP data."""
        if not data:
            return False
        
        # Check that at least one extraction succeeded
        return bool(
            data.get("materials") or
            data.get("synthesis") or
            data.get("eis_parameters") or
            data.get("analytes")
        )
