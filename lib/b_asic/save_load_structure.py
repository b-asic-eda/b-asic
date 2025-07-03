"""
B-ASIC Save/Load Structure Module.

Contains functions for saving/loading SFGs and Schedules to/from strings that can be
stored as files.
"""

from datetime import datetime
from inspect import signature
from pathlib import Path
from typing import cast

from b_asic.graph_component import GraphComponent
from b_asic.port import InputPort
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG


def sfg_to_python(
    sfg: SFG, counter: int = 0, suffix: str | None = None, schedule: bool = False
) -> str:
    """
    Given an SFG structure try to serialize it for saving to a file.

    Parameters
    ----------
    sfg : :class:`~b_asic.signal_flow_graph.SFG`
        The SFG to serialize.
    counter : int, default: 0
        Number used for naming the SFG. Enables SFGs in SFGs.
    suffix : str, optional
        String to append at the end of the result.
    schedule : bool, default: False
        True if printing a schedule.
    """
    if not isinstance(sfg, SFG):
        raise TypeError("An SFG must be provided")

    _type = "Schedule" if schedule else "SFG"

    result = (
        '\n"""\n'
        + f"B-ASIC automatically generated {_type} file.\n"
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
    if schedule:
        result += ", Schedule"

    def kwarg_unpacker(comp: GraphComponent, params=None) -> str:
        if params is None:
            params_filtered = {
                attr: getattr(comp, attr)
                for attr in signature(comp.__init__).parameters
                if attr != "latency" and hasattr(comp, attr)
            }
            params = {
                attr: (
                    getattr(comp, attr)
                    if not isinstance(getattr(comp, attr), str)
                    else f'"{getattr(comp, attr)}"'
                )
                for attr in params_filtered
            }
            params = {k: v for k, v in params.items() if v}
            if params.get("latency_offsets") is not None:
                params["latency_offsets"] = {
                    k: v for k, v in params["latency_offsets"].items() if v is not None
                }
                if not params["latency_offsets"]:
                    del params["latency_offsets"]

        return ", ".join([f"{param}={value}" for param, value in params.items()])

    # No need to redefined I/Os
    io_ops = [*sfg.input_operations, *sfg.output_operations]

    result += "\n# Inputs:\n"
    for input_op in sfg.input_operations:
        result += f"{input_op.graph_id} = Input({kwarg_unpacker(input_op)})\n"

    result += "\n# Outputs:\n"
    for output_op in sfg.output_operations:
        result += f"{output_op.graph_id} = Output({kwarg_unpacker(output_op)})\n"

    result += "\n# Operations:\n"
    for operation in sfg.split():
        if operation in io_ops:
            continue
        if isinstance(operation, SFG):
            counter += 1
            result = sfg_to_python(operation, counter) + result
            continue

        result += (
            f"{operation.graph_id} ="
            f" {operation.__class__.__name__}({kwarg_unpacker(operation)})\n"
        )

    result += "\n# Signals:\n"
    # Keep track of already existing connections to avoid adding duplicates
    connections = []
    for operation in sfg.split():
        for out in operation.outputs:
            for signal in out.signals:
                destination = cast(InputPort, signal.destination)
                dest_op = destination.operation
                connection = (
                    f"Signal(source={operation.graph_id}."
                    f"output({operation.outputs.index(signal.source)}),"
                    f" destination={dest_op.graph_id}."
                    f"input({dest_op.inputs.index(destination)}))\n"
                )
                if connection in connections:
                    continue

                result += connection
                connections.append(connection)

    inputs = "[" + ", ".join(op.graph_id for op in sfg.input_operations) + "]"
    outputs = "[" + ", ".join(op.graph_id for op in sfg.output_operations) + "]"
    sfg_name = sfg.name if sfg.name else f"sfg{counter}" if counter > 0 else "sfg"
    sfg_name_var = sfg_name.replace(" ", "_").replace("-", "_")
    result += "\n# Signal flow graph:\n"
    result += (
        f"{sfg_name_var} = SFG(inputs={inputs}, outputs={outputs}, name='{sfg_name}')\n"
    )
    result += "\n# SFG Properties:\n" + "prop = {'name':" + f"{sfg_name_var}" + "}\n"

    if suffix is not None:
        result += "\n" + suffix + "\n"

    return result


def python_to_sfg(path: str) -> tuple[SFG, dict[str, tuple[int, int]]]:
    """
    Given a serialized file, try to deserialize it and load it to the library.

    Parameters
    ----------
    path : str
        Path to file to read and deserialize.
    """
    local_vars = {}

    with Path(path).open() as file:
        code = compile(file.read(), path, "exec")
        exec(code, globals(), local_vars)

    # access variables from local_vars
    sfg_object = None
    if "prop" in local_vars and "name" in local_vars["prop"]:
        sfg_object = local_vars["prop"]["name"]
    else:
        for v in local_vars.values():
            if isinstance(v, SFG):
                sfg_object = v
                break

    positions = local_vars.get("positions", {})

    if sfg_object is None:
        raise ValueError("No SFG object found in the provided file.")

    return sfg_object, positions


def schedule_to_python(schedule: Schedule) -> str:
    """
    Given a schedule structure try to serialize it for saving to a file.

    Parameters
    ----------
    schedule : :class:`~b_asic.schedule.Schedule`
        The schedule to serialize.
    """
    if not isinstance(schedule, Schedule):
        raise TypeError("A Schedule must be provided")
    sfg_name = (
        schedule.sfg.name.replace(" ", "_").replace("-", "_")
        if schedule.sfg.name
        else "sfg"
    )
    result = "\n# Schedule:\n"
    nonzerolaps = {gid: val for gid, val in dict(schedule.laps).items() if val}
    result += (
        f"{sfg_name}_schedule = Schedule({sfg_name}, {schedule.schedule_time},"
        f" {schedule.cyclic}, 'provided', {schedule.start_times},"
        f" {nonzerolaps})\n"
    )
    return sfg_to_python(schedule.sfg, schedule=True) + result
