import pytest

try:
    from qtpy.QtGui import QColor

    from b_asic.gui_utils.about_window import AboutWindow
    from b_asic.gui_utils.color_button import ColorButton
    from b_asic.gui_utils.mpl_window import MPLWindow
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def test_about_window_loads_logo(qtbot):
    widget = AboutWindow(None)
    qtbot.addWidget(widget)

    assert not widget.logo2.pixmap().isNull()


def test_color_button_preserves_background_when_setting_text_color(qtbot):
    button = ColorButton(QColor("red"))
    qtbot.addWidget(button)

    button.set_text_color(QColor("white"))

    assert "background-color: #ff0000;" in button.styleSheet()
    assert "color: #ffffff;" in button.styleSheet()


def test_mpl_window_axes_shapes(qtbot):
    single_axes = MPLWindow()
    multiple_axes = MPLWindow(subplots=(3, 1))
    qtbot.addWidget(single_axes)
    qtbot.addWidget(multiple_axes)

    assert single_axes.axes.__class__.__name__ == "Axes"
    assert multiple_axes.axes.shape == (3,)
