"""Array layout, access validation, and state lowering for LLVM import."""

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from b_asic.special_operations import Delay, Input, MemoryRead, MemoryWrite, Output

if TYPE_CHECKING:
    from llvmlite.binding import ValueRef

    from b_asic.port import SignalSourceProvider


@dataclass(frozen=True, slots=True)
class LLVMArray:
    """
    Describe an LLVM pointer argument or global as an SFG array.

    Parameters
    ----------
    role : {"input", "output", "inout", "state"}
        Input arrays are supplied anew each iteration. Output arrays expose
        final stored values. Inout arrays do both without persisting internally.
        State arrays persist between iterations as delays.
        Combining state with input/output arrays is currently unsupported.
    size : int
        Number of scalar elements. Addresses are zero-based element indices,
        with nested LLVM arrays flattened in row-major order.
    interface : {"memory", "stream"}, default: "memory"
        For input/output arrays, use MemoryRead/MemoryWrite or ordinary
        Input/Output ports respectively. Streams expose a separate scalar port
        per element in the same SFG iteration, not a serialized bus protocol.
        State always uses Delay operations, independent of this setting.
    initial_values : sequence of float, optional
        Reset values for state, one per element. Pointer state defaults to zero.
        Globals require explicit values; C/LLVM initializers are not inferred.
    element_type : {"float", "double"}, default: "float"
        LLVM scalar element type, used to reject reinterpretation and mixed
        access widths. SFG constants and reset values are Python floats.
    """

    role: Literal["input", "output", "inout", "state"]
    size: int
    interface: Literal["memory", "stream"] = "memory"
    initial_values: Sequence[float] | None = None
    element_type: Literal["float", "double"] = "float"

    def __post_init__(self) -> None:
        if self.role not in {"input", "output", "inout", "state"}:
            raise ValueError(
                "Array role must be 'input', 'output', 'inout', or 'state'."
            )
        if type(self.size) is not int or self.size <= 0:
            raise ValueError("Array size must be a positive integer.")
        if self.interface not in {"memory", "stream"}:
            raise ValueError("Array interface must be 'memory' or 'stream'.")
        if self.element_type not in {"float", "double"}:
            raise ValueError("Array element_type must be 'float' or 'double'.")
        if self.initial_values is not None:
            if self.role != "state":
                raise ValueError("Only state arrays can have initial_values.")
            initial = tuple(float(value) for value in self.initial_values)
            if len(initial) != self.size:
                raise ValueError(
                    "State initial_values must have one value per element."
                )
            object.__setattr__(self, "initial_values", initial)


class _UnsupportedMemory(ValueError):
    """An access cannot be given static array semantics."""


def _signed_index(value: "ValueRef") -> int:
    """Sign-extend LLVM indices at their declared width, not a host word width."""
    number = value.get_constant_value()
    width = int(str(value.type)[1:])
    return number - (1 << width) if number & (1 << (width - 1)) else number


def _shape(type_text: str) -> tuple[list[int], str]:
    """Read only homogeneous scalar or nested-array LLVM types."""
    dimensions = []
    while match := re.fullmatch(r"\[(\d+) x (.*)\]", type_text):
        dimensions.append(int(match[1]))
        type_text = match[2]
    if type_text not in {"float", "double", "i8"}:
        raise _UnsupportedMemory(f"Unsupported array element type: {type_text}.")
    return dimensions, type_text


class _ArrayContext:
    """Validate accesses before translating them in original instruction order."""

    def __init__(
        self,
        function: "ValueRef",
        globals_: Sequence["ValueRef"],
        arrays: Mapping[str, LLVMArray],
        issues: list[str],
    ) -> None:
        self.arrays = arrays
        self.issues = issues
        self.arguments = list(function.arguments)
        self.argument_names = {
            arg: arg.name or f"arg{index}" for index, arg in enumerate(self.arguments)
        }
        self.globals = {"@" + value.name: value for value in globals_}
        known = set(self.argument_names.values()) | set(self.globals)
        for name, array in arrays.items():
            if name not in known:
                raise ValueError(
                    f"Unknown LLVM array {name!r}; use argument names or @global names."
                )
            if not isinstance(array, LLVMArray):
                raise TypeError(f"Array {name!r} must be an LLVMArray.")
        roles = {array.role for array in arrays.values()}
        if "state" in roles and roles & {"input", "output", "inout"}:
            issues.append(
                "Combining state arrays with input/output arrays is unsupported."
            )
        self.pointers: dict[ValueRef, tuple[str, int]] = {}
        self.global_tokens: dict[str, str] = {}
        for arg, name in self.argument_names.items():
            if name in arrays:
                if str(arg.type) != "ptr":
                    issues.append(
                        f"Configured array {name!r} is not a default-address-space pointer."
                    )
                else:
                    self.pointers[arg] = (name, 0)
                attributes = b" ".join(arg.attributes).decode()
                if re.search(
                    r"\b(?:byval|sret|inalloca|preallocated|byref)\b", attributes
                ):
                    issues.append(
                        f"Array argument {name!r} has unsupported ABI copy/aggregate attributes."
                    )
        for name, value in self.globals.items():
            if name not in arrays:
                continue
            array = arrays[name]
            try:
                if str(value.type) != "ptr":
                    raise _UnsupportedMemory(
                        "Only default-address-space array globals are supported."
                    )
                dimensions, element = _shape(str(value.global_value_type))
                if element != array.element_type or math.prod(dimensions) != array.size:
                    raise _UnsupportedMemory(
                        f"Global {name} does not match its configured size/type."
                    )
                if array.role == "state" and array.initial_values is None:
                    raise _UnsupportedMemory(
                        f"Global state {name} requires explicit initial_values; LLVM initializers are not inferred."
                    )
            except _UnsupportedMemory as exc:
                issues.append(str(exc))
            self.pointers[value] = (name, 0)
            token = re.match(
                r'(@(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+))\s*=', str(value)
            )
            if token:
                self.global_tokens[token[1]] = name
        self.accesses: dict[ValueRef, tuple[str, int]] = {}
        self.written: set[tuple[str, int]] = set()
        self.current: dict[tuple[str, int], SignalSourceProvider] = {}
        self.delays: dict[tuple[str, int], Delay] = {}
        self.array_inputs: dict[tuple[str, int], Input] = {}

    def _gep(
        self, base: tuple[str, int], type_text: str, indices: Sequence[int]
    ) -> tuple[str, int]:
        name, offset = base
        dimensions, element = _shape(type_text)
        if element not in {self.arrays[name].element_type, "i8"}:
            raise _UnsupportedMemory("GEP changes the configured array element type.")
        if not indices or len(indices) > len(dimensions) + 1:
            raise _UnsupportedMemory("Unsupported GEP indexing depth.")
        displacement = sum(
            index * math.prod(dimensions[level:]) for level, index in enumerate(indices)
        )
        if element == "i8":
            width = 4 if self.arrays[name].element_type == "float" else 8
            if displacement % width:
                raise _UnsupportedMemory(
                    "Byte GEPs must address whole floating-point elements."
                )
            displacement //= width
        offset += displacement
        if not 0 <= offset <= self.arrays[name].size:
            raise _UnsupportedMemory(
                f"Array pointer {name}[{offset}] is outside its configured bounds."
            )
        return name, offset

    def _pointer(self, value: "ValueRef") -> tuple[str, int]:
        if value in self.pointers:
            return self.pointers[value]
        # LLVM folds GEPs of globals into constant expressions. llvmlite exposes
        # their text, but not their operands. Accept only this narrow grammar.
        if value.value_kind.name == "constant_expr":
            match = re.fullmatch(
                r"ptr getelementptr(?:\s+(?:inbounds|nuw|nusw))*\s*\(([^,]+), ptr "
                r'(@(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)), (.*)\)',
                str(value),
            )
            if match and match[2] in self.global_tokens:
                parts = match[3].split(", ")
                indices = [re.fullmatch(r"i\d+ (-?\d+)", part) for part in parts]
                if all(indices):
                    return self._gep(
                        (self.global_tokens[match[2]], 0),
                        match[1],
                        [int(index[1]) for index in indices],
                    )
        raise _UnsupportedMemory(f"Unconfigured or unsupported array pointer: {value}.")

    def plan(self, inst: "ValueRef") -> None:
        """Record a validated constant-address GEP, load, or store."""
        operands = list(inst.operands)
        if inst.opcode == "getelementptr":
            indices = operands[1:]
            if any(index.value_kind.name != "constant_int" for index in indices):
                raise _UnsupportedMemory(
                    "Array addresses must be compile-time constants."
                )
            match = re.search(
                r"getelementptr(?:\s+(?:inbounds|nuw|nusw))*\s+([^,]+),", str(inst)
            )
            if not match:
                raise _UnsupportedMemory("Unsupported GEP source type or flags.")
            self.pointers[inst] = self._gep(
                self._pointer(operands[0]),
                match[1],
                [_signed_index(index) for index in indices],
            )
            return
        if re.search(r"\b(?:load|store)\s+(?:atomic|volatile)\b", str(inst)):
            raise _UnsupportedMemory(
                "Volatile and atomic memory accesses are unsupported."
            )
        address = self._pointer(operands[0] if inst.opcode == "load" else operands[1])
        name, index = address
        array = self.arrays[name]
        if not 0 <= index < array.size:
            raise _UnsupportedMemory(f"Access to {name}[{index}] is out of bounds.")
        value_type = str(inst.type if inst.opcode == "load" else operands[0].type)
        if value_type != array.element_type:
            raise _UnsupportedMemory(
                f"Access type {value_type} does not match {name}'s {array.element_type} elements."
            )
        if inst.opcode == "store":
            if array.role == "input":
                raise _UnsupportedMemory(f"Cannot write input array {name!r}.")
            if operands[0].value_kind.name not in {
                "argument",
                "instruction",
                "constant_fp",
            }:
                raise _UnsupportedMemory(f"Unsupported stored value: {operands[0]}.")
            self.written.add(address)
        elif array.role == "output" and address not in self.written:
            raise _UnsupportedMemory(
                f"Output array {name}[{index}] is read before it is written."
            )
        self.accesses[inst] = address

    def create_inputs(
        self,
    ) -> tuple[list[Input], dict["ValueRef", "SignalSourceProvider"]]:
        """Keep argument ordering, followed by global arrays in name order."""
        inputs = []
        values = {}

        def add_array(name):
            array = self.arrays[name]
            if array.role in {"input", "inout"}:
                for index in range(array.size):
                    operation = (
                        MemoryRead(
                            index,
                            memory_name=name,
                            name=f"{name}[{index}]",
                            real_valued=True,
                        )
                        if array.interface == "memory"
                        else Input(name=f"{name}[{index}]", real_valued=True)
                    )
                    inputs.append(operation)
                    self.array_inputs[name, index] = operation

        for arg, name in self.argument_names.items():
            if name in self.arrays:
                add_array(name)
            else:
                operation = Input(name=name, real_valued=True)
                inputs.append(operation)
                values[arg] = operation
        for name in sorted(self.globals.keys() & self.arrays.keys()):
            add_array(name)
        return inputs, values

    def _delay(self, address: tuple[str, int]) -> Delay:
        if address not in self.delays:
            name, index = address
            initial = self.arrays[name].initial_values
            self.delays[address] = Delay(
                initial_value=0.0 if initial is None else initial[index],
                name=f"{name}[{index}]",
            )
        return self.delays[address]

    def load(self, inst: "ValueRef") -> "SignalSourceProvider":
        """Forward stores within an iteration; read delays across iterations."""
        address = self.accesses[inst]
        if address in self.current:
            return self.current[address]
        if self.arrays[address[0]].role == "state":
            return self._delay(address)
        return self.array_inputs[address]

    def store(self, inst: "ValueRef", value: "SignalSourceProvider") -> None:
        """Keep the final stored value for each output or state element."""
        address = self.accesses[inst]
        self.current[address] = value
        if self.arrays[address[0]].role == "state":
            self._delay(address)

    def outputs(self) -> list[Output]:
        """Commit state simultaneously and expose final output-array writes."""
        for address, delay in self.delays.items():
            delay.input(0).connect(self.current.get(address, delay))
        names = [name for name in self.argument_names.values() if name in self.arrays]
        names.extend(sorted(self.globals.keys() & self.arrays.keys()))
        outputs = []
        for name in names:
            array = self.arrays[name]
            if array.role not in {"output", "inout"}:
                continue
            for index in sorted(index for key, index in self.written if key == name):
                value = self.current[name, index]
                outputs.append(
                    MemoryWrite(
                        index,
                        value,
                        memory_name=name,
                        name=f"{name}[{index}]",
                        real_valued=True,
                    )
                    if array.interface == "memory"
                    else Output(value, name=f"{name}[{index}]", real_valued=True)
                )
        return outputs
