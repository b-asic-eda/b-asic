"""Local algebraic patterns used by :meth:`SFG.join`."""

from b_asic.core_operations import (
    MAD,
    MADS,
    Addition,
    AddSub,
    Constant,
    ConstantMultiplication,
    ImaginaryMultiplication,
    LeftShift,
    Max,
    Min,
    Multiplication,
    Negation,
    RightShift,
    Shift,
    Subtraction,
)
from b_asic.fft_operations import (
    R2Butterfly,
    R2DIFButterfly,
    R2DITButterfly,
    R2TFButterfly,
)
from b_asic.operation import Operation
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import Sink

_ARITHMETIC = (Addition, Subtraction, AddSub)
_BUTTERFLIES = (R2Butterfly, R2DIFButterfly, R2TFButterfly)


def _disconnect(operation):
    for port in operation.inputs:
        for signal in list(port.signals):
            signal.remove_source()
            signal.remove_destination()


def _replace(operation, sources):
    """Reconnect existing output signals, retaining their metadata and consumers."""
    for output, source in zip(operation.outputs, sources, strict=True):
        for signal in list(output.signals):
            signal.set_source(source)
    _disconnect(operation)


def _shift(operation):
    if isinstance(operation, Shift | RightShift):
        return operation.value
    if isinstance(operation, LeftShift):
        return -operation.value
    return None


def _coefficient(operation):
    if isinstance(operation, ConstantMultiplication):
        return operation.value
    if isinstance(operation, Negation):
        return -1
    if isinstance(operation, ImaginaryMultiplication):
        return 1j
    shift = _shift(operation)
    if shift is not None:
        return 2 ** (-shift)
    return None


def _scaled(source, coefficient, name=""):
    if coefficient == 1:
        return source
    if coefficient == 0:
        return Constant(0, name=name).output(0)
    if coefficient == -1:
        return Negation(source, name=name).output(0)
    if coefficient == 1j:
        return ImaginaryMultiplication(source, name=name).output(0)
    return ConstantMultiplication(coefficient, source, name=name).output(0)


def _is_add(operation):
    return isinstance(operation, Addition) or (
        isinstance(operation, AddSub) and operation.is_add
    )


def _plain(operation):
    return isinstance(operation, _ARITHMETIC) and not any(
        (
            operation.in0_scale,
            operation.in1_scale,
            operation.out0_scale,
            operation.mul_j,
        )
    )


def _arithmetic(operation, sources, **changes):
    params = {
        "in0_scale": operation.in0_scale,
        "in1_scale": operation.in1_scale,
        "out0_scale": operation.out0_scale,
        "mul_j": operation.mul_j,
        "name": operation.name,
    }
    params.update(changes)
    if isinstance(operation, AddSub):
        params.setdefault("is_add", operation.is_add)
    return (
        type(operation)(*sources, **params)
        if not isinstance(operation, AddSub)
        else AddSub(in0=sources[0], in1=sources[1], **params)
    )


def _pair(first, second):
    """Join a producer into one consumer; other producer uses remain intact."""
    sources = [port.connected_source for port in second.inputs]
    indices = [i for i, source in enumerate(sources) if source.operation is first]
    if not indices:
        return False

    # Constants specialize either operand of a multiplication.
    if isinstance(first, Constant) and isinstance(second, Multiplication):
        index = indices[0]
        result = _scaled(sources[1 - index], first.value, second.name)
        _replace(second, [result])
        return True

    coefficient = _coefficient(first)
    if (
        coefficient is not None
        and isinstance(second, R2Butterfly | R2DITButterfly)
        and indices == [1]
    ):
        weight = second.w if isinstance(second, R2DITButterfly) else 1
        fused = R2DITButterfly(
            weight * coefficient,
            sources[0],
            first.input(0).connected_source,
            name=second.name,
        )
        _replace(second, [fused.output(0), fused.output(1)])
        return True

    if coefficient is not None and second.input_count == 1:
        other = _coefficient(second)
        if other is not None:
            left, right = _shift(first), _shift(second)
            source = first.input(0).connected_source
            result = (
                Shift(left + right, source, name=second.name).output(0)
                if left is not None and right is not None and left + right
                else _scaled(source, coefficient * other, second.name)
            )
            _replace(second, [result])
            return True

    if isinstance(first, _ARITHMETIC) and _shift(second) is not None:
        scale = first.out0_scale + _shift(second)
        if scale >= 0:
            result = _arithmetic(
                first,
                [port.connected_source for port in first.inputs],
                out0_scale=scale,
            )
            _replace(second, [result.output(0)])
            return True

    if (
        isinstance(first, _ARITHMETIC)
        and isinstance(second, Negation)
        and not _is_add(first)
        and not first.mul_j
    ):
        result = AddSub(
            False,
            first.input(1).connected_source,
            first.input(0).connected_source,
            in0_scale=first.in1_scale,
            in1_scale=first.in0_scale,
            out0_scale=first.out0_scale,
            name=second.name,
        )
        _replace(second, [result.output(0)])
        return True

    if isinstance(second, _ARITHMETIC) and coefficient is not None:
        changes = {}
        shift = _shift(first)
        if shift is not None:
            for index in indices:
                key = f"in{index}_scale"
                scale = getattr(second, key) + shift
                if scale < 0:
                    return False
                changes[key] = scale
                sources[index] = first.input(0).connected_source
            result = _arithmetic(second, sources, **changes).output(0)
        elif coefficient in (-1, 1j, -1j, 1):
            # Factor input 0's phase out of the whole expression. The relative
            # phase of input 1 is representable by is_add and mul_j.
            phase0 = coefficient if 0 in indices else 1
            phase1 = coefficient if 1 in indices else 1
            relative = phase1 / phase0
            relative *= (1 if _is_add(second) else -1) * (1j if second.mul_j else 1)
            for index in indices:
                sources[index] = first.input(0).connected_source
            arithmetic = AddSub(
                is_add=relative in (1, 1j),
                in0=sources[0],
                in1=sources[1],
                in0_scale=second.in0_scale,
                in1_scale=second.in1_scale,
                out0_scale=second.out0_scale,
                mul_j=relative in (1j, -1j),
                name=second.name,
            )
            result = _scaled(arithmetic.output(0), phase0)
        else:
            return False
        _replace(second, [result])
        return True

    if isinstance(first, Multiplication) and _plain(second) and len(indices) == 1:
        index = indices[0]
        x, y = [port.connected_source for port in first.inputs]
        z = sources[1 - index]
        if _is_add(second):
            result = MAD(x, y, z, name=second.name)
        elif index == 1:
            result = MADS(False, z, x, y, name=second.name)
        else:
            result = MAD(x, y, Negation(z), name=second.name)
        _replace(second, [result.output(0)])
        return True
    return False


def _siblings(operation):
    """Recognize parallel add/subtract or min/max branches with common inputs."""
    if not (_plain(operation) or isinstance(operation, Min | Max)):
        return False
    sources = [port.connected_source for port in operation.inputs]
    candidates = list(sources[0].signals)
    for signal in candidates:
        other = signal.destination.operation
        if other is operation:
            continue
        other_sources = [port.connected_source for port in other.inputs]
        if isinstance(operation, Min | Max):
            if not isinstance(other, Max if isinstance(operation, Min) else Min):
                continue
            if other_sources != sources and other_sources != sources[::-1]:
                continue
            from b_asic.core_operations import Comparator  # noqa: PLC0415

            fused = Comparator(*sources, name=operation.name)
            minimum, maximum = (
                (operation, other) if isinstance(operation, Min) else (other, operation)
            )
            _replace(minimum, [fused.output(0)])
            _replace(maximum, [fused.output(1)])
            return True
        if not _plain(other) or _is_add(other) == _is_add(operation):
            continue
        addition, subtraction = (
            (operation, other) if _is_add(operation) else (other, operation)
        )
        sub_sources = [port.connected_source for port in subtraction.inputs]
        add_sources = [port.connected_source for port in addition.inputs]
        if add_sources != sub_sources and add_sources != sub_sources[::-1]:
            continue
        x, y = sub_sources
        coefficient = _coefficient(y.operation)
        if coefficient is not None:
            fused = R2DITButterfly(
                coefficient,
                x,
                y.operation.input(0).connected_source,
                name=addition.name,
            )
        else:
            fused = R2Butterfly(x, y, name=addition.name)
        _replace(addition, [fused.output(0)])
        _replace(subtraction, [fused.output(1)])
        _butterfly_outputs(fused)
        return True
    return False


def _butterfly_outputs(operation):
    """Absorb exclusive output scales into a DIF or two-factor butterfly."""
    if not isinstance(operation, _BUTTERFLIES):
        return False
    factors = [1, 1]
    consumers = [None, None]
    for index, output in enumerate(operation.outputs):
        if len(output.signals) != 1:
            continue
        consumer = output.signals[0].destination.operation
        factor = _coefficient(consumer)
        if factor is not None:
            factors[index] = factor
            consumers[index] = consumer
    if not any(consumers):
        return False
    if isinstance(operation, R2DIFButterfly):
        factors[1] *= operation.w
    elif isinstance(operation, R2TFButterfly):
        factors[0] *= operation.w0
        factors[1] *= operation.w1
    sources = [port.connected_source for port in operation.inputs]
    fused = (
        R2DIFButterfly(factors[1], *sources, name=operation.name)
        if factors[0] == 1
        else R2TFButterfly(*factors, *sources, name=operation.name)
    )
    for index, consumer in enumerate(consumers):
        if consumer is not None:
            _replace(consumer, [fused.output(index)])
        else:
            for signal in list(operation.output(index).signals):
                signal.set_source(fused.output(index))
    _disconnect(operation)
    return True


def join(sfg, target, direction):
    """Apply local patterns to a copy, then discard disconnected intermediates."""
    if direction not in ("forward", "backward"):
        raise ValueError("Direction must be 'forward' or 'backward'")
    result = sfg()
    operation = result.find_by_id(target)
    if not isinstance(operation, Operation):
        raise ValueError(f"Operation {target} not found in SFG")

    changed = _siblings(operation)
    if not changed:
        changed = _butterfly_outputs(operation) if direction == "forward" else False
        if not changed:
            if direction == "forward":
                pairs = [
                    (operation, signal.destination.operation)
                    for output in operation.outputs
                    for signal in list(output.signals)
                ]
            else:
                pairs = [
                    (port.connected_source.operation, operation)
                    for port in operation.inputs
                ]
                # A multiplier following a butterfly can initiate output fusion.
                for first, _ in pairs:
                    if _butterfly_outputs(first):
                        changed = True
                        break
            if not changed:
                for first, second in dict.fromkeys(pairs):
                    if _pair(first, second):
                        changed = True
                        # Backward joins consume the selected node in one step.
                        if direction == "backward":
                            break

    if not changed:
        return result
    return finish(result)


def finish(result):
    """Remove dead input edges and terminate unused interface ports."""
    live = set()
    pending = list(result.output_operations)
    while pending:
        node = pending.pop()
        if node in live:
            continue
        live.add(node)
        pending.extend(port.connected_source.operation for port in node.inputs)
    for node in result.operations:
        if node not in live and not isinstance(node, Input | Output):
            _disconnect(node)
    for node in live | set(result.input_operations):
        for output in node.outputs:
            if not output.signals:
                Sink().input(0).connect(output)
    return result()
