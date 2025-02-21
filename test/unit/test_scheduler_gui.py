import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler

try:
    from b_asic.scheduler_gui.main_window import ScheduleMainWindow
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def test_start(qtbot):
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


def test_load_schedule(qtbot, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 4)

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    widget.open(schedule)
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"
