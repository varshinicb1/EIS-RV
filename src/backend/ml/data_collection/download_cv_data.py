#!/usr/bin/env python3
"""
Download CV datasets from DUCK platform
Based on the paper: "Database utility for cyclovoltammetry knowledge (DUCK)"
Garay-Ruiz et al., Digital Discovery, 2026
"""

import os
import requests
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "ml_datasets" / "raw" / "cv"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def download_duck_datasets():
    """
    Download DUCK CV datasets
    Source: https://doi.org/10.1039/D6DD00019C
    
    Dataset includes:
    - TL (Traditional Lab): 130 CV experiments
    - SDL (Self-Driving Lab): 79 CV experiments
    - Total: 209 CV measurements
    """
    logger.info("="*80)
    logger.info("Downloading DUCK CV Datasets")
    logger.info("="*80)
    
    # Repository information
    repo_url = "https://gitlab.com/dgarayr/duck"
    zenodo_url = "https://doi.org/10.5281/zenodo.18015308"
    
    logger.info(f"Repository: {repo_url}")
    logger.info(f"Data: {zenodo_url}")
    logger.info("\nThis dataset is from the paper:")
    logger.info("'Database utility for cyclovoltammetry knowledge (DUCK):'")
    logger.info("'unified platform for electrochemical data'")
    logger.info("Garay-Ruiz et al., Digital Discovery, 2026")
    logger.info("\nDataset details:")
    logger.info("  - TL Dataset: 130 CV experiments (electrodeposition)")
    logger.info("    • Materials: Bi-Te, Zn-O, Cu-Ni, PEDOT, Cu-Se, Ag-Se")
    logger.info("    • Metals: Ag, Cu, Ni, Zn, Fe, Bi, Se, Te")
    logger.info("    • Scan rates: 5-200 mV/s")
    logger.info("  - SDL Dataset: 79 CV experiments (metal-ligand complexes)")
    logger.info("    • Metals: V, Ni, Cu")
    logger.info("    • Ligands: ethylenediamine")
    logger.info("    • Automated Bayesian optimization")
    logger.info("  - Total: 209 CV measurements")
    logger.info("  - License: Open Access (RSC)")
    
    # Try to download via git
    logger.info("\nAttempting to clone repository...")
    
    try:
        import subprocess
        
        clone_dir = DATA_DIR / "duck"
        
        if clone_dir.exists():
            logger.info(f"Repository already exists at {clone_dir}")
            logger.info("Pulling latest changes...")
            subprocess.run(
                ["git", "pull"],
                cwd=clone_dir,
                check=True,
                capture_output=True
            )
        else:
            logger.info(f"Cloning to {clone_dir}...")
            subprocess.run(
                ["git", "clone", repo_url, str(clone_dir)],
                check=True,
                capture_output=True
            )
        
        logger.info("✅ Successfully downloaded DUCK repository")
        
        # Save metadata
        metadata = {
            'dataset': 'DUCK CV Data',
            'source_repo': repo_url,
            'source_data': zenodo_url,
            'paper': 'Garay-Ruiz et al., Digital Discovery, 2026',
            'doi': '10.1039/D6DD00019C',
            'tl_measurements': 130,
            'sdl_measurements': 79,
            'total_measurements': 209,
            'applications': [
                'Mechanism classification',
                'Peak detection',
                'Species identification',
                'Electrochemical parameters'
            ],
            'license': 'Open Access',
            'download_date': '2026-05-05'
        }
        
        with open(DATA_DIR / 'duck_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git clone failed: {e}")
        logger.info("\n⚠️  Manual download required:")
        logger.info(f"   1. Visit: {repo_url}")
        logger.info(f"   2. Download the repository")
        logger.info(f"   3. Extract to: {DATA_DIR}")
        logger.info(f"   4. Download data from: {zenodo_url}")
        return False
    
    except FileNotFoundError:
        logger.error("Git not found. Please install git or download manually.")
        logger.info("\n⚠️  Manual download required:")
        logger.info(f"   1. Visit: {repo_url}")
        logger.info(f"   2. Download the repository")
        logger.info(f"   3. Extract to: {DATA_DIR}")
        logger.info(f"   4. Download data from: {zenodo_url}")
        return False


def download_radar_cv_data():
    """
    Download additional CV data from RADAR repository
    Source: https://doi.org/10.22000/1753
    
    Dataset: Analytical data: cyclic voltammetry - Draft v.1.0
    Author: David Herrmann, KIT
    Complex: [Cu(TMGqu)2]PF6
    """
    logger.info("\n" + "="*80)
    logger.info("Downloading RADAR CV Dataset")
    logger.info("="*80)
    
    radar_url = "https://doi.org/10.22000/1753"
    
    logger.info(f"Source: {radar_url}")
    logger.info("\nThis dataset is from:")
    logger.info("'Analytical data: cyclic voltammetry - Draft v.1.0'")
    logger.info("Herrmann et al., KIT, 2023")
    logger.info("\nDataset details:")
    logger.info("  - Complex: [Cu(TMGqu)2]PF6")
    logger.info("  - From: Chemotion ELN")
    logger.info("  - License: CC0 1.0")
    
    logger.info("\n⚠️  Manual download required:")
    logger.info(f"   1. Visit: {radar_url}")
    logger.info("   2. Download the dataset")
    logger.info(f"   3. Extract to: {DATA_DIR / 'radar_cv'}")
    
    # Save metadata
    metadata = {
        'dataset': 'RADAR CV Data',
        'source': radar_url,
        'author': 'David Herrmann, KIT',
        'complex': '[Cu(TMGqu)2]PF6',
        'tool': 'Chemotion ELN',
        'license': 'CC0 1.0',
        'download_date': '2026-05-05'
    }
    
    with open(DATA_DIR / 'radar_cv_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return False  # Manual download required


def main():
    """Download all CV datasets"""
    logger.info("="*80)
    logger.info("CV Dataset Collection")
    logger.info("Training data for CV Transformer model")
    logger.info("="*80)
    
    # Download datasets
    success1 = download_duck_datasets()
    success2 = download_radar_cv_data()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("="*80)
    
    if success1:
        logger.info("✅ DUCK datasets: Downloaded (209 measurements)")
    else:
        logger.info("⚠️  DUCK datasets: Manual download required")
    
    logger.info("⚠️  RADAR CV: Manual download required")
    
    logger.info("\n📊 Total potential measurements: 209+ CV curves")
    logger.info("\nThese datasets will be used to train the CV Transformer model for:")
    logger.info("  - Mechanism classification (reversible/irreversible)")
    logger.info("  - Peak detection (anodic/cathodic)")
    logger.info("  - Electrochemical parameter extraction")
    logger.info("  - Species identification")
    
    logger.info("\n" + "="*80)
    logger.info("Next steps:")
    logger.info("1. Complete manual downloads if needed")
    logger.info("2. Run: python src/backend/ml/training/train_cv.py")
    logger.info("3. Validate model performance")
    logger.info("="*80)


if __name__ == "__main__":
    main()
