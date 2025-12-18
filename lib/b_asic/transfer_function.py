"""
B-ASIC Transfer Function Module.

Contains a class for the transfer function representation of a linear system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from b_asic.sfg import SFG
    from b_asic.state_space import StateSpace


class TransferFunction:
    """
    Transfer function representation of a linear system.

    Parameters
    ----------
    numerator : numpy array or list or dict
        Numerator coefficients. Can be:
        - Array/list: Single transfer function coefficients
        - Dict: Multiple transfer functions keyed by input (e.g., {"in0": array, "in1": array})
    denominator : numpy array or list
        Denominator coefficients (shared across all transfer functions).
    """

    __slots__ = ("_n_inputs", "_n_outputs", "denominator", "numerator")

    def __init__(
        self,
        numerator: npt.NDArray | list | dict[str, npt.NDArray],
        denominator: npt.NDArray | list,
    ) -> None:
        if isinstance(numerator, dict):
            # Multiple transfer functions - normalize each
            self.numerator = {}
            for k, v in numerator.items():
                num_array = np.atleast_1d(np.asarray(v))
                # Squeeze out single output dimension for SISO
                if num_array.ndim == 2 and num_array.shape[0] == 1:
                    num_array = num_array.squeeze(axis=0)
                self.numerator[k] = num_array

            self._n_inputs = len(self.numerator)
            # Assume all have same number of outputs
            first_key = next(iter(self.numerator))
            num_array = self.numerator[first_key]
            self._n_outputs = 1 if num_array.ndim == 1 else num_array.shape[0]
        else:
            # Single transfer function
            num_array = np.atleast_1d(np.asarray(numerator))
            # Squeeze out single output dimension for SISO
            if num_array.ndim == 2 and num_array.shape[0] == 1:
                num_array = num_array.squeeze(axis=0)
            self.numerator = {"in0": num_array}
            self._n_inputs = 1
            self._n_outputs = 1 if num_array.ndim == 1 else num_array.shape[0]

        self.denominator = np.atleast_1d(np.asarray(denominator))

    @classmethod
    def from_state_space(cls, ss: StateSpace) -> TransferFunction:
        """
        Create a TransferFunction from a StateSpace representation.

        Parameters
        ----------
        ss : StateSpace
            State-space representation of a linear system.

        Returns
        -------
        :class:`~b_asic.transfer_function.TransferFunction`
            The transfer function representation.
        """
        tf_dict = ss._calc_tfs()

        # Extract numerators and denominator (same for all inputs)
        numerators = {}
        denominator = None

        for input_key, (num, den) in tf_dict.items():
            numerators[input_key] = num
            if denominator is None:
                denominator = den

        return cls(numerators, denominator)

    @classmethod
    def from_sfg(cls, sfg: SFG) -> TransferFunction:
        """
        Create a TransferFunction from an SFG.

        Parameters
        ----------
        sfg : SFG
            Signal flow graph of a linear system.

        Returns
        -------
        :class:`~b_asic.transfer_function.TransferFunction`
            The transfer function representation.
        """
        from b_asic.state_space import StateSpace  # noqa: PLC0415

        if not sfg.is_linear:
            raise ValueError(
                "SFG must be linear to generate transfer function representation"
            )
        ss = StateSpace.from_sfg(sfg)
        return cls.from_state_space(ss)

    def __repr__(self) -> str:
        """Return a string representation of the transfer function."""
        lines = [
            f"TransferFunction ({self._n_inputs} inputs, {self._n_outputs} outputs)",
            f"  Denominator: {self.denominator}",
        ]

        for input_key, num in self.numerator.items():
            lines.append(f"  {input_key} Numerator: {num}")

        return "\n".join(lines)

    def __getitem__(self, key: str) -> tuple[npt.NDArray, npt.NDArray]:
        """
        Get the numerator and denominator for a specific input.

        Parameters
        ----------
        key : str
            Input identifier (e.g., "in0", "in1").

        Returns
        -------
        tuple[npt.NDArray, npt.NDArray]
            Tuple of (numerator, denominator) for the specified input.
        """
        return self.numerator[key], self.denominator
