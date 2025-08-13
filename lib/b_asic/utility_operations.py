"""
B-ASIC Utility Operations Module.

Contains some operations that are not really operations, but needed for other reasons.
"""

from typing import TYPE_CHECKING, NoReturn

from b_asic.codegen.vhdl import VHDL_TAB
from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation
from b_asic.types import ShapeCoordinates

if TYPE_CHECKING:
    from b_asic.architecture import ProcessingElement


class DontCare(AbstractOperation):
    """
    Dont-care operation.

    Used for ignoring the input to another operation and thus avoiding dangling input nodes.

    Parameters
    ----------
    name : Name, optional
        Operation name.
    """

    __slots__ = ("_name",)
    _name: Name

    is_linear = True

    def __init__(self, name: Name = "") -> None:
        """Construct a DontCare operation."""
        super().__init__(
            input_count=0,
            output_count=1,
            name=name,
            latency_offsets={"out0": 0},
            execution_time=0,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("dontcare")

    def evaluate(self) -> int:
        return 0

    @property
    def latency(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "DontCare()"

    def __str__(self) -> str:
        return "dontcare"

    def get_plot_coordinates(
        self,
    ) -> tuple[ShapeCoordinates, ShapeCoordinates]:
        # Doc-string inherited
        return (
            (
                (-0.5, 0),
                (-0.5, 1),
                (-0.25, 1),
                (0, 0.5),
                (-0.25, 0),
                (-0.5, 0),
            ),
            (
                (-0.5, 0),
                (-0.5, 1),
                (-0.25, 1),
                (0, 0.5),
                (-0.25, 0),
                (-0.5, 0),
            ),
        )

    def get_input_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ()

    def get_output_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ((0, 0.5),)

    @classmethod
    def _vhdl(cls, pe: "ProcessingElement") -> tuple[str, str]:
        code = super()._vhdl(pe)

        new_arch_code = f"{VHDL_TAB}res_0 <= (others => '-');\n"

        return code[0], code[1] + new_arch_code


class Sink(AbstractOperation):
    """
    Sink operation.

    Used for ignoring the output from another operation to avoid dangling output nodes.

    Parameters
    ----------
    name : Name, optional
        Operation name.
    """

    __slots__ = ("_name",)
    _name: Name

    is_linear = True

    def __init__(self, name: Name = "") -> None:
        """Construct a Sink operation."""
        super().__init__(
            input_count=1,
            output_count=0,
            name=name,
            latency_offsets={"in0": 0},
            execution_time=0,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sink")

    def evaluate(self) -> NoReturn:
        raise NotImplementedError

    @property
    def latency(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "Sink()"

    def __str__(self) -> str:
        return "sink"

    def get_plot_coordinates(
        self,
    ) -> tuple[ShapeCoordinates, ShapeCoordinates]:
        # Doc-string inherited
        return (
            ((0, 0), (0, 1), (0.25, 1), (0.5, 0.5), (0.25, 0), (0, 0)),
            ((0, 0), (0, 1), (0.25, 1), (0.5, 0.5), (0.25, 0), (0, 0)),
        )

    def get_input_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ((0, 0.5),)

    def get_output_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ()
