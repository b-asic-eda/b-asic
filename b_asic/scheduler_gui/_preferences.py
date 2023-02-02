from qtpy.QtGui import QColor

from b_asic._preferences import (
    EXECUTION_TIME_COLOR,
    LATENCY_COLOR,
    SIGNAL_COLOR,
)

SIGNAL_INACTIVE = QColor(*SIGNAL_COLOR)
SIGNAL_ACTIVE = QColor(0, 207, 181)
SIGNAL_WIDTH = 0.03

OPERATION_LATENCY_INACTIVE = QColor(*LATENCY_COLOR)
OPERATION_LATENCY_ACTIVE = QColor(0, 207, 181)
OPERATION_EXECUTION_TIME_INACTIVE = QColor(*EXECUTION_TIME_COLOR)
OPERATION_EXECUTION_TIME_ACTIVE = QColor(*EXECUTION_TIME_COLOR)

OPERATION_HEIGHT = 0.75
OPERATION_GAP = 0.25
