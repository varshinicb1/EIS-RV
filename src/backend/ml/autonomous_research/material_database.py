#!/usr/bin/env python3
"""
Material Database
Stores and queries extracted material knowledge

Database: MongoDB for structured data + Neo4j for knowledge graph
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MaterialDatabase:
    """
    Material database for storing and querying extracted knowledge
    
    Uses in-memory storage for now (can be upgraded to MongoDB later)
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize material database
        
        Args:
            db_path: Path to database directory
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory collections
        self.materials = []
        self.electrodes = []
        self.biosensor_performance = []
        self.supercapacitor_performance = []
        self.battery_performance = []
        self.papers = []
        
        # Load existing data
        self.load_database()
        
        logger.info(f"Material database initialized at {db_path}")
        logger.info(f"Loaded: {len(self.materials)} materials, {len(self.papers)} papers")
    
    def load_database(self):
        """Load database from disk"""
        # Load materials
        materials_file = self.db_path / 'materials.json'
        if materials_file.exists():
            with open(materials_file, 'r') as f:
                self.materials = json.load(f)
        
        # Load electrodes
        electrodes_file = self.db_path / 'electrodes.json'
        if electrodes_file.exists():
            with open(electrodes_file, 'r') as f:
                self.electrodes = json.load(f)
        
        # Load biosensor performance
        biosensor_file = self.db_path / 'biosensor_performance.json'
        if biosensor_file.exists():
            with open(biosensor_file, 'r') as f:
                self.biosensor_performance = json.load(f)
        
        # Load papers
        papers_file = self.db_path / 'papers.json'
        if papers_file.exists():
            with open(papers_file, 'r') as f:
                self.papers = json.load(f)
    
    def save_database(self):
        """Save database to disk"""
        # Save materials
        with open(self.db_path / 'materials.json', 'w') as f:
            json.dump(self.materials, f, indent=2)
        
        # Save electrodes
        with open(self.db_path / 'electrodes.json', 'w') as f:
            json.dump(self.electrodes, f, indent=2)
        
        # Save biosensor performance
        with open(self.db_path / 'biosensor_performance.json', 'w') as f:
            json.dump(self.biosensor_performance, f, indent=2)
        
        # Save papers
        with open(self.db_path / 'papers.json', 'w') as f:
            json.dump(self.papers, f, indent=2)
        
        logger.info("Database saved to disk")
    
    def ingest_extracted_data(self, extracted_data_dir: Path):
        """
        Ingest extracted data into database
        
        Args:
            extracted_data_dir: Directory with extracted data files
        """
        extracted_data_dir = Path(extracted_data_dir)
        
        logger.info(f"Ingesting data from {extracted_data_dir}")
        
        count = 0
        for data_file in extracted_data_dir.rglob('*.json'):
            if data_file.name == 'extraction_summary.json':
                continue
            
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Add to database
                self.add_extracted_data(data)
                count += 1
                
                if count % 10 == 0:
                    logger.info(f"Ingested {count} papers")
            
            except Exception as e:
                logger.error(f"Failed to ingest {data_file}: {e}")
                continue
        
        logger.info(f"Ingestion complete: {count} papers added")
        
        # Save database
        self.save_database()
        
        # Generate statistics
        self.print_statistics()
    
    def add_extracted_data(self, data: Dict):
        """Add extracted data to database"""
        # Add paper
        paper_entry = {
            'paper_id': data['paper_id'],
            'paper_doi': data['paper_doi'],
            'application': data['application'],
            'target_analyte': data['target_analyte'],
            'sample_type': data['sample_type'],
            'extraction_confidence': data['extraction_confidence'],
            'added_date': datetime.now().isoformat()
        }
        self.papers.append(paper_entry)
        
        # Add material
        if data['material']:
            material_entry = {
                'material_id': self.generate_id('material'),
                'name': data['material']['name'],
                'type': data['material']['type'],
                'formula': data['material'].get('formula'),
                'morphology': data['material'].get('morphology'),
                'size_nm': data['material'].get('size_nm'),
                'paper_id': data['paper_id'],
                'added_date': datetime.now().isoformat()
            }
            self.materials.append(material_entry)
        
        # Add electrode
        if data['electrode']:
            electrode_entry = {
                'electrode_id': self.generate_id('electrode'),
                'type': data['electrode']['type'],
                'material': data['electrode']['material'],
                'modification': data['electrode'].get('modification'),
                'area_cm2': data['electrode'].get('area_cm2'),
                'paper_id': data['paper_id'],
                'added_date': datetime.now().isoformat()
            }
            self.electrodes.append(electrode_entry)
        
        # Add biosensor performance
        if data['application'] == 'biosensor' and data['performance']:
            perf = data['performance']
            perf_entry = {
                'performance_id': self.generate_id('performance'),
                'paper_id': data['paper_id'],
                'material_name': data['material']['name'] if data['material'] else None,
                'electrode_type': data['electrode']['type'] if data['electrode'] else None,
                'target_analyte': data['target_analyte'],
                'sample_type': data['sample_type'],
                'sensitivity': perf.get('sensitivity'),
                'sensitivity_unit': perf.get('sensitivity_unit'),
                'detection_limit': perf.get('detection_limit'),
                'detection_limit_unit': perf.get('detection_limit_unit'),
                'linear_range_min': perf.get('linear_range_min'),
                'linear_range_max': perf.get('linear_range_max'),
                'linear_range_unit': perf.get('linear_range_unit'),
                'added_date': datetime.now().isoformat()
            }
            self.biosensor_performance.append(perf_entry)
    
    def generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"{prefix}_{timestamp}"
    
    def query_materials(self, **filters) -> List[Dict]:
        """
        Query materials
        
        Args:
            **filters: Filter criteria (name, type, etc.)
        
        Returns:
            List of matching materials
        """
        results = self.materials
        
        for key, value in filters.items():
            if value:
                results = [m for m in results if m.get(key) == value]
        
        return results
    
    def query_electrodes(self, **filters) -> List[Dict]:
        """Query electrodes"""
        results = self.electrodes
        
        for key, value in filters.items():
            if value:
                results = [e for e in results if e.get(key) == value]
        
        return results
    
    def query_biosensor_performance(self, **filters) -> List[Dict]:
        """Query biosensor performance"""
        results = self.biosensor_performance
        
        for key, value in filters.items():
            if value:
                results = [p for p in results if p.get(key) == value]
        
        return results
    
    def recommend_material_for_analyte(self, analyte: str, 
                                      sample_type: Optional[str] = None) -> List[Dict]:
        """
        Recommend best materials for detecting specific analyte
        
        Args:
            analyte: Target analyte (e.g., 'glucose')
            sample_type: Sample type (e.g., 'blood')
        
        Returns:
            List of recommended materials with performance data
        """
        # Query performance data
        filters = {'target_analyte': analyte}
        if sample_type:
            filters['sample_type'] = sample_type
        
        performance_data = self.query_biosensor_performance(**filters)
        
        # Group by material
        by_material = {}
        for perf in performance_data:
            material = perf['material_name']
            if material:
                if material not in by_material:
                    by_material[material] = []
                by_material[material].append(perf)
        
        # Rank materials
        recommendations = []
        for material, perfs in by_material.items():
            # Calculate average performance
            avg_sensitivity = sum(p['sensitivity'] for p in perfs if p['sensitivity']) / len(perfs) if perfs else 0
            avg_lod = sum(p['detection_limit'] for p in perfs if p['detection_limit']) / len(perfs) if perfs else 0
            
            recommendations.append({
                'material': material,
                'num_papers': len(perfs),
                'avg_sensitivity': avg_sensitivity,
                'avg_detection_limit': avg_lod,
                'papers': [p['paper_id'] for p in perfs]
            })
        
        # Sort by number of papers (more papers = more proven)
        recommendations.sort(key=lambda x: x['num_papers'], reverse=True)
        
        return recommendations
    
    def get_electrode_statistics(self) -> Dict:
        """Get electrode usage statistics"""
        from collections import Counter
        
        electrode_types = [e['type'] for e in self.electrodes]
        modifications = [e['modification'] for e in self.electrodes if e['modification']]
        
        return {
            'total_electrodes': len(self.electrodes),
            'by_type': dict(Counter(electrode_types)),
            'by_modification': dict(Counter(modifications)),
            'most_common_type': Counter(electrode_types).most_common(1)[0] if electrode_types else None,
            'most_common_modification': Counter(modifications).most_common(1)[0] if modifications else None
        }
    
    def get_material_statistics(self) -> Dict:
        """Get material statistics"""
        from collections import Counter
        
        material_types = [m['type'] for m in self.materials if m['type']]
        material_names = [m['name'] for m in self.materials]
        
        return {
            'total_materials': len(self.materials),
            'by_type': dict(Counter(material_types)),
            'by_name': dict(Counter(material_names)),
            'most_common_type': Counter(material_types).most_common(1)[0] if material_types else None,
            'most_common_material': Counter(material_names).most_common(1)[0] if material_names else None
        }
    
    def get_analyte_statistics(self) -> Dict:
        """Get analyte statistics"""
        from collections import Counter
        
        analytes = [p['target_analyte'] for p in self.papers if p['target_analyte']]
        sample_types = [p['sample_type'] for p in self.papers if p['sample_type']]
        
        return {
            'total_analytes': len(set(analytes)),
            'by_analyte': dict(Counter(analytes)),
            'by_sample_type': dict(Counter(sample_types)),
            'most_common_analyte': Counter(analytes).most_common(1)[0] if analytes else None
        }
    
    def print_statistics(self):
        """Print database statistics"""
        print('\n' + '='*80)
        print('MATERIAL DATABASE STATISTICS')
        print('='*80)
        
        print(f'\nTotal entries:')
        print(f'  Papers: {len(self.papers)}')
        print(f'  Materials: {len(self.materials)}')
        print(f'  Electrodes: {len(self.electrodes)}')
        print(f'  Biosensor performance: {len(self.biosensor_performance)}')
        
        # Material statistics
        mat_stats = self.get_material_statistics()
        print(f'\nMaterial statistics:')
        print(f'  Total unique materials: {mat_stats["total_materials"]}')
        if mat_stats['most_common_material']:
            print(f'  Most common: {mat_stats["most_common_material"][0]} ({mat_stats["most_common_material"][1]} papers)')
        print(f'  By type:')
        for mat_type, count in sorted(mat_stats['by_type'].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f'    {mat_type}: {count}')
        
        # Electrode statistics
        elec_stats = self.get_electrode_statistics()
        print(f'\nElectrode statistics:')
        print(f'  Total electrodes: {elec_stats["total_electrodes"]}')
        if elec_stats['most_common_type']:
            print(f'  Most common: {elec_stats["most_common_type"][0]} ({elec_stats["most_common_type"][1]} papers)')
        print(f'  By type:')
        for elec_type, count in sorted(elec_stats['by_type'].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f'    {elec_type}: {count}')
        
        # Analyte statistics
        analyte_stats = self.get_analyte_statistics()
        print(f'\nAnalyte statistics:')
        print(f'  Total unique analytes: {analyte_stats["total_analytes"]}')
        if analyte_stats['most_common_analyte']:
            print(f'  Most common: {analyte_stats["most_common_analyte"][0]} ({analyte_stats["most_common_analyte"][1]} papers)')
        print(f'  By analyte:')
        for analyte, count in sorted(analyte_stats['by_analyte'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f'    {analyte}: {count}')
        
        print('\n' + '='*80)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Material Database')
    parser.add_argument('--build', action='store_true',
                        help='Build database from extracted data')
    parser.add_argument('--input', type=str,
                        help='Input directory with extracted data')
    parser.add_argument('--db', type=str, default='data/material_database',
                        help='Database directory')
    parser.add_argument('--query', type=str,
                        help='Query materials (e.g., "glucose biosensor")')
    parser.add_argument('--recommend', type=str,
                        help='Recommend material for analyte')
    parser.add_argument('--stats', action='store_true',
                        help='Show database statistics')
    
    args = parser.parse_args()
    
    # Initialize database
    db = MaterialDatabase(Path(args.db))
    
    if args.build:
        if not args.input:
            logger.error("--input required for --build")
            return
        
        logger.info(f"Building database from {args.input}")
        db.ingest_extracted_data(Path(args.input))
    
    elif args.query:
        logger.info(f"Querying: {args.query}")
        # Simple query implementation
        materials = db.query_materials()
        print(f"\nFound {len(materials)} materials")
        for mat in materials[:10]:
            print(f"  - {mat['name']} ({mat['type']})")
    
    elif args.recommend:
        logger.info(f"Recommending materials for: {args.recommend}")
        recommendations = db.recommend_material_for_analyte(args.recommend)
        
        print(f"\nTop materials for {args.recommend} detection:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"\n{i}. {rec['material']}")
            print(f"   Papers: {rec['num_papers']}")
            if rec['avg_sensitivity']:
                print(f"   Avg sensitivity: {rec['avg_sensitivity']:.2f}")
            if rec['avg_detection_limit']:
                print(f"   Avg LOD: {rec['avg_detection_limit']:.2f}")
    
    elif args.stats:
        db.print_statistics()
    
    else:
        logger.info("Use --build, --query, --recommend, or --stats")
        db.print_statistics()


if __name__ == "__main__":
    main()
