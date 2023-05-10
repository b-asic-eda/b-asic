"""
B-ASIC utilities for Matplotlib integration.
"""
import io

from matplotlib.figure import Figure


class FigureWrapper:
    """Simple wrapper to display a figure inline in enriched shells."""

    def __init__(self, figure: Figure):
        self._figure = figure

    def _repr_svg_(self):
        buffer = io.StringIO()
        self._figure.savefig(buffer, format="svg")
        return buffer.getvalue()
