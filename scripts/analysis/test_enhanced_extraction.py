#!/usr/bin/env python3
"""
Test Enhanced Data Extraction System
Tests PDF parsing, table extraction, and integration
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'backend' / 'ml' / 'autonomous_research'))

from enhanced_data_extractor import EnhancedDataExtractor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_single_paper():
    """Test extraction on a single paper"""
    logger.info("=" * 60)
    logger.info("TEST 1: Single Paper Extraction")
    logger.info("=" * 60)
    
    # Sample paper with PDF URL
    paper = {
        'doi': '10.3390/s20216013',
        'pmid': '33114446',
        'title': 'A Critical Review of Electrochemical Glucose Sensing: Evolution of Biosensor Platforms Based on Advanced Nanosystems',
        'abstract': 'Diabetes mellitus is a chronic disease that has become a major global health concern...',
        'pdf_url': 'https://www.mdpi.com/1424-8220/20/21/6013/pdf',
        'journal': 'Sensors',
        'publication_date': '2020-10-23'
    }
    
    # Initialize extractor
    extractor = EnhancedDataExtractor(cache_dir='data/pdf_cache')
    
    # Extract data
    result = extractor.extract_from_paper(paper)
    
    # Print results
    logger.info("\n" + "=" * 60)
    logger.info("EXTRACTION RESULTS")
    logger.info("=" * 60)
    logger.info(f"Paper ID: {result.paper_id}")
    logger.info(f"Overall Confidence: {result.extraction_confidence:.2f}")
    logger.info(f"\nExtraction Methods Used: {', '.join(result.extraction_methods)}")
    logger.info(f"\nConfidence Breakdown:")
    for method, conf in result.confidence_breakdown.items():
        logger.info(f"  {method}: {conf:.2f}")
    
    logger.info(f"\nPDF Extraction:")
    logger.info(f"  Full text available: {result.full_text_available}")
    logger.info(f"  Page count: {result.page_count}")
    logger.info(f"  Sections found: {', '.join(result.sections_found)}")
    
    logger.info(f"\nTable Extraction:")
    logger.info(f"  Tables found: {result.tables_found}")
    logger.info(f"  Performance from tables: {result.performance_from_tables}")
    
    logger.info(f"\nExtracted Data:")
    logger.info(f"  Material: {result.material.name if result.material else 'None'}")
    logger.info(f"  Electrode: {result.electrode.type if result.electrode else 'None'}")
    logger.info(f"  Target analyte: {result.target_analyte or 'None'}")
    logger.info(f"  Application: {result.application or 'None'}")
    
    if result.performance:
        logger.info(f"\nPerformance Metrics:")
        if result.performance.sensitivity:
            logger.info(f"  Sensitivity: {result.performance.sensitivity} {result.performance.sensitivity_unit or ''}")
        if result.performance.detection_limit:
            logger.info(f"  Detection limit: {result.performance.detection_limit} {result.performance.detection_limit_unit or ''}")
        if result.performance.linear_range_min:
            logger.info(f"  Linear range: {result.performance.linear_range_min}-{result.performance.linear_range_max} {result.performance.linear_range_unit or ''}")
    
    logger.info("=" * 60)
    
    return result


def test_batch_extraction():
    """Test batch extraction on existing mined papers"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Batch Extraction")
    logger.info("=" * 60)
    
    # Check if mined papers exist
    mined_dir = Path('data/mined_papers/biosensor_blood')
    if not mined_dir.exists():
        logger.warning("No mined papers found. Run literature miner first.")
        logger.info("Skipping batch extraction test.")
        return None
    
    # Load papers
    papers = []
    for paper_file in mined_dir.glob('*.json'):
        if paper_file.name != 'mining_state.json':
            with open(paper_file, 'r', encoding='utf-8') as f:
                papers.append(json.load(f))
    
    if not papers:
        logger.warning("No papers found in mined directory.")
        return None
    
    logger.info(f"Found {len(papers)} papers")
    
    # Limit to first 5 for testing
    papers = papers[:5]
    logger.info(f"Testing with first {len(papers)} papers")
    
    # Initialize extractor
    extractor = EnhancedDataExtractor(cache_dir='data/pdf_cache')
    
    # Extract data
    output_dir = Path('data/enhanced_extracted_data/test')
    results = extractor.extract_batch(papers, output_dir)
    
    logger.info(f"\n✅ Batch extraction complete: {len(results)} papers processed")
    logger.info(f"Results saved to: {output_dir}")
    
    return results


def test_comparison():
    """Compare basic vs enhanced extraction"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Basic vs Enhanced Comparison")
    logger.info("=" * 60)
    
    # Check if both extractions exist
    basic_dir = Path('data/extracted_data/biosensor_blood')
    enhanced_dir = Path('data/enhanced_extracted_data/test')
    
    if not basic_dir.exists():
        logger.warning("Basic extraction results not found.")
        logger.info("Skipping comparison test.")
        return
    
    if not enhanced_dir.exists():
        logger.warning("Enhanced extraction results not found.")
        logger.info("Run test_batch_extraction first.")
        return
    
    # Load summaries
    basic_summary_file = basic_dir / 'extraction_summary.json'
    enhanced_summary_file = enhanced_dir / 'enhanced_extraction_summary.json'
    
    if not basic_summary_file.exists() or not enhanced_summary_file.exists():
        logger.warning("Summary files not found.")
        return
    
    with open(basic_summary_file, 'r') as f:
        basic_summary = json.load(f)
    
    with open(enhanced_summary_file, 'r') as f:
        enhanced_summary = json.load(f)
    
    # Compare
    logger.info("\nComparison:")
    logger.info(f"{'Metric':<30} {'Basic':<15} {'Enhanced':<15} {'Improvement':<15}")
    logger.info("-" * 75)
    
    metrics = [
        ('Material extraction', 'with_material'),
        ('Electrode extraction', 'with_electrode'),
        ('Performance extraction', 'with_performance'),
        ('Analyte extraction', 'with_analyte'),
        ('Average confidence', 'avg_confidence')
    ]
    
    for metric_name, key in metrics:
        basic_val = basic_summary.get(key, 0)
        enhanced_val = enhanced_summary.get(key, 0)
        
        if key == 'avg_confidence':
            basic_pct = basic_val * 100
            enhanced_pct = enhanced_val * 100
            improvement = enhanced_pct - basic_pct
            logger.info(f"{metric_name:<30} {basic_pct:>6.1f}%{'':<8} {enhanced_pct:>6.1f}%{'':<8} {improvement:>+6.1f}%")
        else:
            total = basic_summary.get('total_papers', 1)
            basic_pct = (basic_val / total) * 100
            enhanced_pct = (enhanced_val / total) * 100
            improvement = enhanced_pct - basic_pct
            logger.info(f"{metric_name:<30} {basic_pct:>6.1f}%{'':<8} {enhanced_pct:>6.1f}%{'':<8} {improvement:>+6.1f}%")
    
    logger.info("-" * 75)
    
    # Additional enhanced features
    logger.info("\nEnhanced Features:")
    logger.info(f"  Full text extraction: {enhanced_summary.get('with_full_text', 0)}/{enhanced_summary.get('total_papers', 0)} papers")
    logger.info(f"  Table extraction: {enhanced_summary.get('with_tables', 0)}/{enhanced_summary.get('total_papers', 0)} papers")
    logger.info(f"  Performance from tables: {enhanced_summary.get('performance_from_tables', 0)}/{enhanced_summary.get('total_papers', 0)} papers")


def main():
    """Run all tests"""
    logger.info("🧪 Testing Enhanced Data Extraction System")
    logger.info("=" * 60)
    
    try:
        # Test 1: Single paper
        result1 = test_single_paper()
        
        # Test 2: Batch extraction
        result2 = test_batch_extraction()
        
        # Test 3: Comparison
        test_comparison()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS COMPLETE")
        logger.info("=" * 60)
        
        logger.info("\nNext Steps:")
        logger.info("1. Install dependencies: pip install -r requirements_extraction.txt")
        logger.info("2. Run enhanced extraction on all papers:")
        logger.info("   python src/backend/ml/autonomous_research/enhanced_data_extractor.py \\")
        logger.info("       --input data/mined_papers/biosensor_blood \\")
        logger.info("       --output data/enhanced_extracted_data/biosensor_blood")
        logger.info("3. Compare results with basic extraction")
        logger.info("4. Proceed to Phase 3: Figure Digitization")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
