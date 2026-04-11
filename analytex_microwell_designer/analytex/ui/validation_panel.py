"""
Validation & Simulation Panel
================================
Right-side panel displaying:
    - Constraint validation results
    - Design validation report
    - Droplet simulation output
    - Export controls
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QScrollArea, QGroupBox, QLabel, QTextEdit, QPushButton,
    QFrame, QComboBox, QCheckBox, QProgressBar, QTabWidget,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..core.constraints import ConstraintReport, ConstraintResult
from ..core.validation import ValidationReport, ManufacturingMethod
from ..core.droplet_sim import DropletProfile, EvaporationEstimate


class ValidationPanel(QWidget):
    """
    Right panel showing validation results, simulation, and export controls.

    Emits:
        export_step_requested(str): STEP export with filepath
        export_stl_requested(str): STL export with filepath
        show_droplet_requested(): Show droplet overlay
        hide_droplet_requested(): Hide droplet overlay
    """

    export_step_requested = pyqtSignal(str)
    export_stl_requested = pyqtSignal(str)
    show_droplet_requested = pyqtSignal()
    hide_droplet_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Tab widget for organized sections
        self._tabs = QTabWidget()

        # --- Tab 1: Validation ---
        self._validation_tab = QWidget()
        self._setup_validation_tab()
        self._tabs.addTab(self._validation_tab, "Validation")

        # --- Tab 2: Simulation ---
        self._simulation_tab = QWidget()
        self._setup_simulation_tab()
        self._tabs.addTab(self._simulation_tab, "Simulation")

        # --- Tab 3: Export ---
        self._export_tab = QWidget()
        self._setup_export_tab()
        self._tabs.addTab(self._export_tab, "Export")

        layout.addWidget(self._tabs)

    # ------------------------------------------------------------------
    #   Validation Tab
    # ------------------------------------------------------------------

    def _setup_validation_tab(self):
        layout = QVBoxLayout(self._validation_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Manufacturing method selector
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self._method_combo = QComboBox()
        self._method_combo.addItems(["FDM", "SLA", "CNC Milling", "Injection Molding"])
        method_layout.addWidget(self._method_combo)
        layout.addLayout(method_layout)

        # Scientific constraints section
        sci_label = QLabel("Scientific Constraints")
        sci_label.setProperty("heading", True)
        sci_label.setStyleSheet("color: #8ec8f5; font-weight: bold; font-size: 10pt;")
        layout.addWidget(sci_label)

        self._constraints_text = QTextEdit()
        self._constraints_text.setReadOnly(True)
        self._constraints_text.setMaximumHeight(200)
        self._constraints_text.setFont(QFont("Consolas", 8))
        layout.addWidget(self._constraints_text)

        # Manufacturing validation section
        mfg_label = QLabel("Manufacturing Validation")
        mfg_label.setStyleSheet("color: #8ec8f5; font-weight: bold; font-size: 10pt;")
        layout.addWidget(mfg_label)

        self._validation_text = QTextEdit()
        self._validation_text.setReadOnly(True)
        self._validation_text.setFont(QFont("Consolas", 8))
        layout.addWidget(self._validation_text)

        # Summary bar
        self._validation_summary = QLabel("No validation run")
        self._validation_summary.setStyleSheet(
            "padding: 4px; border-radius: 3px; font-weight: bold;"
        )
        layout.addWidget(self._validation_summary)

    # ------------------------------------------------------------------
    #   Simulation Tab
    # ------------------------------------------------------------------

    def _setup_simulation_tab(self):
        layout = QVBoxLayout(self._simulation_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Droplet profile section
        group_droplet = QGroupBox("Droplet Profile")
        form = QFormLayout()
        form.setSpacing(4)

        self._sim_volume = QLabel("—")
        form.addRow("Droplet Volume:", self._sim_volume)

        self._sim_well_volume = QLabel("—")
        form.addRow("Well Volume:", self._sim_well_volume)

        self._sim_fill_ratio = QLabel("—")
        form.addRow("Fill Ratio:", self._sim_fill_ratio)

        self._sim_cap_height = QLabel("—")
        form.addRow("Cap Height:", self._sim_cap_height)

        self._sim_sphere_radius = QLabel("—")
        form.addRow("Sphere Radius:", self._sim_sphere_radius)

        self._sim_laplace = QLabel("—")
        form.addRow("Laplace ΔP:", self._sim_laplace)

        self._sim_contact_line = QLabel("—")
        form.addRow("Contact Line:", self._sim_contact_line)

        self._sim_surface_area = QLabel("—")
        form.addRow("Surface Area:", self._sim_surface_area)

        self._sim_confined = QLabel("—")
        form.addRow("Confined:", self._sim_confined)

        group_droplet.setLayout(form)
        layout.addWidget(group_droplet)

        # Evaporation estimate
        group_evap = QGroupBox("Evaporation Estimate")
        evap_form = QFormLayout()
        evap_form.setSpacing(4)

        self._evap_rate = QLabel("—")
        evap_form.addRow("Rate:", self._evap_rate)

        self._evap_half = QLabel("—")
        evap_form.addRow("Time to 50%:", self._evap_half)

        self._evap_dry = QLabel("—")
        evap_form.addRow("Time to Dry:", self._evap_dry)

        group_evap.setLayout(evap_form)
        layout.addWidget(group_evap)

        # Droplet overlay controls
        overlay_layout = QHBoxLayout()
        self._btn_show_droplet = QPushButton("Show Droplet")
        self._btn_show_droplet.setProperty("primary", True)
        self._btn_show_droplet.clicked.connect(self.show_droplet_requested.emit)
        overlay_layout.addWidget(self._btn_show_droplet)

        self._btn_hide_droplet = QPushButton("Hide Droplet")
        self._btn_hide_droplet.clicked.connect(self.hide_droplet_requested.emit)
        overlay_layout.addWidget(self._btn_hide_droplet)
        layout.addLayout(overlay_layout)

        # Fill ratio progress bar
        self._fill_bar = QProgressBar()
        self._fill_bar.setRange(0, 100)
        self._fill_bar.setValue(0)
        self._fill_bar.setFormat("Fill Ratio: %p%")
        layout.addWidget(self._fill_bar)

        layout.addStretch()

    # ------------------------------------------------------------------
    #   Export Tab
    # ------------------------------------------------------------------

    def _setup_export_tab(self):
        layout = QVBoxLayout(self._export_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Design info
        info_group = QGroupBox("Design Summary")
        info_form = QFormLayout()
        info_form.setSpacing(4)

        self._export_dims = QLabel("—")
        info_form.addRow("Substrate:", self._export_dims)

        self._export_wells = QLabel("—")
        info_form.addRow("Wells:", self._export_wells)

        self._export_volume = QLabel("—")
        info_form.addRow("Total Well Vol:", self._export_volume)

        info_group.setLayout(info_form)
        layout.addWidget(info_group)

        # Export buttons
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout()
        export_layout.setSpacing(8)

        self._btn_export_step = QPushButton("💾  Export STEP File (.step)")
        self._btn_export_step.setProperty("success", True)
        self._btn_export_step.setMinimumHeight(36)
        self._btn_export_step.clicked.connect(self._on_export_step)
        export_layout.addWidget(self._btn_export_step)

        self._btn_export_stl = QPushButton("📦  Export STL File (.stl)")
        self._btn_export_stl.setMinimumHeight(32)
        self._btn_export_stl.clicked.connect(self._on_export_stl)
        export_layout.addWidget(self._btn_export_stl)

        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # Export status
        self._export_status = QLabel("")
        self._export_status.setWordWrap(True)
        self._export_status.setStyleSheet("color: #808590; font-size: 8pt;")
        layout.addWidget(self._export_status)

        layout.addStretch()

    # ------------------------------------------------------------------
    #   Update Methods
    # ------------------------------------------------------------------

    def update_constraints(self, report: ConstraintReport):
        """Display scientific constraint results."""
        html = ""
        for r in report.results:
            if r.passed:
                icon = '<span style="color: #27ae60;">✓</span>'
            elif r.severity == "warning":
                icon = '<span style="color: #f5a623;">⚠</span>'
            else:
                icon = '<span style="color: #e74c3c;">✗</span>'

            html += f'<p style="margin: 2px 0;">{icon} <b>{r.name}</b><br/>'
            html += f'<span style="color: #808590; font-size: 8pt;">{r.message}</span></p>'

        self._constraints_text.setHtml(html)

    def update_validation(self, report: ValidationReport):
        """Display manufacturing validation results."""
        html = ""
        for issue in report.issues:
            if issue.severity == "info":
                color = "#27ae60"
                icon = "✓"
            elif issue.severity == "warning":
                color = "#f5a623"
                icon = "⚠"
            else:
                color = "#e74c3c"
                icon = "✗"

            html += f'<p style="margin: 2px 0;"><span style="color: {color};">{icon}</span> '
            html += f'<b>{issue.parameter}</b><br/>'
            html += f'<span style="color: #808590; font-size: 8pt;">{issue.message}</span>'
            if issue.suggestion:
                html += f'<br/><span style="color: #6fa8dc; font-size: 8pt;">→ {issue.suggestion}</span>'
            html += '</p>'

        self._validation_text.setHtml(html)

        # Summary
        if report.is_valid:
            self._validation_summary.setText("✓ Design is valid for manufacturing")
            self._validation_summary.setStyleSheet(
                "padding: 6px; border-radius: 4px; font-weight: bold; "
                "background-color: #1d3a25; color: #27ae60; border: 1px solid #27ae60;"
            )
        else:
            n_errors = len(report.errors)
            self._validation_summary.setText(f"✗ {n_errors} issue(s) found")
            self._validation_summary.setStyleSheet(
                "padding: 6px; border-radius: 4px; font-weight: bold; "
                "background-color: #3a1d1d; color: #e74c3c; border: 1px solid #e74c3c;"
            )

    def update_simulation(
        self, profile: DropletProfile, evap: EvaporationEstimate
    ):
        """Display droplet simulation results."""
        self._sim_volume.setText(f"{profile.droplet_volume_uL:.3f} µL")
        self._sim_well_volume.setText(f"{profile.well_volume_uL:.3f} µL")
        self._sim_fill_ratio.setText(f"{profile.fill_ratio:.1%}")
        self._sim_cap_height.setText(f"{profile.cap_height:.3f} mm")
        self._sim_sphere_radius.setText(f"{profile.sphere_radius:.3f} mm")
        self._sim_laplace.setText(f"{profile.laplace_pressure_Pa:.1f} Pa")
        self._sim_contact_line.setText(f"{profile.contact_line_length:.2f} mm")
        self._sim_surface_area.setText(f"{profile.surface_area:.3f} mm²")

        if profile.is_confined:
            self._sim_confined.setText("✓ Yes — droplet fits within well")
            self._sim_confined.setStyleSheet("color: #27ae60;")
        else:
            self._sim_confined.setText(
                f"✗ No — overflow {profile.overflow_volume_uL:.3f} µL"
            )
            self._sim_confined.setStyleSheet("color: #e74c3c;")

        # Fill ratio bar
        self._fill_bar.setValue(int(profile.fill_ratio * 100))

        # Evaporation
        self._evap_rate.setText(f"{evap.evaporation_rate_uL_per_min:.4f} µL/min")
        self._evap_half.setText(f"{evap.time_to_50pct:.1f} min")
        self._evap_dry.setText(f"{evap.time_to_dry:.1f} min")

    def update_export_info(self, dims, n_wells, total_vol):
        """Update design summary in the export tab."""
        self._export_dims.setText(dims)
        self._export_wells.setText(str(n_wells))
        self._export_volume.setText(f"{total_vol:.2f} µL")

    def set_export_status(self, message: str, success: bool = True):
        """Show export result status."""
        color = "#27ae60" if success else "#e74c3c"
        self._export_status.setStyleSheet(f"color: {color}; font-size: 8.5pt;")
        self._export_status.setText(message)

    def get_manufacturing_method(self) -> ManufacturingMethod:
        """Get the selected manufacturing method."""
        methods = {
            0: ManufacturingMethod.FDM,
            1: ManufacturingMethod.SLA,
            2: ManufacturingMethod.CNC,
            3: ManufacturingMethod.INJECTION,
        }
        return methods.get(self._method_combo.currentIndex(), ManufacturingMethod.FDM)

    # ------------------------------------------------------------------
    #   Export Actions
    # ------------------------------------------------------------------

    def _on_export_step(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export STEP File",
            "analytex_microwell.step",
            "STEP Files (*.step *.stp);;All Files (*)"
        )
        if filepath:
            self.export_step_requested.emit(filepath)

    def _on_export_stl(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export STL File",
            "analytex_microwell.stl",
            "STL Files (*.stl);;All Files (*)"
        )
        if filepath:
            self.export_stl_requested.emit(filepath)
