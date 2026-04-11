"""
Application Stylesheet
========================
Dark engineering-grade UI theme for AnalyteX MicroWell Designer.
Inspired by professional CAD software (SolidWorks, Fusion 360).
"""


def get_stylesheet() -> str:
    """Return the complete Qt stylesheet for the application."""
    return """
    /* ========== Global ========== */
    QWidget {
        background-color: #1a1d23;
        color: #d4d8e0;
        font-family: 'Segoe UI', 'Roboto', sans-serif;
        font-size: 9pt;
    }

    /* ========== Main Window ========== */
    QMainWindow {
        background-color: #1a1d23;
    }

    QMainWindow::separator {
        background-color: #2a2e36;
        width: 2px;
        height: 2px;
    }

    /* ========== Menu Bar ========== */
    QMenuBar {
        background-color: #12141a;
        color: #b8bcc4;
        border-bottom: 1px solid #2a2e36;
        padding: 2px;
    }

    QMenuBar::item {
        padding: 4px 12px;
        border-radius: 3px;
    }

    QMenuBar::item:selected {
        background-color: #2d6af2;
        color: #ffffff;
    }

    QMenu {
        background-color: #1e2128;
        border: 1px solid #2a2e36;
        border-radius: 4px;
        padding: 4px;
    }

    QMenu::item {
        padding: 6px 24px 6px 12px;
        border-radius: 3px;
    }

    QMenu::item:selected {
        background-color: #2d6af2;
        color: #ffffff;
    }

    QMenu::separator {
        height: 1px;
        background-color: #2a2e36;
        margin: 4px 8px;
    }

    /* ========== Tool Bar ========== */
    QToolBar {
        background-color: #12141a;
        border-bottom: 1px solid #2a2e36;
        spacing: 4px;
        padding: 2px;
    }

    QToolButton {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px 8px;
        color: #b8bcc4;
    }

    QToolButton:hover {
        background-color: #2a2e36;
        border: 1px solid #3a3e46;
    }

    QToolButton:pressed {
        background-color: #2d6af2;
        color: #ffffff;
    }

    /* ========== Status Bar ========== */
    QStatusBar {
        background-color: #12141a;
        border-top: 1px solid #2a2e36;
        color: #808590;
        font-size: 8pt;
    }

    QStatusBar::item {
        border: none;
    }

    /* ========== Dock Widgets ========== */
    QDockWidget {
        titlebar-close-icon: url(close.png);
        titlebar-normal-icon: url(float.png);
        color: #d4d8e0;
        font-weight: 600;
    }

    QDockWidget::title {
        background-color: #12141a;
        padding: 6px 8px;
        border-bottom: 2px solid #2d6af2;
        text-align: left;
        font-size: 10pt;
    }

    QDockWidget::close-button, QDockWidget::float-button {
        border: none;
        background: transparent;
        padding: 2px;
    }

    /* ========== Scroll Area ========== */
    QScrollArea {
        border: none;
        background-color: #1a1d23;
    }

    QScrollBar:vertical {
        background-color: #1a1d23;
        width: 8px;
        margin: 0;
    }

    QScrollBar::handle:vertical {
        background-color: #3a3e46;
        border-radius: 4px;
        min-height: 30px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #4a4e56;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }

    QScrollBar:horizontal {
        background-color: #1a1d23;
        height: 8px;
    }

    QScrollBar::handle:horizontal {
        background-color: #3a3e46;
        border-radius: 4px;
        min-width: 30px;
    }

    /* ========== Group Boxes ========== */
    QGroupBox {
        border: 1px solid #2a2e36;
        border-radius: 6px;
        margin-top: 12px;
        padding: 12px 8px 8px 8px;
        font-weight: 600;
        font-size: 9pt;
        color: #8ec8f5;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 10px;
        background-color: #1a1d23;
        border-radius: 3px;
        color: #8ec8f5;
    }

    /* ========== Labels ========== */
    QLabel {
        color: #b0b4bc;
        background-color: transparent;
    }

    QLabel[heading="true"] {
        color: #2d9bf2;
        font-weight: bold;
        font-size: 11pt;
    }

    /* ========== Input Fields ========== */
    QDoubleSpinBox, QSpinBox {
        background-color: #12141a;
        border: 1px solid #2a2e36;
        border-radius: 4px;
        padding: 3px 6px;
        color: #e0e4ec;
        selection-background-color: #2d6af2;
        min-height: 22px;
    }

    QDoubleSpinBox:focus, QSpinBox:focus {
        border: 1px solid #2d6af2;
    }

    QDoubleSpinBox::up-button, QSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 16px;
        border-left: 1px solid #2a2e36;
        border-bottom: 1px solid #2a2e36;
        border-top-right-radius: 4px;
        background-color: #1e2128;
    }

    QDoubleSpinBox::down-button, QSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 16px;
        border-left: 1px solid #2a2e36;
        border-bottom-right-radius: 4px;
        background-color: #1e2128;
    }

    QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid #808590;
    }

    QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid #808590;
    }

    QLineEdit {
        background-color: #12141a;
        border: 1px solid #2a2e36;
        border-radius: 4px;
        padding: 4px 8px;
        color: #e0e4ec;
        min-height: 22px;
    }

    QLineEdit:focus {
        border: 1px solid #2d6af2;
    }

    /* ========== Combo Box ========== */
    QComboBox {
        background-color: #12141a;
        border: 1px solid #2a2e36;
        border-radius: 4px;
        padding: 3px 8px;
        color: #e0e4ec;
        min-height: 22px;
    }

    QComboBox:hover {
        border: 1px solid #3a3e46;
    }

    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left: 1px solid #2a2e36;
        border-top-right-radius: 4px;
        border-bottom-right-radius: 4px;
    }

    QComboBox QAbstractItemView {
        background-color: #1e2128;
        border: 1px solid #2a2e36;
        selection-background-color: #2d6af2;
        color: #d4d8e0;
        padding: 2px;
    }

    /* ========== Check Box ========== */
    QCheckBox {
        spacing: 6px;
        color: #b0b4bc;
    }

    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border-radius: 3px;
        border: 1px solid #3a3e46;
        background-color: #12141a;
    }

    QCheckBox::indicator:checked {
        background-color: #2d6af2;
        border: 1px solid #2d6af2;
    }

    QCheckBox::indicator:hover {
        border: 1px solid #2d9bf2;
    }

    /* ========== Buttons ========== */
    QPushButton {
        background-color: #2a2e36;
        border: 1px solid #3a3e46;
        border-radius: 5px;
        padding: 6px 16px;
        color: #d4d8e0;
        font-weight: 500;
        min-height: 24px;
    }

    QPushButton:hover {
        background-color: #3a3e46;
        border: 1px solid #4a4e56;
    }

    QPushButton:pressed {
        background-color: #2d6af2;
        border: 1px solid #2d6af2;
        color: #ffffff;
    }

    QPushButton[primary="true"] {
        background-color: #2d6af2;
        border: 1px solid #2d6af2;
        color: #ffffff;
        font-weight: 600;
    }

    QPushButton[primary="true"]:hover {
        background-color: #3d7af2;
    }

    QPushButton[primary="true"]:pressed {
        background-color: #1d5ae2;
    }

    QPushButton[success="true"] {
        background-color: #1d8348;
        border: 1px solid #1d8348;
        color: #ffffff;
    }

    QPushButton[success="true"]:hover {
        background-color: #219653;
    }

    QPushButton[danger="true"] {
        background-color: #c0392b;
        border: 1px solid #c0392b;
        color: #ffffff;
    }

    QPushButton[danger="true"]:hover {
        background-color: #e74c3c;
    }

    /* ========== Tab Widget ========== */
    QTabWidget::pane {
        border: 1px solid #2a2e36;
        border-radius: 4px;
        background-color: #1a1d23;
    }

    QTabBar::tab {
        background-color: #12141a;
        border: 1px solid #2a2e36;
        border-bottom: none;
        padding: 6px 14px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        color: #808590;
    }

    QTabBar::tab:selected {
        background-color: #1a1d23;
        color: #2d9bf2;
        border-bottom: 2px solid #2d6af2;
    }

    QTabBar::tab:hover:!selected {
        background-color: #1e2128;
        color: #b0b4bc;
    }

    /* ========== Splitter ========== */
    QSplitter::handle {
        background-color: #2a2e36;
    }

    QSplitter::handle:horizontal {
        width: 3px;
    }

    QSplitter::handle:vertical {
        height: 3px;
    }

    /* ========== Progress Bar ========== */
    QProgressBar {
        border: 1px solid #2a2e36;
        border-radius: 4px;
        background-color: #12141a;
        text-align: center;
        color: #d4d8e0;
        min-height: 16px;
    }

    QProgressBar::chunk {
        background-color: #2d6af2;
        border-radius: 3px;
    }

    /* ========== Text Edit (for logs/reports) ========== */
    QTextEdit, QPlainTextEdit {
        background-color: #12141a;
        border: 1px solid #2a2e36;
        border-radius: 4px;
        color: #d4d8e0;
        font-family: 'Consolas', 'JetBrains Mono', monospace;
        font-size: 8.5pt;
        padding: 4px;
    }

    /* ========== Slider ========== */
    QSlider::groove:horizontal {
        height: 4px;
        background-color: #2a2e36;
        border-radius: 2px;
    }

    QSlider::handle:horizontal {
        background-color: #2d6af2;
        border: none;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }

    QSlider::handle:horizontal:hover {
        background-color: #3d7af2;
    }

    /* ========== List Widget ========== */
    QListWidget {
        background-color: #12141a;
        border: 1px solid #2a2e36;
        border-radius: 4px;
        padding: 2px;
    }

    QListWidget::item {
        padding: 4px 8px;
        border-radius: 3px;
    }

    QListWidget::item:selected {
        background-color: #2d6af2;
        color: #ffffff;
    }

    QListWidget::item:hover:!selected {
        background-color: #2a2e36;
    }

    /* ========== Frame separators ========== */
    QFrame[frameShape="4"] {
        background-color: #2a2e36;
        max-height: 1px;
        border: none;
    }

    /* ========== ToolTip ========== */
    QToolTip {
        background-color: #1e2128;
        border: 1px solid #3a3e46;
        border-radius: 4px;
        padding: 4px 8px;
        color: #d4d8e0;
        font-size: 8.5pt;
    }
    """


# Color constants for viewer and charts
COLORS = {
    "substrate": (0.65, 0.68, 0.72, 1.0),     # Light gray
    "well_inner": (0.85, 0.75, 0.40, 1.0),     # Gold (WE)
    "re_region": (0.70, 0.72, 0.75, 1.0),      # Silver
    "ce_region": (0.45, 0.48, 0.52, 1.0),       # Dark gray
    "channel": (0.80, 0.50, 0.20, 1.0),          # Copper
    "droplet": (0.20, 0.55, 0.90, 0.45),         # Translucent blue
    "grid": (0.25, 0.27, 0.30, 0.6),             # Subtle grid
    "accent_blue": (0.18, 0.42, 0.95, 1.0),      # Primary accent
    "accent_green": (0.18, 0.72, 0.45, 1.0),     # Success
    "accent_red": (0.85, 0.25, 0.20, 1.0),       # Error
    "accent_yellow": (0.95, 0.75, 0.20, 1.0),    # Warning
}


# Status bar color codes
STATUS_COLORS = {
    "ready": "#2d9bf2",
    "generating": "#f5a623",
    "error": "#e74c3c",
    "success": "#27ae60",
    "exporting": "#9b59b6",
}
