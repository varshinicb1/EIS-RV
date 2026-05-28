#!/usr/bin/env python3
"""
Parse EBIO Electrochemistry Dataset
====================================
Parses 3,848 .mpr/.mpt Biologic files from the EBIO dataset into structured
training data for ML models.

Dataset: Raw data Electrochemistry_Talal WP2 Part 1
Source: EU EBIO Project - Zenodo
License: CC BY 4.0

Techniques identified:
- CV (Cyclic Voltammetry): ~1,308 files
- CI (Chronoamperometry): ~449 files
- CP (Chronopotentiometry): ~200 files
- PEIS/EIS/GEIS (Impedance): ~208 files
- CA (Chronoamperometry): ~53 files
- LSV (Linear Sweep Voltammetry): ~11 files
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np
from tqdm import tqdm

try:
    from galvani import BioLogic
except ImportError:
    print("ERROR: galvani not installed. Run: pip install galvani")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
EBIO_RAW_DIR = BASE_DIR / "External datasets" / "14902951" / "Raw data Electrochemistry_Talal WP2 Part 1" / "Raw data eChem"
OUTPUT_DIR = BASE_DIR / "data" / "ml_datasets" / "processed" / "ebio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class EBIOMeasurement:
    """Structured electrochemistry measurement from EBIO dataset"""
    file_id: str
    technique: str
    filename: str
    folder: str
    
    # Time series data
    time: List[float]  # seconds
    voltage: List[float]  # V
    current: List[float]  # A or mA
    
    # Metadata
    num_points: int
    duration: float  # seconds
    electrode_material: Optional[str] = None
    electrolyte: Optional[str] = None
    current_density: Optional[float] = None  # mA/cm²
    ph: Optional[float] = None
    temperature: Optional[float] = None
    
    # Additional fields from file
    metadata: Optional[Dict] = None
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        d = asdict(self)
        # Convert numpy arrays to lists if present
        for key in ['time', 'voltage', 'current']:
            if isinstance(d[key], np.ndarray):
                d[key] = d[key].tolist()
        return d


class EBIOParser:
    """Parser for EBIO electrochemistry dataset"""
    
    # Technique identification patterns
    TECHNIQUE_PATTERNS = {
        'CV': [r'_CV_', r'^CV', r'cyclic', r'voltammetry'],
        'EIS': [r'_EIS_', r'_PEIS_', r'_GEIS_', r'_ZIR_', r'impedance'],
        'CA': [r'_CA_', r'^CA', r'chronoamperometry'],
        'CP': [r'_CP_', r'^CP', r'chronopotentiometry'],
        'CI': [r'_CI_', r'^CI'],  # Chronoamperometry variant
        'LSV': [r'_LSV_', r'^LSV', r'linear.*sweep'],
        'OCV': [r'_OCV_', r'open.*circuit'],
        'GCPL': [r'_GCPL_', r'galvanostatic'],
        'MB': [r'_MB_', r'modulo.*bat'],
        'LOOP': [r'_LOOP_'],
    }
    
    # Metadata extraction patterns
    ELECTRODE_PATTERNS = {
        'Pt': [r'\bPt\b', r'platinum'],
        'BDD': [r'\bBDD\b', r'diamond'],
        'Graphite': [r'graphite', r'\bG\d+\b'],
        'Ti': [r'\bTi\b', r'titanium'],
        'Ni': [r'\bNi\b', r'nickel'],
        'Au': [r'\bAu\b', r'gold'],
        'FTO': [r'\bFTO\b'],
    }
    
    ELECTROLYTE_PATTERNS = {
        'acetate': [r'acetate', r'NaAc', r'KAc', r'CaAc'],
        'KOH': [r'KOH'],
        'NaOH': [r'NaOH'],
        'LiOH': [r'LiOH'],
        'CsOH': [r'CsOH'],
        'propionate': [r'propionate', r'NaPr'],
    }
    
    def __init__(self, raw_dir: Path, output_dir: Path):
        self.raw_dir = raw_dir
        self.output_dir = output_dir
        self.stats = {
            'total_files': 0,
            'parsed_success': 0,
            'parsed_failed': 0,
            'by_technique': {},
            'by_electrode': {},
        }
    
    def identify_technique(self, filename: str, folder: str) -> str:
        """Identify electrochemical technique from filename and folder"""
        search_text = f"{filename} {folder}".lower()
        
        for technique, patterns in self.TECHNIQUE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, search_text, re.IGNORECASE):
                    return technique
        
        return 'UNKNOWN'
    
    def extract_metadata(self, filename: str, folder: str) -> Dict:
        """Extract metadata from filename and folder path"""
        metadata = {}
        search_text = f"{filename} {folder}"
        
        # Electrode material
        for material, patterns in self.ELECTRODE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, search_text, re.IGNORECASE):
                    metadata['electrode_material'] = material
                    break
            if 'electrode_material' in metadata:
                break
        
        # Electrolyte
        for electrolyte, patterns in self.ELECTROLYTE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, search_text, re.IGNORECASE):
                    metadata['electrolyte'] = electrolyte
                    break
            if 'electrolyte' in metadata:
                break
        
        # Current density (mA/cm²)
        cd_match = re.search(r'(\d+)\s*mA[/\s]*(?:cm2|sqcm)', search_text, re.IGNORECASE)
        if cd_match:
            metadata['current_density'] = float(cd_match.group(1))
        
        # pH
        ph_match = re.search(r'pH\s*(\d+(?:\.\d+)?)', search_text, re.IGNORECASE)
        if ph_match:
            metadata['ph'] = float(ph_match.group(1))
        
        return metadata
    
    def parse_mpr_file(self, filepath: Path) -> Optional[EBIOMeasurement]:
        """Parse a single .mpr file using galvani"""
        try:
            # Load file with galvani
            mpr_file = BioLogic.MPRfile(str(filepath))
            
            # Get data as structured array
            data = mpr_file.data
            
            if data is None or len(data) == 0:
                logger.warning(f"No data in file: {filepath.name}")
                return None
            
            # Extract time series
            # Common field names in Biologic files
            time = None
            voltage = None
            current = None
            
            # Try different field name variations
            time_fields = ['time/s', 'Time/s', 'time', 'Time']
            voltage_fields = ['Ewe/V', 'Voltage/V', 'voltage', 'Ewe', '<Ewe>/V']
            current_fields = ['<I>/mA', 'I/mA', 'Current/mA', 'current', '<I>/A', 'I/A']
            
            for field in time_fields:
                if field in data.dtype.names:
                    time = data[field]
                    break
            
            for field in voltage_fields:
                if field in data.dtype.names:
                    voltage = data[field]
                    break
            
            for field in current_fields:
                if field in data.dtype.names:
                    current = data[field]
                    # Convert mA to A if needed
                    if 'mA' in field:
                        current = current / 1000.0
                    break
            
            if time is None or voltage is None or current is None:
                logger.warning(f"Missing required fields in {filepath.name}. Available: {data.dtype.names}")
                return None
            
            # Identify technique
            technique = self.identify_technique(filepath.name, filepath.parent.name)
            
            # Extract metadata
            metadata = self.extract_metadata(filepath.name, str(filepath.parent))
            
            # Create measurement object
            measurement = EBIOMeasurement(
                file_id=filepath.stem,
                technique=technique,
                filename=filepath.name,
                folder=filepath.parent.name,
                time=time.tolist() if isinstance(time, np.ndarray) else list(time),
                voltage=voltage.tolist() if isinstance(voltage, np.ndarray) else list(voltage),
                current=current.tolist() if isinstance(current, np.ndarray) else list(current),
                num_points=len(time),
                duration=float(time[-1] - time[0]) if len(time) > 0 else 0.0,
                electrode_material=metadata.get('electrode_material'),
                electrolyte=metadata.get('electrolyte'),
                current_density=metadata.get('current_density'),
                ph=metadata.get('ph'),
                metadata={
                    'fields_available': list(data.dtype.names),
                    'raw_folder': str(filepath.parent.relative_to(self.raw_dir)),
                }
            )
            
            return measurement
        
        except Exception as e:
            logger.error(f"Failed to parse {filepath.name}: {e}")
            return None
    
    def parse_mpt_file(self, filepath: Path) -> Optional[EBIOMeasurement]:
        """Parse a single .mpt file (text format)"""
        try:
            # .mpt files are text-based, easier to parse
            mpt_file = BioLogic.MPTfile(str(filepath))
            data = mpt_file.data
            
            if data is None or len(data) == 0:
                logger.warning(f"No data in file: {filepath.name}")
                return None
            
            # Extract time series (same logic as .mpr)
            time = None
            voltage = None
            current = None
            
            time_fields = ['time/s', 'Time/s', 'time', 'Time']
            voltage_fields = ['Ewe/V', 'Voltage/V', 'voltage', 'Ewe', '<Ewe>/V']
            current_fields = ['<I>/mA', 'I/mA', 'Current/mA', 'current', '<I>/A', 'I/A']
            
            for field in time_fields:
                if field in data.dtype.names:
                    time = data[field]
                    break
            
            for field in voltage_fields:
                if field in data.dtype.names:
                    voltage = data[field]
                    break
            
            for field in current_fields:
                if field in data.dtype.names:
                    current = data[field]
                    if 'mA' in field:
                        current = current / 1000.0
                    break
            
            if time is None or voltage is None or current is None:
                logger.warning(f"Missing required fields in {filepath.name}")
                return None
            
            technique = self.identify_technique(filepath.name, filepath.parent.name)
            metadata = self.extract_metadata(filepath.name, str(filepath.parent))
            
            measurement = EBIOMeasurement(
                file_id=filepath.stem,
                technique=technique,
                filename=filepath.name,
                folder=filepath.parent.name,
                time=time.tolist() if isinstance(time, np.ndarray) else list(time),
                voltage=voltage.tolist() if isinstance(voltage, np.ndarray) else list(voltage),
                current=current.tolist() if isinstance(current, np.ndarray) else list(current),
                num_points=len(time),
                duration=float(time[-1] - time[0]) if len(time) > 0 else 0.0,
                electrode_material=metadata.get('electrode_material'),
                electrolyte=metadata.get('electrolyte'),
                current_density=metadata.get('current_density'),
                ph=metadata.get('ph'),
                metadata={
                    'fields_available': list(data.dtype.names),
                    'raw_folder': str(filepath.parent.relative_to(self.raw_dir)),
                }
            )
            
            return measurement
        
        except Exception as e:
            logger.error(f"Failed to parse {filepath.name}: {e}")
            return None
    
    def parse_all(self) -> Dict[str, List[EBIOMeasurement]]:
        """Parse all .mpr and .mpt files in the dataset"""
        logger.info("="*80)
        logger.info("EBIO Dataset Parser")
        logger.info("="*80)
        logger.info(f"Raw data directory: {self.raw_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        
        # Find all files
        mpr_files = list(self.raw_dir.rglob("*.mpr"))
        mpt_files = list(self.raw_dir.rglob("*.mpt"))
        all_files = mpr_files + mpt_files
        
        self.stats['total_files'] = len(all_files)
        logger.info(f"\nFound {len(mpr_files)} .mpr files and {len(mpt_files)} .mpt files")
        logger.info(f"Total: {len(all_files)} files to parse")
        
        # Parse all files
        measurements_by_technique = {}
        
        logger.info("\nParsing files...")
        for filepath in tqdm(all_files, desc="Parsing"):
            if filepath.suffix == '.mpr':
                measurement = self.parse_mpr_file(filepath)
            else:
                measurement = self.parse_mpt_file(filepath)
            
            if measurement:
                self.stats['parsed_success'] += 1
                
                # Group by technique
                technique = measurement.technique
                if technique not in measurements_by_technique:
                    measurements_by_technique[technique] = []
                measurements_by_technique[technique].append(measurement)
                
                # Update stats
                self.stats['by_technique'][technique] = self.stats['by_technique'].get(technique, 0) + 1
                if measurement.electrode_material:
                    self.stats['by_electrode'][measurement.electrode_material] = \
                        self.stats['by_electrode'].get(measurement.electrode_material, 0) + 1
            else:
                self.stats['parsed_failed'] += 1
        
        logger.info(f"\n✅ Successfully parsed: {self.stats['parsed_success']} files")
        logger.info(f"❌ Failed to parse: {self.stats['parsed_failed']} files")
        
        return measurements_by_technique
    
    def save_measurements(self, measurements_by_technique: Dict[str, List[EBIOMeasurement]]):
        """Save parsed measurements to disk"""
        logger.info("\n" + "="*80)
        logger.info("Saving Parsed Data")
        logger.info("="*80)
        
        for technique, measurements in measurements_by_technique.items():
            if not measurements:
                continue
            
            technique_dir = self.output_dir / technique.lower()
            technique_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"\n{technique}: {len(measurements)} measurements")
            
            # Save individual JSON files
            json_dir = technique_dir / "json"
            json_dir.mkdir(exist_ok=True)
            
            for i, measurement in enumerate(measurements):
                json_path = json_dir / f"{measurement.file_id}.json"
                with open(json_path, 'w') as f:
                    json.dump(measurement.to_dict(), f, indent=2)
            
            # Save combined numpy arrays for ML training
            numpy_dir = technique_dir / "numpy"
            numpy_dir.mkdir(exist_ok=True)
            
            # Stack all measurements
            all_time = []
            all_voltage = []
            all_current = []
            metadata_list = []
            
            for measurement in measurements:
                all_time.append(np.array(measurement.time))
                all_voltage.append(np.array(measurement.voltage))
                all_current.append(np.array(measurement.current))
                metadata_list.append({
                    'file_id': measurement.file_id,
                    'electrode': measurement.electrode_material,
                    'electrolyte': measurement.electrolyte,
                    'current_density': measurement.current_density,
                    'ph': measurement.ph,
                    'num_points': measurement.num_points,
                    'duration': measurement.duration,
                })
            
            # Save as numpy arrays (ragged arrays saved as object arrays)
            np.save(numpy_dir / "time.npy", np.array(all_time, dtype=object))
            np.save(numpy_dir / "voltage.npy", np.array(all_voltage, dtype=object))
            np.save(numpy_dir / "current.npy", np.array(all_current, dtype=object))
            
            # Save metadata
            with open(numpy_dir / "metadata.json", 'w') as f:
                json.dump(metadata_list, f, indent=2)
            
            logger.info(f"  ✅ Saved to {technique_dir}")
        
        # Save overall statistics
        stats_file = self.output_dir / "parsing_stats.json"
        with open(stats_file, 'w') as f:
            json.dump({
                **self.stats,
                'parsed_date': datetime.now().isoformat(),
                'raw_dir': str(self.raw_dir),
                'output_dir': str(self.output_dir),
            }, f, indent=2)
        
        logger.info(f"\n✅ Statistics saved to {stats_file}")
    
    def print_summary(self):
        """Print parsing summary"""
        logger.info("\n" + "="*80)
        logger.info("PARSING SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\nTotal files: {self.stats['total_files']}")
        logger.info(f"Successfully parsed: {self.stats['parsed_success']}")
        logger.info(f"Failed: {self.stats['parsed_failed']}")
        logger.info(f"Success rate: {100*self.stats['parsed_success']/self.stats['total_files']:.1f}%")
        
        logger.info("\nBy Technique:")
        for technique, count in sorted(self.stats['by_technique'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {technique}: {count} measurements")
        
        logger.info("\nBy Electrode Material:")
        for material, count in sorted(self.stats['by_electrode'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {material}: {count} measurements")
        
        logger.info("\n" + "="*80)
        logger.info("NEXT STEPS")
        logger.info("="*80)
        logger.info("\n1. Train CV Transformer:")
        logger.info(f"   python src/backend/ml/training/train_cv.py")
        logger.info("\n2. Train EIS Transformer:")
        logger.info(f"   python src/backend/ml/training/train_eis.py")
        logger.info("\n3. Integrate with RĀMAN Studio API")
        logger.info("\n4. Test predictions on new data")


def main():
    """Main parsing function"""
    parser = EBIOParser(EBIO_RAW_DIR, OUTPUT_DIR)
    
    # Check if raw data exists
    if not EBIO_RAW_DIR.exists():
        logger.error(f"Raw data directory not found: {EBIO_RAW_DIR}")
        logger.error("Please ensure the EBIO dataset is extracted to the correct location")
        return
    
    # Parse all files
    measurements_by_technique = parser.parse_all()
    
    # Save results
    parser.save_measurements(measurements_by_technique)
    
    # Print summary
    parser.print_summary()
    
    logger.info("\n✅ EBIO dataset parsing complete!")


if __name__ == "__main__":
    main()
