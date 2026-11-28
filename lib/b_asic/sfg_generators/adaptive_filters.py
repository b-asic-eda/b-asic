"""Signal flow graph generators for adaptive filters."""

from collections.abc import Callable, Sequence
from math import isfinite
from numbers import Number, Real
from typing import Literal

from b_asic.core_operations import (
    Addition,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    Multiplication,
    Reciprocal,
    Subtraction,
)
from b_asic.port import OutputPort, SignalSourceProvider
from b_asic.sfg import SFG
from b_asic.special_operations import Delay, Input, Output

type WeightUpdate = Callable[
    [tuple[OutputPort, ...], tuple[OutputPort, ...], OutputPort, float],
    Sequence[SignalSourceProvider],
]


def adaptive_fir(
    taps: int,
    step_size: float = 0.01,
    name: str | None = None,
    *,
    update_method: Literal["lms", "nlms"] | WeightUpdate = "lms",
    initial_weights: Sequence[complex] | None = None,
    epsilon: float = 1e-8,
) -> SFG:
    r"""
    Generate a direct-form adaptive FIR filter with configurable weight updates.

    With :math:`u_k[n] = x[n-k]`, the outputs are

    .. math::

        y[n] = \sum_{k=0}^{M-1} w_k[n] u_k[n], \qquad e[n] = d[n] - y[n].

    LMS updates the coefficients using

    .. math::

        w_k[n+1] = w_k[n] + \mu e[n] u_k^*[n].

    NLMS replaces :math:`\mu` by
    :math:`\mu/(\epsilon + \sum_k |u_k[n]|^2)`. Real and complex signals
    are supported. Weights multiply samples directly in this convention.
    The weight delays make updates effective on the next sample, while the
    sample history starts at zero.

    Parameters
    ----------
    taps : int
        Positive number of filter coefficients, M.
    step_size : float, default: 0.01
        Finite, nonnegative adaptation step, mu. Zero freezes the built-in
        updates. Choose a step appropriate to the input power for convergence.
    name : str, optional
        Graph name. Defaults to "Adaptive FIR filter".
    update_method : {"lms", "nlms"} or callable, default: "lms"
        Built-in update rule or a graph-building callable with signature
        ``update(weights, samples, error, step_size)``. It receives tuples of
        current weight and sample output ports (newest sample first), the
        error output port, and the numeric step size. It must return exactly
        *taps* signal sources representing the next weights. Called once
        during graph construction, it may build and share arbitrary operations;
        the generator supplies the weight delays.
    initial_weights : sequence of numbers, optional
        Initial coefficients in newest-to-oldest sample order. Must contain
        exactly *taps* finite values. Defaults to all zeros.
    epsilon : float, default: 1e-8
        Finite positive regularization constant for NLMS. Prevents division
        by zero during silence. Unused by LMS and custom update rules.

    Returns
    -------
    SFG
        Inputs ``x`` and ``d``, in that order; outputs ``y`` and ``e``, in
        that order. Coefficient delays are named ``w[k]`` and sample delays
        ``x[k]`` for k starting at one.

    Examples
    --------
    >>> sfg = adaptive_fir(8, step_size=0.1, update_method="nlms")

    A custom update can implement leaky LMS using port arithmetic:

    >>> def leaky_lms(weights, samples, error, step_size):
    ...     return [
    ...         0.999 * w + step_size * error * ComplexConjugate(x)
    ...         for w, x in zip(weights, samples)
    ...     ]
    >>> sfg = adaptive_fir(4, update_method=leaky_lms)
    """
    if isinstance(taps, bool) or not isinstance(taps, int):
        raise TypeError("taps must be an integer")
    if taps < 1:
        raise ValueError("taps must be positive")
    if not isinstance(step_size, Real) or not isfinite(step_size) or step_size < 0:
        raise ValueError("step_size must be finite and nonnegative")
    if not callable(update_method) and update_method not in ("lms", "nlms"):
        raise ValueError("update_method must be 'lms', 'nlms', or a callable")
    if not isinstance(epsilon, Real) or not isfinite(epsilon) or epsilon <= 0:
        raise ValueError("epsilon must be finite and positive")
    coefficients = (0,) * taps if initial_weights is None else tuple(initial_weights)
    if len(coefficients) != taps:
        raise ValueError("initial_weights must contain exactly taps values")
    for value in coefficients:
        if not isinstance(value, Number):
            raise TypeError("initial_weights must contain numbers")
        if not (isfinite(complex(value).real) and isfinite(complex(value).imag)):
            raise ValueError("initial_weights must contain finite values")

    x = Input(name="x")
    desired = Input(name="d")
    samples = [x.output(0)]
    for k in range(1, taps):
        samples.append(Delay(samples[-1], name=f"x[{k}]").output(0))
    weights = [
        Delay(initial_value=value, name=f"w[{k}]")
        for k, value in enumerate(coefficients)
    ]
    products = [
        Multiplication(weight, sample, name=f"tap[{k}]")
        for k, (weight, sample) in enumerate(zip(weights, samples, strict=True))
    ]
    filtered = products[0].output(0)
    for product in products[1:]:
        filtered = Addition(filtered, product).output(0)
    error = Subtraction(desired, filtered, name="error").output(0)

    if callable(update_method):
        next_weights = list(
            update_method(
                tuple(weight.output(0) for weight in weights),
                tuple(samples),
                error,
                step_size,
            )
        )
        if len(next_weights) != taps:
            raise ValueError("update_method must return exactly taps signal sources")
        if any(not isinstance(value, SignalSourceProvider) for value in next_weights):
            raise TypeError("update_method must return signal sources")
    else:
        conjugates = [ComplexConjugate(sample) for sample in samples]
        scaled_error = ConstantMultiplication(step_size, error)
        if update_method == "nlms":
            power = Constant(epsilon).output(0)
            for sample, conjugate in zip(samples, conjugates, strict=True):
                power = Addition(power, Multiplication(sample, conjugate)).output(0)
            scaled_error = Multiplication(scaled_error, Reciprocal(power))
        next_weights = [
            Addition(weight, Multiplication(scaled_error, conjugate))
            for weight, conjugate in zip(weights, conjugates, strict=True)
        ]
    for weight, next_weight in zip(weights, next_weights, strict=True):
        weight.input(0).connect(next_weight)

    return SFG(
        [x, desired],
        [Output(filtered, name="y"), Output(error, name="e")],
        name="Adaptive FIR filter" if name is None else name,
    )
