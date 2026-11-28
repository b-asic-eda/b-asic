"""Scalar arithmetic and interfaces used while generating matrix algorithms."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import overload

from b_asic.core_operations import (
    MADS,
    Addition,
    AddSub,
    ComplexConjugate,
    Constant,
    Multiplication,
    Negation,
    Reciprocal,
    ReciprocalSquareRoot,
    Subtraction,
)
from b_asic.port import SignalSourceProvider
from b_asic.sfg import SFG
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output
from b_asic.types import Name
from b_asic.utility_operations import DontCare, Sink


@dataclass(eq=False)
class _Expression:
    """Emit a real expression once, and only if an output needs it."""

    build: Callable[[], SignalSourceProvider]

    @cached_property
    def source(self) -> SignalSourceProvider:
        return self.build()


def _node(operation, *inputs: _Expression, **kwargs) -> _Expression:
    return _Expression(lambda: operation(*(value.source for value in inputs), **kwargs))


@dataclass(eq=False)
class _SplitValue:
    """A complex scalar whose absent imaginary component is identically zero."""

    arithmetic: _MatrixArithmetic
    re: _Expression
    im: _Expression | None = None
    conjugate_of: _SplitValue | None = None

    def __add__(self, other: _SplitValue) -> _SplitValue:
        return self.arithmetic.addsub(True, self, other)

    def __sub__(self, other: _SplitValue) -> _SplitValue:
        return self.arithmetic.addsub(False, self, other)

    def __mul__(self, other: _SplitValue) -> _SplitValue:
        return self.arithmetic.multiplication(self, other)

    def __neg__(self) -> _SplitValue:
        return self.arithmetic.negation(self)


class _MatrixArithmetic:
    """Build native or split scalar operations directly from the same algorithm."""

    def __init__(
        self, data_type: str, multiplication_method: str, pe: str | None
    ) -> None:
        if data_type not in ("real", "complex", "split"):
            raise ValueError('data_type must be "real", "complex", or "split"')
        if multiplication_method not in ("four", "three", "threealt"):
            raise ValueError(
                'multiplication_method must be "four", "three", or "threealt"'
            )
        self.data_type = data_type
        self.multiplication_method = multiplication_method
        self.pe = pe
        self.inputs: list[Input] = []

    @overload
    def _addsub(
        self, is_add: bool, left: _Expression, right: _Expression | None
    ) -> _Expression: ...

    @overload
    def _addsub(
        self, is_add: bool, left: _Expression | None, right: _Expression
    ) -> _Expression: ...

    @overload
    def _addsub(
        self, is_add: bool, left: _Expression | None, right: _Expression | None
    ) -> _Expression | None: ...

    def _addsub(
        self, is_add: bool, left: _Expression | None, right: _Expression | None
    ) -> _Expression | None:
        if right is None:
            return left
        if left is None:
            return right if is_add else _node(Negation, right)
        if self.pe == "addsub":
            return _node(lambda a, b: AddSub(is_add, a, b), left, right)
        return _node(Addition if is_add else Subtraction, left, right)

    def _mac(
        self,
        accumulator: _Expression | None,
        left: _Expression,
        right: _Expression,
        is_add: bool = True,
    ) -> _Expression:
        if self.pe == "mads":
            if accumulator is None:
                accumulator = _node(DontCare)
                do_addsub = False
            else:
                do_addsub = True
            return _node(
                lambda acc, a, b: MADS(
                    is_add=is_add, in0=acc, in1=a, in2=b, do_addsub=do_addsub
                ),
                accumulator,
                left,
                right,
            )
        return self._addsub(is_add, accumulator, _node(Multiplication, left, right))

    def _product(
        self,
        left: _SplitValue,
        right: _SplitValue,
        accumulator: _SplitValue | None = None,
        is_add: bool = True,
    ) -> _SplitValue:
        a, b, c, d = left.re, left.im, right.re, right.im
        real = None if accumulator is None else accumulator.re
        imag = None if accumulator is None else accumulator.im
        if b is None or d is None:
            real = self._mac(real, a, c, is_add)
            if b is not None:
                imag = self._mac(imag, b, c, is_add)
            elif d is not None:
                imag = self._mac(imag, a, d, is_add)
            return _SplitValue(self, real, imag)
        if left.conjugate_of is right or right.conjugate_of is left:
            # z * conj(z) is real and only needs two squares.
            imag_part = right.im if left.conjugate_of is right else b
            assert imag_part is not None
            real = self._mac(
                self._mac(real, a, a, is_add), imag_part, imag_part, is_add
            )
            return _SplitValue(self, real, imag)
        if self.multiplication_method == "four":
            real = self._mac(self._mac(real, a, c, is_add), b, d, not is_add)
            imag = self._mac(self._mac(imag, a, d, is_add), b, c, is_add)
            return _SplitValue(self, real, imag)
        if self.multiplication_method == "threealt":
            k1 = self._mac(None, d, self._addsub(True, a, b))
            k2 = self._mac(None, a, self._addsub(True, c, d))
            k3 = self._mac(None, b, self._addsub(False, c, d))
            product_re = self._addsub(False, k2, k1)
            product_im = self._addsub(True, k1, k3)
        else:
            ac = self._mac(None, a, c)
            bd = self._mac(None, b, d)
            product_re = self._addsub(False, ac, bd)
            product_im = self._addsub(
                False,
                self._mac(None, self._addsub(True, a, b), self._addsub(True, c, d)),
                self._addsub(True, ac, bd),
            )
        return _SplitValue(
            self,
            self._addsub(is_add, real, product_re),
            self._addsub(is_add, imag, product_im),
        )

    def _real_product(
        self,
        left: _SplitValue,
        right: _SplitValue,
        accumulator: _SplitValue | None = None,
        is_add: bool = True,
    ) -> _SplitValue:
        """Accumulate only Re(left * right), absorbing conjugation into signs."""
        real = self._mac(
            None if accumulator is None else accumulator.re, left.re, right.re, is_add
        )
        if left.im is not None and right.im is not None:
            imag_is_add = not is_add
            left_imag, right_imag = left.im, right.im
            if left.conjugate_of is not None:
                left_imag = left.conjugate_of.im
                imag_is_add = not imag_is_add
            if right.conjugate_of is not None:
                right_imag = right.conjugate_of.im
                imag_is_add = not imag_is_add
            assert left_imag is not None
            assert right_imag is not None
            real = self._mac(real, left_imag, right_imag, imag_is_add)
        return _SplitValue(self, real)

    def addsub(self, is_add: bool, in0, in1):
        if self.data_type != "split":
            return AddSub(is_add, in0, in1)
        return _SplitValue(
            self,
            self._addsub(is_add, in0.re, in1.re),
            self._addsub(is_add, in0.im, in1.im),
        )

    def multiplication(self, in0, in1, *, real_valued: bool = False):
        if self.data_type != "split":
            return Multiplication(in0, in1)
        if real_valued:
            return self._real_product(in0, in1)
        return self._product(in0, in1)

    def negation(self, in0):
        if self.data_type != "split":
            return Negation(in0)
        return _SplitValue(
            self, _node(Negation, in0.re), self._addsub(False, None, in0.im)
        )

    def mads(
        self, is_add: bool, in0, in1, in2, do_addsub: bool, *, real_valued: bool = False
    ):
        if self.data_type != "split":
            return MADS(
                is_add=is_add,
                in0=DontCare() if in0 is None else in0,
                in1=in1,
                in2=in2,
                do_addsub=do_addsub,
            )
        product = self._real_product if real_valued else self._product
        return product(in1, in2, in0 if do_addsub else None, is_add)

    def reciprocal(self, in0, **kwargs):
        if self.data_type != "split":
            return Reciprocal(in0, **kwargs)
        return _SplitValue(self, _node(Reciprocal, in0.re, **kwargs))

    def reciprocal_square_root(self, in0, **kwargs):
        if self.data_type != "split":
            return ReciprocalSquareRoot(in0, **kwargs)
        return _SplitValue(self, _node(ReciprocalSquareRoot, in0.re, **kwargs))

    def conjugate(self, value):
        if self.data_type == "real":
            return value
        if self.data_type == "complex":
            return ComplexConjugate(value)
        if value.im is None:
            return value
        if value.conjugate_of is not None:
            return value.conjugate_of
        return _SplitValue(self, value.re, _node(Negation, value.im), value)

    def real(self, value):
        """Record an algorithmically real diagonal before subsequent arithmetic."""
        if self.data_type != "split":
            return value
        return _SplitValue(self, value.re)

    def constant(self, value):
        """Build a real constant in the selected arithmetic representation."""
        if self.data_type != "split":
            return Constant(value)
        return _SplitValue(self, _Expression(lambda: Constant(value)))

    def matrix_entry(self, matrix, row: int, col: int):
        if row == col:
            return self.real(matrix[row][col])
        if row >= col:
            return matrix[row][col]
        return self.conjugate(matrix[col][row])

    def input(self, row: int, col: int, mem: bool):
        name = f"A[{row},{col}]"
        address = row * (row + 1) // 2 + col
        if self.data_type != "split":
            real_valued = self.data_type == "real" or row == col
            operation = (
                MemoryRead(address=address, name=name, real_valued=real_valued)
                if mem
                else Input(name=name, real_valued=real_valued)
            )
            self.inputs.append(operation)
            return operation
        parts = []
        for index, part in enumerate(("real", "imag")):
            operation = (
                MemoryRead(
                    address=2 * address + index,
                    name=f"{name}_{part}",
                    real_valued=True,
                )
                if mem
                else Input(name=f"{name}_{part}", real_valued=True)
            )
            self.inputs.append(operation)
            parts.append(_Expression(lambda operation=operation: operation))
        if row == col:
            Sink(parts[1].source)
            return _SplitValue(self, parts[0])
        return _SplitValue(self, *parts)

    def output(
        self,
        row: int,
        col: int,
        value,
        mem: bool,
        *,
        name: str | None = None,
        address: int | None = None,
        memory_name: str = "",
    ) -> tuple[Output, ...]:
        name = f"res[{row},{col}]" if name is None else name
        address = row * (row + 1) // 2 + col if address is None else address
        if self.data_type == "split":
            parts = (
                value.re.source,
                Constant(0) if row == col or value.im is None else value.im.source,
            )
            return tuple(
                MemoryWrite(
                    address=2 * address + index,
                    memory_name=memory_name,
                    in0=part,
                    name=f"{name}_{suffix}",
                    real_valued=True,
                )
                if mem
                else Output(part, name=f"{name}_{suffix}", real_valued=True)
                for index, (part, suffix) in enumerate(
                    zip(parts, ("real", "imag"), strict=True)
                )
            )
        real_valued = self.data_type == "real" or row == col
        return (
            MemoryWrite(
                address=address,
                in0=value,
                name=name,
                real_valued=real_valued,
                memory_name=memory_name,
            )
            if mem
            else Output(value, name=name, real_valued=real_valued),
        )

    def graph(self, outputs: Sequence[tuple[Output, ...]], name: str) -> SFG:
        return SFG(
            inputs=self.inputs,
            outputs=[part for entry in outputs for part in entry],
            name=Name(name),
        )
