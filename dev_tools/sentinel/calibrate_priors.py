import os
import sqlite3
import re
import subprocess
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] calibrate_priors: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'autonomous.log'), mode='a')
    ]
)

DB_PATH = os.path.join(os.path.dirname(__file__), 'sota_intel.db')
ENGINE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'engine_core')
TYPES_HPP_PATH = os.path.join(ENGINE_DIR, 'include', 'raman', 'types.hpp')

def fetch_recent_intel():
    """Fetch recent research intelligence from the local database."""
    if not os.path.exists(DB_PATH):
        logging.warning(f"Database not found at {DB_PATH}")
        return []

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get research from the last 24 hours (for demonstration, we get all)
        cursor.execute("SELECT id, title, summary, category FROM intel ORDER BY found_at DESC LIMIT 50")
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        logging.error(f"Failed to fetch intel: {e}")
        return []

def extract_new_priors(intel_records):
    """
    Extract proposed updates to physical priors based on SOTA research.
    In a fully production system, this would call the Alchemi AI backend 
    to extract exact values. Here we simulate the extraction logic using regex
    on the abstracts/summaries for specific keywords.
    """
    updates = {}
    
    # Mock extraction logic: Look for mentions of updated values in the summaries
    for record in intel_records:
        summary = record['summary'].lower()
        
        # Example: look for updated standard temperature (rare, but possible for specific domains)
        temp_match = re.search(r'standard temperature revised to (\d+\.?\d*)', summary)
        if temp_match and 'T_STD' not in updates:
            updates['T_STD'] = float(temp_match.group(1))

        # Example: diffusion coefficients or capacitance updates
        diff_match = re.search(r'diffusion coefficient of (.*?) is (\d+\.?\d*e[-+]\d+)', summary)
        if diff_match and 'diff_coeff' not in updates:
            updates['diff_coeff'] = float(diff_match.group(2))

        # Example: double-layer capacitance updates
        cdl_match = re.search(r'double-layer capacitance is (\d+\.?\d*e[-+]\d+)', summary)
        if cdl_match and 'Cdl' not in updates:
            updates['Cdl'] = float(cdl_match.group(1))
            
    return updates

def apply_priors_to_cpp(updates):
    """Apply the extracted priors to the C++ types.hpp file."""
    if not updates:
        logging.info("No new priors extracted. Skipping C++ update.")
        return False
        
    if not os.path.exists(TYPES_HPP_PATH):
        logging.error(f"Cannot find {TYPES_HPP_PATH}")
        return False

    with open(TYPES_HPP_PATH, 'r') as f:
        content = f.read()

    modified = False
    
    for key, value in updates.items():
        # Handle constexpr double updates
        pattern_constexpr = rf'(constexpr double\s+{key}\s*=\s*)([^;]+)(;.*)'
        if re.search(pattern_constexpr, content):
            new_content = re.sub(pattern_constexpr, rf'\g<1>{value}\g<3>', content)
            if new_content != content:
                content = new_content
                modified = True
                logging.info(f"Updated constexpr {key} to {value}")
                continue

        # Handle struct default parameter updates (e.g., double Rs = 10.0;)
        pattern_struct = rf'(double\s+{key}\s*=\s*)([^;]+)(;.*)'
        if re.search(pattern_struct, content):
            new_content = re.sub(pattern_struct, rf'\g<1>{value}\g<3>', content)
            if new_content != content:
                content = new_content
                modified = True
                logging.info(f"Updated parameter {key} to {value}")

    if modified:
        with open(TYPES_HPP_PATH, 'w') as f:
            f.write(content)
        logging.info(f"Successfully patched {TYPES_HPP_PATH}")
        return True
        
    return False

def recompile_engine():
    """Trigger C++ engine recompilation."""
    logging.info("Triggering C++ engine recompile...")
    build_dir = os.path.join(ENGINE_DIR, 'build')
    
    if not os.path.exists(build_dir):
        logging.error(f"Build directory {build_dir} does not exist. Cannot recompile.")
        return False

    try:
        result = subprocess.run(
            ['cmake', '--build', '.'],
            cwd=build_dir,
            capture_output=True,
            text=True,
            check=True
        )
        logging.info("C++ engine recompiled successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Recompilation failed: {e.stderr}")
        return False

def run_calibration():
    logging.info("Starting Autonomous Priors Calibration Hook...")
    
    intel = fetch_recent_intel()
    logging.info(f"Fetched {len(intel)} recent intelligence records.")
    
    updates = extract_new_priors(intel)
    
    if updates:
        logging.info(f"Proposed updates based on literature: {updates}")
        if apply_priors_to_cpp(updates):
            recompile_engine()
    else:
        logging.info("No actionable updates found in recent literature.")

if __name__ == "__main__":
    run_calibration()
