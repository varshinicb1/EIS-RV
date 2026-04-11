"""
3D Viewer Widget
==================
OpenGL-based 3D preview window using pyqtgraph.

Features:
    - Real-time mesh rendering
    - Mouse rotation, zoom, pan
    - Electrode region color coding
    - Droplet overlay visualization
    - Axis indicators and grid
"""

import math
import numpy as np

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

try:
    import pyqtgraph.opengl as gl
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from ..ui.styles import COLORS


class Viewer3DWidget(QWidget):
    """
    3D CAD model preview widget with interactive controls.

    Uses pyqtgraph's GLViewWidget for hardware-accelerated rendering.
    """

    model_clicked = pyqtSignal(float, float, float)  # x, y, z

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mesh_items = []
        self._droplet_item = None
        self._grid_item = None
        self._axis_items = []
        self._annotation_items = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not HAS_PYQTGRAPH:
            label = QLabel("pyqtgraph not available.\nInstall: pip install pyqtgraph PyOpenGL")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #e74c3c; font-size: 12pt;")
            layout.addWidget(label)
            return

        # GL View widget
        self._gl_widget = gl.GLViewWidget()
        self._gl_widget.setBackgroundColor(28, 30, 36, 255)  # Match dark theme
        self._gl_widget.setCameraPosition(distance=30, elevation=30, azimuth=45)
        layout.addWidget(self._gl_widget)

        # Control bar
        control_bar = QHBoxLayout()
        control_bar.setContentsMargins(4, 2, 4, 2)

        btn_reset = QPushButton("Reset View")
        btn_reset.setMaximumWidth(80)
        btn_reset.clicked.connect(self.reset_view)
        control_bar.addWidget(btn_reset)

        btn_top = QPushButton("Top")
        btn_top.setMaximumWidth(50)
        btn_top.clicked.connect(lambda: self.set_view("top"))
        control_bar.addWidget(btn_top)

        btn_front = QPushButton("Front")
        btn_front.setMaximumWidth(50)
        btn_front.clicked.connect(lambda: self.set_view("front"))
        control_bar.addWidget(btn_front)

        btn_side = QPushButton("Side")
        btn_side.setMaximumWidth(50)
        btn_side.clicked.connect(lambda: self.set_view("side"))
        control_bar.addWidget(btn_side)

        btn_iso = QPushButton("Isometric")
        btn_iso.setMaximumWidth(70)
        btn_iso.clicked.connect(lambda: self.set_view("iso"))
        control_bar.addWidget(btn_iso)

        control_bar.addStretch()

        self._info_label = QLabel("No model loaded")
        self._info_label.setStyleSheet("color: #606570; font-size: 8pt;")
        control_bar.addWidget(self._info_label)

        layout.addLayout(control_bar)

        # Add base elements
        self._add_grid()
        self._add_axes()

    def _add_grid(self):
        """Add reference grid to the scene."""
        if not HAS_PYQTGRAPH:
            return

        grid = gl.GLGridItem()
        grid.setSize(40, 40)
        grid.setSpacing(2, 2)
        grid.setColor((60, 63, 70, 100))
        self._gl_widget.addItem(grid)
        self._grid_item = grid

    def _add_axes(self):
        """Add X/Y/Z axis indicators."""
        if not HAS_PYQTGRAPH:
            return

        axis_length = 8.0
        axis_data = [
            # X axis - red
            (np.array([[0, 0, 0], [axis_length, 0, 0]]), (255, 80, 80, 200)),
            # Y axis - green
            (np.array([[0, 0, 0], [0, axis_length, 0]]), (80, 255, 80, 200)),
            # Z axis - blue
            (np.array([[0, 0, 0], [0, 0, axis_length]]), (80, 80, 255, 200)),
        ]

        for pts, color in axis_data:
            line = gl.GLLinePlotItem(
                pos=pts, color=color,
                width=2.0, antialias=True
            )
            self._gl_widget.addItem(line)
            self._axis_items.append(line)

    def display_mesh(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        color=None,
        label: str = "substrate"
    ):
        """
        Display a triangle mesh in the viewer.

        Args:
            vertices: (N, 3) float32 array
            faces: (M, 3) int32 array
            color: RGBA tuple (0-1 range) or None for default
            label: Component label for identification
        """
        if not HAS_PYQTGRAPH:
            return

        if color is None:
            color = COLORS.get(label, COLORS["substrate"])

        # Create mesh colors array
        face_colors = np.zeros((len(faces), 4), dtype=np.float32)
        face_colors[:] = color

        mesh_item = gl.GLMeshItem(
            vertexes=vertices,
            faces=faces,
            faceColors=face_colors,
            smooth=True,
            drawEdges=True,
            edgeColor=(0.3, 0.3, 0.35, 0.4),
        )

        self._gl_widget.addItem(mesh_item)
        self._mesh_items.append(mesh_item)

        # Update info
        self._info_label.setText(
            f"Vertices: {len(vertices):,} | Faces: {len(faces):,}"
        )

    def display_droplet(
        self,
        vertices: np.ndarray,
        faces: np.ndarray
    ):
        """Display the droplet overlay (semi-transparent)."""
        if not HAS_PYQTGRAPH:
            return

        self.clear_droplet()

        color = COLORS["droplet"]
        face_colors = np.zeros((len(faces), 4), dtype=np.float32)
        face_colors[:] = color

        droplet = gl.GLMeshItem(
            vertexes=vertices,
            faces=faces,
            faceColors=face_colors,
            smooth=True,
            drawEdges=False,
        )
        droplet.setGLOptions('translucent')

        self._gl_widget.addItem(droplet)
        self._droplet_item = droplet

    def add_annotation_ring(
        self,
        center: tuple,
        radius: float,
        color: tuple,
        label: str = "",
        z_offset: float = 0.05,
        n_points: int = 64
    ):
        """
        Add a colored ring annotation (for WE/RE/CE marking).
        """
        if not HAS_PYQTGRAPH:
            return

        cx, cy, cz = center
        angles = np.linspace(0, 2 * math.pi, n_points + 1)
        pts = np.zeros((n_points + 1, 3), dtype=np.float32)
        pts[:, 0] = cx + radius * np.cos(angles)
        pts[:, 1] = cy + radius * np.sin(angles)
        pts[:, 2] = cz + z_offset

        rgba = tuple(int(c * 255) for c in color[:3]) + (255,)
        line = gl.GLLinePlotItem(
            pos=pts, color=rgba,
            width=2.5, antialias=True
        )
        self._gl_widget.addItem(line)
        self._annotation_items.append(line)

    def clear_model(self):
        """Remove all mesh items from the viewer."""
        if not HAS_PYQTGRAPH:
            return

        for item in self._mesh_items:
            self._gl_widget.removeItem(item)
        self._mesh_items.clear()

        self.clear_droplet()
        self.clear_annotations()

        self._info_label.setText("No model loaded")

    def clear_droplet(self):
        """Remove the droplet overlay."""
        if self._droplet_item is not None:
            self._gl_widget.removeItem(self._droplet_item)
            self._droplet_item = None

    def clear_annotations(self):
        """Remove all annotation items."""
        if not HAS_PYQTGRAPH:
            return
        for item in self._annotation_items:
            self._gl_widget.removeItem(item)
        self._annotation_items.clear()

    def reset_view(self):
        """Reset camera to default isometric view."""
        if not HAS_PYQTGRAPH:
            return
        self._gl_widget.setCameraPosition(distance=30, elevation=30, azimuth=45)

    def set_view(self, view_name: str):
        """Set camera to a predefined view."""
        if not HAS_PYQTGRAPH:
            return

        views = {
            "top": {"distance": 25, "elevation": 90, "azimuth": 0},
            "front": {"distance": 25, "elevation": 0, "azimuth": 0},
            "side": {"distance": 25, "elevation": 0, "azimuth": 90},
            "iso": {"distance": 30, "elevation": 30, "azimuth": 45},
        }

        if view_name in views:
            self._gl_widget.setCameraPosition(**views[view_name])

    def fit_to_model(self, bounds: dict):
        """Adjust camera distance to fit the model in view."""
        if not HAS_PYQTGRAPH:
            return

        size = bounds.get("size", 20.0)
        center = bounds.get("center", [0, 0, 0])

        self._gl_widget.setCameraPosition(
            distance=size * 2.0,
            elevation=30,
            azimuth=45
        )
        self._gl_widget.pan(center[0], center[1], center[2])
