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
