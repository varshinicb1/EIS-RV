#!/usr/bin/env python3
"""
Data Extraction Engine
Extracts experimental data from scientific papers

Extracts:
- Material composition and properties
- Electrode specifications
- Synthesis methods
- Performance metrics
- Experimental data (CV curves, EIS spectra, etc.)
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MaterialInfo:
    """Material information extracted from paper"""
    name: str
    formula: Optional[str] = None
    type: Optional[str] = None  # 'graphene', 'CNT', 'metal oxide', etc.
    morphology: Optional[str] = None  # 'nanoparticle', 'nanosheet', etc.
    size_nm: Optional[float] = None
    surface_area_m2g: Optional[float] = None
    conductivity_sm: Optional[float] = None


@dataclass
class ElectrodeInfo:
    """Electrode information"""
    type: str  # 'screen printed', 'glassy carbon', etc.
    material: str
    modification: Optional[str] = None
    area_cm2: Optional[float] = None
    commercial: bool = False


@dataclass
class SynthesisInfo:
    """Synthesis method information"""
    method: str  # 'hydrothermal', 'sol-gel', etc.
    temperature_c: Optional[float] = None
    time_hours: Optional[float] = None
    precursors: List[str] = None
    steps: List[str] = None
    yield_percent: Optional[float] = None
    cost: Optional[str] = None  # 'low', 'medium', 'high'
    difficulty: Optional[str] = None  # 'easy', 'medium', 'hard'


@dataclass
class PerformanceMetrics:
    """Performance metrics for biosensors"""
    sensitivity: Optional[float] = None  # μA/μM or μA/mM
    sensitivity_unit: Optional[str] = None
    detection_limit: Optional[float] = None  # nM or μM
    detection_limit_unit: Optional[str] = None
    linear_range_min: Optional[float] = None
    linear_range_max: Optional[float] = None
    linear_range_unit: Optional[str] = None
    selectivity: Dict[str, float] = None
    stability_days: Optional[int] = None
    reproducibility_rsd: Optional[float] = None
    response_time_s: Optional[float] = None


@dataclass
class ExtractedData:
    """Complete extracted data from a paper"""
    paper_id: str
    paper_doi: Optional[str]
    material: Optional[MaterialInfo] = None
    electrode: Optional[ElectrodeInfo] = None
    synthesis: Optional[SynthesisInfo] = None
    performance: Optional[PerformanceMetrics] = None
    target_analyte: Optional[str] = None
    sample_type: Optional[str] = None  # 'blood', 'water', 'food'
    application: Optional[str] = None  # 'biosensor', 'supercapacitor', 'battery'
    raw_text: Optional[str] = None
    extraction_confidence: float = 0.0


class DataExtractor:
    """
    Intelligent data extraction from papers
    Uses NLP and pattern matching
    """
    
    # Common nanomaterials
    NANOMATERIALS = [
        'graphene', 'graphene oxide', 'reduced graphene oxide',
        'carbon nanotube', 'CNT', 'MWCNT', 'SWCNT',
        'gold nanoparticle', 'AuNP', 'silver nanoparticle', 'AgNP',
        'platinum nanoparticle', 'PtNP',
        'MnO2', 'manganese oxide', 'RuO2', 'ruthenium oxide',
        'TiO2', 'titanium oxide', 'ZnO', 'zinc oxide',
        'PANI', 'polyaniline', 'PPy', 'polypyrrole',
        'PEDOT', 'prussian blue', 'chitosan'
    ]
    
    # Electrode types
    ELECTRODE_TYPES = [
        'screen printed electrode', 'SPE',
        'glassy carbon electrode', 'GCE',
        'gold electrode', 'platinum electrode',
        'carbon paste electrode', 'CPE',
        'indium tin oxide', 'ITO'
    ]
    
    # Synthesis methods
    SYNTHESIS_METHODS = [
        'hydrothermal', 'solvothermal', 'sol-gel',
        'electrodeposition', 'chemical vapor deposition', 'CVD',
        'drop-casting', 'spin coating', 'dip coating',
        'chemical reduction', 'thermal reduction',
        'electrochemical synthesis', 'polymerization'
    ]
    
    # Target analytes
    ANALYTES = {
        'blood': ['glucose', 'lactate', 'cholesterol', 'uric acid', 
                  'ascorbic acid', 'dopamine', 'hemoglobin'],
        'water': ['lead', 'cadmium', 'mercury', 'arsenic', 'copper',
                  'zinc', 'chromium', 'nitrate', 'phosphate'],
        'food': ['pesticide', 'mycotoxin', 'aflatoxin', 'melamine',
                 'antibiotic', 'heavy metal']
    }
    
    def __init__(self):
        """Initialize data extractor"""
        logger.info("Data extractor initialized")
    
    def extract_from_paper(self, paper: Dict) -> ExtractedData:
        """
        Extract data from a paper
        
        Args:
            paper: Paper metadata dict
        
        Returns:
            ExtractedData object
        """
        # Combine title and abstract for text analysis
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
        text_lower = text.lower()
        
        # Extract components
        material = self.extract_material(text_lower)
        electrode = self.extract_electrode(text_lower)
        synthesis = self.extract_synthesis(text_lower)
        performance = self.extract_performance(text_lower)
        target_analyte = self.extract_analyte(text_lower)
        sample_type = self.extract_sample_type(text_lower)
        application = self.extract_application(text_lower)
        
        # Calculate confidence
        confidence = self.calculate_confidence(
            material, electrode, synthesis, performance, target_analyte
        )
        
        extracted = ExtractedData(
            paper_id=paper.get('doi') or paper.get('pmid') or paper.get('arxiv_id'),
            paper_doi=paper.get('doi'),
            material=material,
            electrode=electrode,
            synthesis=synthesis,
            performance=performance,
            target_analyte=target_analyte,
            sample_type=sample_type,
            application=application,
            raw_text=text[:1000],  # First 1000 chars
            extraction_confidence=confidence
        )
        
        return extracted
    
    def extract_material(self, text: str) -> Optional[MaterialInfo]:
        """Extract material information"""
        # Look for nanomaterials
        for material in self.NANOMATERIALS:
            if material.lower() in text:
                # Try to extract size
                size = self.extract_size(text, material)
                
                # Determine type
                mat_type = self.determine_material_type(material)
                
                return MaterialInfo(
                    name=material,
                    type=mat_type,
                    size_nm=size
                )
        
        return None
    
    def extract_electrode(self, text: str) -> Optional[ElectrodeInfo]:
        """Extract electrode information"""
        for electrode_type in self.ELECTRODE_TYPES:
            if electrode_type.lower() in text:
                # Extract modification
                modification = None
                for material in self.NANOMATERIALS:
                    if material.lower() in text:
                        modification = material
                        break
                
                return ElectrodeInfo(
                    type=electrode_type,
                    material='carbon' if 'carbon' in electrode_type else 'unknown',
                    modification=modification
                )
        
        return None
    
    def extract_synthesis(self, text: str) -> Optional[SynthesisInfo]:
        """Extract synthesis method"""
        for method in self.SYNTHESIS_METHODS:
            if method.lower() in text:
                # Try to extract temperature
                temp = self.extract_temperature(text)
                
                # Try to extract time
                time_h = self.extract_time(text)
                
                return SynthesisInfo(
                    method=method,
                    temperature_c=temp,
                    time_hours=time_h
                )
        
        return None
    
    def extract_performance(self, text: str) -> Optional[PerformanceMetrics]:
        """Extract performance metrics"""
        metrics = PerformanceMetrics()
        
        # Extract sensitivity
        sensitivity_match = re.search(
            r'sensitivity[:\s]+([0-9.]+)\s*(μA|uA|µA)/(μM|uM|µM|mM)',
            text, re.IGNORECASE
        )
        if sensitivity_match:
            metrics.sensitivity = float(sensitivity_match.group(1))
            metrics.sensitivity_unit = f"{sensitivity_match.group(2)}/{sensitivity_match.group(3)}"
        
        # Extract detection limit
        lod_match = re.search(
            r'(detection limit|LOD|limit of detection)[:\s]+([0-9.]+)\s*(nM|μM|uM|µM|mM|ppb)',
            text, re.IGNORECASE
        )
        if lod_match:
            metrics.detection_limit = float(lod_match.group(2))
            metrics.detection_limit_unit = lod_match.group(3)
        
        # Extract linear range
        range_match = re.search(
            r'linear range[:\s]+([0-9.]+)\s*[-–to]+\s*([0-9.]+)\s*(μM|uM|µM|mM)',
            text, re.IGNORECASE
        )
        if range_match:
            metrics.linear_range_min = float(range_match.group(1))
            metrics.linear_range_max = float(range_match.group(2))
            metrics.linear_range_unit = range_match.group(3)
        
        # Return None if no metrics found
        if not any([metrics.sensitivity, metrics.detection_limit, 
                    metrics.linear_range_min]):
            return None
        
        return metrics
    
    def extract_analyte(self, text: str) -> Optional[str]:
        """Extract target analyte"""
        for sample_type, analytes in self.ANALYTES.items():
            for analyte in analytes:
                if analyte.lower() in text:
                    return analyte
        return None
    
    def extract_sample_type(self, text: str) -> Optional[str]:
        """Extract sample type"""
        if any(word in text for word in ['blood', 'serum', 'plasma']):
            return 'blood'
        elif any(word in text for word in ['water', 'aqueous', 'wastewater']):
            return 'water'
        elif any(word in text for word in ['food', 'milk', 'juice', 'beverage']):
            return 'food'
        return None
    
    def extract_application(self, text: str) -> Optional[str]:
        """Extract application type"""
        if 'biosensor' in text or 'sensor' in text:
            return 'biosensor'
        elif 'supercapacitor' in text or 'capacitor' in text:
            return 'supercapacitor'
        elif 'battery' in text or 'lithium' in text:
            return 'battery'
        return None
    
    def extract_size(self, text: str, material: str) -> Optional[float]:
        """Extract nanoparticle size"""
        # Look for size near material mention
        pattern = rf'{material}.*?([0-9.]+)\s*nm'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None
    
    def extract_temperature(self, text: str) -> Optional[float]:
        """Extract synthesis temperature"""
        match = re.search(r'([0-9.]+)\s*[°◦]?C', text)
        if match:
            temp = float(match.group(1))
            if 0 < temp < 1000:  # Reasonable range
                return temp
        return None
    
    def extract_time(self, text: str) -> Optional[float]:
        """Extract synthesis time"""
        # Look for hours
        match = re.search(r'([0-9.]+)\s*h(our)?s?', text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        # Look for minutes (convert to hours)
        match = re.search(r'([0-9.]+)\s*min(ute)?s?', text, re.IGNORECASE)
        if match:
            return float(match.group(1)) / 60.0
        
        return None
    
    def determine_material_type(self, material: str) -> str:
        """Determine material type category"""
        material_lower = material.lower()
        
        if 'graphene' in material_lower:
            return 'carbon nanomaterial'
        elif 'cnt' in material_lower or 'nanotube' in material_lower:
            return 'carbon nanomaterial'
        elif 'gold' in material_lower or 'aunp' in material_lower:
            return 'metal nanoparticle'
        elif 'silver' in material_lower or 'agnp' in material_lower:
            return 'metal nanoparticle'
        elif 'oxide' in material_lower or 'mno2' in material_lower or 'ruo2' in material_lower:
            return 'metal oxide'
        elif 'pani' in material_lower or 'ppy' in material_lower or 'pedot' in material_lower:
            return 'conducting polymer'
        else:
            return 'other'
    
    def calculate_confidence(self, material, electrode, synthesis, 
                           performance, analyte) -> float:
        """Calculate extraction confidence score"""
        score = 0.0
        
        if material:
            score += 0.3
        if electrode:
            score += 0.2
        if synthesis:
            score += 0.1
        if performance:
            score += 0.3
        if analyte:
            score += 0.1
        
        return score
    
    def extract_batch(self, papers: List[Dict], 
                     output_dir: Path) -> List[ExtractedData]:
        """
        Extract data from multiple papers
        
        Args:
            papers: List of paper dicts
            output_dir: Directory to save extracted data
        
        Returns:
            List of ExtractedData objects
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        extracted_data = []
        
        logger.info(f"Extracting data from {len(papers)} papers...")
        
        for i, paper in enumerate(papers, 1):
            try:
                # Extract data
                data = self.extract_from_paper(paper)
                extracted_data.append(data)
                
                # Save to file
                filename = f"{data.paper_id or f'paper_{i}'}.json"
                filename = filename.replace('/', '_').replace('\\', '_')
                filepath = output_dir / filename
                
                with open(filepath, 'w') as f:
                    json.dump(asdict(data), f, indent=2)
                
                if i % 10 == 0:
                    logger.info(f"Processed {i}/{len(papers)} papers")
            
            except Exception as e:
                logger.error(f"Failed to extract from paper {i}: {e}")
                continue
        
        logger.info(f"Extraction complete: {len(extracted_data)} papers processed")
        
        # Generate summary
        self.generate_summary(extracted_data, output_dir)
        
        return extracted_data
    
    def generate_summary(self, extracted_data: List[ExtractedData], 
                        output_dir: Path):
        """Generate extraction summary"""
        summary = {
            'total_papers': len(extracted_data),
            'with_material': sum(1 for d in extracted_data if d.material),
            'with_electrode': sum(1 for d in extracted_data if d.electrode),
            'with_synthesis': sum(1 for d in extracted_data if d.synthesis),
            'with_performance': sum(1 for d in extracted_data if d.performance),
            'with_analyte': sum(1 for d in extracted_data if d.target_analyte),
            'avg_confidence': sum(d.extraction_confidence for d in extracted_data) / len(extracted_data) if extracted_data else 0,
            'by_application': {},
            'by_sample_type': {},
            'by_analyte': {}
        }
        
        # Count by application
        for data in extracted_data:
            if data.application:
                summary['by_application'][data.application] = \
                    summary['by_application'].get(data.application, 0) + 1
            if data.sample_type:
                summary['by_sample_type'][data.sample_type] = \
                    summary['by_sample_type'].get(data.sample_type, 0) + 1
            if data.target_analyte:
                summary['by_analyte'][data.target_analyte] = \
                    summary['by_analyte'].get(data.target_analyte, 0) + 1
        
        # Save summary
        summary_file = output_dir / 'extraction_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Summary saved to {summary_file}")
        logger.info(f"Average confidence: {summary['avg_confidence']:.2f}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Data Extraction Engine')
    parser.add_argument('--input', type=str, required=True,
                        help='Input directory with mined papers')
    parser.add_argument('--output', type=str, required=True,
                        help='Output directory for extracted data')
    
    args = parser.parse_args()
    
    # Load papers
    input_dir = Path(args.input)
    papers = []
    
    for paper_file in input_dir.rglob('*.json'):
        if paper_file.name != 'mining_state.json':
            with open(paper_file, 'r', encoding='utf-8') as f:
                papers.append(json.load(f))
    
    logger.info(f"Loaded {len(papers)} papers from {input_dir}")
    
    # Extract data
    extractor = DataExtractor()
    extracted = extractor.extract_batch(papers, Path(args.output))
    
    logger.info(f"Extraction complete: {len(extracted)} papers processed")


if __name__ == "__main__":
    main()
