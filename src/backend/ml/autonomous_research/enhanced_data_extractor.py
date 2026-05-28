"""
Enhanced Data Extraction Engine
Integrates PDF parsing, table extraction, figure digitization, and NLP

This is the new extraction pipeline that replaces the basic data_extractor.py
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
import logging

# Import extractors
from extractors.pdf_parser import PDFParser
from extractors.table_extractor import TableExtractor
from extractors.figure_digitizer import FigureDigitizer
from extractors.nlp_extractor import NLPExtractor

# Import original data structures
import sys
sys.path.append(str(Path(__file__).parent))
from data_extractor import (
    MaterialInfo, ElectrodeInfo, SynthesisInfo, 
    PerformanceMetrics, ExtractedData, DataExtractor
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EnhancedExtractedData(ExtractedData):
    """
    Enhanced extracted data with additional fields
    """
    # PDF extraction
    full_text_available: bool = False
    sections_found: List[str] = field(default_factory=list)
    page_count: int = 0
    
    # Table extraction
    tables_found: int = 0
    performance_from_tables: bool = False
    
    # Figure extraction
    figures_found: int = 0
    curves_digitized: int = 0
    
    # Extraction methods used
    extraction_methods: List[str] = field(default_factory=list)
    
    # Enhanced confidence breakdown
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)


class EnhancedDataExtractor:
    """
    Enhanced Data Extraction Engine
    
    Extraction Pipeline:
    1. PDF Parser → Extract full text
    2. Table Extractor → Extract performance metrics
    3. Figure Digitizer → Extract measurement curves
    4. NLP Extractor → Extract materials, synthesis, properties
    5. Data Merger → Combine all extractions
    6. Validator → Quality checks
    
    Features:
    - Modular architecture (pluggable extractors)
    - Extraction priority with fallback chain
    - Confidence aggregation across methods
    - Comprehensive error handling
    """
    
    def __init__(self, cache_dir: str = "data/pdf_cache"):
        """
        Initialize enhanced data extractor
        
        Args:
            cache_dir: Directory for PDF cache
        """
        logger.info("Initializing Enhanced Data Extractor...")
        
        # Initialize extractors
        self.pdf_parser = PDFParser(cache_dir=cache_dir)
        self.table_extractor = TableExtractor(cache_dir=cache_dir)
        # self.figure_digitizer = FigureDigitizer(cache_dir=cache_dir)  # Phase 3
        # self.nlp_extractor = NLPExtractor()  # Phase 4
        
        # Fallback to basic extractor for materials/electrodes
        self.basic_extractor = DataExtractor()
        
        logger.info("✅ Enhanced Data Extractor initialized")
        logger.info("📋 Active extractors: PDF Parser, Table Extractor")
        logger.info("⏳ Coming soon: Figure Digitizer (Phase 3), NLP Extractor (Phase 4)")
    
    def extract_from_paper(self, paper: Dict) -> EnhancedExtractedData:
        """
        Extract data from a paper using all available methods
        
        Args:
            paper: Paper metadata dict
        
        Returns:
            EnhancedExtractedData object
        """
        paper_id = paper.get('doi') or paper.get('pmid') or paper.get('arxiv_id', 'unknown')
        logger.info(f"🔍 Extracting from paper: {paper_id}")
        
        # Initialize result
        extraction_methods = []
        confidence_breakdown = {}
        
        # Stage 1: PDF Parsing
        pdf_result = self.pdf_parser.extract(paper)
        full_text = ""
        sections = {}
        page_count = 0
        
        if pdf_result.success:
            extraction_methods.append('pdf_parser')
            confidence_breakdown['pdf'] = pdf_result.confidence
            full_text = pdf_result.data['full_text']
            sections = pdf_result.data['sections']
            page_count = pdf_result.data['page_count']
            logger.info(f"  ✅ PDF parsed: {len(full_text)} chars, {len(sections)} sections")
        else:
            logger.info(f"  ⚠️  PDF parsing failed, using abstract only")
            full_text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
        
        # Stage 2: Table Extraction
        table_result = self.table_extractor.extract(paper)
        tables_found = 0
        performance_from_tables = {}
        
        if table_result.success:
            extraction_methods.append('table_extractor')
            confidence_breakdown['tables'] = table_result.confidence
            tables_found = table_result.data['table_count']
            performance_from_tables = table_result.data.get('performance_metrics', {})
            logger.info(f"  ✅ Tables extracted: {tables_found} tables, {len(performance_from_tables)} metrics")
        else:
            logger.info(f"  ⚠️  Table extraction failed")
        
        # Stage 3: Basic Extraction (materials, electrodes, etc.)
        # Use full text if available, otherwise abstract
        text_for_extraction = full_text if full_text else f"{paper.get('title', '')} {paper.get('abstract', '')}"
        paper_with_text = {**paper, 'abstract': text_for_extraction}
        basic_data = self.basic_extractor.extract_from_paper(paper_with_text)
        
        extraction_methods.append('basic_extractor')
        confidence_breakdown['basic'] = basic_data.extraction_confidence
        
        # Stage 4: Merge Performance Metrics
        # Prefer table-extracted metrics over text-extracted
        final_performance = basic_data.performance
        if performance_from_tables:
            final_performance = self._merge_performance_metrics(
                basic_data.performance,
                performance_from_tables
            )
        
        # Stage 5: Calculate Overall Confidence
        overall_confidence = self._calculate_overall_confidence(
            confidence_breakdown,
            extraction_methods
        )
        
        # Create enhanced result
        enhanced_data = EnhancedExtractedData(
            paper_id=basic_data.paper_id,
            paper_doi=basic_data.paper_doi,
            material=basic_data.material,
            electrode=basic_data.electrode,
            synthesis=basic_data.synthesis,
            performance=final_performance,
            target_analyte=basic_data.target_analyte,
            sample_type=basic_data.sample_type,
            application=basic_data.application,
            raw_text=full_text[:1000] if full_text else basic_data.raw_text,
            extraction_confidence=overall_confidence,
            # Enhanced fields
            full_text_available=bool(pdf_result.success),
            sections_found=list(sections.keys()),
            page_count=page_count,
            tables_found=tables_found,
            performance_from_tables=bool(performance_from_tables),
            figures_found=0,  # Phase 3
            curves_digitized=0,  # Phase 3
            extraction_methods=extraction_methods,
            confidence_breakdown=confidence_breakdown
        )
        
        logger.info(f"  ✅ Extraction complete: confidence={overall_confidence:.2f}")
        
        return enhanced_data
    
    def _merge_performance_metrics(self, text_metrics: Optional[PerformanceMetrics],
                                   table_metrics: Dict) -> PerformanceMetrics:
        """
        Merge performance metrics from text and tables
        Prefer table metrics (more reliable)
        
        Args:
            text_metrics: Metrics from text extraction
            table_metrics: Metrics from table extraction
        
        Returns:
            Merged PerformanceMetrics
        """
        if not text_metrics:
            text_metrics = PerformanceMetrics()
        
        # Merge metrics (table takes precedence)
        merged = PerformanceMetrics(
            sensitivity=text_metrics.sensitivity,
            sensitivity_unit=text_metrics.sensitivity_unit,
            detection_limit=text_metrics.detection_limit,
            detection_limit_unit=text_metrics.detection_limit_unit,
            linear_range_min=text_metrics.linear_range_min,
            linear_range_max=text_metrics.linear_range_max,
            linear_range_unit=text_metrics.linear_range_unit,
            selectivity=text_metrics.selectivity,
            stability_days=text_metrics.stability_days,
            reproducibility_rsd=text_metrics.reproducibility_rsd,
            response_time_s=text_metrics.response_time_s
        )
        
        # Override with table metrics
        if 'sensitivity' in table_metrics:
            value, unit = table_metrics['sensitivity']
            merged.sensitivity = value
            merged.sensitivity_unit = unit
        
        if 'detection_limit' in table_metrics:
            value, unit = table_metrics['detection_limit']
            merged.detection_limit = value
            merged.detection_limit_unit = unit
        
        if 'linear_range' in table_metrics:
            min_val, max_val, unit = table_metrics['linear_range']
            merged.linear_range_min = min_val
            merged.linear_range_max = max_val
            merged.linear_range_unit = unit
        
        return merged
    
    def _calculate_overall_confidence(self, confidence_breakdown: Dict[str, float],
                                     methods: List[str]) -> float:
        """
        Calculate overall extraction confidence
        
        Args:
            confidence_breakdown: Confidence per method
            methods: Methods used
        
        Returns:
            Overall confidence score (0-1)
        """
        if not confidence_breakdown:
            return 0.0
        
        # Weighted average
        weights = {
            'pdf': 0.3,
            'tables': 0.4,  # Tables are most reliable
            'figures': 0.2,
            'nlp': 0.1,
            'basic': 0.2
        }
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for method, confidence in confidence_breakdown.items():
            weight = weights.get(method, 0.1)
            weighted_sum += confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    def extract_batch(self, papers: List[Dict], 
                     output_dir: Path) -> List[EnhancedExtractedData]:
        """
        Extract data from multiple papers
        
        Args:
            papers: List of paper dicts
            output_dir: Directory to save extracted data
        
        Returns:
            List of EnhancedExtractedData objects
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        extracted_data = []
        
        logger.info(f"🚀 Starting batch extraction: {len(papers)} papers")
        logger.info("=" * 60)
        
        for i, paper in enumerate(papers, 1):
            try:
                logger.info(f"\n📄 Paper {i}/{len(papers)}")
                
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
                    logger.info(f"\n✅ Progress: {i}/{len(papers)} papers processed")
            
            except Exception as e:
                logger.error(f"❌ Failed to extract from paper {i}: {e}")
                continue
        
        logger.info("\n" + "=" * 60)
        logger.info(f"✅ Batch extraction complete: {len(extracted_data)}/{len(papers)} papers")
        
        # Generate summary
        self.generate_summary(extracted_data, output_dir)
        
        return extracted_data
    
    def generate_summary(self, extracted_data: List[EnhancedExtractedData], 
                        output_dir: Path):
        """Generate extraction summary with enhanced metrics"""
        summary = {
            'total_papers': len(extracted_data),
            'extraction_success_rate': len(extracted_data) / len(extracted_data) if extracted_data else 0,
            
            # Basic extraction stats
            'with_material': sum(1 for d in extracted_data if d.material),
            'with_electrode': sum(1 for d in extracted_data if d.electrode),
            'with_synthesis': sum(1 for d in extracted_data if d.synthesis),
            'with_performance': sum(1 for d in extracted_data if d.performance),
            'with_analyte': sum(1 for d in extracted_data if d.target_analyte),
            
            # Enhanced extraction stats
            'with_full_text': sum(1 for d in extracted_data if d.full_text_available),
            'with_tables': sum(1 for d in extracted_data if d.tables_found > 0),
            'with_figures': sum(1 for d in extracted_data if d.figures_found > 0),
            'performance_from_tables': sum(1 for d in extracted_data if d.performance_from_tables),
            
            # Confidence stats
            'avg_confidence': sum(d.extraction_confidence for d in extracted_data) / len(extracted_data) if extracted_data else 0,
            'avg_pdf_confidence': sum(d.confidence_breakdown.get('pdf', 0) for d in extracted_data) / len(extracted_data) if extracted_data else 0,
            'avg_table_confidence': sum(d.confidence_breakdown.get('tables', 0) for d in extracted_data) / len(extracted_data) if extracted_data else 0,
            
            # Extraction methods
            'extraction_methods_used': {},
            
            # Application breakdown
            'by_application': {},
            'by_sample_type': {},
            'by_analyte': {}
        }
        
        # Count extraction methods
        for data in extracted_data:
            for method in data.extraction_methods:
                summary['extraction_methods_used'][method] = \
                    summary['extraction_methods_used'].get(method, 0) + 1
        
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
        
        # Calculate improvement over basic extraction
        summary['improvement'] = {
            'material_extraction': f"{summary['with_material']/summary['total_papers']*100:.1f}%",
            'performance_extraction': f"{summary['with_performance']/summary['total_papers']*100:.1f}%",
            'full_text_usage': f"{summary['with_full_text']/summary['total_papers']*100:.1f}%",
            'table_usage': f"{summary['with_tables']/summary['total_papers']*100:.1f}%"
        }
        
        # Save summary
        summary_file = output_dir / 'enhanced_extraction_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 EXTRACTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total papers: {summary['total_papers']}")
        logger.info(f"Average confidence: {summary['avg_confidence']:.2f}")
        logger.info(f"\nExtraction Success Rates:")
        logger.info(f"  Materials: {summary['with_material']}/{summary['total_papers']} ({summary['with_material']/summary['total_papers']*100:.1f}%)")
        logger.info(f"  Electrodes: {summary['with_electrode']}/{summary['total_papers']} ({summary['with_electrode']/summary['total_papers']*100:.1f}%)")
        logger.info(f"  Performance: {summary['with_performance']}/{summary['total_papers']} ({summary['with_performance']/summary['total_papers']*100:.1f}%)")
        logger.info(f"  Analytes: {summary['with_analyte']}/{summary['total_papers']} ({summary['with_analyte']/summary['total_papers']*100:.1f}%)")
        logger.info(f"\nEnhanced Features:")
        logger.info(f"  Full text: {summary['with_full_text']}/{summary['total_papers']} ({summary['with_full_text']/summary['total_papers']*100:.1f}%)")
        logger.info(f"  Tables: {summary['with_tables']}/{summary['total_papers']} ({summary['with_tables']/summary['total_papers']*100:.1f}%)")
        logger.info(f"  Performance from tables: {summary['performance_from_tables']}/{summary['total_papers']} ({summary['performance_from_tables']/summary['total_papers']*100:.1f}%)")
        logger.info("=" * 60)
        logger.info(f"Summary saved to {summary_file}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Data Extraction Engine')
    parser.add_argument('--input', type=str, required=True,
                        help='Input directory with mined papers')
    parser.add_argument('--output', type=str, required=True,
                        help='Output directory for extracted data')
    parser.add_argument('--cache', type=str, default='data/pdf_cache',
                        help='PDF cache directory')
    
    args = parser.parse_args()
    
    # Load papers
    input_dir = Path(args.input)
    papers = []
    
    for paper_file in input_dir.rglob('*.json'):
        if paper_file.name not in ['mining_state.json', 'extraction_summary.json', 
                                    'enhanced_extraction_summary.json']:
            with open(paper_file, 'r', encoding='utf-8') as f:
                papers.append(json.load(f))
    
    logger.info(f"📚 Loaded {len(papers)} papers from {input_dir}")
    
    # Extract data
    extractor = EnhancedDataExtractor(cache_dir=args.cache)
    extracted = extractor.extract_batch(papers, Path(args.output))
    
    logger.info(f"\n✅ Enhanced extraction complete: {len(extracted)} papers processed")


if __name__ == "__main__":
    main()
