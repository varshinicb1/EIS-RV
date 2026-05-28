"""
Raman Material Identification Visualization
============================================
Visualization tools for material identification and spectral matching.

Features:
- Spectral comparison plots
- Peak matching visualization
- Confidence score visualization
- Material database browser
- Interactive spectral library

Author: VidyuthLabs
Date: May 6, 2026
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.backend.ml.models.raman_material_identifier import (
    RamanMaterialIdentifier,
    MaterialMatch
)

logger = logging.getLogger(__name__)


class RamanMaterialVisualizer:
    """
    Visualization tools for Raman material identification.
    """
    
    def __init__(self, identifier: Optional[RamanMaterialIdentifier] = None):
        """
        Initialize visualizer.
        
        Args:
            identifier: RamanMaterialIdentifier instance (optional)
        """
        self.identifier = identifier or RamanMaterialIdentifier()
        
        # Set matplotlib style
        plt.style.use('seaborn-v0_8-darkgrid')
    
    def plot_material_match(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
        detected_peaks: List[Dict[str, Any]],
        match: MaterialMatch,
        save_path: Optional[str] = None,
        show: bool = True
    ):
        """
        Plot measured spectrum with material match overlay.
        
        Args:
            wavenumber: Measured wavenumber array
            intensity: Measured intensity array
            detected_peaks: List of detected peaks
            match: MaterialMatch object
            save_path: Path to save figure (optional)
            show: Whether to show figure
        """
        fig = plt.figure(figsize=(14, 10))
        gs = GridSpec(3, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # Main spectrum plot
        ax1 = fig.add_subplot(gs[0:2, :])
        
        # Plot measured spectrum
        ax1.plot(wavenumber, intensity, 'k-', linewidth=1.5, label='Measured', alpha=0.7)
        
        # Plot detected peaks
        for peak in detected_peaks:
            pos = peak['position_cm']
            idx = np.argmin(np.abs(wavenumber - pos))
            ax1.plot(pos, intensity[idx], 'ro', markersize=8, label='Detected peak' if peak == detected_peaks[0] else '')
            ax1.axvline(pos, color='red', linestyle='--', alpha=0.3)
        
        # Plot reference peaks
        material = self.identifier.get_material_by_id(match.material_id)
        if material:
            ref_peaks = material.get('reference_peaks', [])
            
            # Generate synthetic reference spectrum
            ref_intensity = np.zeros_like(wavenumber)
            for ref_peak in ref_peaks:
                pos = ref_peak['position_cm']
                amp = ref_peak.get('intensity_relative', 1.0)
                fwhm = ref_peak.get('fwhm_cm', 20)
                gamma = fwhm / 2
                ref_intensity += amp * (gamma**2) / ((wavenumber - pos)**2 + gamma**2)
            
            # Normalize and scale
            ref_intensity = ref_intensity / ref_intensity.max() * intensity.max() * 0.8
            
            # Plot reference spectrum
            ax1.plot(wavenumber, ref_intensity, 'b-', linewidth=1.5, label='Reference', alpha=0.5)
            
            # Plot reference peaks
            for ref_peak in ref_peaks:
                pos = ref_peak['position_cm']
                ax1.axvline(pos, color='blue', linestyle=':', alpha=0.5)
                
                # Add peak assignment labels
                assignment = ref_peak.get('assignment', '')
                if assignment:
                    idx = np.argmin(np.abs(wavenumber - pos))
                    ax1.text(pos, intensity[idx] * 1.1, assignment, 
                            rotation=90, fontsize=8, ha='center', va='bottom')
        
        ax1.set_xlabel('Raman Shift (cm⁻¹)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Intensity (a.u.)', fontsize=12, fontweight='bold')
        ax1.set_title(f'Material Match: {match.name} ({match.formula})\n'
                     f'Confidence: {match.confidence:.3f} | Quality: {match.quality_score:.3f}',
                     fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right', fontsize=10)
        ax1.grid(True, alpha=0.3)
        
        # Peak matching table
        ax2 = fig.add_subplot(gs[2, 0])
        ax2.axis('off')
        
        # Create table data
        table_data = [['Ref. Peak', 'Det. Peak', 'Δ (cm⁻¹)', 'Assignment']]
        for pm in match.peak_matches[:8]:  # Show first 8 matches
            ref_pos = f"{pm['reference_position_cm']:.1f}"
            det_pos = f"{pm['detected_position_cm']:.1f}" if pm['matched'] else 'N/A'
            delta = f"{pm['distance_cm']:.1f}" if pm['matched'] else 'N/A'
            assignment = pm.get('assignment', '')[:20]  # Truncate long assignments
            table_data.append([ref_pos, det_pos, delta, assignment])
        
        table = ax2.table(cellText=table_data, cellLoc='center', loc='center',
                         colWidths=[0.2, 0.2, 0.2, 0.4])
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 2)
        
        # Header row styling
        for i in range(4):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')
        
        # Matched rows in green, unmatched in red
        for i, pm in enumerate(match.peak_matches[:8], 1):
            color = '#C8E6C9' if pm['matched'] else '#FFCDD2'
            for j in range(4):
                table[(i, j)].set_facecolor(color)
        
        ax2.set_title('Peak Matching Details', fontsize=10, fontweight='bold', pad=10)
        
        # Confidence metrics
        ax3 = fig.add_subplot(gs[2, 1])
        
        metrics = {
            'Confidence': match.confidence,
            'Match Ratio': match.matched_peaks / match.total_expected_peaks if match.total_expected_peaks > 0 else 0,
            'Quality Score': match.quality_score,
            'Spectral Sim.': match.spectral_similarity
        }
        
        colors = ['#4CAF50' if v >= 0.7 else '#FFC107' if v >= 0.5 else '#F44336' for v in metrics.values()]
        
        bars = ax3.barh(list(metrics.keys()), list(metrics.values()), color=colors, alpha=0.7)
        ax3.set_xlim(0, 1)
        ax3.set_xlabel('Score', fontsize=10, fontweight='bold')
        ax3.set_title('Identification Metrics', fontsize=10, fontweight='bold')
        ax3.grid(True, alpha=0.3, axis='x')
        
        # Add value labels
        for i, (bar, value) in enumerate(zip(bars, metrics.values())):
            ax3.text(value + 0.02, i, f'{value:.3f}', va='center', fontsize=9, fontweight='bold')
        
        plt.suptitle(f'Raman Material Identification Report\n{match.description}',
                    fontsize=16, fontweight='bold', y=0.98)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Saved material match plot to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def plot_top_matches(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
        detected_peaks: List[Dict[str, Any]],
        matches: List[MaterialMatch],
        save_path: Optional[str] = None,
        show: bool = True
    ):
        """
        Plot top N material matches comparison.
        
        Args:
            wavenumber: Measured wavenumber array
            intensity: Measured intensity array
            detected_peaks: List of detected peaks
            matches: List of MaterialMatch objects
            save_path: Path to save figure (optional)
            show: Whether to show figure
        """
        n_matches = min(len(matches), 5)
        
        fig, axes = plt.subplots(n_matches + 1, 1, figsize=(14, 4 * (n_matches + 1)))
        
        if n_matches == 0:
            axes[0].text(0.5, 0.5, 'No matches found', ha='center', va='center', fontsize=16)
            axes[0].axis('off')
            return
        
        # Plot measured spectrum
        ax = axes[0]
        ax.plot(wavenumber, intensity, 'k-', linewidth=1.5, label='Measured')
        
        for peak in detected_peaks:
            pos = peak['position_cm']
            idx = np.argmin(np.abs(wavenumber - pos))
            ax.plot(pos, intensity[idx], 'ro', markersize=8)
            ax.axvline(pos, color='red', linestyle='--', alpha=0.3)
        
        ax.set_xlabel('Raman Shift (cm⁻¹)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Intensity (a.u.)', fontsize=11, fontweight='bold')
        ax.set_title('Measured Spectrum', fontsize=12, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot each match
        for i, match in enumerate(matches[:n_matches], 1):
            ax = axes[i]
            
            # Plot measured spectrum (faded)
            ax.plot(wavenumber, intensity, 'k-', linewidth=1, alpha=0.3, label='Measured')
            
            # Generate and plot reference spectrum
            material = self.identifier.get_material_by_id(match.material_id)
            if material:
                ref_peaks = material.get('reference_peaks', [])
                ref_intensity = np.zeros_like(wavenumber)
                
                for ref_peak in ref_peaks:
                    pos = ref_peak['position_cm']
                    amp = ref_peak.get('intensity_relative', 1.0)
                    fwhm = ref_peak.get('fwhm_cm', 20)
                    gamma = fwhm / 2
                    ref_intensity += amp * (gamma**2) / ((wavenumber - pos)**2 + gamma**2)
                
                ref_intensity = ref_intensity / ref_intensity.max() * intensity.max()
                
                ax.plot(wavenumber, ref_intensity, 'b-', linewidth=1.5, label='Reference')
                
                # Plot reference peaks
                for ref_peak in ref_peaks:
                    pos = ref_peak['position_cm']
                    ax.axvline(pos, color='blue', linestyle=':', alpha=0.5)
            
            ax.set_xlabel('Raman Shift (cm⁻¹)', fontsize=11, fontweight='bold')
            ax.set_ylabel('Intensity (a.u.)', fontsize=11, fontweight='bold')
            ax.set_title(f'#{i}: {match.name} ({match.formula}) - '
                        f'Confidence: {match.confidence:.3f} | '
                        f'Matched: {match.matched_peaks}/{match.total_expected_peaks}',
                        fontsize=12, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.suptitle('Top Material Matches', fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Saved top matches plot to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def plot_database_overview(
        self,
        save_path: Optional[str] = None,
        show: bool = True
    ):
        """
        Plot overview of material database.
        
        Args:
            save_path: Path to save figure (optional)
            show: Whether to show figure
        """
        stats = self.identifier.get_statistics()
        
        fig = plt.figure(figsize=(16, 10))
        gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # Category distribution
        ax1 = fig.add_subplot(gs[0, 0])
        categories = stats['categories']
        ax1.bar(range(len(categories)), list(categories.values()), color='#4CAF50', alpha=0.7)
        ax1.set_xticks(range(len(categories)))
        ax1.set_xticklabels(list(categories.keys()), rotation=45, ha='right')
        ax1.set_ylabel('Number of Materials', fontsize=11, fontweight='bold')
        ax1.set_title('Materials by Category', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Peak distribution
        ax2 = fig.add_subplot(gs[0, 1])
        peak_counts = [len(m.get('reference_peaks', [])) for m in self.identifier.materials]
        ax2.hist(peak_counts, bins=range(1, max(peak_counts) + 2), color='#2196F3', alpha=0.7, edgecolor='black')
        ax2.set_xlabel('Number of Reference Peaks', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Number of Materials', fontsize=11, fontweight='bold')
        ax2.set_title('Peak Count Distribution', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Peak position heatmap
        ax3 = fig.add_subplot(gs[1, :])
        
        # Collect all peaks by category
        category_peaks = {}
        for material in self.identifier.materials:
            cat = material.get('category', 'unknown')
            if cat not in category_peaks:
                category_peaks[cat] = []
            
            for peak in material.get('reference_peaks', []):
                category_peaks[cat].append(peak['position_cm'])
        
        # Plot peaks by category
        y_pos = 0
        y_labels = []
        for cat, peaks in sorted(category_peaks.items()):
            ax3.scatter(peaks, [y_pos] * len(peaks), alpha=0.6, s=50)
            y_labels.append(f"{cat} ({len(peaks)})")
            y_pos += 1
        
        ax3.set_yticks(range(len(y_labels)))
        ax3.set_yticklabels(y_labels)
        ax3.set_xlabel('Raman Shift (cm⁻¹)', fontsize=11, fontweight='bold')
        ax3.set_title('Peak Position Distribution by Category', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3, axis='x')
        
        # Add statistics text
        stats_text = f"Total Materials: {stats['total_materials']}\n"
        stats_text += f"Total Reference Peaks: {stats['total_reference_peaks']}\n"
        stats_text += f"Avg Peaks/Material: {stats['average_peaks_per_material']:.1f}"
        
        fig.text(0.02, 0.98, stats_text, fontsize=12, fontweight='bold',
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.suptitle('Raman Material Database Overview', fontsize=16, fontweight='bold', y=0.995)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Saved database overview to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def plot_spectral_library(
        self,
        category: Optional[str] = None,
        wavenumber_range: Tuple[float, float] = (100, 3500),
        save_path: Optional[str] = None,
        show: bool = True
    ):
        """
        Plot spectral library for a category.
        
        Args:
            category: Material category (None for all)
            wavenumber_range: Wavenumber range to plot
            save_path: Path to save figure (optional)
            show: Whether to show figure
        """
        # Get materials
        if category:
            materials = self.identifier.get_materials_by_category(category)
        else:
            materials = self.identifier.materials
        
        if not materials:
            logger.warning(f"No materials found for category: {category}")
            return
        
        # Generate wavenumber array
        wavenumber = np.linspace(wavenumber_range[0], wavenumber_range[1], 2000)
        
        # Create figure
        n_materials = len(materials)
        fig, axes = plt.subplots(n_materials, 1, figsize=(14, 3 * n_materials))
        
        if n_materials == 1:
            axes = [axes]
        
        for i, material in enumerate(materials):
            ax = axes[i]
            
            # Generate synthetic spectrum
            ref_peaks = material.get('reference_peaks', [])
            intensity = np.zeros_like(wavenumber)
            
            for ref_peak in ref_peaks:
                pos = ref_peak['position_cm']
                amp = ref_peak.get('intensity_relative', 1.0)
                fwhm = ref_peak.get('fwhm_cm', 20)
                gamma = fwhm / 2
                intensity += amp * (gamma**2) / ((wavenumber - pos)**2 + gamma**2)
            
            # Plot spectrum
            ax.plot(wavenumber, intensity, 'b-', linewidth=1.5)
            ax.fill_between(wavenumber, intensity, alpha=0.3)
            
            # Mark peaks
            for ref_peak in ref_peaks:
                pos = ref_peak['position_cm']
                ax.axvline(pos, color='red', linestyle='--', alpha=0.5)
                assignment = ref_peak.get('assignment', '')
                if assignment:
                    idx = np.argmin(np.abs(wavenumber - pos))
                    ax.text(pos, intensity[idx] * 1.1, assignment,
                           rotation=90, fontsize=8, ha='center', va='bottom')
            
            ax.set_ylabel('Intensity', fontsize=10, fontweight='bold')
            ax.set_title(f"{material['name']} ({material.get('formula', '')})",
                        fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            if i == n_materials - 1:
                ax.set_xlabel('Raman Shift (cm⁻¹)', fontsize=11, fontweight='bold')
        
        title = f'Raman Spectral Library - {category}' if category else 'Raman Spectral Library - All Materials'
        plt.suptitle(title, fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Saved spectral library to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()


if __name__ == "__main__":
    # Test visualizer
    logging.basicConfig(level=logging.INFO)
    
    visualizer = RamanMaterialVisualizer()
    
    # Plot database overview
    visualizer.plot_database_overview(save_path="raman_database_overview.png", show=False)
    
    # Plot spectral library for carbon materials
    visualizer.plot_spectral_library(category="carbon", save_path="raman_carbon_library.png", show=False)
    
    print("✅ Visualization test complete!")
    print("Generated:")
    print("  - raman_database_overview.png")
    print("  - raman_carbon_library.png")
