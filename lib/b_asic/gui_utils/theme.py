"""Shared visual theme definitions for the B-ASIC Qt interfaces."""

from dataclasses import dataclass
from typing import Literal, cast

from qtpy.QtCore import QSettings
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication, QMenu, QWidget

ThemeMode = Literal["system", "light", "dark"]

THEME_SETTING = "gui/theme"
THEME_MODES: tuple[ThemeMode, ...] = ("system", "light", "dark")


@dataclass(frozen=True)
class VisualTheme:
    """Semantic colors and layout values shared by Qt windows."""

    canvas: QColor
    panel: QColor
    surface: QColor
    border: QColor
    text: QColor
    text_secondary: QColor
    accent: QColor
    accent_text: QColor
    success: QColor
    warning: QColor
    danger: QColor
    wire: QColor
    spacing: int = 8
    compact_spacing: int = 4
    corner_radius: int = 6
    border_width: int = 1


LIGHT_THEME = VisualTheme(
    canvas=QColor("#f7f8fa"),
    panel=QColor("#f0f2f5"),
    surface=QColor("#ffffff"),
    border=QColor("#c7ccd4"),
    text=QColor("#202124"),
    text_secondary=QColor("#5f6368"),
    accent=QColor("#1a73e8"),
    accent_text=QColor("#ffffff"),
    success=QColor("#188038"),
    warning=QColor("#d97706"),
    danger=QColor("#c5221f"),
    wire=QColor("#344054"),
)

DARK_THEME = VisualTheme(
    canvas=QColor("#17191d"),
    panel=QColor("#202329"),
    surface=QColor("#292d34"),
    border=QColor("#484d57"),
    text=QColor("#f1f3f4"),
    text_secondary=QColor("#b4bac3"),
    accent=QColor("#6ea8fe"),
    accent_text=QColor("#101214"),
    success=QColor("#6dd58c"),
    warning=QColor("#f6c453"),
    danger=QColor("#f28b82"),
    wire=QColor("#d0d5dd"),
)


def read_theme_mode(settings: QSettings | None = None) -> ThemeMode:
    """Read and validate the persisted GUI theme choice."""
    settings = settings or QSettings()
    value = settings.value(THEME_SETTING, "system", type=str).lower()
    return cast(ThemeMode, value) if value in THEME_MODES else "system"


def _system_palette(app: QApplication) -> QPalette:
    """Return the platform style's current default palette."""
    return app.style().standardPalette()


def _system_is_dark(palette: QPalette) -> bool:
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


def active_theme(app: QApplication) -> VisualTheme:
    """Return semantic colors for the palette currently applied to *app*."""
    return DARK_THEME if _system_is_dark(app.palette()) else LIGHT_THEME


def _palette(theme: VisualTheme) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, theme.panel)
    palette.setColor(QPalette.ColorRole.WindowText, theme.text)
    palette.setColor(QPalette.ColorRole.Base, theme.surface)
    palette.setColor(QPalette.ColorRole.AlternateBase, theme.canvas)
    palette.setColor(QPalette.ColorRole.Text, theme.text)
    palette.setColor(QPalette.ColorRole.Button, theme.surface)
    palette.setColor(QPalette.ColorRole.ButtonText, theme.text)
    palette.setColor(QPalette.ColorRole.ToolTipBase, theme.surface)
    palette.setColor(QPalette.ColorRole.ToolTipText, theme.text)
    palette.setColor(QPalette.ColorRole.Highlight, theme.accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, theme.accent_text)
    palette.setColor(QPalette.ColorRole.Link, theme.accent)
    palette.setColor(QPalette.ColorRole.LinkVisited, theme.accent)
    palette.setColor(QPalette.ColorRole.PlaceholderText, theme.text_secondary)
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, theme.text_secondary
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        theme.text_secondary,
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        theme.text_secondary,
    )
    return palette


def apply_theme(
    app: QApplication,
    mode: ThemeMode,
    settings: QSettings | None = None,
) -> None:
    """Apply and optionally persist a GUI theme."""
    if mode not in THEME_MODES:
        raise ValueError(f"Unknown theme mode: {mode}")

    palette = (
        _system_palette(app)
        if mode == "system"
        else _palette(DARK_THEME if mode == "dark" else LIGHT_THEME)
    )
    app.setPalette(palette)
    app.setProperty("b_asic_theme_mode", mode)
    if settings is not None:
        settings.setValue(THEME_SETTING, mode)
        settings.sync()


def install_theme(app: QApplication, settings: QSettings | None = None) -> ThemeMode:
    """Apply the persisted GUI theme to an application."""
    mode = read_theme_mode(settings)
    apply_theme(app, mode)
    return mode


def add_theme_menu(
    parent: QWidget,
    menu: QMenu,
    settings: QSettings | None = None,
) -> QMenu:
    """Add a checkable System/Light/Dark submenu to *menu*."""
    from qtpy.QtWidgets import QActionGroup  # noqa: PLC0415

    settings = settings or QSettings()
    theme_menu = menu.addMenu("&Theme")
    group = QActionGroup(theme_menu)
    group.setExclusive(True)
    selected_mode = read_theme_mode(settings)

    for mode, label in (
        ("system", "&System"),
        ("light", "&Light"),
        ("dark", "&Dark"),
    ):
        action = theme_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(mode == selected_mode)
        action.setData(mode)
        group.addAction(action)

    def change_theme(action) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        apply_theme(app, cast(ThemeMode, action.data()), settings)

    group.triggered.connect(change_theme)
    # Keep a reference while the parent window exists; QActionGroup does not
    # otherwise guarantee an extended lifetime through some Qt bindings.
    parent._theme_action_group = group  # type: ignore[attr-defined]
    return theme_menu
