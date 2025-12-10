"""
B-ASIC State Space Module.

Contains a class for the state-space representation of a linear system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from b_asic.sfg import SFG


class StateSpace:
    r"""
    State-space representation of a linear system.

    Parameters
    ----------
    A : numpy array or list of lists
        State matrix.
    B : numpy array or list of lists
        Input matrix.
    C : numpy array or list of lists
        Output matrix.
    D : numpy array or list of lists
        Feedthrough matrix.
    """

    __slots__ = ("A", "B", "C", "D", "_n_inputs", "_n_outputs", "_n_states")

    def __init__(
        self,
        A: npt.NDArray | list[list[float]],
        B: npt.NDArray | list[list[float]],
        C: npt.NDArray | list[list[float]],
        D: npt.NDArray | list[list[float]],
    ) -> None:
        self.A = np.atleast_2d(np.asarray(A, dtype=float))
        self.B = np.atleast_2d(np.asarray(B, dtype=float))
        self.C = np.atleast_2d(np.asarray(C, dtype=float))
        self.D = np.atleast_2d(np.asarray(D, dtype=float))
        self._n_states = self.A.shape[0]
        self._n_inputs = self.B.shape[1]
        self._n_outputs = self.C.shape[0]

    @classmethod
    def from_sfg(cls, sfg: SFG) -> StateSpace:
        """
        Create a StateSpace representation from an SFG.

        Parameters
        ----------
        sfg : SFG
            Signal flow graph of a linear system.

        Returns
        -------
        The State-space representation of the SFG.
        """
        from b_asic.special_operations import Delay  # noqa: PLC0415

        if not sfg.is_linear:
            raise ValueError(
                "SFG must be linear to generate state-space representation"
            )

        delays = list(sfg.find_by_type(Delay))
        inputs = list(sfg.input_operations)
        outputs = list(sfg.output_operations)

        n_states = len(delays)
        n_inputs = len(inputs)
        n_outputs = len(outputs)

        A = np.zeros((n_states, n_states), dtype=float)
        B = np.zeros((n_states, n_inputs), dtype=float)
        C = np.zeros((n_outputs, n_states), dtype=float)
        D = np.zeros((n_outputs, n_inputs), dtype=float)

        if n_states > 0:
            responses_dd = sfg._get_impulse_responses_between_nodes(
                delays, delays, max_iters=2
            )
            cls._populate_matrix_from_responses(
                A, delays, delays, responses_dd, time_index=1
            )

            responses_id = sfg._get_impulse_responses_between_nodes(
                inputs, delays, max_iters=2
            )
            cls._populate_matrix_from_responses(
                B, delays, inputs, responses_id, time_index=1
            )

            responses_do = sfg._get_impulse_responses_between_nodes(
                delays, outputs, max_iters=1
            )
            cls._populate_matrix_from_responses(
                C, outputs, delays, responses_do, time_index=0
            )

        responses_io = sfg._get_impulse_responses_between_nodes(
            inputs, outputs, max_iters=1
        )
        cls._populate_matrix_from_responses(
            D, outputs, inputs, responses_io, time_index=0
        )

        return cls(A, B, C, D)

    @staticmethod
    def _populate_matrix_from_responses(
        matrix: npt.NDArray,
        row_ops: list,
        col_ops: list,
        responses: dict,
        time_index: int,
    ) -> None:
        for col_idx, col_op in enumerate(col_ops):
            for row_idx, row_op in enumerate(row_ops):
                response = responses[(col_op.graph_id, row_op.graph_id)]
                if len(response) > time_index:
                    matrix[row_idx, col_idx] = float(response[time_index])

    @property
    def equations(self) -> tuple:
        r"""
        Get the state-space equations in symbolic form using SymPy.

        Returns
        -------
        A tuple containing (state_equation, output_equation):

        Notes
        -----
        Requires SymPy to be installed.
        """
        try:
            import sympy as sp  # noqa: PLC0415
        except ImportError as e:
            raise ImportError(
                "SymPy is required for symbolic equations. Install with: pip install sympy"
            ) from e

        A_sym = sp.Matrix(self.A)
        B_sym = sp.Matrix(self.B)
        C_sym = sp.Matrix(self.C)
        D_sym = sp.Matrix(self.D)

        x_n = sp.MatrixSymbol("x", self._n_states, 1)
        u_n = sp.MatrixSymbol("u", self._n_inputs, 1)
        y_n = sp.MatrixSymbol("y", self._n_outputs, 1)
        x_n1 = sp.MatrixSymbol("x^+", self._n_states, 1)

        state_eq = (
            sp.Eq(x_n1, A_sym * x_n + B_sym * u_n) if self._n_states > 0 else None
        )
        output_eq = (
            sp.Eq(y_n, C_sym * x_n + D_sym * u_n) if self._n_outputs > 0 else None
        )

        return state_eq, output_eq

    def __repr__(self) -> str:
        """Return a string representation of the state-space system."""
        lines = [
            f"StateSpace ({self._n_states} states, {self._n_inputs} inputs, {self._n_outputs} outputs)",
            f"  A = {np.array2string(self.A, separator=', ')},",
            f"  B = {np.array2string(self.B, separator=', ')},",
            f"  C = {np.array2string(self.C, separator=', ')},",
            f"  D = {np.array2string(self.D, separator=', ')}",
        ]
        return "\n".join(lines)
