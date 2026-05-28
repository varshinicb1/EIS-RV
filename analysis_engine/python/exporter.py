"""
exporter.py — Save matplotlib figures with publication-grade settings.
Supports PNG, SVG, PDF, TIFF at selectable DPI.
All margins are handled via constrained_layout — no clipping.
"""

from pathlib import Path
import matplotlib.pyplot as plt


SUPPORTED_FORMATS = ["png", "svg", "pdf", "tiff"]
SUPPORTED_DPI = [300, 600, 800, 900, 1000, 1200]


def save_figure(
    fig: plt.Figure,
    output_path: str,
    fmt: str = "png",
    dpi: int = 300,
) -> str:
    """
    Save a matplotlib Figure to disk.

    Parameters
    ----------
    fig         : matplotlib Figure
    output_path : full path including filename (extension is overridden by fmt)
    fmt         : one of 'png', 'svg', 'pdf', 'tiff'
    dpi         : dots-per-inch; ignored for SVG/PDF (vector)

    Returns
    -------
    Absolute path string of the saved file.
    """
    fmt = fmt.lower().strip(".")
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Format '{fmt}' not supported. Use: {SUPPORTED_FORMATS}")

    path = Path(output_path).with_suffix(f".{fmt}")
    path.parent.mkdir(parents=True, exist_ok=True)

    save_kwargs = {
        "format": fmt,
        "bbox_inches": "tight",
        "facecolor": "white",
    }

    if fmt in ("png", "tiff"):
        save_kwargs["dpi"] = dpi

    fig.savefig(path, **save_kwargs)
    return str(path.resolve())


def export_all(
    figures: dict[str, plt.Figure],
    output_dir: str,
    fmt: str = "png",
    dpi: int = 300,
) -> list[str]:
    """
    Export all figures in a dict {name: figure} to output_dir.

    Returns list of saved file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for name, fig in figures.items():
        path = save_figure(fig, str(output_dir / name), fmt=fmt, dpi=dpi)
        saved.append(path)

    return saved
