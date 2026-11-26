from qtpy.QtCore import QSettings
from qtpy.QtGui import QColor, QFont

from b_asic._preferences import (
    DEFAULT_FONT_FAMILY,
    EXECUTION_TIME_COLOR,
    LATENCY_COLOR,
    MEMORY_COLOR,
    SIGNAL_COLOR,
)
from b_asic.gui_utils.theme import current_theme

SIGNAL_INACTIVE = QColor(*SIGNAL_COLOR)
SIGNAL_ACTIVE = QColor(*MEMORY_COLOR)
SIGNAL_WARNING = QColor(current_theme().wire_warning)
SIGNAL_WIDTH = 0.03
SIGNAL_WIDTH_ACTIVE = 0.05
SIGNAL_WIDTH_WARNING = 0.05

OPERATION_LATENCY_INACTIVE = QColor(*LATENCY_COLOR)
OPERATION_LATENCY_ACTIVE = QColor(*MEMORY_COLOR)
OPERATION_EXECUTION_TIME_INACTIVE = QColor(*EXECUTION_TIME_COLOR)
OPERATION_EXECUTION_TIME_ACTIVE = QColor(*EXECUTION_TIME_COLOR)

OPERATION_HEIGHT = 0.75
OPERATION_GAP = 1 - OPERATION_HEIGHT  # TODO: For now, should really fix the bug

SCHEDULE_INDENT = 0.2
DEFAULT_FONT = QFont(DEFAULT_FONT_FAMILY, 12)
DEFAULT_FONT_COLOR = QColor(current_theme().text)


class ColorDataType:
    def __init__(
        self,
        DEFAULT: QColor,
        current_color: QColor = SIGNAL_INACTIVE,
        changed: bool = False,
        name: str = "",
    ) -> None:
        self.current_color = current_color
        self.DEFAULT = DEFAULT
        self.changed = changed
        self.name = name


LATENCY_COLOR_TYPE = ColorDataType(
    current_color=OPERATION_LATENCY_INACTIVE,
    DEFAULT=OPERATION_LATENCY_INACTIVE,
    name="Latency color",
)
EXECUTION_TIME_COLOR_TYPE = ColorDataType(
    current_color=OPERATION_EXECUTION_TIME_ACTIVE,
    DEFAULT=OPERATION_EXECUTION_TIME_ACTIVE,
    name="Execution time color",
)
SIGNAL_WARNING_COLOR_TYPE = ColorDataType(
    current_color=SIGNAL_WARNING, DEFAULT=SIGNAL_WARNING, name="Warning color"
)
SIGNAL_COLOR_TYPE = ColorDataType(
    current_color=SIGNAL_INACTIVE, DEFAULT=SIGNAL_INACTIVE, name="Signal color"
)
ACTIVE_COLOR_TYPE = ColorDataType(
    current_color=SIGNAL_ACTIVE, DEFAULT=SIGNAL_ACTIVE, name="Active color"
)


class FontDataType:
    def __init__(
        self,
        current_font: QFont,
        DEFAULT: QFont = DEFAULT_FONT,
        DEFAULT_COLOR: QColor = DEFAULT_FONT_COLOR,
        color: QColor = DEFAULT_FONT_COLOR,
        size: int = 12,
        italic: bool = False,
        bold: bool = False,
        changed: bool = False,
    ) -> None:
        self.current_font = current_font
        self.DEFAULT = DEFAULT
        self.DEFAULT_COLOR = DEFAULT_COLOR
        self.size = size
        self.color = color
        self.italic = italic
        self.bold = bold
        self.changed = changed


FONT = FontDataType(
    current_font=DEFAULT_FONT, DEFAULT=DEFAULT_FONT, DEFAULT_COLOR=DEFAULT_FONT_COLOR
)


def refresh_theme_defaults() -> None:
    """Update non-customized scheduler colors after a theme change."""
    theme = current_theme()
    mappings = (
        (SIGNAL_COLOR_TYPE, theme.wire),
        (ACTIVE_COLOR_TYPE, SIGNAL_ACTIVE),
        (SIGNAL_WARNING_COLOR_TYPE, theme.wire_warning),
        (LATENCY_COLOR_TYPE, OPERATION_LATENCY_INACTIVE),
        (EXECUTION_TIME_COLOR_TYPE, OPERATION_EXECUTION_TIME_INACTIVE),
    )
    for color_type, color in mappings:
        color_type.DEFAULT = QColor(color)
        if not color_type.changed:
            color_type.current_color = QColor(color)
    FONT.DEFAULT_COLOR = QColor(theme.text)
    if not FONT.changed:
        FONT.color = QColor(theme.text)


def read_from_settings(settings: QSettings) -> None:
    refresh_theme_defaults()
    FONT.changed = settings.value("font_changed", FONT.changed, bool)
    for color_type in (
        SIGNAL_COLOR_TYPE,
        ACTIVE_COLOR_TYPE,
        SIGNAL_WARNING_COLOR_TYPE,
        LATENCY_COLOR_TYPE,
        EXECUTION_TIME_COLOR_TYPE,
    ):
        color_type.changed = settings.value(
            f"{color_type.name}_changed", color_type.changed, bool
        )

    FONT.current_font = QFont(
        settings.value("font", defaultValue=FONT.DEFAULT.toString(), type=str)
    )
    FONT.size = settings.value(
        "font_size", defaultValue=FONT.DEFAULT.pointSizeF(), type=int
    )
    FONT.color = (
        QColor(settings.value("font_color", FONT.DEFAULT_COLOR.name(), str))
        if FONT.changed
        else QColor(FONT.DEFAULT_COLOR)
    )
    FONT.bold = settings.value("font_bold", defaultValue=FONT.DEFAULT.bold(), type=bool)
    FONT.italic = settings.value(
        "font_italic", defaultValue=FONT.DEFAULT.italic(), type=bool
    )
    for color_type in (
        SIGNAL_COLOR_TYPE,
        ACTIVE_COLOR_TYPE,
        SIGNAL_WARNING_COLOR_TYPE,
        LATENCY_COLOR_TYPE,
        EXECUTION_TIME_COLOR_TYPE,
    ):
        value = settings.value(color_type.name, color_type.DEFAULT.name(), str)
        color_type.current_color = (
            QColor(value) if color_type.changed else QColor(color_type.DEFAULT)
        )


def write_to_settings(settings: QSettings) -> None:
    settings.setValue("font", FONT.current_font.toString())
    settings.setValue("font_size", FONT.size)
    settings.setValue("font_color", FONT.color)
    settings.setValue("font_bold", FONT.current_font.bold())
    settings.setValue("font_italic", FONT.current_font.italic())
    settings.setValue("font_changed", FONT.changed)

    settings.setValue(SIGNAL_COLOR_TYPE.name, SIGNAL_COLOR_TYPE.current_color.name())
    settings.setValue(ACTIVE_COLOR_TYPE.name, ACTIVE_COLOR_TYPE.current_color.name())
    settings.setValue(
        SIGNAL_WARNING_COLOR_TYPE.name,
        SIGNAL_WARNING_COLOR_TYPE.current_color.name(),
    )
    settings.setValue(
        EXECUTION_TIME_COLOR_TYPE.name,
        EXECUTION_TIME_COLOR_TYPE.current_color.name(),
    )

    settings.setValue(f"{SIGNAL_COLOR_TYPE.name}_changed", SIGNAL_COLOR_TYPE.changed)
    settings.setValue(f"{ACTIVE_COLOR_TYPE.name}_changed", ACTIVE_COLOR_TYPE.changed)
    settings.setValue(
        f"{SIGNAL_WARNING_COLOR_TYPE.name}_changed",
        SIGNAL_WARNING_COLOR_TYPE.changed,
    )


def reset_color_settings(settings: QSettings) -> None:
    LATENCY_COLOR_TYPE.changed = False
    ACTIVE_COLOR_TYPE.changed = False
    SIGNAL_WARNING_COLOR_TYPE.changed = False
    SIGNAL_COLOR_TYPE.changed = False
    EXECUTION_TIME_COLOR_TYPE.changed = False
    settings.beginGroup("scheduler/preferences")
    settings.setValue(LATENCY_COLOR_TYPE.name, LATENCY_COLOR_TYPE.DEFAULT.name())
    settings.setValue(SIGNAL_COLOR_TYPE.name, SIGNAL_COLOR_TYPE.DEFAULT.name())
    settings.setValue(ACTIVE_COLOR_TYPE.name, ACTIVE_COLOR_TYPE.DEFAULT.name())
    settings.setValue(
        SIGNAL_WARNING_COLOR_TYPE.name, SIGNAL_WARNING_COLOR_TYPE.DEFAULT.name()
    )
    settings.setValue(
        EXECUTION_TIME_COLOR_TYPE.name, EXECUTION_TIME_COLOR_TYPE.DEFAULT.name()
    )
    settings.endGroup()
