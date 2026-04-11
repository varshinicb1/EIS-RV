"""
Main Application Window
=========================
Central orchestrator for the AnalyteX MicroWell Designer.

Layout:
    ┌──────────────────────────────────────────────────────────┐
    │  Menu Bar                                                │
    ├──────────┬──────────────────────────┬────────────────────┤
    │ Left     │  Center                  │  Right             │
    │ Panel    │  3D Viewer               │  Panel             │
    │          │                          │                    │
    │ Params   │  [Interactive 3D View]   │  Validation        │
    │          │                          │  Simulation        │
    │          │                          │  Export             │
    ├──────────┴──────────────────────────┴────────────────────┤
    │  Status Bar                                              │
    └──────────────────────────────────────────────────────────┘
"""

import os
import sys
import math
import traceback
import copy

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QStatusBar, QLabel, QFileDialog, QMessageBox,
    QApplication, QDockWidget, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QKeySequence

from .parameter_panel import ParameterPanel
from .viewer_widget import Viewer3DWidget
from .validation_panel import ValidationPanel
from .sweep_dialog import SweepDialog
from .styles import STATUS_COLORS

from ..core.geometry_engine import (
    GeometryEngine, DesignProfile, WellArrayType
)
from ..core.constraints import validate_design
from ..core.validation import validate_for_manufacturing
from ..core.droplet_sim import (
    compute_droplet_profile, estimate_evaporation, generate_droplet_mesh
)
from ..core.presets import (
    get_builtin_presets, profile_to_dict, dict_to_profile,
    save_preset, load_preset
)
from ..core.exporter import export_step, export_stl, ExportFormat
from ..utils.mesh_utils import workplane_to_mesh, compute_mesh_bounds
from ..utils.profile_io import save_profile, load_profile


class GenerateThread(QThread):
    """Background thread for geometry generation."""
    finished = pyqtSignal(object)  # workplane
    error = pyqtSignal(str)

    def __init__(self, engine, profile):
        super().__init__()
        self._engine = engine
        self._profile = profile

    def run(self):
        try:
            result = self._engine.generate(self._profile)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{str(e)}\n\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    """Main application window for AnalyteX MicroWell Designer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AnalyteX MicroWell Designer v1.0")
        self.setMinimumSize(1200, 700)

        # Core objects
        self._engine = GeometryEngine()
        self._current_profile = None
        self._current_workplane = None
        self._generate_thread = None

        self._setup_ui()
        self._setup_menus()
        self._setup_statusbar()
        self._connect_signals()

        # Load default preset
        self._load_default()

    # ------------------------------------------------------------------
    #   UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the three-panel layout."""

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main splitter (three panels)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Parameter Panel
        self._param_panel = ParameterPanel()
        self._splitter.addWidget(self._param_panel)

        # Center: 3D Viewer
        self._viewer = Viewer3DWidget()
        self._splitter.addWidget(self._viewer)

        # Right: Validation Panel
        self._validation_panel = ValidationPanel()
        self._splitter.addWidget(self._validation_panel)

        # Set initial proportions (20%, 55%, 25%)
        self._splitter.setSizes([280, 640, 320])

        main_layout.addWidget(self._splitter)

    def _setup_menus(self):
        """Create application menus."""
        menubar = self.menuBar()

        # --- File Menu ---
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Design", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_design)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        save_action = QAction("&Save Profile...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_profile)
        file_menu.addAction(save_action)

        load_action = QAction("&Load Profile...", self)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(self._load_profile)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        export_step_action = QAction("Export &STEP...", self)
        export_step_action.setShortcut(QKeySequence("Ctrl+E"))
        export_step_action.triggered.connect(self._export_step_dialog)
        file_menu.addAction(export_step_action)

        export_stl_action = QAction("Export S&TL...", self)
        export_stl_action.triggered.connect(self._export_stl_dialog)
        file_menu.addAction(export_stl_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Edit Menu ---
        edit_menu = menubar.addMenu("&Edit")

        generate_action = QAction("&Generate Model", self)
        generate_action.setShortcut(QKeySequence("F5"))
        generate_action.triggered.connect(self._generate_model)
        edit_menu.addAction(generate_action)

        edit_menu.addSeparator()

        validate_action = QAction("Run &Validation", self)
        validate_action.setShortcut(QKeySequence("F6"))
        validate_action.triggered.connect(self._run_validation_only)
        edit_menu.addAction(validate_action)

        # --- Presets Menu ---
        presets_menu = menubar.addMenu("&Presets")

        for name, profile in get_builtin_presets().items():
            action = QAction(name, self)
            action.triggered.connect(
                lambda checked, p=profile: self._apply_preset(p)
            )
            presets_menu.addAction(action)

        # --- Tools Menu ---
        tools_menu = menubar.addMenu("&Tools")

        sweep_action = QAction("Parametric &Sweep...", self)
        sweep_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        sweep_action.triggered.connect(self._open_sweep_dialog)
        tools_menu.addAction(sweep_action)

        # --- View Menu ---
        view_menu = menubar.addMenu("&View")

        reset_view_action = QAction("&Reset Camera", self)
        reset_view_action.setShortcut(QKeySequence("Home"))
        reset_view_action.triggered.connect(self._viewer.reset_view)
        view_menu.addAction(reset_view_action)

        view_menu.addSeparator()

        for view_name in ["Top", "Front", "Side", "Isometric"]:
            action = QAction(f"{view_name} View", self)
            action.triggered.connect(
                lambda checked, vn=view_name.lower(): self._viewer.set_view(
                    "iso" if vn == "isometric" else vn
                )
            )
            view_menu.addAction(action)

        # --- Help Menu ---
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        """Configure the status bar."""
        self._statusbar = self.statusBar()

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(
            f"color: {STATUS_COLORS['ready']}; padding: 0 8px;"
        )
        self._statusbar.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setMaximumWidth(120)
        self._progress.setMaximumHeight(14)
        self._progress.setVisible(False)
        self._statusbar.addPermanentWidget(self._progress)

        self._version_label = QLabel("AnalyteX v1.0.0")
        self._version_label.setStyleSheet("color: #505560; padding: 0 8px;")
        self._statusbar.addPermanentWidget(self._version_label)

    def _connect_signals(self):
        """Wire up all signal/slot connections."""
        self._param_panel.generate_requested.connect(self._generate_model)
        self._param_panel.parameters_changed.connect(self._on_params_changed)

        self._validation_panel.export_step_requested.connect(self._export_step)
        self._validation_panel.export_stl_requested.connect(self._export_stl)
        self._validation_panel.show_droplet_requested.connect(self._show_droplet)
        self._validation_panel.hide_droplet_requested.connect(self._viewer.clear_droplet)

    # ------------------------------------------------------------------
    #   Core Actions
    # ------------------------------------------------------------------

    def _load_default(self):
        """Load the default Standard preset."""
        presets = get_builtin_presets()
        default = presets.get("Standard Electrochemical Well")
        if default:
            self._param_panel.set_profile(default)
            self._on_params_changed()

    def _generate_model(self):
        """Generate the 3D model from current parameters."""
        profile = self._param_panel.get_profile()
        self._current_profile = profile

        self._set_status("Generating geometry...", "generating")
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # Indeterminate

        # Run in background thread
        self._generate_thread = GenerateThread(self._engine, profile)
        self._generate_thread.finished.connect(self._on_generate_complete)
        self._generate_thread.error.connect(self._on_generate_error)
        self._generate_thread.start()

    def _on_generate_complete(self, workplane):
        """Handle successful geometry generation."""
        self._current_workplane = workplane
        self._progress.setVisible(False)

        try:
            # Tessellate for visualization
            vertices, faces, normals = workplane_to_mesh(workplane, tolerance=0.05)

            # Display in viewer
            self._viewer.clear_model()
            self._viewer.display_mesh(vertices, faces, label="substrate")

            # Add electrode annotations if enabled
            if self._current_profile.electrode.enabled:
                self._add_electrode_annotations()

            # Fit camera to model
            bounds = compute_mesh_bounds(vertices)
            self._viewer.fit_to_model(bounds)

            # Run validation
            self._run_validation()

            # Run simulation
            self._run_simulation()

            # Update export info
            self._update_export_info()

            n_wells = len(self._engine.get_well_positions())
            dims = self._engine.get_substrate_dimensions()
            self._set_status(
                f"✓ Model generated — {n_wells} well(s), "
                f"{dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} mm",
                "success"
            )

        except Exception as e:
            self._set_status(f"Display error: {str(e)}", "error")
            traceback.print_exc()

    def _on_generate_error(self, message):
        """Handle geometry generation failure."""
        self._progress.setVisible(False)
        self._set_status("✗ Generation failed", "error")
        QMessageBox.critical(
            self, "Generation Error",
            f"Failed to generate model:\n\n{message}"
        )

    def _on_params_changed(self):
        """Quick-update validation when parameters change."""
        profile = self._param_panel.get_profile()
        self._current_profile = profile

        # Quick constraint check (no geometry needed)
        try:
            constraint_report = validate_design(profile)
            self._validation_panel.update_constraints(constraint_report)
        except Exception:
            pass

    def _run_validation(self):
        """Run full design validation."""
        if not self._current_profile:
            return

        try:
            method = self._validation_panel.get_manufacturing_method()
            constraint_report = validate_design(self._current_profile)
            validation_report = validate_for_manufacturing(
                self._current_profile, method
            )

            self._validation_panel.update_constraints(constraint_report)
            self._validation_panel.update_validation(validation_report)
        except Exception as e:
            print(f"Validation error: {e}")

    def _run_validation_only(self):
        """Run validation without regenerating geometry."""
        self._on_params_changed()
        if self._current_profile:
            method = self._validation_panel.get_manufacturing_method()
            validation_report = validate_for_manufacturing(
                self._current_profile, method
            )
            self._validation_panel.update_validation(validation_report)
            self._set_status("Validation complete", "ready")

    def _run_simulation(self):
        """Run droplet simulation."""
        if not self._current_profile:
            return

        try:
            well = self._current_profile.well
            surface = self._current_profile.surface

            dp = compute_droplet_profile(
                well.radius_top,
                well.depth,
                well.taper_angle,
                surface.contact_angle_well,
                well.volume_uL
            )
            evap = estimate_evaporation(dp)

            self._validation_panel.update_simulation(dp, evap)
        except Exception as e:
            print(f"Simulation error: {e}")

    def _show_droplet(self):
        """Show droplet overlay in the 3D viewer."""
        if not self._current_profile:
            return

        try:
            well = self._current_profile.well
            surface = self._current_profile.surface
            thickness = self._current_profile.substrate.thickness

            positions = self._engine.get_well_positions()

            for x, y in positions:
                verts, faces = generate_droplet_mesh(
                    well.radius_top,
                    surface.contact_angle_well,
                    center=(x, y, thickness),
                    n_radial=20,
                    n_angular=32
                )
                if len(verts) > 0 and len(faces) > 0:
                    self._viewer.display_droplet(verts, faces)
                    break  # Only first well for now

            self._set_status("Droplet overlay shown", "ready")
        except Exception as e:
            self._set_status(f"Droplet display error: {e}", "error")

    def _add_electrode_annotations(self):
        """Add colored rings to mark electrode regions."""
        if not self._current_profile or not self._current_profile.electrode.enabled:
            return

        e = self._current_profile.electrode
        thickness = self._current_profile.substrate.thickness
        positions = self._engine.get_well_positions()

        for x, y in positions:
            # WE ring (gold)
            self._viewer.add_annotation_ring(
                (x, y, thickness), self._current_profile.well.radius_top,
                (0.9, 0.75, 0.3, 1.0), "WE"
            )

            # RE ring (silver)
            re_angle = math.radians(e.re_offset_angle)
            re_x = x + e.we_re_spacing * math.cos(re_angle)
            re_y = y + e.we_re_spacing * math.sin(re_angle)
            self._viewer.add_annotation_ring(
                (re_x, re_y, thickness), max(e.re_width, e.re_length) / 2,
                (0.7, 0.72, 0.8, 1.0), "RE"
            )

            # CE ring (dark gray)
            ce_angle = math.radians(e.ce_offset_angle)
            ce_x = x + e.we_ce_spacing * math.cos(ce_angle)
            ce_y = y + e.we_ce_spacing * math.sin(ce_angle)
            self._viewer.add_annotation_ring(
                (ce_x, ce_y, thickness), max(e.ce_width, e.ce_length) / 2,
                (0.4, 0.45, 0.55, 1.0), "CE"
            )

    def _update_export_info(self):
        """Update the export tab with current design info."""
        if not self._current_profile:
            return

        dims = self._engine.get_substrate_dimensions()
        n_wells = len(self._engine.get_well_positions())
        total_vol = self._current_profile.well.volume_uL * n_wells

        self._validation_panel.update_export_info(
            f"{dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} mm",
            n_wells,
            total_vol
        )

    # ------------------------------------------------------------------
    #   File Operations
    # ------------------------------------------------------------------

    def _new_design(self):
        """Reset to default design."""
        self._load_default()
        self._viewer.clear_model()
        self._current_workplane = None
        self._set_status("New design", "ready")

    def _save_profile(self):
        """Save current profile to JSON."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Design Profile",
            "analytex_design.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if filepath:
            profile = self._param_panel.get_profile()
            try:
                save_profile(profile, filepath)
                self._set_status(f"Profile saved: {os.path.basename(filepath)}", "success")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save: {e}")

    def _load_profile(self):
        """Load a profile from JSON."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Design Profile",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if filepath:
            try:
                profile = load_profile(filepath)
                self._param_panel.set_profile(profile)
                self._on_params_changed()
                self._set_status(f"Profile loaded: {profile.name}", "success")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load: {e}")

    def _apply_preset(self, profile: DesignProfile):
        """Apply a built-in preset."""
        self._param_panel.set_profile(profile)
        self._on_params_changed()
        self._set_status(f"Preset loaded: {profile.name}", "ready")

    # ------------------------------------------------------------------
    #   Export
    # ------------------------------------------------------------------

    def _export_step_dialog(self):
        """Open STEP export dialog."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export STEP File",
            "analytex_microwell.step",
            "STEP Files (*.step *.stp);;All Files (*)"
        )
        if filepath:
            self._export_step(filepath)

    def _export_stl_dialog(self):
        """Open STL export dialog."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export STL File",
            "analytex_microwell.stl",
            "STL Files (*.stl);;All Files (*)"
        )
        if filepath:
            self._export_stl(filepath)

    def _export_step(self, filepath: str):
        """Export current model as STEP."""
        if self._current_workplane is None:
            QMessageBox.warning(
                self, "No Model",
                "Generate a model first before exporting."
            )
            return

        self._set_status("Exporting STEP...", "exporting")
        try:
            result = export_step(self._current_workplane, filepath,
                                 design=self._current_profile)
            if result.success:
                self._set_status(f"STEP exported: {result.filepath}", "success")
                self._validation_panel.set_export_status(result.message, True)
            else:
                self._set_status("Export failed", "error")
                self._validation_panel.set_export_status(result.message, False)
        except Exception as e:
            self._set_status(f"Export error: {e}", "error")

    def _export_stl(self, filepath: str):
        """Export current model as STL."""
        if self._current_workplane is None:
            QMessageBox.warning(
                self, "No Model",
                "Generate a model first before exporting."
            )
            return

        self._set_status("Exporting STL...", "exporting")
        try:
            result = export_stl(self._current_workplane, filepath)
            if result.success:
                self._set_status(f"✓ STL exported: {result.filepath}", "success")
                self._validation_panel.set_export_status(result.message, True)
            else:
                self._set_status(f"✗ Export failed", "error")
                self._validation_panel.set_export_status(result.message, False)
        except Exception as e:
            self._set_status(f"✗ Export error: {e}", "error")

    # ------------------------------------------------------------------
    #   Parametric Sweep
    # ------------------------------------------------------------------

    def _open_sweep_dialog(self):
        """Open the parametric sweep dialog."""
        dialog = SweepDialog(self)
        dialog.sweep_requested.connect(self._run_sweep)
        dialog.exec()

    def _run_sweep(self, param_key, start, end, steps, output_dir):
        """Execute a parametric sweep."""
        if self._current_profile is None:
            self._current_profile = self._param_panel.get_profile()

        import numpy as np
        values = np.linspace(start, end, steps)

        self._set_status(f"Running sweep: {param_key}...", "generating")

        for i, val in enumerate(values):
            profile = copy.deepcopy(self._current_profile)

            # Set the swept parameter
            parts = param_key.split(".")
            obj = profile
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], float(val))

            try:
                engine = GeometryEngine()
                wp = engine.generate(profile)

                filename = f"sweep_{param_key.replace('.', '_')}_{val:.3f}.step"
                filepath = os.path.join(output_dir, filename)
                export_step(wp, filepath)

                self._set_status(
                    f"Sweep {i+1}/{steps}: {param_key} = {val:.3f}", "generating"
                )
            except Exception as e:
                print(f"Sweep step {i+1} failed: {e}")

        self._set_status(f"✓ Sweep complete — {steps} variants exported", "success")

    # ------------------------------------------------------------------
    #   UI Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str, state: str = "ready"):
        """Update status bar with colored message."""
        color = STATUS_COLORS.get(state, STATUS_COLORS["ready"])
        self._status_label.setStyleSheet(f"color: {color}; padding: 0 8px;")
        self._status_label.setText(message)

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About AnalyteX MicroWell Designer",
            "<h2>AnalyteX MicroWell Designer</h2>"
            "<p>Version 1.0.0</p>"
            "<p>Professional parametric design tool for electrochemical "
            "micro-well electrode substrates.</p>"
            "<hr/>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Parametric well geometry generation</li>"
            "<li>Scientific constraint validation</li>"
            "<li>Multi-electrode layout (WE/RE/CE)</li>"
            "<li>Contact channel design</li>"
            "<li>Droplet simulation (Young-Laplace)</li>"
            "<li>STEP & STL export (ISO 10303)</li>"
            "<li>Parametric sweep</li>"
            "</ul>"
            "<p><b>Engine:</b> CadQuery / OpenCascade (OCC)</p>"
            "<p><b>GUI:</b> PyQt6</p>"
            "<p>© 2025 AnalyteX Engineering</p>"
        )
