import pytest

try:
    import b_asic.GUI as GUI
except ImportError:
    pytestmark = pytest.mark.skip('Qt not setup')


def test_start(qtbot):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()
