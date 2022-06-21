import pytest

import b_asic.GUI as GUI

def test_start(qtbot):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()
