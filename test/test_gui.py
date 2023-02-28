import pytest
from qtpy import QtCore
from qtpy.QtWidgets import QInputDialog

try:
    import b_asic.GUI as GUI
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")

from b_asic.core_operations import SquareRoot
from b_asic.special_operations import Input, Output


def test_start(qtbot):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


def test_load(qtbot, datadir):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    assert 'twotapfir' in widget.sfg_dict
    widget.clear_workspace()
    assert 'twotapfir' not in widget.sfg_dict
    assert not widget.sfg_dict

    widget.exit_app()


def test_flip(qtbot, datadir):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    op = sfg.find_by_name("cmul2")
    dragbutton = widget._operation_drag_buttons[op[0]]
    assert not dragbutton.is_flipped()
    dragbutton._flip()
    assert dragbutton.is_flipped()
    widget.exit_app()


def test_sfg_invalidated_by_remove_of_operation(qtbot, datadir):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    ops_before_remove = len(widget._operation_drag_buttons)
    op = sfg.find_by_name("cmul2")
    dragbutton = widget._operation_drag_buttons[op[0]]
    dragbutton.remove()
    assert not widget.sfg_dict
    assert ops_before_remove - 1 == len(widget._operation_drag_buttons)

    widget.exit_app()


def test_sfg_invalidated_by_deleting_of_operation(qtbot, datadir):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    ops_before_remove = len(widget._operation_drag_buttons)
    op = sfg.find_by_name("cmul2")
    dragbutton = widget._operation_drag_buttons[op[0]]
    # Click
    qtbot.mouseClick(dragbutton, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(widget, QtCore.Qt.Key.Key_Delete)
    assert not widget.sfg_dict
    assert ops_before_remove - 1 == len(widget._operation_drag_buttons)

    widget.exit_app()


def test_select_operation(qtbot, datadir):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    op = sfg.find_by_name("cmul2")[0]
    dragbutton = widget._operation_drag_buttons[op]
    assert not dragbutton.pressed
    assert not widget.pressed_operations

    # Click
    qtbot.mouseClick(dragbutton, QtCore.Qt.MouseButton.LeftButton)
    assert dragbutton.pressed
    assert len(widget.pressed_operations) == 1

    # Click again, should unselect
    qtbot.mouseClick(dragbutton, QtCore.Qt.MouseButton.LeftButton)
    # Currently failing
    # assert not dragbutton.pressed
    # assert not widget.pressed_operations

    # Select another operation
    op2 = sfg.find_by_name("add1")[0]
    dragbutton2 = widget._operation_drag_buttons[op2]
    assert not dragbutton2.pressed

    # Click
    qtbot.mouseClick(dragbutton2, QtCore.Qt.MouseButton.LeftButton)
    assert dragbutton2.pressed
    # Unselect previous
    assert not dragbutton.pressed
    assert len(widget.pressed_operations) == 1

    # Control-click first
    qtbot.mouseClick(
        dragbutton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    assert dragbutton2.pressed
    assert dragbutton.pressed
    assert len(widget.pressed_operations) == 2

    # Control-click second
    qtbot.mouseClick(
        dragbutton2,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    assert not dragbutton2.pressed
    assert dragbutton.pressed
    assert len(widget.pressed_operations) == 1

    widget.exit_app()


def test_help_dialogs(qtbot):
    # Smoke test to open up the "help dialogs"
    # Should really test doing this through the menus an/or closing them
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)

    widget.display_faq_page()
    widget.display_about_page()
    widget.display_keybindings_page()
    qtbot.wait(100)
    widget._faq_page.close()
    widget._about_page.close()
    widget._keybindings_page.close()

    widget.exit_app()


def test_simulate(qtbot, datadir):
    # Smoke test to open up the "Simulate SFG" and run default simulation
    # Should really test all different tests
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    assert 'twotapfir' in widget.sfg_dict
    widget.simulate_sfg()
    qtbot.wait(100)
    # widget.dialog.save_properties()
    # qtbot.wait(100)
    widget._simulation_dialog.close()

    widget.exit_app()


def test_properties_window_smoke_test(qtbot, datadir):
    # Smoke test to open up the properties window
    # Should really check that the contents are correct and changes works etc
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    op = sfg.find_by_name("cmul2")[0]
    dragbutton = widget._operation_drag_buttons[op]
    dragbutton.show_properties_window()
    assert dragbutton._properties_window.operation == dragbutton
    qtbot.mouseClick(dragbutton._properties_window.ok, QtCore.Qt.MouseButton.LeftButton)
    widget.exit_app()


def test_properties_window_change_name(qtbot, datadir):
    # Smoke test to open up the properties window
    # Should really check that the contents are correct and changes works etc
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    op = sfg.find_by_name("cmul2")[0]
    dragbutton = widget._operation_drag_buttons[op]
    assert dragbutton.name == "cmul2"
    assert dragbutton.operation.name == "cmul2"
    dragbutton.show_properties_window()
    assert dragbutton._properties_window.edit_name.text() == "cmul2"
    dragbutton._properties_window.edit_name.setText("cmul73")
    qtbot.mouseClick(dragbutton._properties_window.ok, QtCore.Qt.MouseButton.LeftButton)
    dragbutton._properties_window.save_properties()
    assert dragbutton.name == "cmul73"
    assert dragbutton.operation.name == "cmul73"

    widget.exit_app()


def test_add_operation_and_create_sfg(qtbot, monkeypatch):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    in1 = Input()
    sqrt = SquareRoot()
    out1 = Output()
    # Create operations
    widget.create_operation(in1)
    widget.create_operation(sqrt)
    widget.create_operation(out1)
    # Should be three operations
    assert len(widget._operation_drag_buttons) == 3
    # These particular three
    for op in (in1, sqrt, out1):
        assert op in widget._operation_drag_buttons
    # No signals
    assert not widget._arrow_list

    # Click on first port
    in1_port = widget.portDict[widget._operation_drag_buttons[in1]][0]
    qtbot.mouseClick(
        in1_port,
        QtCore.Qt.MouseButton.LeftButton,
    )
    assert len(widget.pressed_ports) == 1

    # Click on second port
    sqrt_in_port = widget.portDict[widget._operation_drag_buttons[sqrt]][0]
    qtbot.mouseClick(
        sqrt_in_port,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    assert len(widget.pressed_ports) == 2

    # Connect ports
    widget._connect_callback()
    # Not sure why this won't work
    # qtbot.keyClick(widget, QtCore.Qt.Key.Key_Space, delay=10)
    # Still one selected!?
    assert len(widget._arrow_list) == 1

    # Click on first port
    sqrt_out_port = widget.portDict[widget._operation_drag_buttons[sqrt]][1]
    qtbot.mouseClick(
        sqrt_out_port,
        QtCore.Qt.MouseButton.LeftButton,
    )
    # Click on second port
    out1_port = widget.portDict[widget._operation_drag_buttons[out1]][0]
    qtbot.mouseClick(
        out1_port,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    # Connect
    widget._connect_callback()
    assert len(widget._arrow_list) == 2

    # Select input op
    qtbot.mouseClick(
        widget._operation_drag_buttons[in1],
        QtCore.Qt.MouseButton.LeftButton,
    )

    # And output op
    qtbot.mouseClick(
        widget._operation_drag_buttons[out1],
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )

    # Monkey patch dialog to return the expected thing
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("foo", True))

    # Create SFG
    widget.create_sfg_from_toolbar()

    # Should be in sfg_dict now
    assert "foo" in widget.sfg_dict
    assert len(widget.sfg_dict) == 1

    widget.exit_app()
