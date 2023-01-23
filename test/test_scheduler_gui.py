import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule

try:
    import b_asic.scheduler_gui as GUI
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def test_start(qtbot):
    widget = GUI.MainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


def test_load_schedule(qtbot, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type(
        ConstantMultiplication.type_name(), 4
    )

    widget = GUI.MainWindow()
    qtbot.addWidget(widget)
    schedule = Schedule(sfg_simple_filter)
    widget.open(schedule)
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"
