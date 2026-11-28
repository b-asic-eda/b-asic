"""Operation counts and plotting behavior for precedence histograms."""

import matplotlib.pyplot as plt
import pytest
from matplotlib.axes import Axes
from matplotlib.colors import to_rgba

from b_asic.core_operations import Addition, Constant, Multiplication
from b_asic.fft_operations import R2Butterfly
from b_asic.sfg import SFG
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import DontCare


def _heights(ax):
    return [bar.get_height() for bar in ax.containers[-1]]


def test_parallel_operations_and_step_positions():
    first, second = Input(), Input()
    total = Addition(first, second)
    product = Multiplication(first, second)
    graph = SFG([first, second], [Output(Addition(total, product))])
    ax = graph.precedence_histogram()
    try:
        assert isinstance(ax, Axes)
        assert _heights(ax) == [0, 2, 1]
        assert [
            bar.get_x() + bar.get_width() / 2 for bar in ax.containers[-1]
        ] == pytest.approx([0, 1, 2])
        assert ax.get_xlabel() == "Precedence step"
        assert ax.get_ylabel() == "Number of operations"
        assert ax.get_ylim()[0] == 0
        ax.figure.canvas.draw()
    finally:
        plt.close(ax.figure)


def test_multiple_outputs_count_once():
    first, second = Input(), Input()
    butterfly = R2Butterfly(first, second)
    graph = SFG(
        [first, second], [Output(Addition(butterfly.output(0), butterfly.output(1)))]
    )
    ax = graph.precedence_histogram()
    try:
        assert _heights(ax) == [0, 1, 1]
    finally:
        plt.close(ax.figure)


def test_constants_and_delays(precedence_sfg_delays_and_constants):
    ax = precedence_sfg_delays_and_constants.precedence_histogram()
    try:
        assert _heights(ax) == [0, 5, 2, 1, 1, 1, 1]
    finally:
        plt.close(ax.figure)


def test_existing_axes_and_bar_options():
    fig, ax = plt.subplots()
    graph = SFG([], [Output(Constant(2))])
    try:
        figure_numbers = plt.get_fignums()
        assert (
            graph.precedence_histogram(
                ax=ax, color="purple", width=0.4, label="operations"
            )
            is ax
        )
        assert plt.get_fignums() == figure_numbers
        assert _heights(ax) == [0]
        assert ax.containers[-1].get_label() == "operations"
        assert ax.containers[-1][0].get_width() == pytest.approx(0.4)
        assert ax.containers[-1][0].get_facecolor() == to_rgba("purple")
    finally:
        plt.close(fig)


def test_empty_graph():
    ax = SFG([], []).precedence_histogram()
    try:
        assert _heights(ax) == []
        ax.figure.canvas.draw()
    finally:
        plt.close(ax.figure)


def test_noncomputational_sources_are_excluded():
    source = Input()
    first = Addition(source, Constant(1))
    second = Addition(Delay(source), DontCare())
    graph = SFG([source], [Output(Addition(first, second))])
    ax = graph.precedence_histogram()
    try:
        assert _heights(ax) == [0, 2, 1]
    finally:
        plt.close(ax.figure)
