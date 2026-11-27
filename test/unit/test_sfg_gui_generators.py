"""Generator configuration, validation, and nested SFG insertion."""

import inspect

import pytest

pytest.importorskip("qtpy.QtWidgets", exc_type=ImportError)

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox

from b_asic import sfg_generators
from b_asic.save_load_structure import python_to_sfg, sfg_to_python
from b_asic.sfg import SFG
from b_asic.sfg_gui import SFGGenerator
from b_asic.sfg_gui.generator_window import GeneratorWindow
from b_asic.sfg_gui.main_window import SFGMainWindow
from b_asic.sfg_gui.sfg_generator import builtin_generators
from b_asic.special_operations import Input, Output


@pytest.mark.parametrize("name", sfg_generators.__all__)
def test_builtin_generator_configuration(qtbot, name):
    function = getattr(sfg_generators, name)
    config = SFGGenerator(function)
    window = GeneratorWindow(generators=[config])
    qtbot.addWidget(window)
    assert set(window._fields) == set(inspect.signature(function).parameters)
    required = {
        "size": "2",
        "factor": "2",
        "points": "2",
        "m": "2",
        "N": "4",
        "coefficients": "[0.25, 0.5]",
        "b": "[1, 0.5]",
        "a": "[1, 0.25]",
    }
    for parameter in config.parameters.values():
        if parameter.default is inspect.Parameter.empty:
            window._fields[parameter.name].setText(required[parameter.name])
    with qtbot.waitSignal(window.generated) as signal:
        qtbot.mouseClick(window._buttons.button(QDialogButtonBox.Ok), Qt.LeftButton)
    assert isinstance(signal.args[0], SFG)
    assert window.result() == QDialog.Accepted


def test_literal_dropdowns_preserve_values_and_defaults(qtbot):
    window = GeneratorWindow(
        generators=[SFGGenerator(sfg_generators.ldlt_matrix_inverse)]
    )
    qtbot.addWidget(window)
    mode, pe, mem = (window._fields[name] for name in ("mode", "pe", "mem"))
    assert isinstance(mode, QComboBox)
    assert isinstance(pe, QComboBox)
    assert isinstance(mem, QCheckBox)
    assert [mode.itemData(i) for i in range(mode.count())] == ["eqs", "mult"]
    assert [pe.itemData(i) for i in range(pe.count())] == ["addsub", "mads", None]
    assert pe.currentData() is None
    assert mode.currentData() == "eqs"
    data_type = window._fields["data_type"]
    multiplication_method = window._fields["multiplication_method"]
    assert isinstance(data_type, QComboBox)
    assert isinstance(multiplication_method, QComboBox)
    assert [data_type.itemData(i) for i in range(data_type.count())] == [
        "real",
        "complex",
        "split",
    ]
    assert data_type.currentData() == "real"
    assert multiplication_method.currentData() == "four"
    window._fields["N"].setText("2")
    mode.setCurrentIndex(1)
    pe.setCurrentIndex(1)
    mem.setChecked(True)
    data_type.setCurrentIndex(2)
    multiplication_method.setCurrentIndex(1)
    assert window.configuration() == {
        "N": 2,
        "name": None,
        "mode": "mult",
        "pe": "mads",
        "mem": True,
        "data_type": "split",
        "multiplication_method": "three",
    }
    with qtbot.waitSignal(window.generated):
        window._generate()


def test_complex_coefficients_and_nested_properties(qtbot):
    window = GeneratorWindow(generators=[SFGGenerator(sfg_generators.fir)])
    qtbot.addWidget(window)
    window._fields["coefficients"].setText("[1+2j, 0.5, -1j]")
    window._fields["mult_properties"].setText(
        "{'latency_offsets': {'in0': 0, 'out0': 3}}"
    )
    window._fields["add_properties"].setText("{'execution_time': 1}")
    window._fields["name"].setText("123")
    values = window.configuration()
    assert values["coefficients"] == [1 + 2j, 0.5, -1j]
    assert values["mult_properties"] == {"latency_offsets": {"in0": 0, "out0": 3}}
    assert values["name"] == "123"
    with qtbot.waitSignal(window.generated):
        window._generate()


@pytest.mark.parametrize("value", ["", "1.5", "True", "__import__('os')", "0"])
def test_invalid_configuration_can_be_corrected(qtbot, value):
    window = GeneratorWindow(generators=[SFGGenerator(sfg_generators.bitonic_sort)])
    qtbot.addWidget(window)
    graphs = []
    window.generated.connect(graphs.append)
    window._fields["size"].setText(value)
    window._generate()
    assert window._error.text()
    assert not graphs
    assert window.result() != QDialog.Accepted
    window._fields["size"].setText("2")
    window._generate()
    assert len(graphs) == 1


def test_switching_generators_and_cancellation(qtbot):
    configs = builtin_generators()
    window = GeneratorWindow(generators=configs)
    qtbot.addWidget(window)
    for index, config in enumerate(configs):
        window._selector.setCurrentIndex(index)
        assert set(window._fields) == set(config.parameters)
    graphs = []
    window.generated.connect(graphs.append)
    qtbot.mouseClick(window._buttons.button(QDialogButtonBox.Cancel), Qt.LeftButton)
    assert not graphs
    assert window.result() == QDialog.Rejected


def test_generator_can_be_subclassed_with_defaults():
    class FIRGenerator(SFGGenerator):
        generator = staticmethod(sfg_generators.fir)

    config = FIRGenerator(defaults={"coefficients": [1, 2]}, name="Two tap FIR")
    assert config.name == "Two tap FIR"
    assert isinstance(config.generate(), SFG)
    assert isinstance(config.generate(coefficients=[2, 3]), SFG)
    with pytest.raises(ValueError, match="Unknown generator parameters"):
        FIRGenerator(defaults={"unknown": 1})

    # A default for the first required parameter must not hide later ones.
    iir = SFGGenerator(sfg_generators.direct_form_1_iir, defaults={"b": [1, 2]})
    assert isinstance(iir.generate(a=[1, 0.25]), SFG)


def test_saving_multiple_and_deeply_nested_generated_graphs(tmp_path):
    source = Input()
    first = sfg_generators.fir([2], name="FIR's (1)")
    first.input(0).connect(source)
    middle = SFG(inputs=[source], outputs=[Output(first)], name="Middle (1)")
    source = Input()
    middle.input(0).connect(source)
    second = sfg_generators.fir([3], name="FIR's (1)")
    second.input(0).connect(middle)
    graph = SFG(inputs=[source], outputs=[Output(second)], name="Outer (1)")
    path = tmp_path / "deep.py"
    path.write_text(sfg_to_python(graph))
    loaded, _ = python_to_sfg(str(path))
    assert loaded.evaluate_outputs([5]) == [30]
    assert len([op for op in loaded.split() if isinstance(op, SFG)]) == 2


def test_generated_sfg_is_one_connectable_serializable_operation(qtbot, tmp_path):
    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._generate_sfg_action.trigger()
    dialog = window._generator_window
    configs = dialog.generators
    index = next(
        i for i, config in enumerate(configs) if config.generator is sfg_generators.fir
    )
    dialog._selector.setCurrentIndex(index)
    dialog._fields["coefficients"].setText("[2]")
    dialog._generate()
    assert len(window._drag_buttons) == 1
    graph = next(iter(window._drag_buttons))
    assert isinstance(graph, SFG)
    button = window._drag_buttons[graph]
    assert len(button.port_list) == graph.input_count + graph.output_count == 2
    source, output = Input(), Output()
    window.add_operation(source)
    window.add_operation(output)
    window._connect_button(
        window._drag_buttons[source].port_list[0], button.port_list[0]
    )
    window._connect_button(
        button.port_list[1], window._drag_buttons[output].port_list[0]
    )
    outer = SFG(inputs=[source], outputs=[output], name="Outer")
    assert outer.evaluate_outputs([3]) == [6]
    assert len([op for op in outer.split() if isinstance(op, SFG)]) == 1
    path = tmp_path / "nested.py"
    path.write_text(sfg_to_python(outer))
    loaded, _ = python_to_sfg(str(path))
    assert loaded.evaluate_outputs([3]) == [6]
    assert len([op for op in loaded.split() if isinstance(op, SFG)]) == 1
    dialog = GeneratorWindow(window, [SFGGenerator(sfg_generators.fir)])
    dialog.generated.connect(window._insert_generated_sfg)
    dialog._fields["coefficients"].setText("[2]")
    dialog._generate()
    assert len(window._drag_buttons) == 4
    assert len({op.name for op in window._drag_buttons if isinstance(op, SFG)}) == 2
