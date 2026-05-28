#!/usr/bin/env python3
"""
Download EBIO electrochemistry dataset from Zenodo
Source: EU Open Research Repository - EBIO Project

Dataset: Raw data Electrochemistry_Talal WP2 Part 1
Size: 3.1 GB
License: CC BY 4.0
Published: February 20, 2025

This dataset is CRITICAL for:
- GCD Transformer training (NO OTHER DATA SOURCE)
- Biosensor Transformer training (NO OTHER DATA SOURCE)
- CV Transformer enhancement
- EIS Transformer enhancement
"""

import os
import requests
import json
from pathlib import Path
import logging
from tqdm import tqdm
import hashlib
import zipfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "ml_datasets" / "raw" / "ebio"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Dataset information
DATASET_INFO = {
    'name': 'EBIO Electrochemistry Dataset',
    'title': 'Raw data Electrochemistry_Talal WP2 Part 1',
    'source': 'Zenodo - EU Open Research Repository',
    'project': 'EBIO - Biofuels through Electrochemical transformation',
    'grant': 'European Commission - 101006612197',
    'published': '2025-02-20',
    'version': 'v1',
    'size': '3.1 GB',
    'license': 'CC BY 4.0',
    'md5': 'ca058b3ebccccd2943ede33ce2d214433',
    'views': 197,
    'downloads': 94
}

# Zenodo record URL (update with actual record ID)
# Note: The user provided the dataset info but not the direct Zenodo record ID
# This will need to be updated with the actual Zenodo record URL
ZENODO_RECORD_URL = "https://zenodo.org/records/[RECORD_ID]"
ZENODO_API_URL = "https://zenodo.org/api/records/[RECORD_ID]"

# Alternative: Search Zenodo for the dataset
ZENODO_SEARCH_URL = "https://zenodo.org/api/records/?q=EBIO+electrochemistry+Talal"


def search_zenodo_for_ebio():
    """
    Search Zenodo for the EBIO dataset
    """
    logger.info("="*80)
    logger.info("Searching Zenodo for EBIO Dataset")
    logger.info("="*80)
    
    try:
        logger.info(f"Searching: {ZENODO_SEARCH_URL}")
        response = requests.get(ZENODO_SEARCH_URL, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        hits = data.get('hits', {}).get('hits', [])
        
        logger.info(f"\nFound {len(hits)} potential matches:")
        
        for i, hit in enumerate(hits, 1):
            metadata = hit.get('metadata', {})
            title = metadata.get('title', 'Unknown')
            doi = metadata.get('doi', 'Unknown')
            pub_date = metadata.get('publication_date', 'Unknown')
            
            # Check if this is our dataset
            if 'Electrochemistry' in title and 'Talal' in title:
                logger.info(f"\n✅ MATCH FOUND:")
                logger.info(f"   Title: {title}")
                logger.info(f"   DOI: {doi}")
                logger.info(f"   Published: {pub_date}")
                logger.info(f"   Record ID: {hit.get('id')}")
                
                # Get files
                files = hit.get('files', [])
                for file_info in files:
                    filename = file_info.get('key', 'Unknown')
                    filesize = file_info.get('size', 0)
                    filesize_mb = filesize / (1024 * 1024)
                    logger.info(f"   File: {filename} ({filesize_mb:.1f} MB)")
                
                return hit
            else:
                logger.info(f"\n{i}. {title}")
                logger.info(f"   DOI: {doi}")
        
        return None
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return None


def download_file_with_progress(url: str, output_path: Path, expected_md5: str = None):
    """
    Download a file with progress bar and MD5 verification
    """
    logger.info(f"Downloading from: {url}")
    logger.info(f"Saving to: {output_path}")
    
    try:
        # Start download
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Get file size
        total_size = int(response.headers.get('content-length', 0))
        total_size_mb = total_size / (1024 * 1024)
        logger.info(f"File size: {total_size_mb:.1f} MB")
        
        # Download with progress bar
        md5_hash = hashlib.md5()
        
        with open(output_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        md5_hash.update(chunk)
                        pbar.update(len(chunk))
        
        # Verify MD5
        if expected_md5:
            actual_md5 = md5_hash.hexdigest()
            logger.info(f"Expected MD5: {expected_md5}")
            logger.info(f"Actual MD5:   {actual_md5}")
            
            if actual_md5 == expected_md5:
                logger.info("✅ MD5 checksum verified!")
            else:
                logger.error("❌ MD5 checksum mismatch!")
                return False
        
        logger.info("✅ Download complete!")
        return True
    
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False


def extract_zip(zip_path: Path, extract_dir: Path):
    """
    Extract ZIP file with progress
    """
    logger.info(f"Extracting: {zip_path}")
    logger.info(f"To: {extract_dir}")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            members = zip_ref.namelist()
            logger.info(f"Files in archive: {len(members)}")
            
            with tqdm(total=len(members), desc="Extracting") as pbar:
                for member in members:
                    zip_ref.extract(member, extract_dir)
                    pbar.update(1)
        
        logger.info("✅ Extraction complete!")
        return True
    
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return False


def explore_dataset(data_dir: Path):
    """
    Explore the downloaded dataset structure
    """
    logger.info("\n" + "="*80)
    logger.info("Exploring Dataset Structure")
    logger.info("="*80)
    
    try:
        # Count files by extension
        file_counts = {}
        total_size = 0
        
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                file_counts[ext] = file_counts.get(ext, 0) + 1
                total_size += file_path.stat().st_size
        
        logger.info(f"\nTotal files: {sum(file_counts.values())}")
        logger.info(f"Total size: {total_size / (1024**3):.2f} GB")
        logger.info("\nFiles by extension:")
        
        for ext, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {ext or '(no extension)'}: {count} files")
        
        # Look for Biologic files
        biologic_extensions = ['.mpt', '.mps', '.mpr']
        biologic_files = []
        
        for ext in biologic_extensions:
            files = list(data_dir.rglob(f"*{ext}"))
            if files:
                logger.info(f"\n✅ Found {len(files)} {ext} files (Biologic format)")
                biologic_files.extend(files)
        
        if biologic_files:
            logger.info(f"\n✅ Total Biologic files: {len(biologic_files)}")
            logger.info("These files can be parsed with the 'galvani' library")
            logger.info("Install: pip install galvani")
        
        # Try to identify techniques
        logger.info("\n" + "="*80)
        logger.info("Attempting to identify electrochemical techniques...")
        logger.info("="*80)
        
        technique_keywords = {
            'GCD': ['charge', 'discharge', 'gcd', 'galvanostatic', 'gcpl', 'battery', 'cycle'],
            'CV': ['cv', 'cyclic', 'voltammetry', 'voltammogram'],
            'EIS': ['eis', 'impedance', 'peis', 'geis', 'nyquist', 'bode'],
            'CA': ['ca', 'chronoamperometry', 'amperometry'],
            'CP': ['cp', 'chronopotentiometry', 'potentiometry'],
            'LSV': ['lsv', 'linear', 'sweep'],
            'Biosensor': ['biosensor', 'sensor', 'analyte', 'glucose', 'lactate']
        }
        
        technique_counts = {tech: 0 for tech in technique_keywords}
        
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                filename_lower = file_path.name.lower()
                
                for technique, keywords in technique_keywords.items():
                    if any(keyword in filename_lower for keyword in keywords):
                        technique_counts[technique] += 1
                        break
        
        logger.info("\nPotential technique distribution:")
        for technique, count in sorted(technique_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                logger.info(f"  {technique}: ~{count} files")
        
        # Save exploration results
        exploration_results = {
            'total_files': sum(file_counts.values()),
            'total_size_gb': total_size / (1024**3),
            'file_counts': file_counts,
            'biologic_files': len(biologic_files),
            'technique_counts': technique_counts,
            'exploration_date': '2026-05-05'
        }
        
        results_file = data_dir / 'exploration_results.json'
        with open(results_file, 'w') as f:
            json.dump(exploration_results, f, indent=2)
        
        logger.info(f"\n✅ Exploration results saved to: {results_file}")
        
        return exploration_results
    
    except Exception as e:
        logger.error(f"Exploration failed: {e}")
        return None


def download_ebio_dataset():
    """
    Main function to download EBIO dataset
    """
    logger.info("="*80)
    logger.info("EBIO Electrochemistry Dataset Download")
    logger.info("="*80)
    
    logger.info("\nDataset Information:")
    for key, value in DATASET_INFO.items():
        logger.info(f"  {key}: {value}")
    
    logger.info("\n" + "="*80)
    logger.info("CRITICAL IMPORTANCE")
    logger.info("="*80)
    logger.info("This dataset is ESSENTIAL for:")
    logger.info("  1. GCD Transformer - NO OTHER DATA SOURCE")
    logger.info("  2. Biosensor Transformer - NO OTHER DATA SOURCE")
    logger.info("  3. CV Transformer - Enhancement")
    logger.info("  4. EIS Transformer - Enhancement")
    logger.info("\nWithout this dataset, 2/5 models cannot be trained!")
    
    # Search for dataset
    logger.info("\n" + "="*80)
    logger.info("Step 1: Searching Zenodo")
    logger.info("="*80)
    
    dataset_record = search_zenodo_for_ebio()
    
    if dataset_record:
        # Found the dataset, try to download
        logger.info("\n" + "="*80)
        logger.info("Step 2: Downloading Dataset")
        logger.info("="*80)
        
        files = dataset_record.get('files', [])
        
        for file_info in files:
            filename = file_info.get('key', 'unknown.zip')
            file_url = file_info.get('links', {}).get('self', '')
            
            if file_url:
                output_path = DATA_DIR / filename
                
                success = download_file_with_progress(
                    file_url,
                    output_path,
                    expected_md5=DATASET_INFO['md5']
                )
                
                if success and filename.endswith('.zip'):
                    # Extract
                    logger.info("\n" + "="*80)
                    logger.info("Step 3: Extracting Dataset")
                    logger.info("="*80)
                    
                    extract_success = extract_zip(output_path, DATA_DIR)
                    
                    if extract_success:
                        # Explore
                        logger.info("\n" + "="*80)
                        logger.info("Step 4: Exploring Dataset")
                        logger.info("="*80)
                        
                        explore_dataset(DATA_DIR)
                        
                        # Clean up zip file
                        logger.info(f"\nRemoving zip file: {output_path}")
                        output_path.unlink()
    
    else:
        # Manual download required
        logger.info("\n" + "="*80)
        logger.info("⚠️  MANUAL DOWNLOAD REQUIRED")
        logger.info("="*80)
        
        logger.info("\nThe dataset could not be automatically downloaded.")
        logger.info("Please download manually:")
        logger.info("\n1. Search Zenodo for:")
        logger.info("   'EBIO electrochemistry Talal WP2'")
        logger.info("\n2. Or visit:")
        logger.info("   https://zenodo.org/")
        logger.info("   Search: 'Raw data Electrochemistry_Talal WP2 Part 1'")
        logger.info("\n3. Download the file:")
        logger.info("   'Raw data Electrochemistry_Talal WP2 Part 1.zip' (3.1 GB)")
        logger.info(f"\n4. Save to: {DATA_DIR}")
        logger.info("\n5. Extract the ZIP file")
        logger.info("\n6. Run this script again to explore the dataset")
        
        # Check if already downloaded
        if any(DATA_DIR.iterdir()):
            logger.info("\n" + "="*80)
            logger.info("Files detected in data directory!")
            logger.info("="*80)
            logger.info("Exploring existing files...")
            explore_dataset(DATA_DIR)
    
    # Save metadata
    metadata_file = DATA_DIR / 'ebio_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(DATASET_INFO, f, indent=2)
    
    logger.info(f"\n✅ Metadata saved to: {metadata_file}")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("NEXT STEPS")
    logger.info("="*80)
    logger.info("\n1. Install Biologic parser:")
    logger.info("   pip install galvani")
    logger.info("\n2. Parse the data:")
    logger.info("   python src/backend/ml/data_collection/parse_ebio_data.py")
    logger.info("\n3. Train models:")
    logger.info("   python src/backend/ml/training/train_gcd.py")
    logger.info("   python src/backend/ml/training/train_biosensor.py")
    logger.info("\n4. Validate performance")
    logger.info("\n5. Integrate with RĀMAN Studio")
    
    logger.info("\n" + "="*80)
    logger.info("This dataset will COMPLETE the ML system!")
    logger.info("="*80)


if __name__ == "__main__":
    download_ebio_dataset()
