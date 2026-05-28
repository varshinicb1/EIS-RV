#!/usr/bin/env python3
"""
Download EIS datasets from open-source repositories
Based on the paper: "Open source online electrochemical impedance spectroscopy data analytics tool"
Blömeke et al., Journal of Power Sources, 2024
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
DATA_DIR = BASE_DIR / "data" / "ml_datasets" / "raw" / "eis"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def download_eis_data_analytics():
    """
    Download EIS Data Analytics dataset
    Source: https://git.rwth-aachen.de/isea/eis_data_analytics
    
    Dataset includes:
    - LiFun 575166-01 battery (1 Ah, NMC532)
    - Temperature: -15°C to 55°C (8 steps)
    - SOC: 0% to 100% (15 steps)
    - ~120 EIS measurements
    """
    logger.info("="*80)
    logger.info("Downloading EIS Data Analytics Dataset")
    logger.info("="*80)
    
    # Repository information
    repo_url = "https://git.rwth-aachen.de/isea/eis_data_analytics"
    
    logger.info(f"Repository: {repo_url}")
    logger.info("\nThis dataset is from the paper:")
    logger.info("'Open source online electrochemical impedance spectroscopy data analytics tool'")
    logger.info("Blömeke et al., Journal of Power Sources, Volume 615, 2024")
    logger.info("\nDataset details:")
    logger.info("  - Battery: LiFun 575166-01 (1 Ah, NMC532 cathode, graphite anode)")
    logger.info("  - Temperature range: -15°C to 55°C (8 steps)")
    logger.info("  - SOC range: 0% to 100% (15 steps)")
    logger.info("  - Total measurements: ~120 EIS spectra")
    logger.info("  - License: Open source (Creative Commons)")
    
    # Try to download via git
    logger.info("\nAttempting to clone repository...")
    
    try:
        import subprocess
        
        clone_dir = DATA_DIR / "eis_data_analytics"
        
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
        
        logger.info("✅ Successfully downloaded EIS Data Analytics dataset")
        
        # Save metadata
        metadata = {
            'dataset': 'EIS Data Analytics',
            'source': repo_url,
            'paper': 'Blömeke et al., J. Power Sources 615 (2024) 235049',
            'doi': '10.1016/j.jpowsour.2024.235049',
            'battery': 'LiFun 575166-01 (1 Ah, NMC532)',
            'temperature_range': '-15°C to 55°C',
            'soc_range': '0% to 100%',
            'num_measurements': '~120',
            'license': 'Creative Commons',
            'download_date': '2026-05-05'
        }
        
        with open(DATA_DIR / 'eis_data_analytics_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git clone failed: {e}")
        logger.info("\n⚠️  Manual download required:")
        logger.info(f"   1. Visit: {repo_url}")
        logger.info(f"   2. Download the repository")
        logger.info(f"   3. Extract to: {DATA_DIR}")
        return False
    
    except FileNotFoundError:
        logger.error("Git not found. Please install git or download manually.")
        logger.info("\n⚠️  Manual download required:")
        logger.info(f"   1. Visit: {repo_url}")
        logger.info(f"   2. Download the repository")
        logger.info(f"   3. Extract to: {DATA_DIR}")
        return False


def download_rashid_dataset():
    """
    Download Rashid et al. (2023) dataset
    Source: Published dataset for SOH estimation
    
    Dataset includes:
    - 21700 NMC 811 cells
    - 360 EIS measurements
    - Temperature: 15, 25, 35°C
    - SOC: 5, 20, 50, 70, 95%
    - SOH: 80, 85, 90, 95, 100%
    """
    logger.info("\n" + "="*80)
    logger.info("Downloading Rashid et al. (2023) Dataset")
    logger.info("="*80)
    
    logger.info("\nThis dataset is from the paper:")
    logger.info("'Dataset for rapid state of health estimation of lithium batteries")
    logger.info(" using EIS and machine learning: Training and validation'")
    logger.info("Rashid et al., Data in Brief, Volume 48, 2023")
    logger.info("\nDataset details:")
    logger.info("  - Battery: 21700 NMC 811 cells")
    logger.info("  - Total measurements: 360 EIS spectra")
    logger.info("  - Temperature: 15, 25, 35°C")
    logger.info("  - SOC: 5, 20, 50, 70, 95%")
    logger.info("  - SOH: 80, 85, 90, 95, 100%")
    logger.info("  - License: CC BY 4.0")
    
    # This dataset is typically available on Mendeley Data or similar
    logger.info("\n⚠️  Manual download required:")
    logger.info("   1. Visit: https://data.mendeley.com/")
    logger.info("   2. Search for: 'Rashid EIS battery SOH'")
    logger.info("   3. Download the dataset")
    logger.info(f"   4. Extract to: {DATA_DIR / 'rashid_2023'}")
    
    # Save metadata
    metadata = {
        'dataset': 'Rashid et al. 2023',
        'paper': 'Rashid et al., Data in Brief 48 (2023) 109157',
        'doi': '10.1016/j.dib.2023.109157',
        'battery': '21700 NMC 811',
        'num_measurements': 360,
        'temperature_values': [15, 25, 35],
        'soc_values': [5, 20, 50, 70, 95],
        'soh_values': [80, 85, 90, 95, 100],
        'license': 'CC BY 4.0',
        'download_date': '2026-05-05'
    }
    
    with open(DATA_DIR / 'rashid_2023_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return False  # Manual download required


def main():
    """Download all EIS datasets"""
    logger.info("="*80)
    logger.info("EIS Dataset Collection")
    logger.info("Training data for EIS Transformer model")
    logger.info("="*80)
    
    # Download datasets
    success1 = download_eis_data_analytics()
    success2 = download_rashid_dataset()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("="*80)
    
    if success1:
        logger.info("✅ EIS Data Analytics: Downloaded (~120 measurements)")
    else:
        logger.info("⚠️  EIS Data Analytics: Manual download required")
    
    logger.info("⚠️  Rashid et al. 2023: Manual download required (360 measurements)")
    
    logger.info("\n📊 Total potential measurements: ~480 EIS spectra")
    logger.info("\nThese datasets will be used to train the EIS Transformer model for:")
    logger.info("  - Temperature estimation (MSE target: <1 K)")
    logger.info("  - SOC estimation")
    logger.info("  - SOH estimation")
    logger.info("  - Battery diagnostics")
    
    logger.info("\n" + "="*80)
    logger.info("Next steps:")
    logger.info("1. Complete manual downloads if needed")
    logger.info("2. Run: python src/backend/ml/training/train_eis.py")
    logger.info("3. Validate model performance")
    logger.info("="*80)


if __name__ == "__main__":
    main()
