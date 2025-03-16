from qtpy.QtCore import QSettings
from qtpy.QtGui import QColor, QFont

from b_asic._preferences import EXECUTION_TIME_COLOR, LATENCY_COLOR, SIGNAL_COLOR

SIGNAL_INACTIVE = QColor(*SIGNAL_COLOR)
SIGNAL_ACTIVE = QColor(0, 207, 181)
SIGNAL_WARNING = QColor(255, 0, 0)
SIGNAL_WIDTH = 0.03
SIGNAL_WIDTH_ACTIVE = 0.05
SIGNAL_WIDTH_WARNING = 0.05

OPERATION_LATENCY_INACTIVE = QColor(*LATENCY_COLOR)
OPERATION_LATENCY_ACTIVE = QColor(0, 207, 181)
OPERATION_EXECUTION_TIME_INACTIVE = QColor(*EXECUTION_TIME_COLOR)
OPERATION_EXECUTION_TIME_ACTIVE = QColor(*EXECUTION_TIME_COLOR)

OPERATION_HEIGHT = 0.75
OPERATION_GAP = 1 - OPERATION_HEIGHT  # TODO: For now, should really fix the bug

SCHEDULE_INDENT = 0.2
DEFAULT_FONT = QFont("Times", 12)
DEFAULT_FONT_COLOR = QColor(*SIGNAL_COLOR)


class ColorDataType:
    def __init__(
        self,
        DEFAULT: QColor,
        current_color: QColor = SIGNAL_INACTIVE,
        changed: bool = False,
        name: str = "",
    ):
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
    ):
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


def read_from_settings(settings: QSettings):
    FONT.current_font = QFont(
        settings.value("font", defaultValue=FONT.DEFAULT.toString(), type=str)
    )
    FONT.size = settings.value(
        "font_size", defaultValue=FONT.DEFAULT.pointSizeF(), type=int
    )
    FONT.color = QColor(
        settings.value("font_color", defaultValue=FONT.DEFAULT_COLOR, type=str)
    )
    FONT.bold = settings.value("font_bold", defaultValue=FONT.DEFAULT.bold(), type=bool)
    FONT.italic = settings.value(
        "font_italic", defaultValue=FONT.DEFAULT.italic(), type=bool
    )
    FONT.changed = settings.value("font_changed", FONT.changed, bool)

    SIGNAL_COLOR_TYPE.current_color = QColor(
        settings.value(
            SIGNAL_COLOR_TYPE.name,
            defaultValue=SIGNAL_COLOR_TYPE.DEFAULT.name(),
            type=str,
        )
    )
    ACTIVE_COLOR_TYPE.current_color = QColor(
        settings.value(
            ACTIVE_COLOR_TYPE.name,
            defaultValue=ACTIVE_COLOR_TYPE.DEFAULT.name(),
            type=str,
        )
    )
    SIGNAL_WARNING_COLOR_TYPE.current_color = QColor(
        settings.value(
            SIGNAL_WARNING_COLOR_TYPE.name,
            defaultValue=SIGNAL_WARNING_COLOR_TYPE.DEFAULT.name(),
            type=str,
        )
    )
    LATENCY_COLOR_TYPE.current_color = QColor(
        settings.value(
            LATENCY_COLOR_TYPE.name,
            defaultValue=LATENCY_COLOR_TYPE.DEFAULT.name(),
            type=str,
        )
    )
    EXECUTION_TIME_COLOR_TYPE.current_color = QColor(
        settings.value(
            EXECUTION_TIME_COLOR_TYPE.name,
            defaultValue=EXECUTION_TIME_COLOR_TYPE.DEFAULT.name(),
            type=str,
        )
    )
    SIGNAL_COLOR_TYPE.changed = settings.value(
        f"{SIGNAL_COLOR_TYPE.name}_changed", False, bool
    )
    ACTIVE_COLOR_TYPE.changed = settings.value(
        f"{ACTIVE_COLOR_TYPE.name}_changed", False, bool
    )
    SIGNAL_WARNING_COLOR_TYPE.changed = settings.value(
        f"{SIGNAL_WARNING_COLOR_TYPE.name}_changed",
        False,
        bool,
    )
    LATENCY_COLOR_TYPE.changed = settings.value(
        f"{LATENCY_COLOR_TYPE.name}_changed", False, bool
    )
    EXECUTION_TIME_COLOR_TYPE.changed = settings.value(
        f"{EXECUTION_TIME_COLOR_TYPE.name}_changed",
        False,
        bool,
    )


def write_to_settings(settings: QSettings):
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


def reset_color_settings(settings: QSettings):
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
