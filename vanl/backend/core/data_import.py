"""
Data Import Module
==================
Import electrochemical data from various potentiostat formats.

Supported Formats:
- Gamry (.DTA)
- Metrohm Autolab (.txt)
- BioLogic (.mpt)
- Generic CSV (E, I, Z', Z'')
- AnalyteX native format

Author: VidyuthLabs
Date: May 1, 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class EISData:
    """Electrochemical Impedance Spectroscopy data."""
    frequencies: np.ndarray  # Hz
    Z_real: np.ndarray       # Ω (real part)
    Z_imag: np.ndarray       # Ω (imaginary part)
    Z_magnitude: np.ndarray  # |Z| in Ω
    Z_phase: np.ndarray      # Phase in degrees
    
    # Metadata
    source_file: str = ""
    format_type: str = ""
    measurement_date: str = ""
    temperature_C: Optional[float] = None
    electrode_area_cm2: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "frequencies": self.frequencies.tolist(),
            "Z_real": self.Z_real.tolist(),
            "Z_imag": self.Z_imag.tolist(),
            "Z_magnitude": self.Z_magnitude.tolist(),
            "Z_phase": self.Z_phase.tolist(),
            "n_points": len(self.frequencies),
            "freq_range": [float(self.frequencies.min()), float(self.frequencies.max())],
            "source_file": self.source_file,
            "format_type": self.format_type,
            "measurement_date": self.measurement_date,
            "temperature_C": self.temperature_C,
            "electrode_area_cm2": self.electrode_area_cm2
        }


@dataclass
class CVData:
    """Cyclic Voltammetry data."""
    potential: np.ndarray    # V
    current: np.ndarray      # A
    scan_rate: float         # V/s
    
    # Metadata
    source_file: str = ""
    format_type: str = ""
    measurement_date: str = ""
    temperature_C: Optional[float] = None
    electrode_area_cm2: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "potential": self.potential.tolist(),
            "current": self.current.tolist(),
            "scan_rate": self.scan_rate,
            "n_points": len(self.potential),
            "potential_range": [float(self.potential.min()), float(self.potential.max())],
            "current_range": [float(self.current.min()), float(self.current.max())],
            "source_file": self.source_file,
            "format_type": self.format_type,
            "measurement_date": self.measurement_date,
            "temperature_C": self.temperature_C,
            "electrode_area_cm2": self.electrode_area_cm2
        }


class DataImporter:
    """
    Import electrochemical data from various formats.
    
    Supports:
    - Gamry (.DTA)
    - Metrohm Autolab (.txt)
    - BioLogic (.mpt)
    - Generic CSV
    - AnalyteX native format
    """
    
    def __init__(self):
        """Initialize data importer."""
        self.supported_formats = [
            "gamry_dta",
            "autolab_txt",
            "biologic_mpt",
            "generic_csv",
            "analytex"
        ]
    
    def import_eis_data(
        self,
        file_path: str,
        format_type: str = "auto"
    ) -> EISData:
        """
        Import EIS data from file.
        
        Args:
            file_path: Path to data file
            format_type: Format type ("auto", "gamry_dta", "autolab_txt", etc.)
        
        Returns:
            EISData object
        """
        # Auto-detect format if not specified
        if format_type == "auto":
            format_type = self._detect_format(file_path)
        
        logger.info(f"Importing EIS data from {file_path} (format: {format_type})")
        
        # Import based on format
        if format_type == "gamry_dta":
            return self._import_gamry_eis(file_path)
        elif format_type == "autolab_txt":
            return self._import_autolab_eis(file_path)
        elif format_type == "biologic_mpt":
            return self._import_biologic_eis(file_path)
        elif format_type == "generic_csv":
            return self._import_generic_csv_eis(file_path)
        elif format_type == "analytex":
            return self._import_analytex_eis(file_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def import_cv_data(
        self,
        file_path: str,
        format_type: str = "auto"
    ) -> CVData:
        """
        Import CV data from file.
        
        Args:
            file_path: Path to data file
            format_type: Format type ("auto", "gamry_dta", "autolab_txt", etc.)
        
        Returns:
            CVData object
        """
        # Auto-detect format if not specified
        if format_type == "auto":
            format_type = self._detect_format(file_path)
        
        logger.info(f"Importing CV data from {file_path} (format: {format_type})")
        
        # Import based on format
        if format_type == "gamry_dta":
            return self._import_gamry_cv(file_path)
        elif format_type == "autolab_txt":
            return self._import_autolab_cv(file_path)
        elif format_type == "biologic_mpt":
            return self._import_biologic_cv(file_path)
        elif format_type == "generic_csv":
            return self._import_generic_csv_cv(file_path)
        elif format_type == "analytex":
            return self._import_analytex_cv(file_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _detect_format(self, file_path: str) -> str:
        """
        Auto-detect file format based on extension and content.
        
        Args:
            file_path: Path to data file
        
        Returns:
            Detected format type
        """
        # Check file extension
        if file_path.endswith('.DTA') or file_path.endswith('.dta'):
            return "gamry_dta"
        elif file_path.endswith('.mpt') or file_path.endswith('.MPT'):
            return "biologic_mpt"
        elif file_path.endswith('.txt') or file_path.endswith('.TXT'):
            # Could be Autolab or generic
            # Check content to distinguish
            try:
                with open(file_path, 'r') as f:
                    first_line = f.readline()
                    if "AUTOLAB" in first_line.upper():
                        return "autolab_txt"
            except:
                pass
            return "generic_csv"
        elif file_path.endswith('.csv') or file_path.endswith('.CSV'):
            return "generic_csv"
        else:
            # Default to generic CSV
            return "generic_csv"
    
    def _import_gamry_eis(self, file_path: str) -> EISData:
        """Import EIS data from Gamry .DTA file."""
        # Gamry format: Tab-separated with header
        # Columns: Pt, Time, Freq, Zreal, Zimag, Zmod, Zphz, Idc, Vdc, IERange
        
        try:
            # Read file, skip header lines
            df = pd.read_csv(file_path, sep='\t', skiprows=self._find_gamry_data_start(file_path))
            
            # Extract data
            frequencies = df['Freq'].values
            Z_real = df['Zreal'].values
            Z_imag = df['Zimag'].values
            Z_magnitude = df['Zmod'].values
            Z_phase = df['Zphz'].values
            
            # Extract metadata
            metadata = self._extract_gamry_metadata(file_path)
            
            return EISData(
                frequencies=frequencies,
                Z_real=Z_real,
                Z_imag=Z_imag,
                Z_magnitude=Z_magnitude,
                Z_phase=Z_phase,
                source_file=file_path,
                format_type="gamry_dta",
                **metadata
            )
        
        except Exception as e:
            logger.error(f"Failed to import Gamry EIS data: {e}")
            raise
    
    def _import_autolab_eis(self, file_path: str) -> EISData:
        """Import EIS data from Metrohm Autolab .txt file."""
        # Autolab format: Space or tab-separated
        # Columns vary, but typically: freq, Z', Z'', |Z|, phase
        
        try:
            # Read file
            df = pd.read_csv(file_path, sep=r'\s+', skiprows=self._find_autolab_data_start(file_path))
            
            # Extract data (column names may vary)
            frequencies = df.iloc[:, 0].values
            Z_real = df.iloc[:, 1].values
            Z_imag = df.iloc[:, 2].values
            
            # Calculate magnitude and phase if not present
            if df.shape[1] >= 4:
                Z_magnitude = df.iloc[:, 3].values
            else:
                Z_magnitude = np.sqrt(Z_real**2 + Z_imag**2)
            
            if df.shape[1] >= 5:
                Z_phase = df.iloc[:, 4].values
            else:
                Z_phase = np.degrees(np.arctan2(Z_imag, Z_real))
            
            return EISData(
                frequencies=frequencies,
                Z_real=Z_real,
                Z_imag=Z_imag,
                Z_magnitude=Z_magnitude,
                Z_phase=Z_phase,
                source_file=file_path,
                format_type="autolab_txt"
            )
        
        except Exception as e:
            logger.error(f"Failed to import Autolab EIS data: {e}")
            raise
    
    def _import_biologic_eis(self, file_path: str) -> EISData:
        """Import EIS data from BioLogic .mpt file."""
        # BioLogic format: Tab-separated with extensive header
        # Columns: freq/Hz, Re(Z)/Ohm, -Im(Z)/Ohm, |Z|/Ohm, Phase(Z)/deg
        
        try:
            # Read file, skip header
            df = pd.read_csv(file_path, sep='\t', skiprows=self._find_biologic_data_start(file_path))
            
            # Extract data
            frequencies = df['freq/Hz'].values
            Z_real = df['Re(Z)/Ohm'].values
            Z_imag = -df['-Im(Z)/Ohm'].values  # Note: BioLogic uses -Im(Z)
            Z_magnitude = df['|Z|/Ohm'].values
            Z_phase = df['Phase(Z)/deg'].values
            
            return EISData(
                frequencies=frequencies,
                Z_real=Z_real,
                Z_imag=Z_imag,
                Z_magnitude=Z_magnitude,
                Z_phase=Z_phase,
                source_file=file_path,
                format_type="biologic_mpt"
            )
        
        except Exception as e:
            logger.error(f"Failed to import BioLogic EIS data: {e}")
            raise
    
    def _import_generic_csv_eis(self, file_path: str) -> EISData:
        """Import EIS data from generic CSV file."""
        # Generic format: CSV with columns freq, Z_real, Z_imag
        # Or: freq, Z_real, Z_imag, Z_mag, Z_phase
        
        try:
            # Try to read CSV
            df = pd.read_csv(file_path)
            
            # Try different column name variations
            freq_cols = ['freq', 'frequency', 'f', 'Freq', 'Frequency', 'F']
            real_cols = ['Z_real', 'Zreal', 'Z\'', 'Re(Z)', 'real', 'Real']
            imag_cols = ['Z_imag', 'Zimag', 'Z\'\'', 'Im(Z)', 'imag', 'Imag']
            
            # Find columns
            freq_col = next((c for c in freq_cols if c in df.columns), df.columns[0])
            real_col = next((c for c in real_cols if c in df.columns), df.columns[1])
            imag_col = next((c for c in imag_cols if c in df.columns), df.columns[2])
            
            # Extract data
            frequencies = df[freq_col].values
            Z_real = df[real_col].values
            Z_imag = df[imag_col].values
            
            # Calculate magnitude and phase
            Z_magnitude = np.sqrt(Z_real**2 + Z_imag**2)
            Z_phase = np.degrees(np.arctan2(Z_imag, Z_real))
            
            return EISData(
                frequencies=frequencies,
                Z_real=Z_real,
                Z_imag=Z_imag,
                Z_magnitude=Z_magnitude,
                Z_phase=Z_phase,
                source_file=file_path,
                format_type="generic_csv"
            )
        
        except Exception as e:
            logger.error(f"Failed to import generic CSV EIS data: {e}")
            raise
    
    def _import_analytex_eis(self, file_path: str) -> EISData:
        """Import EIS data from AnalyteX native format."""
        # AnalyteX format: JSON with metadata
        import json
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            return EISData(
                frequencies=np.array(data['frequencies']),
                Z_real=np.array(data['Z_real']),
                Z_imag=np.array(data['Z_imag']),
                Z_magnitude=np.array(data['Z_magnitude']),
                Z_phase=np.array(data['Z_phase']),
                source_file=file_path,
                format_type="analytex",
                measurement_date=data.get('measurement_date', ''),
                temperature_C=data.get('temperature_C'),
                electrode_area_cm2=data.get('electrode_area_cm2')
            )
        
        except Exception as e:
            logger.error(f"Failed to import AnalyteX EIS data: {e}")
            raise
    
    def _import_gamry_cv(self, file_path: str) -> CVData:
        """Import CV data from Gamry .DTA file."""
        try:
            df = pd.read_csv(file_path, sep='\t', skiprows=self._find_gamry_data_start(file_path))
            
            potential = df['Vf'].values
            current = df['Im'].values
            
            # Estimate scan rate from data
            scan_rate = self._estimate_scan_rate(potential, df['T'].values)
            
            return CVData(
                potential=potential,
                current=current,
                scan_rate=scan_rate,
                source_file=file_path,
                format_type="gamry_dta"
            )
        
        except Exception as e:
            logger.error(f"Failed to import Gamry CV data: {e}")
            raise
    
    def _import_autolab_cv(self, file_path: str) -> CVData:
        """Import CV data from Autolab .txt file."""
        try:
            df = pd.read_csv(file_path, sep=r'\s+', skiprows=self._find_autolab_data_start(file_path))
            
            potential = df.iloc[:, 0].values
            current = df.iloc[:, 1].values
            
            # Estimate scan rate
            if df.shape[1] >= 3:
                time = df.iloc[:, 2].values
                scan_rate = self._estimate_scan_rate(potential, time)
            else:
                scan_rate = 0.1  # Default
            
            return CVData(
                potential=potential,
                current=current,
                scan_rate=scan_rate,
                source_file=file_path,
                format_type="autolab_txt"
            )
        
        except Exception as e:
            logger.error(f"Failed to import Autolab CV data: {e}")
            raise
    
    def _import_biologic_cv(self, file_path: str) -> CVData:
        """Import CV data from BioLogic .mpt file."""
        try:
            df = pd.read_csv(file_path, sep='\t', skiprows=self._find_biologic_data_start(file_path))
            
            potential = df['Ewe/V'].values
            current = df['<I>/mA'].values * 1e-3  # Convert mA to A
            
            # Get scan rate from header or estimate
            scan_rate = 0.1  # Default, should extract from header
            
            return CVData(
                potential=potential,
                current=current,
                scan_rate=scan_rate,
                source_file=file_path,
                format_type="biologic_mpt"
            )
        
        except Exception as e:
            logger.error(f"Failed to import BioLogic CV data: {e}")
            raise
    
    def _import_generic_csv_cv(self, file_path: str) -> CVData:
        """Import CV data from generic CSV file."""
        try:
            df = pd.read_csv(file_path)
            
            # Find columns
            pot_cols = ['potential', 'E', 'V', 'voltage', 'Potential', 'Voltage']
            curr_cols = ['current', 'I', 'A', 'Current']
            
            pot_col = next((c for c in pot_cols if c in df.columns), df.columns[0])
            curr_col = next((c for c in curr_cols if c in df.columns), df.columns[1])
            
            potential = df[pot_col].values
            current = df[curr_col].values
            
            # Estimate scan rate
            if 'time' in df.columns or 't' in df.columns:
                time_col = 'time' if 'time' in df.columns else 't'
                scan_rate = self._estimate_scan_rate(potential, df[time_col].values)
            else:
                scan_rate = 0.1  # Default
            
            return CVData(
                potential=potential,
                current=current,
                scan_rate=scan_rate,
                source_file=file_path,
                format_type="generic_csv"
            )
        
        except Exception as e:
            logger.error(f"Failed to import generic CSV CV data: {e}")
            raise
    
    def _import_analytex_cv(self, file_path: str) -> CVData:
        """Import CV data from AnalyteX native format."""
        import json
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            return CVData(
                potential=np.array(data['potential']),
                current=np.array(data['current']),
                scan_rate=data['scan_rate'],
                source_file=file_path,
                format_type="analytex",
                measurement_date=data.get('measurement_date', ''),
                temperature_C=data.get('temperature_C'),
                electrode_area_cm2=data.get('electrode_area_cm2')
            )
        
        except Exception as e:
            logger.error(f"Failed to import AnalyteX CV data: {e}")
            raise
    
    # Helper methods
    
    def _find_gamry_data_start(self, file_path: str) -> int:
        """Find the line where Gamry data starts."""
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                if line.startswith('Pt\t') or line.startswith('Pt '):
                    return i
        return 0
    
    def _find_autolab_data_start(self, file_path: str) -> int:
        """Find the line where Autolab data starts."""
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                if re.match(r'^\d+\.?\d*\s+', line):
                    return i
        return 0
    
    def _find_biologic_data_start(self, file_path: str) -> int:
        """Find the line where BioLogic data starts."""
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                if 'freq/Hz' in line or 'Ewe/V' in line:
                    return i
        return 0
    
    def _extract_gamry_metadata(self, file_path: str) -> dict:
        """Extract metadata from Gamry file header."""
        metadata = {}
        
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.startswith('DATE'):
                        metadata['measurement_date'] = line.split('\t')[1].strip()
                    elif line.startswith('AREA'):
                        metadata['electrode_area_cm2'] = float(line.split('\t')[1])
                    elif line.startswith('TEMP'):
                        metadata['temperature_C'] = float(line.split('\t')[1])
                    elif line.startswith('Pt\t'):
                        break
        except:
            pass
        
        return metadata
    
    def _estimate_scan_rate(self, potential: np.ndarray, time: np.ndarray) -> float:
        """Estimate scan rate from potential vs time data."""
        try:
            # Calculate dE/dt
            dE = np.diff(potential)
            dt = np.diff(time)
            scan_rates = np.abs(dE / dt)
            
            # Return median scan rate
            return float(np.median(scan_rates[scan_rates > 0]))
        except:
            return 0.1  # Default 100 mV/s
