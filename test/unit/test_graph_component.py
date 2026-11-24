"""Base copying of required constructor parameters and additional metadata."""

import pytest

from b_asic import graph_component
from b_asic.core_operations import Addition, AddSub, Subtraction
from b_asic.graph_component import AbstractGraphComponent, Name, TypeName


class ParameterizedComponent(AbstractGraphComponent):
    def __init__(self, config, /, *, scale):
        super().__init__()
        self.constructor_config = config
        self.constructor_scale = scale
        self.set_param("config", config)
        self.set_param("scale", scale)

    @classmethod
    def type_name(cls):
        return TypeName("parameterized")

    @property
    def neighbors(self):
        return []


def test_copy_supplies_required_constructor_parameters():
    original = ParameterizedComponent({"values": [1, 2]}, scale=3)
    original.name = Name("original")
    original.graph_id = "parameterized0"
    original.set_param("metadata", {"labels": ["a"]})
    copied = original.copy()
    assert copied.name == original.name
    assert copied.graph_id == original.graph_id
    assert copied.params == original.params
    assert copied.constructor_config == {"values": [1, 2]}
    assert copied.constructor_scale == 3
    copied.param("config")["values"].append(4)
    copied.param("metadata")["labels"].append("b")
    assert original.param("config") == {"values": [1, 2]}
    assert original.param("metadata") == {"labels": ["a"]}


def test_copy_respects_explicit_constructor_arguments():
    original = ParameterizedComponent({"values": [1]}, scale=3)
    copied = original.copy({"values": [2]}, scale=4)
    assert copied.constructor_config == {"values": [2]}
    assert copied.constructor_scale == 4
    # As before, stored parameters are restored after construction.
    assert copied.params == original.params


def test_copy_reuses_signature_but_binds_current_parameters(monkeypatch):
    class Component(ParameterizedComponent):
        pass

    inspected = []
    original_signature = graph_component.signature

    def track_signature(component_type):
        inspected.append(component_type)
        return original_signature(component_type)

    monkeypatch.setattr(graph_component, "signature", track_signature)
    original = Component({"values": [1]}, scale=3)
    first = original.copy()
    original.set_param("config", {"values": [2]})
    original.set_param("scale", 4)
    second = original.copy()

    assert inspected == [Component]
    assert first.constructor_config == {"values": [1]}
    assert first.constructor_scale == 3
    assert second.constructor_config == {"values": [2]}
    assert second.constructor_scale == 4
    second.param("config")["values"].append(5)
    assert original.param("config") == {"values": [2]}


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize("parameter", ["in0_scale", "in1_scale", "out0_scale"])
def test_copy_preserves_generic_scaling_parameters(operation_type, parameter):
    original = operation_type()
    original.set_param(parameter, -2)

    copied = original.copy()

    assert copied.params == original.params
    assert copied.evaluate(3, 5) == original.evaluate(3, 5)
