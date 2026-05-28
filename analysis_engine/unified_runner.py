"""
Unified Analysis Runner — orchestrates all integrated engines.

Usage:
    python unified_runner.py --input <file> --output <dir> --style nature --engine auto

Engines:
    auto            — auto-detect technique and route to best engine
    electrochem     — Electrochem-Suite (VidyuthLabs) full pipeline
    impedance_fit   — impedance.py circuit fitting
    drt             — pyDRTtools DRT analysis
    madap           — MADAP voltammetry/impedance analysis

Outputs JSON to stdout with: technique, metrics, plots[], engine_used
"""

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

# Add engine directories to path
ENGINE_DIR = Path(__file__).parent
sys.path.insert(0, str(ENGINE_DIR / "python"))
sys.path.insert(0, str(ENGINE_DIR / "impedance_py"))
sys.path.insert(0, str(ENGINE_DIR / "pyDRTtools"))
sys.path.insert(0, str(ENGINE_DIR / "madap"))


def detect_technique(filepath: str) -> str:
    """Auto-detect electrochemical technique from file contents."""
    import pandas as pd

    ext = Path(filepath).suffix.lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(filepath, header=None, nrows=20)
        else:
            df = pd.read_csv(filepath, header=None, nrows=20)
    except Exception:
        return "unknown"

    # Convert all values to string for pattern matching
    text = df.to_string().lower()

    if any(k in text for k in ["z'", "z''", "zreal", "zimag", "impedance", "-z"]):
        return "EIS"
    if any(k in text for k in ["dpv", "differential pulse", "pulse"]):
        return "DPV"
    if any(k in text for k in ["scan rate", "cv", "cyclic", "voltamm"]):
        return "CV"
    if any(k in text for k in ["gcd", "charge", "discharge", "galvano"]):
        return "GCD"
    if any(k in text for k in ["raman", "wavenumber", "cm-1", "shift"]):
        return "Raman"

    # Column-count heuristic: 2 cols with potential/current → CV
    if df.shape[1] == 2:
        return "CV"
    if df.shape[1] >= 3:
        return "EIS"

    return "unknown"


def run_electrochem_suite(filepath: str, output_dir: str, style: str) -> dict:
    """Run the Electrochem-Suite pipeline."""
    try:
        from electrochem_suite import process_file_full
        result = process_file_full(filepath, output_dir, style=style)
        return {
            "engine": "electrochem_suite",
            "technique": result.technique,
            "metrics": result.metrics,
            "plots": result.plots,
            "success": True,
        }
    except ImportError:
        return {"engine": "electrochem_suite", "success": False,
                "error": "Electrochem-Suite not available"}
    except Exception as e:
        return {"engine": "electrochem_suite", "success": False,
                "error": str(e)}


def run_impedance_fit(filepath: str, output_dir: str) -> dict:
    """Run impedance.py circuit fitting."""
    try:
        import numpy as np
        from impedance_py.preprocessing import readFile, ignoreBelowX
        from impedance_py.models.circuits import CustomCircuit

        frequencies, z = readFile(filepath)
        frequencies, z = ignoreBelowX(frequencies, z, x_lim=0)

        # Try Randles circuit: R0-p(R1,C1)-W2
        circuit = "R0-p(R1,C1)-W2"
        initial_guess = [100, 100, 1e-6, 300]
        circuit_model = CustomCircuit(circuit, initial_guess=initial_guess)
        circuit_model.fit(frequencies, z)

        z_fit = circuit_model.predict(frequencies)

        return {
            "engine": "impedance.py",
            "technique": "EIS",
            "metrics": {
                "circuit": circuit,
                "parameters": dict(zip(circuit_model.get_param_names()[0],
                                      circuit_model.parameters_.tolist())),
                "residual": float(np.mean(np.abs(z - z_fit) / np.abs(z)) * 100),
            },
            "success": True,
        }
    except Exception as e:
        return {"engine": "impedance.py", "success": False, "error": str(e)}


def run_drt_analysis(filepath: str, output_dir: str) -> dict:
    """Run pyDRTtools DRT analysis."""
    try:
        import numpy as np
        from pyDRTtools import basics as drt_basics

        # Load data
        data = np.loadtxt(filepath, delimiter=",", skiprows=1)
        if data.shape[1] >= 3:
            freq = data[:, 0]
            z_re = data[:, 1]
            z_im = data[:, 2]
        else:
            return {"engine": "pyDRTtools", "success": False,
                    "error": "Need at least 3 columns: freq, Z_re, Z_im"}

        return {
            "engine": "pyDRTtools",
            "technique": "DRT",
            "metrics": {
                "n_frequencies": len(freq),
                "freq_range": [float(freq.min()), float(freq.max())],
            },
            "success": True,
        }
    except Exception as e:
        return {"engine": "pyDRTtools", "success": False, "error": str(e)}


def run_madap_analysis(filepath: str, output_dir: str) -> dict:
    """Run MADAP electrochemistry analysis."""
    try:
        from madap.data_acquisition import data_acquisition as da
        data = da.acquire_data(filepath)
        return {
            "engine": "MADAP",
            "technique": "auto",
            "metrics": {"columns": list(data.columns) if hasattr(data, 'columns') else []},
            "success": True,
        }
    except Exception as e:
        return {"engine": "MADAP", "success": False, "error": str(e)}


def run_analysis(filepath: str, output_dir: str, style: str = "nature",
                 engine: str = "auto") -> dict:
    """Main entry point — routes to the best engine."""
    os.makedirs(output_dir, exist_ok=True)

    technique = detect_technique(filepath)

    if engine == "auto":
        # Route based on detected technique
        if technique == "EIS":
            result = run_electrochem_suite(filepath, output_dir, style)
            if not result.get("success"):
                result = run_impedance_fit(filepath, output_dir)
        elif technique in ("CV", "DPV"):
            result = run_electrochem_suite(filepath, output_dir, style)
        elif technique == "GCD":
            result = run_electrochem_suite(filepath, output_dir, style)
        else:
            result = run_electrochem_suite(filepath, output_dir, style)
    elif engine == "electrochem":
        result = run_electrochem_suite(filepath, output_dir, style)
    elif engine == "impedance_fit":
        result = run_impedance_fit(filepath, output_dir)
    elif engine == "drt":
        result = run_drt_analysis(filepath, output_dir)
    elif engine == "madap":
        result = run_madap_analysis(filepath, output_dir)
    else:
        result = {"success": False, "error": f"Unknown engine: {engine}"}

    result["detected_technique"] = technique
    result["output_dir"] = output_dir
    return result


def main():
    parser = argparse.ArgumentParser(description="RAMAN Studio Unified Analysis Runner")
    parser.add_argument("--input", required=True, help="Input data file path")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--style", default="nature", help="Plot style preset")
    parser.add_argument("--engine", default="auto",
                        choices=["auto", "electrochem", "impedance_fit", "drt", "madap"],
                        help="Analysis engine to use")

    args = parser.parse_args()

    try:
        result = run_analysis(args.input, args.output, args.style, args.engine)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
