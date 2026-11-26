"""Shared visual theme and theming controls for the Qt GUIs."""

from dataclasses import dataclass
from typing import Literal

from qtpy.QtCore import QSettings
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QAction, QActionGroup, QApplication, QMenu, QWidget

from b_asic._preferences import MEMORY_CLUSTER_COLOR, MEMORY_COLOR, MUX_COLOR, PE_COLOR

ThemeMode = Literal["system", "light", "dark"]

SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
CORNER_RADIUS = 6
BORDER_WIDTH = 1
FONT_SIZE = 10
FONT_FAMILY = "sans-serif"

THEME_SETTINGS_KEY = "gui/theme"
ROUNDED_CORNERS_SETTINGS_KEY = "gui/rounded-corners"


@dataclass(frozen=True)
class ThemeColors:
    canvas: QColor
    panel: QColor
    surface: QColor
    border: QColor
    text: QColor
    text_muted: QColor
    accent: QColor
    success: QColor
    warning: QColor
    selection: QColor
    grid: QColor
    wire: QColor
    wire_active: QColor
    wire_warning: QColor


_LIGHT = ThemeColors(
    canvas=QColor("#f7f9fc"),
    panel=QColor("#eef2f7"),
    surface=QColor("#ffffff"),
    border=QColor("#c7d0dc"),
    text=QColor("#17212b"),
    text_muted=QColor("#64748b"),
    accent=QColor(*PE_COLOR),
    success=QColor(*MEMORY_COLOR),
    warning=QColor(*MUX_COLOR),
    selection=QColor(*MEMORY_CLUSTER_COLOR),
    grid=QColor("#696969"),
    wire=QColor("#475569"),
    wire_active=QColor(*MEMORY_COLOR),
    wire_warning=QColor("#dc2626"),
)

# Charcoal surfaces keep the dark mode modern without becoming near-black.
_DARK = ThemeColors(
    canvas=QColor("#252b35"),
    panel=QColor("#2e3541"),
    surface=QColor("#394251"),
    border=QColor("#596579"),
    text=QColor("#eef2f8"),
    text_muted=QColor("#b3bdcc"),
    accent=QColor(*PE_COLOR),
    success=QColor(*MEMORY_COLOR),
    warning=QColor(*MUX_COLOR),
    selection=QColor("#24574f"),
    grid=QColor("#758195"),
    wire=QColor("#c2ccda"),
    wire_active=QColor(*MEMORY_COLOR),
    wire_warning=QColor("#fb7185"),
)


@dataclass
class _ThemeState:
    mode: ThemeMode
    colors: ThemeColors
    rounded: bool


_state = _ThemeState("light", _LIGHT, True)


def current_theme() -> ThemeColors:
    """Return the semantic colors currently applied to the application."""
    return _state.colors


def theme_mode() -> ThemeMode:
    """Return the active theme mode."""
    return _state.mode


def corner_radius() -> int:
    """Return the active shared corner radius in logical pixels."""
    return CORNER_RADIUS if _state.rounded else 0


def saved_theme_mode(settings: QSettings | None = None) -> ThemeMode:
    """Read and validate the persisted theme preference."""
    settings = settings or QSettings()
    value = settings.value(THEME_SETTINGS_KEY, "system", str)
    return value if value in ("system", "light", "dark") else "system"


def saved_rounded_corners(settings: QSettings | None = None) -> bool:
    """Read the persisted rounded-corner preference."""
    settings = settings or QSettings()
    return settings.value(ROUNDED_CORNERS_SETTINGS_KEY, True, bool)


def _palette(colors: ThemeColors) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, colors.panel)
    palette.setColor(QPalette.ColorRole.WindowText, colors.text)
    palette.setColor(QPalette.ColorRole.Base, colors.canvas)
    palette.setColor(QPalette.ColorRole.AlternateBase, colors.panel)
    palette.setColor(QPalette.ColorRole.ToolTipBase, colors.surface)
    palette.setColor(QPalette.ColorRole.ToolTipText, colors.text)
    palette.setColor(QPalette.ColorRole.Text, colors.text)
    palette.setColor(QPalette.ColorRole.Button, colors.surface)
    palette.setColor(QPalette.ColorRole.ButtonText, colors.text)
    palette.setColor(QPalette.ColorRole.BrightText, colors.text)
    palette.setColor(QPalette.ColorRole.Highlight, colors.accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, colors.accent)
    palette.setColor(QPalette.ColorRole.PlaceholderText, colors.text_muted)
    return palette


def apply_theme(app: QApplication, mode: ThemeMode) -> ThemeColors:
    """Apply a palette-first theme and shared component stylesheet."""
    if mode == "system":
        style = app.style() if hasattr(app, "style") else None
        system_palette = style.standardPalette() if style is not None else QPalette()
        system_is_dark = (
            system_palette.color(QPalette.ColorRole.Window).lightness() < 128
        )
        colors = _DARK if system_is_dark else _LIGHT
        palette = _palette(colors)
    else:
        colors = _DARK if mode == "dark" else _LIGHT
        palette = _palette(colors)

    if not hasattr(app, "setPalette"):
        return colors
    _state.mode = mode
    _state.colors = colors
    _state.rounded = saved_rounded_corners()
    app.setPalette(palette)
    app.setProperty("b-asic-theme", mode)
    app.setStyleSheet(
        f"""
        QGraphicsView, QListWidget, QTableWidget {{
            border: {BORDER_WIDTH}px solid {colors.border.name()};
            border-radius: {corner_radius()}px;
            background: {colors.canvas.name()};
        }}
        QGroupBox {{
            border: {BORDER_WIDTH}px solid {colors.border.name()};
            border-radius: {corner_radius()}px;
            margin-top: {SPACING_MD}px;
            padding-top: {SPACING_SM}px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {SPACING_SM}px;
            padding: 0 {SPACING_XS}px;
        }}
        QSplitter::handle {{
            background: {colors.border.name()};
        }}
        QToolBar {{
            spacing: {SPACING_SM}px;
            padding: {SPACING_XS}px;
        }}
        QToolTip {{
            color: {colors.text.name()};
            background: {colors.surface.name()};
            border: {BORDER_WIDTH}px solid {colors.border.name()};
            padding: {SPACING_XS}px;
            border-radius: {SPACING_XS}px;
        }}
        """
    )
    for window in app.topLevelWidgets():
        window.update()
    return colors


def install_theme_menu(
    parent: QWidget, menu: QMenu, refresh: object | None = None
) -> QMenu:
    """Add a persisted System/Light/Dark selector to *menu*."""
    theme_menu = QMenu("Theme", menu)
    menu.addMenu(theme_menu)
    parent._theme_menu = theme_menu
    group = QActionGroup(parent)
    group.setExclusive(True)
    selected = saved_theme_mode()

    def change_mode(checked: bool, mode: ThemeMode) -> None:
        if not checked:
            return
        settings = QSettings()
        settings.setValue(THEME_SETTINGS_KEY, mode)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, mode)
        if callable(refresh):
            refresh()

    for mode, label in (("system", "System"), ("light", "Light"), ("dark", "Dark")):
        action = QAction(label, parent)
        action.setCheckable(True)
        action.setChecked(mode == selected)
        action.triggered.connect(
            lambda checked=False, selected_mode=mode: change_mode(
                checked, selected_mode
            )
        )
        group.addAction(action)
        theme_menu.addAction(action)
    theme_menu.addSeparator()
    rounded_action = QAction("Rounded corners", parent)
    rounded_action.setCheckable(True)
    rounded_action.setChecked(saved_rounded_corners())

    def change_rounding(checked: bool) -> None:
        settings = QSettings()
        settings.setValue(ROUNDED_CORNERS_SETTINGS_KEY, checked)
        _state.rounded = checked
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme_mode())
        if callable(refresh):
            refresh()

    rounded_action.triggered.connect(change_rounding)
    theme_menu.addAction(rounded_action)
    return theme_menu
