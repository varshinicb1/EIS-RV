#!/usr/bin/env python3
"""
AnalyteX MicroWell Designer
============================
Professional engineering tool for generating scientifically accurate 3D models
of electrochemical micro-well electrode substrates.

Entry point for the application.
"""

import sys
import os

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies():
    """Verify all required dependencies are available."""
    missing = []

    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")

    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    try:
        import pyqtgraph
    except ImportError:
        missing.append("pyqtgraph")

    try:
        import OpenGL
    except ImportError:
        missing.append("PyOpenGL")

    # CadQuery is optional - native kernel is used as fallback
    try:
        import cadquery
        print("  [OK] CadQuery available (OpenCascade kernel)")
    except ImportError:
        print("  [INFO] CadQuery not found - using native geometry kernel")

    if missing:
        print("=" * 60)
        print("  AnalyteX MicroWell Designer -- Missing Dependencies")
        print("=" * 60)
        print("")
        print("  The following packages are not installed:")
        print("")
        for pkg in missing:
            print(f"    [X] {pkg}")
        print("")
        print("  Install via pip:")
        print("    pip install PyQt6 pyqtgraph PyOpenGL numpy")
        print("")
        print("  See README.md for full instructions.")
        print("=" * 60)
        sys.exit(1)


def main():
    """Launch the AnalyteX MicroWell Designer application."""
    check_dependencies()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont
    from PyQt6.QtCore import Qt

    # High-DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("AnalyteX MicroWell Designer")
    app.setOrganizationName("AnalyteX")
    app.setApplicationVersion("1.0.0")

    # Set default font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Import and apply stylesheet
    from analytex.ui.styles import get_stylesheet
    app.setStyleSheet(get_stylesheet())

    # Create and show main window
    from analytex.ui.main_window import MainWindow
    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
