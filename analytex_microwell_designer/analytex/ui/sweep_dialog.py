"""
Parametric Sweep Dialog
========================
Generate multiple design variants by sweeping one or more parameters
across a range of values.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QSpinBox,
    QComboBox, QCheckBox, QPushButton, QProgressBar,
    QFileDialog, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..core.geometry_engine import DesignProfile


SWEEP_PARAMETERS = [
    ("Well Diameter", "well.diameter", "mm", 0.5, 20.0, 3.0),
    ("Well Depth", "well.depth", "mm", 0.1, 10.0, 1.0),
    ("Taper Angle", "well.taper_angle", "°", 0.0, 30.0, 3.0),
    ("Fillet Radius", "well.fillet_radius", "mm", 0.0, 2.0, 0.1),
    ("Substrate Thickness", "substrate.thickness", "mm", 0.5, 10.0, 2.5),
    ("Well Spacing X", "array.spacing_x", "mm", 2.0, 30.0, 6.0),
    ("Well Spacing Y", "array.spacing_y", "mm", 2.0, 30.0, 6.0),
    ("Contact Angle (Well)", "surface.contact_angle_well", "°", 5.0, 170.0, 30.0),
]


class SweepDialog(QDialog):
    """Dialog for configuring and running parametric sweeps."""

    sweep_requested = pyqtSignal(str, float, float, int, str)  # param, start, end, steps, output_dir

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parametric Sweep — AnalyteX MicroWell Designer")
        self.setMinimumSize(500, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("Parametric Sweep Generator")
        header.setStyleSheet("color: #2d9bf2; font-size: 13pt; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Generate multiple design variants by sweeping a parameter\n"
            "across a range. Each variant is exported as a separate STEP file."
        )
        desc.setStyleSheet("color: #808590;")
        layout.addWidget(desc)

        # Parameter selection
        param_group = QGroupBox("Sweep Configuration")
        form = QFormLayout()
        form.setSpacing(6)

        self._param_combo = QComboBox()
        for name, key, unit, _, _, _ in SWEEP_PARAMETERS:
            self._param_combo.addItem(f"{name} ({unit})")
        self._param_combo.currentIndexChanged.connect(self._on_param_changed)
        form.addRow("Parameter:", self._param_combo)

        self._start_val = QDoubleSpinBox()
        self._start_val.setRange(0.01, 1000)
        self._start_val.setDecimals(3)
        form.addRow("Start Value:", self._start_val)

        self._end_val = QDoubleSpinBox()
        self._end_val.setRange(0.01, 1000)
        self._end_val.setDecimals(3)
        form.addRow("End Value:", self._end_val)

        self._num_steps = QSpinBox()
        self._num_steps.setRange(2, 50)
        self._num_steps.setValue(5)
        form.addRow("Number of Steps:", self._num_steps)

        param_group.setLayout(form)
        layout.addWidget(param_group)

        # Output directory
        dir_group = QGroupBox("Output")
        dir_layout = QHBoxLayout()

        self._output_dir = QLabel("Select output directory...")
        self._output_dir.setStyleSheet("color: #808590;")
        dir_layout.addWidget(self._output_dir)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(btn_browse)

        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 8))
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_run = QPushButton("Run Sweep")
        self._btn_run.setProperty("primary", True)
        self._btn_run.clicked.connect(self._on_run)
        btn_layout.addWidget(self._btn_run)

        btn_cancel = QPushButton("Close")
        btn_cancel.clicked.connect(self.close)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

        # Initialize values
        self._on_param_changed(0)

    def _on_param_changed(self, index):
        if 0 <= index < len(SWEEP_PARAMETERS):
            _, _, unit, min_v, max_v, default = SWEEP_PARAMETERS[index]
            self._start_val.setSuffix(f" {unit}")
            self._end_val.setSuffix(f" {unit}")
            self._start_val.setRange(min_v, max_v)
            self._end_val.setRange(min_v, max_v)
            self._start_val.setValue(default * 0.5)
            self._end_val.setValue(default * 2.0)

    def _browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory"
        )
        if dir_path:
            self._output_dir.setText(dir_path)
            self._output_dir.setStyleSheet("color: #d4d8e0;")

    def _on_run(self):
        output = self._output_dir.text()
        if output.startswith("Select"):
            QMessageBox.warning(self, "No Output Directory",
                                "Please select an output directory first.")
            return

        index = self._param_combo.currentIndex()
        _, param_key, _, _, _, _ = SWEEP_PARAMETERS[index]

        self.sweep_requested.emit(
            param_key,
            self._start_val.value(),
            self._end_val.value(),
            self._num_steps.value(),
            output
        )

    def log(self, message: str):
        self._log.append(message)

    def set_progress(self, value: int):
        self._progress.setValue(value)
