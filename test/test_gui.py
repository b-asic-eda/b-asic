from qtpy import QtCore


import pytest

try:
    import b_asic.GUI as GUI
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


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
    dragbutton = widget.operationDragDict[op[0]]
    assert not dragbutton.is_flipped()
    dragbutton._flip()
    assert dragbutton.is_flipped()
    widget.exit_app()


def test_sfg_invalidated_by_remove_of_operation(qtbot, datadir):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    ops_before_remove = len(widget.operationDragDict)
    op = sfg.find_by_name("cmul2")
    dragbutton = widget.operationDragDict[op[0]]
    dragbutton.remove()
    assert not widget.sfg_dict
    assert ops_before_remove - 1 == len(widget.operationDragDict)

    widget.exit_app()


def test_select_operation(qtbot, datadir):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join('twotapfir.py'))
    sfg = widget.sfg_dict['twotapfir']
    op = sfg.find_by_name("cmul2")[0]
    dragbutton = widget.operationDragDict[op]
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
    dragbutton2 = widget.operationDragDict[op2]
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
