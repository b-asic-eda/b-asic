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
        name: str = '',
    ):
        self.current_color = current_color
        self.DEFAULT = DEFAULT
        self.changed = changed
        self.name = name


LATENCY_COLOR_TYPE = ColorDataType(
    current_color=OPERATION_LATENCY_INACTIVE,
    DEFAULT=OPERATION_LATENCY_INACTIVE,
    name='Latency color',
)
EXECUTION_TIME_COLOR_TYPE = ColorDataType(
    current_color=OPERATION_EXECUTION_TIME_ACTIVE,
    DEFAULT=OPERATION_EXECUTION_TIME_ACTIVE,
    name='Execution time color',
)
SIGNAL_WARNING_COLOR_TYPE = ColorDataType(
    current_color=SIGNAL_WARNING, DEFAULT=SIGNAL_WARNING, name='Warning color'
)
SIGNAL_COLOR_TYPE = ColorDataType(
    current_color=SIGNAL_INACTIVE, DEFAULT=SIGNAL_INACTIVE, name='Signal color'
)
ACTIVE_COLOR_TYPE = ColorDataType(
    current_color=SIGNAL_ACTIVE, DEFAULT=SIGNAL_ACTIVE, name='Active color'
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
