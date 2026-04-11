"""
Parameter Panel
=================
Left-side panel containing all design parameter inputs organized
in collapsible sections with real-time validation feedback.
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QScrollArea, QGroupBox, QLabel, QDoubleSpinBox, QSpinBox,
    QComboBox, QCheckBox, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..core.geometry_engine import (
    DesignProfile, WellParameters, SubstrateParameters,
    ArrayParameters, ElectrodeLayout, ChannelParameters,
    SurfaceConfig, WellArrayType, SurfaceType
)


class ParameterPanel(QWidget):
    """
    Design parameter input panel with organized sections.

    Emits:
        parameters_changed: When any parameter is modified
        generate_requested: When 'Generate' button is clicked
    """

    parameters_changed = pyqtSignal()
    generate_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)

        self._building = True  # Suppress signals during init
        self._setup_ui()
        self._building = False

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Scroll area for all parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(2, 2, 2, 2)
        self._content_layout.setSpacing(6)

        # --- Well Geometry Section ---
        self._add_well_section()

        # --- Substrate Section ---
        self._add_substrate_section()

        # --- Array Layout Section ---
        self._add_array_section()

        # --- Surface Engineering Section ---
        self._add_surface_section()

        # --- Electrode Layout Section ---
        self._add_electrode_section()

        # --- Contact Channels Section ---
        self._add_channel_section()

        self._content_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # --- Generate Button ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        btn_layout = QHBoxLayout()

        self._btn_generate = QPushButton("⚙  Generate Model")
        self._btn_generate.setProperty("primary", True)
        self._btn_generate.setMinimumHeight(36)
        self._btn_generate.clicked.connect(self.generate_requested.emit)
        btn_layout.addWidget(self._btn_generate)

        layout.addLayout(btn_layout)

        # Volume info
        self._volume_label = QLabel("")
        self._volume_label.setStyleSheet(
            "color: #8ec8f5; font-size: 8.5pt; padding: 2px;"
        )
        layout.addWidget(self._volume_label)

    # ------------------------------------------------------------------
    #   Section Builders
    # ------------------------------------------------------------------

    def _add_well_section(self):
        group = QGroupBox("Well Geometry")
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._well_diameter = self._make_double_spin(0.1, 50.0, 3.0, 0.1, " mm")
        self._well_diameter.setToolTip("Inner diameter at the top of the well")
        form.addRow("Diameter:", self._well_diameter)

        self._well_depth = self._make_double_spin(0.05, 20.0, 1.0, 0.05, " mm")
        self._well_depth.setToolTip("Depth from substrate top surface to well bottom")
        form.addRow("Depth:", self._well_depth)

        self._well_taper = self._make_double_spin(0.0, 30.0, 3.0, 0.5, "°")
        self._well_taper.setToolTip("Wall taper angle from vertical (0° = straight)")
        form.addRow("Taper Angle:", self._well_taper)

        self._well_fillet = self._make_double_spin(0.0, 2.0, 0.1, 0.01, " mm")
        self._well_fillet.setToolTip("Fillet radius at well rim edge")
        form.addRow("Edge Fillet:", self._well_fillet)

        self._well_bottom_fillet = self._make_double_spin(0.0, 2.0, 0.08, 0.01, " mm")
        self._well_bottom_fillet.setToolTip("Fillet radius at well bottom edge")
        form.addRow("Bottom Fillet:", self._well_bottom_fillet)

        # Computed info
        self._well_vol_info = QLabel("Vol: — µL")
        self._well_vol_info.setStyleSheet("color: #6fa8dc; font-size: 8pt;")
        form.addRow("", self._well_vol_info)

        group.setLayout(form)
        self._content_layout.addWidget(group)

    def _add_substrate_section(self):
        group = QGroupBox("Substrate")
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._sub_thickness = self._make_double_spin(0.5, 20.0, 2.5, 0.1, " mm")
        self._sub_thickness.setToolTip("Total substrate plate thickness")
        form.addRow("Thickness:", self._sub_thickness)

        self._sub_margin = self._make_double_spin(0.5, 30.0, 4.0, 0.5, " mm")
        self._sub_margin.setToolTip("Margin around wells to substrate edge")
        form.addRow("Margin:", self._sub_margin)

        self._sub_corner = self._make_double_spin(0.0, 10.0, 1.5, 0.1, " mm")
        self._sub_corner.setToolTip("Corner rounding radius of substrate")
        form.addRow("Corner Radius:", self._sub_corner)

        group.setLayout(form)
        self._content_layout.addWidget(group)

    def _add_array_section(self):
        group = QGroupBox("Array Layout")
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._array_type = QComboBox()
        self._array_type.addItems(["Single", "Linear", "Rectangular", "Hexagonal"])
        self._array_type.setToolTip("Well array arrangement pattern")
        self._array_type.currentIndexChanged.connect(self._on_array_type_changed)
        form.addRow("Pattern:", self._array_type)

        self._array_rows = self._make_int_spin(1, 20, 1)
        self._array_rows.setToolTip("Number of rows in the array")
        form.addRow("Rows:", self._array_rows)

        self._array_cols = self._make_int_spin(1, 20, 1)
        self._array_cols.setToolTip("Number of columns in the array")
        form.addRow("Columns:", self._array_cols)

        self._array_spacing_x = self._make_double_spin(1.0, 50.0, 5.0, 0.5, " mm")
        self._array_spacing_x.setToolTip("Center-to-center spacing in X direction")
        form.addRow("Spacing X:", self._array_spacing_x)

        self._array_spacing_y = self._make_double_spin(1.0, 50.0, 5.0, 0.5, " mm")
        self._array_spacing_y.setToolTip("Center-to-center spacing in Y direction")
        form.addRow("Spacing Y:", self._array_spacing_y)

        group.setLayout(form)
        self._content_layout.addWidget(group)

        # Default: hide array params for single mode
        self._on_array_type_changed(0)

    def _add_surface_section(self):
        group = QGroupBox("Surface Engineering")
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._surface_well = QComboBox()
        self._surface_well.addItems(["Hydrophilic", "Hydrophobic", "Mixed"])
        form.addRow("Well Surface:", self._surface_well)

        self._surface_outer = QComboBox()
        self._surface_outer.addItems(["Hydrophobic", "Hydrophilic", "Mixed"])
        form.addRow("Outer Surface:", self._surface_outer)

        self._contact_angle_well = self._make_double_spin(5.0, 170.0, 30.0, 1.0, "°")
        self._contact_angle_well.setToolTip("Contact angle of liquid on well surface")
        form.addRow("θ Well:", self._contact_angle_well)

        self._contact_angle_outer = self._make_double_spin(5.0, 170.0, 110.0, 1.0, "°")
        self._contact_angle_outer.setToolTip("Contact angle of liquid on outer surface")
        form.addRow("θ Outer:", self._contact_angle_outer)

        group.setLayout(form)
        self._content_layout.addWidget(group)

    def _add_electrode_section(self):
        group = QGroupBox("Multi-Electrode Layout")
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._electrode_enabled = QCheckBox("Enable WE/RE/CE Layout")
        self._electrode_enabled.toggled.connect(self._on_electrode_toggled)
        form.addRow(self._electrode_enabled)

        self._re_width = self._make_double_spin(0.5, 10.0, 1.5, 0.1, " mm")
        form.addRow("RE Width:", self._re_width)

        self._re_length = self._make_double_spin(0.5, 15.0, 3.0, 0.1, " mm")
        form.addRow("RE Length:", self._re_length)

        self._ce_width = self._make_double_spin(0.5, 15.0, 2.0, 0.1, " mm")
        form.addRow("CE Width:", self._ce_width)

        self._ce_length = self._make_double_spin(0.5, 20.0, 4.0, 0.1, " mm")
        form.addRow("CE Length:", self._ce_length)

        self._we_re_spacing = self._make_double_spin(0.5, 20.0, 4.0, 0.1, " mm")
        form.addRow("WE↔RE Spacing:", self._we_re_spacing)

        self._we_ce_spacing = self._make_double_spin(0.5, 20.0, 5.0, 0.1, " mm")
        form.addRow("WE↔CE Spacing:", self._we_ce_spacing)

        self._re_angle = self._make_double_spin(0, 360, 135, 5, "°")
        form.addRow("RE Angle:", self._re_angle)

        self._ce_angle = self._make_double_spin(0, 360, 225, 5, "°")
        form.addRow("CE Angle:", self._ce_angle)

        group.setLayout(form)
        self._content_layout.addWidget(group)
        self._electrode_group = group
        self._on_electrode_toggled(False)

    def _add_channel_section(self):
        group = QGroupBox("Contact Channels")
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._channel_enabled = QCheckBox("Enable Contact Channels")
        self._channel_enabled.toggled.connect(self._on_channel_toggled)
        form.addRow(self._channel_enabled)

        self._groove_width = self._make_double_spin(0.3, 5.0, 1.5, 0.1, " mm")
        form.addRow("Groove Width:", self._groove_width)

        self._groove_depth = self._make_double_spin(0.05, 2.0, 0.3, 0.05, " mm")
        form.addRow("Groove Depth:", self._groove_depth)

        self._pad_width = self._make_double_spin(1.0, 15.0, 4.0, 0.5, " mm")
        form.addRow("Pad Width:", self._pad_width)

        self._pad_length = self._make_double_spin(1.0, 20.0, 6.0, 0.5, " mm")
        form.addRow("Pad Length:", self._pad_length)

        self._snap_fit = QCheckBox("Snap-Fit Connector")
        form.addRow(self._snap_fit)

        group.setLayout(form)
        self._content_layout.addWidget(group)
        self._channel_group = group
        self._on_channel_toggled(False)

    # ------------------------------------------------------------------
    #   Helper Methods
    # ------------------------------------------------------------------

    def _make_double_spin(
        self, min_val, max_val, default, step, suffix=""
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        spin.setSuffix(suffix)
        spin.setMinimumWidth(100)
        spin.valueChanged.connect(self._on_param_changed)
        return spin

    def _make_int_spin(self, min_val, max_val, default) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setMinimumWidth(100)
        spin.valueChanged.connect(self._on_param_changed)
        return spin

    def _on_param_changed(self):
        if self._building:
            return
        self._update_computed_values()
        self.parameters_changed.emit()

    def _on_array_type_changed(self, index):
        is_single = (index == 0)
        is_linear = (index == 1)

        self._array_rows.setEnabled(not is_single and not is_linear)
        self._array_cols.setEnabled(not is_single)
        self._array_spacing_x.setEnabled(not is_single)
        self._array_spacing_y.setEnabled(not is_single and not is_linear)

        if is_single:
            self._array_rows.setValue(1)
            self._array_cols.setValue(1)
        elif is_linear:
            self._array_rows.setValue(1)

        if not self._building:
            self.parameters_changed.emit()

    def _on_electrode_toggled(self, checked):
        for widget in [self._re_width, self._re_length, self._ce_width,
                        self._ce_length, self._we_re_spacing, self._we_ce_spacing,
                        self._re_angle, self._ce_angle]:
            widget.setEnabled(checked)

    def _on_channel_toggled(self, checked):
        for widget in [self._groove_width, self._groove_depth,
                        self._pad_width, self._pad_length, self._snap_fit]:
            widget.setEnabled(checked)

    def _update_computed_values(self):
        """Update computed display values (volume, etc.)."""
        well = self.get_well_params()
        vol = well.volume_uL
        self._well_vol_info.setText(f"Vol: {vol:.2f} µL  |  r_bot: {well.radius_bottom:.3f} mm")

    # ------------------------------------------------------------------
    #   Get / Set Profile
    # ------------------------------------------------------------------

    def get_well_params(self) -> WellParameters:
        return WellParameters(
            diameter=self._well_diameter.value(),
            depth=self._well_depth.value(),
            taper_angle=self._well_taper.value(),
            fillet_radius=self._well_fillet.value(),
            bottom_fillet=self._well_bottom_fillet.value(),
        )

    def get_profile(self) -> DesignProfile:
        """Collect all parameter values into a DesignProfile."""
        array_types = {
            0: WellArrayType.SINGLE,
            1: WellArrayType.LINEAR,
            2: WellArrayType.RECTANGULAR,
            3: WellArrayType.HEXAGONAL,
        }

        surface_types_well = {0: SurfaceType.HYDROPHILIC, 1: SurfaceType.HYDROPHOBIC, 2: SurfaceType.MIXED}
        surface_types_outer = {0: SurfaceType.HYDROPHOBIC, 1: SurfaceType.HYDROPHILIC, 2: SurfaceType.MIXED}

        return DesignProfile(
            name="Custom Design",
            well=self.get_well_params(),
            substrate=SubstrateParameters(
                thickness=self._sub_thickness.value(),
                margin=self._sub_margin.value(),
                corner_radius=self._sub_corner.value(),
            ),
            array=ArrayParameters(
                array_type=array_types.get(self._array_type.currentIndex(), WellArrayType.SINGLE),
                rows=self._array_rows.value(),
                cols=self._array_cols.value(),
                spacing_x=self._array_spacing_x.value(),
                spacing_y=self._array_spacing_y.value(),
            ),
            electrode=ElectrodeLayout(
                enabled=self._electrode_enabled.isChecked(),
                we_diameter=self._well_diameter.value(),
                re_width=self._re_width.value(),
                re_length=self._re_length.value(),
                ce_width=self._ce_width.value(),
                ce_length=self._ce_length.value(),
                we_re_spacing=self._we_re_spacing.value(),
                we_ce_spacing=self._we_ce_spacing.value(),
                re_offset_angle=self._re_angle.value(),
                ce_offset_angle=self._ce_angle.value(),
            ),
            channel=ChannelParameters(
                enabled=self._channel_enabled.isChecked(),
                groove_width=self._groove_width.value(),
                groove_depth=self._groove_depth.value(),
                pad_width=self._pad_width.value(),
                pad_length=self._pad_length.value(),
                pad_depth=0.2,
                snap_fit=self._snap_fit.isChecked(),
            ),
            surface=SurfaceConfig(
                well_surface=surface_types_well.get(self._surface_well.currentIndex(), SurfaceType.HYDROPHILIC),
                outer_surface=surface_types_outer.get(self._surface_outer.currentIndex(), SurfaceType.HYDROPHOBIC),
                contact_angle_well=self._contact_angle_well.value(),
                contact_angle_outer=self._contact_angle_outer.value(),
            ),
        )

    def set_profile(self, profile: DesignProfile):
        """Load a design profile into the parameter panel."""
        self._building = True

        # Well
        self._well_diameter.setValue(profile.well.diameter)
        self._well_depth.setValue(profile.well.depth)
        self._well_taper.setValue(profile.well.taper_angle)
        self._well_fillet.setValue(profile.well.fillet_radius)
        self._well_bottom_fillet.setValue(profile.well.bottom_fillet)

        # Substrate
        self._sub_thickness.setValue(profile.substrate.thickness)
        self._sub_margin.setValue(profile.substrate.margin)
        self._sub_corner.setValue(profile.substrate.corner_radius)

        # Array
        type_map = {
            WellArrayType.SINGLE: 0,
            WellArrayType.LINEAR: 1,
            WellArrayType.RECTANGULAR: 2,
            WellArrayType.HEXAGONAL: 3,
        }
        self._array_type.setCurrentIndex(type_map.get(profile.array.array_type, 0))
        self._array_rows.setValue(profile.array.rows)
        self._array_cols.setValue(profile.array.cols)
        self._array_spacing_x.setValue(profile.array.spacing_x)
        self._array_spacing_y.setValue(profile.array.spacing_y)

        # Surface
        surface_well_map = {SurfaceType.HYDROPHILIC: 0, SurfaceType.HYDROPHOBIC: 1, SurfaceType.MIXED: 2}
        surface_outer_map = {SurfaceType.HYDROPHOBIC: 0, SurfaceType.HYDROPHILIC: 1, SurfaceType.MIXED: 2}
        self._surface_well.setCurrentIndex(surface_well_map.get(profile.surface.well_surface, 0))
        self._surface_outer.setCurrentIndex(surface_outer_map.get(profile.surface.outer_surface, 0))
        self._contact_angle_well.setValue(profile.surface.contact_angle_well)
        self._contact_angle_outer.setValue(profile.surface.contact_angle_outer)

        # Electrode
        self._electrode_enabled.setChecked(profile.electrode.enabled)
        self._re_width.setValue(profile.electrode.re_width)
        self._re_length.setValue(profile.electrode.re_length)
        self._ce_width.setValue(profile.electrode.ce_width)
        self._ce_length.setValue(profile.electrode.ce_length)
        self._we_re_spacing.setValue(profile.electrode.we_re_spacing)
        self._we_ce_spacing.setValue(profile.electrode.we_ce_spacing)
        self._re_angle.setValue(profile.electrode.re_offset_angle)
        self._ce_angle.setValue(profile.electrode.ce_offset_angle)

        # Channels
        self._channel_enabled.setChecked(profile.channel.enabled)
        self._groove_width.setValue(profile.channel.groove_width)
        self._groove_depth.setValue(profile.channel.groove_depth)
        self._pad_width.setValue(profile.channel.pad_width)
        self._pad_length.setValue(profile.channel.pad_length)
        self._snap_fit.setChecked(profile.channel.snap_fit)

        self._building = False
        self._update_computed_values()
