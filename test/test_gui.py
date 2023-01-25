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
    assert ops_before_remove -1 == len(widget.operationDragDict)

    widget.exit_app()
