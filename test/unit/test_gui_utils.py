import pytest

try:
    from qtpy.QtCore import QSettings
    from qtpy.QtGui import QColor, QPalette

    from b_asic.gui_utils.about_window import AboutWindow
    from b_asic.gui_utils.color_button import ColorButton
    from b_asic.gui_utils.mpl_window import MPLWindow
    from b_asic.gui_utils.theme import (
        THEME_SETTINGS_KEY,
        apply_theme,
        saved_theme_mode,
        theme_mode,
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


def test_theme_modes_update_palette_and_read_settings(qapp, tmp_path):
    original_mode = theme_mode()
    try:
        colors = apply_theme(qapp, "dark")

        assert qapp.palette().color(QPalette.ColorRole.Base) == colors.canvas
        assert colors.canvas.lightness() > 40
        assert qapp.property("b-asic-theme") == "dark"

        settings = QSettings(str(tmp_path / "theme.ini"), QSettings.IniFormat)
        settings.setValue(THEME_SETTINGS_KEY, "light")
        assert saved_theme_mode(settings) == "light"
        settings.setValue(THEME_SETTINGS_KEY, "invalid")
        assert saved_theme_mode(settings) == "system"
    finally:
        apply_theme(qapp, original_mode)


def test_system_theme_uses_matching_shared_palette(qapp):
    original_mode = theme_mode()
    try:
        system_colors = apply_theme(qapp, "system")
        system_palette = qapp.style().standardPalette()
        expected_mode = (
            "dark"
            if system_palette.color(QPalette.ColorRole.Window).lightness() < 128
            else "light"
        )
        expected_colors = apply_theme(qapp, expected_mode)

        assert system_colors == expected_colors
    finally:
        apply_theme(qapp, original_mode)


def test_scheduler_data_colors_survive_dark_theme(qapp):
    from b_asic._preferences import EXECUTION_TIME_COLOR, LATENCY_COLOR, MEMORY_COLOR
    from b_asic.scheduler_gui._preferences import (
        ACTIVE_COLOR_TYPE,
        EXECUTION_TIME_COLOR_TYPE,
        LATENCY_COLOR_TYPE,
        refresh_theme_defaults,
    )

    original_mode = theme_mode()
    try:
        apply_theme(qapp, "dark")
        refresh_theme_defaults()

        assert QColor(*LATENCY_COLOR) == LATENCY_COLOR_TYPE.DEFAULT
        assert QColor(*EXECUTION_TIME_COLOR) == EXECUTION_TIME_COLOR_TYPE.DEFAULT
        assert QColor(*MEMORY_COLOR) == ACTIVE_COLOR_TYPE.DEFAULT
    finally:
        apply_theme(qapp, original_mode)
        refresh_theme_defaults()
