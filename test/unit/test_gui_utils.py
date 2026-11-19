import pytest

try:
    from qtpy.QtCore import QSettings
    from qtpy.QtGui import QColor, QPalette
    from qtpy.QtWidgets import QMenu, QWidget

    from b_asic.gui_utils.about_window import AboutWindow
    from b_asic.gui_utils.color_button import ColorButton
    from b_asic.gui_utils.mpl_window import MPLWindow
    from b_asic.gui_utils.theme import (
        DARK_THEME,
        LIGHT_THEME,
        add_theme_menu,
        apply_theme,
        install_theme,
    )
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
    assert single_axes.axes.xaxis.label.get_fontfamily() == ["DejaVu Serif"]


def test_theme_palette_and_persistence(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat)
    original_palette = QPalette(qapp.palette())

    try:
        apply_theme(qapp, "dark", settings)
        assert qapp.palette().color(QPalette.ColorRole.Window) == DARK_THEME.panel
        assert settings.value("gui/theme") == "dark"

        assert install_theme(qapp, settings) == "dark"

        apply_theme(qapp, "light")
        assert qapp.palette().color(QPalette.ColorRole.Window) == LIGHT_THEME.panel
    finally:
        qapp.setPalette(original_palette)


def test_theme_menu_updates_application(qapp, qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat)
    parent = QWidget()
    menu = QMenu(parent)
    qtbot.addWidget(parent)

    theme_menu = add_theme_menu(parent, menu, settings)
    light_action = next(
        action for action in theme_menu.actions() if action.data() == "light"
    )
    dark_action = next(
        action for action in theme_menu.actions() if action.data() == "dark"
    )
    original_palette = QPalette(qapp.palette())

    try:
        light_action.trigger()
        assert settings.value("gui/theme") == "light"
        assert qapp.palette().color(QPalette.ColorRole.Window) == LIGHT_THEME.panel

        dark_action.trigger()
        assert settings.value("gui/theme") == "dark"
        assert qapp.palette().color(QPalette.ColorRole.Window) == DARK_THEME.panel
    finally:
        qapp.setPalette(original_palette)
