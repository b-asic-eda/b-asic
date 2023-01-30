"""
B-ASIC Save/Load Structure Module.

Contains functions for saving/loading SFGs to/from strings that can be stored
as files.
"""

from datetime import datetime
from inspect import signature
from typing import Dict, Optional, Tuple, cast

from b_asic.graph_component import GraphComponent
from b_asic.port import InputPort
from b_asic.signal_flow_graph import SFG


def sfg_to_python(
    sfg: SFG, counter: int = 0, suffix: Optional[str] = None
) -> str:
    """
    Given an SFG structure try to serialize it for saving to a file.

    Parameters
    ==========
    sfg : SFG
        The SFG to serialize
    counter : int, default: 0
        Number used for naming the SFG. Enables SFGs in SFGs.
    suffix : str, optional
        String to append at the end of the result.

    """
    result = (
        '\n"""\nB-ASIC automatically generated SFG file.\n'
        + "Name: "
        + f"{sfg.name}"
        + "\n"
        + "Last saved: "
        + f"{datetime.now()}"
        + ".\n"
        + '"""'
    )

    result += "\nfrom b_asic import SFG, Signal, Input, Output"
    for op_type in {type(op) for op in sfg.operations}:
        result += f", {op_type.__name__}"

    def kwarg_unpacker(comp: GraphComponent, params=None) -> str:
        if params is None:
            params_filtered = {
                attr: getattr(comp, attr)
                for attr in signature(comp.__init__).parameters
                if attr != "latency" and hasattr(comp, attr)
            }
            params = {
                attr: getattr(comp, attr)
                if not isinstance(getattr(comp, attr), str)
                else f'"{getattr(comp, attr)}"'
                for attr in params_filtered
            }

        return ", ".join(
            [f"{param[0]}={param[1]}" for param in params.items()]
        )

    # No need to redefined I/Os
    io_ops = [*sfg._input_operations, *sfg._output_operations]

    result += "\n# Inputs:\n"
    for input_op in sfg._input_operations:
        result += f"{input_op.graph_id} = Input({kwarg_unpacker(input_op)})\n"

    result += "\n# Outputs:\n"
    for output_op in sfg._output_operations:
        result += (
            f"{output_op.graph_id} = Output({kwarg_unpacker(output_op)})\n"
        )

    result += "\n# Operations:\n"
    for op in sfg.split():
        if op in io_ops:
            continue
        if isinstance(op, SFG):
            counter += 1
            result = sfg_to_python(op, counter) + result
            continue

        result += (
            f"{op.graph_id} = {op.__class__.__name__}({kwarg_unpacker(op)})\n"
        )

    result += "\n# Signals:\n"
    # Keep track of already existing connections to avoid adding duplicates
    connections = []
    for op in sfg.split():
        for out in op.outputs:
            for signal in out.signals:
                destination = cast(InputPort, signal.destination)
                dest_op = destination.operation
                connection = (
                    f"\nSignal(source={op.graph_id}.output({op.outputs.index(signal.source)}),"
                    f" destination={dest_op.graph_id}.input({dest_op.inputs.index(destination)}))"
                )
                if connection in connections:
                    continue

                result += connection
                connections.append(connection)

    inputs = "[" + ", ".join(op.graph_id for op in sfg.input_operations) + "]"
    outputs = (
        "[" + ", ".join(op.graph_id for op in sfg.output_operations) + "]"
    )
    sfg_name = (
        sfg.name if sfg.name else f"sfg{counter}" if counter > 0 else "sfg"
    )
    sfg_name_var = sfg_name.replace(" ", "_")
    result += (
        f"\n{sfg_name_var} = SFG(inputs={inputs}, outputs={outputs},"
        f" name='{sfg_name}')\n"
    )
    result += (
        "\n# SFG Properties:\n" + "prop = {'name':" + f"{sfg_name_var}" + "}"
    )

    if suffix is not None:
        result += "\n" + suffix + "\n"

    return result


def python_to_sfg(path: str) -> Tuple[SFG, Dict[str, Tuple[int, int]]]:
    """
    Given a serialized file try to deserialize it and load it to the library.

    Parameters
    ==========
    path : str
        Path to file to read and deserialize.
    """
    with open(path) as f:
        code = compile(f.read(), path, "exec")
        exec(code, globals(), locals())

    return (
        locals()["prop"]["name"]
        if "prop" in locals()
        else [v for k, v in locals().items() if isinstance(v, SFG)][0],
        locals()["positions"] if "positions" in locals() else {},
    )
