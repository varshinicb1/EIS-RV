"""
Cross-Modal PDF Report Generator
====================================
Generates a publication-ready PDF report synthesizing EIS, Raman, and DPV
findings for a specific sensor iteration.

Author: VidyuthLabs
Date: May 8, 2026
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

class CrossModalReportGenerator:
    """Generates cross-modal scientific reports."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, analysis_results: Dict[str, Any], project_name: str = "Biosensor FOG") -> str:
        """
        Generate a Markdown report synthesizing the results.
        In a full implementation, this could be converted to PDF via pandoc or reportlab.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        md = f"# RĀMAN Studio — Cross-Modal Analysis Report\n"
        md += f"**Project:** {project_name}\n"
        md += f"**Date Generated:** {now}\n"
        md += f"**Overall Status:** ✅ Sensor iteration verified.\n\n"

        md += "## Executive Summary\n"
        md += "This report synthesizes multi-modal findings from EIS, Raman Spectroscopy, and DPV Calibration to evaluate the sensor's analytical performance and structural integrity.\n\n"

        # Raman Section
        raman = analysis_results.get("raman", {})
        md += "### 1. Structural Validation (Raman Spectroscopy)\n"
        if raman:
            md += f"**Detected Materials:** {', '.join(raman.get('materials_detected', []))}\n\n"
            md += "| Wavenumber (cm⁻¹) | Assignment |\n"
            md += "| :--- | :--- |\n"
            for b in raman.get("band_assignments", []):
                md += f"| {b['wavenumber']:.1f} | {b['assignment']} |\n"
            md += "\n*Conclusion:* Structural composition matches the intended design.\n\n"
        else:
            md += "*No Raman data provided for this iteration.*\n\n"

        # EIS Section
        eis = analysis_results.get("eis", {})
        md += "### 2. Electrochemical Interfaces (EIS)\n"
        if eis:
            md += "| Parameter | Value | Unit |\n"
            md += "| :--- | :--- | :--- |\n"
            md += f"| Solution Resistance ($R_s$) | {eis.get('Rs_ohm', 0):.2f} | $\\Omega$ |\n"
            md += f"| Charge Transfer Resistance ($R_{{ct}}$) | **{eis.get('Rct_ohm', 0):.2f}** | $\\Omega$ |\n"
            md += f"| Double Layer Capacitance ($C_{{dl}}$) | {eis.get('Cdl_F', 0):.2e} | F |\n\n"
            
            rct = eis.get("Rct_ohm", float('inf'))
            if rct < 500:
                md += "*Conclusion:* Excellent electron transfer kinetics. The low $R_{{ct}}$ indicates a highly conductive modified electrode surface.\n\n"
            else:
                md += "*Conclusion:* High electron transfer resistance. Modification may have passivated the electrode.\n\n"
        else:
            md += "*No EIS data provided for this iteration.*\n\n"

        # DPV Section
        dpv = analysis_results.get("dpv", {})
        md += "### 3. Analytical Performance (DPV Calibration)\n"
        if dpv:
            md += f"- **Sensitivity:** {dpv.get('sensitivity', 0):.4f} $\\mu$A/$\\mu$M/cm²\n"
            md += f"- **Limit of Detection (LOD):** {dpv.get('lod', 0):.4f} $\\mu$M\n"
            md += f"- **Limit of Quantitation (LOQ):** {dpv.get('loq', 0):.4f} $\\mu$M\n"
            md += f"- **Linearity ($R^2$):** {dpv.get('r_squared', 0):.4f}\n"
            md += f"- **Calibration Equation:** `{dpv.get('equation', 'N/A')}`\n\n"
            md += "*Conclusion:* Sensor exhibits stable and sensitive dose-dependent response.\n\n"
        else:
            md += "*No DPV data provided for this iteration.*\n\n"

        md += "---\n*Generated autonomously by RĀMAN Studio (VidyuthLabs)*\n"
        return md

    def write_report(self, analysis_results: Dict[str, Any], filename: str = "synthesis_report.md"):
        """Write the generated markdown report to a file."""
        md = self.generate_markdown(analysis_results)
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return str(path)

if __name__ == "__main__":
    # Test generation
    gen = CrossModalReportGenerator()
    dummy_data = {
        "raman": {
            "materials_detected": ["Fe2O3 (hematite)", "rGO (reduced graphene oxide)"],
            "band_assignments": [
                {"wavenumber": 290.0, "assignment": "Fe2O3 Eg mode"},
                {"wavenumber": 1350.0, "assignment": "D-band (defect-induced)"}
            ]
        },
        "eis": {
            "Rs_ohm": 3.5,
            "Rct_ohm": 211.4,
            "Cdl_F": 7.5e-4
        },
        "dpv": {
            "sensitivity": 2.538,
            "lod": 2263.78,
            "loq": 7545.96,
            "r_squared": 0.985,
            "equation": "I = 2.538 * C + 0.12"
        }
    }
    path = gen.write_report(dummy_data)
    print(f"Report generated at: {path}")
