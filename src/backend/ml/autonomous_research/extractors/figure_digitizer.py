"""
Figure digitizer for extracting data from scientific figures.
Uses computer vision to extract plots and tables from figures.
"""

import logging
import cv2
import numpy as np
from typing import Dict, Any, Optional, List
import base64
from .base_extractor import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)

class FigureDigitizer(BaseExtractor):
    """Extract numerical data from figures in papers."""
    
    def __init__(self, name: str = "FigureDigitizer"):
        """Initialize figure digitizer."""
        super().__init__(name)
    
    def extract(self, paper: Dict[str, Any]) -> ExtractionResult:
        """Extract figures from paper PDF."""
        try:
            # This would integrate with a figure extraction library
            # For now, implement basic image processing
            
            figures = paper.get("_figures", [])
            extracted_data = []
            
            for i, figure in enumerate(figures):
                # Convert base64 image to numpy array
                if isinstance(figure, str) and figure.startswith("data:image"):
                    img_data = base64.b64decode(figure.split(",")[1])
                    img_array = np.frombuffer(img_data, dtype=np.uint8)
                    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    # Detect axes
                    axes = self._detect_axes(img)
                    
                    # Extract plot data
                    plot_data = self._extract_plot_data(img, axes)
                    
                    if plot_data:
                        extracted_data.append({
                            "figure_index": i,
                            "type": "plot",
                            "x_data": plot_data.get("x", []),
                            "y_data": plot_data.get("y", []),
                            "axes_labels": plot_data.get("labels", {})
                        })
            
            return ExtractionResult(
                success=len(extracted_data) > 0,
                data={"figures": extracted_data},
                method='figure_digitizer'
            )
            
        except Exception as e:
            logger.error(f"Figure extraction failed: {e}")
            return ExtractionResult(
                success=False,
                error=str(e),
                method='figure_digitizer'
            )
    
    def _detect_axes(self, img: np.ndarray) -> Dict[str, Any]:
        """Detect x and y axes in figure."""
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Hough line transform to detect axis lines
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
        
        axes = {"x_axis": None, "y_axis": None}
        
        if lines is not None:
            # Classify lines as horizontal (x-axis) or vertical (y-axis)
            horizontal_lines = []
            vertical_lines = []
            
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                
                if abs(angle) < 10 or abs(angle) > 170:
                    horizontal_lines.append(line[0])
                elif abs(angle - 90) < 10 or abs(angle + 90) < 10:
                    vertical_lines.append(line[0])
            
            if horizontal_lines:
                axes["x_axis"] = horizontal_lines[0]
            if vertical_lines:
                axes["y_axis"] = vertical_lines[0]
        
        return axes
    
    def _extract_plot_data(self, img: np.ndarray, axes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract x,y data from plot."""
        # This is a simplified implementation
        # Real implementation would use more sophisticated algorithms
        
        if not axes.get("x_axis") or not axes.get("y_axis"):
            return None
        
        # Extract data points (placeholder)
        # In production, use libraries like plotdigitizer or WebPlotDigitizer
        
        return {
            "x": [],
            "y": [],
            "labels": {"x": "x", "y": "y"}
        }
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate extracted figure data."""
        if not data or "figures" not in data:
            return False
        
        for figure in data["figures"]:
            if not figure.get("x_data") or not figure.get("y_data"):
                return False
        
        return True
