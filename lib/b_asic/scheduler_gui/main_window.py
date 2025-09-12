#!/usr/bin/env python3
"""
B-ASIC Scheduler-GUI Module.

Contains the scheduler_gui MainWindow class for scheduling operations in an SFG.

Start main-window with ``start_gui()``.
"""

import copy
import inspect
import os
import pickle
import sys
import webbrowser
from collections import defaultdict, deque
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast, overload

# Qt/qtpy
import qtpy
import qtpy.QtCore

# QGraphics and QPainter imports
from qtpy.QtCore import (
    QByteArray,
    QCoreApplication,
    QFileInfo,
    QRectF,
    QSettings,
    QStandardPaths,
    Qt,
    Slot,
)
from qtpy.QtGui import QCloseEvent, QColor, QPalette, QTransform, QWheelEvent
from qtpy.QtWidgets import (
    QAbstractButton,
    QAction,
    QApplication,
    QCheckBox,
    QFileDialog,
    QGraphicsItemGroup,
    QGraphicsScene,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTableWidgetItem,
)

# B-ASIC
import b_asic.logger
from b_asic._version import version
from b_asic.graph_component import GraphComponent, GraphID
from b_asic.gui_utils.about_window import AboutWindow
from b_asic.gui_utils.icons import get_icon
from b_asic.gui_utils.mpl_window import MPLWindow
from b_asic.schedule import Schedule
from b_asic.scheduler_gui._preferences import (
    FONT,
    LATENCY_COLOR_TYPE,
    read_from_settings,
    write_to_settings,
)
from b_asic.scheduler_gui.axes_item import AxesItem
from b_asic.scheduler_gui.operation_item import OperationItem
from b_asic.scheduler_gui.preferences_dialog import PreferencesDialog
from b_asic.scheduler_gui.scheduler_item import SchedulerItem
from b_asic.scheduler_gui.ui_main_window import Ui_MainWindow

if TYPE_CHECKING:
    from logging import Logger

log: "Logger" = b_asic.logger.getLogger()
sys.excepthook = b_asic.logger.handle_exceptions


# Debug stuff
if __debug__:
    log.setLevel("DEBUG")

if __debug__:
    # Print some system version information
    from qtpy import QtCore

    QT_API = os.environ.get("QT_API", "")
    log.debug("Qt version (runtime):      %s", QtCore.qVersion())
    log.debug("Qt version (compile time): %s", QtCore.__version__)
    log.debug("QT_API:                    %s", QT_API)
    if QT_API.lower().startswith("pyside"):
        import PySide6

        log.debug("PySide version:           %s", PySide6.__version__)
    if QT_API.lower().startswith("pyqt"):
        from qtpy.QtCore import PYQT_VERSION_STR

        log.debug("PyQt version:             %s", PYQT_VERSION_STR)
    log.debug("QtPy version:             %s", qtpy.__version__)


# The following QCoreApplication values is used for QSettings among others
QCoreApplication.setOrganizationName("Linköping University")
QCoreApplication.setOrganizationDomain("liu.se")
QCoreApplication.setApplicationName("B-ASIC Scheduling GUI")
QCoreApplication.setApplicationVersion(version)


class ScheduleMainWindow(QMainWindow, Ui_MainWindow):
    """Schedule of an SFG with scheduled Operations."""

    _scene: QGraphicsScene
    _schedule: Schedule | None
    _graph: SchedulerItem | None
    _scale: float
    _debug_rectangles: QGraphicsItemGroup
    _splitter_pos: int
    _splitter_min: int
    _color_per_type: ClassVar[dict[str, QColor]] = {}
    _converted_color_per_type: ClassVar[dict[str, str]] = {}
    _changed_operation_colors: dict[str, QColor]
    _recent_files_actions: list[QAction]
    _recent_file_paths: deque[str]
    _file_name: str | None

    def __init__(self) -> None:
        """Initialize Scheduler-GUI."""
        super().__init__()
        self._schedule = None
        self._graph = None
        self._scale = 75.0
        self._debug_rectangles = None

        self.setupUi(self)
        self._read_settings()
        self._init_ui()
        self._file_name = None
        self._show_incorrect_execution_time = True
        self._show_port_numbers = True
        self._execution_time_for_variables = None
        self._total_execution_time_for_variables = None
        self._execution_time_plot_dialogs = defaultdict(lambda: None)
        self._total_execution_time_plot_dialogs = defaultdict(lambda: None)
        self._ports_accesses_for_storage = None
        self._color_changed_per_type = False
        self._changed_operation_colors = {}

        # Recent files
        self._max_recent_files = 4
        self._recent_files_actions = []
        self._recent_file_paths = deque(maxlen=self._max_recent_files)
        self._create_recent_file_actions_and_menus()

        self._init_graphics()

    def _init_ui(self) -> None:
        """Initialize the UI."""
        # Connect signals to slots
        self.menu_load_from_file.triggered.connect(self._load_schedule_from_pyfile)
        self.menu_load_from_file.setIcon(get_icon("import"))
        self.menu_open.setIcon(get_icon("open"))
        self.menu_open.triggered.connect(self.open_schedule)
        self.menu_close_schedule.triggered.connect(self.close_schedule)
        self.menu_close_schedule.setIcon(get_icon("close"))
        self.menu_save.triggered.connect(self.save)
        self.menu_save.setIcon(get_icon("save"))
        self.menu_save_as.triggered.connect(self.save_as)
        self.menu_save_as.setIcon(get_icon("save-as"))
        self.actionPreferences.triggered.connect(self.open_preferences_dialog)
        self.menu_quit.triggered.connect(self.close)
        self.menu_quit.setIcon(get_icon("quit"))
        self.menu_node_info.triggered.connect(self.show_info_table)
        self.menu_node_info.setIcon(get_icon("info"))
        self.menu_exit_dialog.triggered.connect(self.hide_exit_dialog)
        self.actionReorder.triggered.connect(self._action_reorder)
        self.actionReorder.setIcon(get_icon("reorder"))
        self.actionRotateForward.triggered.connect(self._rotate_forward)
        self.actionRotateBackward.triggered.connect(self._rotate_backward)
        self.actionStatus_bar.triggered.connect(self._toggle_statusbar)
        self.action_incorrect_execution_time.setIcon(get_icon("warning"))
        self.action_incorrect_execution_time.triggered.connect(
            self._toggle_execution_time_warning
        )
        self.action_show_port_numbers.setIcon(get_icon("port-numbers"))
        self.action_show_port_numbers.triggered.connect(self._toggle_port_number)
        self.actionPlot_schedule.setIcon(get_icon("plot-schedule"))
        self.actionPlot_schedule.triggered.connect(self._plot_schedule)
        self.action_view_variables.triggered.connect(
            self._show_execution_times_for_variables
        )
        self.action_total_execution_times_of_variables.triggered.connect(
            self._show_total_execution_times_for_variables
        )
        self.action_view_port_accesses.triggered.connect(
            self._show_ports_accesses_for_storage
        )
        self.actionZoom_to_fit.setIcon(get_icon("zoom-to-fit"))
        self.actionZoom_to_fit.triggered.connect(self._zoom_to_fit)
        self.actionZoom_to_fit_ignore_aspect_ratio.triggered.connect(
            self._zoom_to_fit_no_aspect
        )
        self.actionRestore_aspect_ratio.triggered.connect(self._reset_aspect_ratio)
        self.actionToggle_full_screen.setIcon(get_icon("full-screen"))
        self.actionToggle_full_screen.triggered.connect(self._toggle_fullscreen)
        self.actionUndo.setIcon(get_icon("undo"))
        self.actionRedo.setIcon(get_icon("redo"))
        self.splitter.splitterMoved.connect(self._splitter_moved)
        self.actionDocumentation.triggered.connect(self._open_documentation)
        self.actionDocumentation.setIcon(get_icon("docs"))
        self.actionAbout.triggered.connect(self._open_about_window)
        self.actionAbout.setIcon(get_icon("about"))
        self.actionDecrease_time_resolution.triggered.connect(
            self._decrease_time_resolution
        )
        self.actionDecrease_time_resolution.setIcon(get_icon("decrease-timeresolution"))
        self.actionIncrease_time_resolution.triggered.connect(
            self._increase_time_resolution
        )
        self.actionIncrease_time_resolution.setIcon(get_icon("increase-timeresolution"))
        # Setup event member functions
        self.closeEvent = self._close_event

        # Setup info table
        self.info_table.setSpan(0, 0, 1, 2)  # Span 'Schedule' over 2 columns
        self.info_table.setSpan(1, 0, 1, 2)  # Span 'Operator' over 2 columns

        # Init central-widget splitter
        self._splitter_min = self.splitter.minimumSizeHint().height()
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)

    def _init_graphics(self) -> None:
        """Initialize the QGraphics framework."""
        self._scene = QGraphicsScene()
        self._scene.addRect(0, 0, 0, 0)  # dummy rect to be able to setPos() graph
        self.view.setScene(self._scene)
        self.view.scale(self._scale, self._scale)
        OperationItem._scale = self._scale
        AxesItem._scale = self._scale
        self._scene.sceneRectChanged.connect(self.shrink_scene_to_min_size)

    @property
    def schedule(self) -> Schedule | None:
        """The current schedule."""
        return self._schedule

    #########
    # Slots #
    #########
    @Slot()
    def _plot_schedule(self) -> None:
        """Plot the schedule using Matplotlib."""
        if self.schedule is None:
            return
        self.schedule.show()

    @Slot()
    def _open_documentation(self) -> None:
        """Open documentation web page."""
        webbrowser.open_new_tab("https://da.gitlab-pages.liu.se/B-ASIC/")

    @Slot()
    def _action_reorder(self) -> None:
        """Reorder all operations vertically based on start time."""
        if self.schedule is None:
            return
        if self._graph is not None:
            self._graph._redraw_from_start()
            self.update_statusbar("Operations reordered based on start time")

    @Slot()
    def _rotate_forward(self) -> None:
        """Rotate the schedule one step forward."""
        if self.schedule is None:
            return
        if self._graph is not None:
            self._schedule = self._schedule.rotate_forward()
            self.open(self._schedule)
            print("schedule.rotate_forward())")
            self.update_statusbar("Scheduled rotated forward.")

    @Slot()
    def _rotate_backward(self) -> None:
        """Rotate the schedule one step backward."""
        if self.schedule is None:
            return
        if self._graph is not None:
            self._schedule = self._schedule.rotate_backward()
            self.open(self._schedule)
            print("schedule.rotate_backward())")
            self.update_statusbar("Scheduled rotated backward.")

    @Slot()
    def _increase_time_resolution(self) -> None:
        """Increasing the time resolution."""
        # Create dialog asking for int
        factor, ok = QInputDialog.getInt(
            self, "Increase time resolution", "Factor", 1, 1
        )
        # Check return value
        if ok:
            if factor > 1:
                schedule = cast(Schedule, self._schedule)
                schedule.increase_time_resolution(factor)
                self._schedule = schedule
                self.open(self._schedule)
                print(f"schedule.increase_time_resolution({factor})")
                self.update_statusbar(f"Time resolution increased by a factor {factor}")
        else:  # Cancelled
            self.update_statusbar("Cancelled")

    @Slot()
    def _decrease_time_resolution(self) -> None:
        """Decreasing the time resolution."""
        schedule = cast(Schedule, self._schedule)
        # Get possible factors
        vals = [str(v) for v in schedule.get_possible_time_resolution_decrements()]
        # Create dialog
        factor, ok = QInputDialog.getItem(
            self, "Decrease time resolution", "Factor", vals, editable=False
        )
        # Check return value
        if ok:
            if int(factor) > 1:
                schedule.decrease_time_resolution(int(factor))
                self._schedule = schedule
                self.open(self._schedule)
                print(f"schedule.decrease_time_resolution({factor})")
                self.update_statusbar(f"Time resolution decreased by a factor {factor}")
        else:  # Cancelled
            self.update_statusbar("Cancelled")

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom in or out using mouse wheel if control is pressed."""
        delta = event.angleDelta().y() / 2500
        new_zoom = 1.0 + delta
        modifiers = event.modifiers()
        # Only y-direction
        if (
            modifiers
            == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            self.view.scale(1.0, new_zoom)
        # Both directions
        elif modifiers == Qt.KeyboardModifier.ControlModifier:
            self.view.scale(new_zoom, new_zoom)

        event.ignore()

    @Slot()
    def _load_schedule_from_pyfile(self) -> None:
        """SLOT() for SIGNAL(menu_load_from_file.triggered)."""
        settings = QSettings()
        last_file = settings.value(
            "scheduler/last_opened_file",
            QStandardPaths.standardLocations(QStandardPaths.HomeLocation)[0],
            str,
        )
        if not Path(last_file).exists():  # if filename does not exist
            last_file = Path(last_file).parent
            if not last_file.exists():  # if path does not exist
                last_file = QStandardPaths.standardLocations(
                    QStandardPaths.HomeLocation
                )[0]

        abs_path_filename, accepted = QFileDialog.getOpenFileName(
            self,
            self.tr("Open python file"),
            last_file,
            self.tr("Python Files (*.py *.py3)"),
        )

        if not abs_path_filename or not accepted:
            return

        self._load_from_file(abs_path_filename)

    def _load_from_file(self, abs_path_filename) -> None:
        """
        Import from Python-file.

        Load a python script as a module and search for a Schedule object. If
        found, opens it.
        """
        log.debug("abs_path_filename = %s", abs_path_filename)

        module_name = inspect.getmodulename(abs_path_filename)
        if not module_name:  # return if empty module name
            log.error("Could not load module from file '%s'", abs_path_filename)
            return

        try:
            module = SourceFileLoader(module_name, abs_path_filename).load_module()
        except Exception as e:
            log.exception(
                "Exception occurred. Could not load module from file '%s'.\n\n%s",
                abs_path_filename,
                e,
            )
            return

        self._add_recent_file(abs_path_filename)

        schedule_obj_list = dict(
            inspect.getmembers(module, (lambda x: isinstance(x, Schedule)))
        )

        if not schedule_obj_list:  # return if no Schedule objects in script
            filename = Path(abs_path_filename).name
            QMessageBox.warning(
                self,
                self.tr("File not found"),
                self.tr("Cannot find any Schedule object in file {}").format(filename),
            )
            log.info(
                "Cannot find any Schedule object in file %s",
                filename,
            )
            del module
            return

        if len(schedule_obj_list) == 1:
            schedule = next(iter(schedule_obj_list.values()))
        else:
            ret_tuple = QInputDialog.getItem(
                self,
                self.tr("Load object"),
                self.tr(
                    "Found the following Schedule objects in file.\n\n"
                    "Select an object to proceed:"
                ),
                schedule_obj_list.keys(),
                0,
                False,
            )

            if not ret_tuple[1]:  # User canceled the operation
                log.debug("Load schedule operation: user canceled")
                del module
                return
            schedule = schedule_obj_list[ret_tuple[0]]

        self.open(schedule)
        del module
        settings = QSettings()
        settings.setValue("scheduler/last_opened_file", abs_path_filename)
        self._file_name = abs_path_filename
        self._toggle_file_loaded(True)

    @Slot()
    def close_schedule(self) -> None:
        """
        Close current schedule.

        SLOT() for SIGNAL(menu_close_schedule.triggered)
        """
        if self._graph:
            self._graph._signals.component_selected.disconnect(
                self.info_table_update_component
            )
            self._graph._signals.schedule_time_changed.disconnect(
                self.info_table_update_schedule
            )
            self._graph._signals.schedule_time_changed.disconnect(
                self._schedule_changed
            )
            self._graph._signals.reopen.disconnect(self._reopen_schedule)
            self._graph._signals.execution_time_plot.disconnect(
                self._execution_time_plot
            )
            self._graph._signals.total_execution_time_plot.disconnect(
                self._total_execution_time_plot
            )
            self._graph.removeSceneEventFilters(self._graph.event_items)
            self._scene.removeItem(self._graph)
            self.menu_close_schedule.setEnabled(False)
            self.menu_save.setEnabled(False)
            self.menu_save_as.setEnabled(False)

            del self._graph
            self._graph = None
            del self._schedule
            self._schedule = None
            self.info_table_clear()
            self.update_statusbar("Closed schedule")
            self._toggle_file_loaded(False)
            self.action_view_variables.setEnabled(False)
            self.action_total_execution_times_of_variables.setEnabled(False)
            self.action_view_port_accesses.setEnabled(False)
            self.menu_view_execution_times.setEnabled(False)
            self.menu_view_total_execution_times_of_type.setEnabled(False)
            self.actionPreferences.setEnabled(False)

    @Slot()
    def save(self) -> None:
        """
        Save current schedule.

        SLOT() for SIGNAL(menu_save.triggered)
        """
        # TODO: all
        if self._schedule is None:
            return
        if self._file_name is None:
            self.save_as()
            return
        self._schedule._sfg._graph_id_generator = None
        with Path(self._file_name).open("wb") as f:
            pickle.dump(self._schedule, f)
        self._add_recent_file(self._file_name)
        self.update_statusbar(self.tr("Schedule saved successfully"))

    @Slot()
    def save_as(self) -> None:
        """
        Save current schedule asking for file name.

        SLOT() for SIGNAL(menu_save_as.triggered)
        """
        # TODO: Implement
        if self._schedule is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save File", ".", filter=self.tr("B-ASIC schedule (*.bsc)")
        )
        if not filename:
            return
        if not filename.endswith(".bsc"):
            filename += ".bsc"
        self._file_name = filename
        self._schedule._sfg._graph_id_generator = None
        with Path(self._file_name).open("wb") as f:
            pickle.dump(self._schedule, f)
        self._add_recent_file(self._file_name)
        self.update_statusbar(self.tr("Schedule saved successfully"))

    @Slot()
    def open_schedule(self) -> None:
        """
        Open a schedule.

        SLOT() for SIGNAL(menu_open.triggered)
        """
        # TODO: all
        last_file = QStandardPaths.standardLocations(QStandardPaths.HomeLocation)[0]

        abs_path_filename, accepted = QFileDialog.getOpenFileName(
            self,
            self.tr("Open schedule file"),
            last_file,
            self.tr("B-ASIC schedule (*.bsc)"),
        )

        if not abs_path_filename or not accepted:
            return
        self._open_schedule_file(abs_path_filename)

    def _open_schedule_file(self, abs_path_filename: str) -> None:
        """Open a saved schedule (*.bsc-file), which is a pickled Schedule."""
        self._file_name = abs_path_filename
        self._add_recent_file(abs_path_filename)

        with Path(self._file_name).open("rb") as f:
            schedule = pickle.load(f)
        self.open(schedule)
        settings = QSettings()
        settings.setValue("scheduler/last_opened_file", self._file_name)
        self._toggle_file_loaded(True)
        self.update_statusbar(self.tr("Schedule loaded successfully"))

    @Slot(bool)
    def show_info_table(self, checked: bool) -> None:
        """
        Show or hide the info table.

        SLOT(bool) for SIGNAL(menu_node_info.triggered)
        Takes in a boolean and hide or show the info table accordingly with
        *checked*.
        """
        # Note: splitter handler index 0 is a hidden splitter handle far most left,
        # use index 1
        # settings = QSettings()
        _, max_ = self.splitter.getRange(1)  # tuple(min, max)

        if checked:
            if self._splitter_pos < self._splitter_min:
                self.splitter.moveSplitter(max_ - self._splitter_min, 1)
            else:
                self.splitter.moveSplitter(max_ - self._splitter_pos, 1)
        else:
            self.splitter.moveSplitter(max_, 1)

    def _toggle_file_loaded(self, enable: bool) -> None:
        self.menu_save.setEnabled(enable)
        self.menu_save_as.setEnabled(enable)

    @Slot(bool)
    def hide_exit_dialog(self, checked: bool) -> None:
        """
        Update state of exit dialog setting.

        SLOT(bool) for SIGNAL(menu_exit_dialog.triggered)
        Takes in a boolean and stores 'checked' in 'hide_exit_dialog' item in
        settings.
        """
        settings = QSettings()
        settings.setValue("scheduler/hide_exit_dialog", checked)

    @Slot(int, int)
    def _splitter_moved(self, pos: int, index: int) -> None:
        """
        SLOT(int, int) for SIGNAL(splitter.splitterMoved)
        Callback method used to check if the right widget (info window)
        has collapsed. Update the checkbutton accordingly.
        """
        width = self.splitter.sizes()[1]

        if width == 0:
            if self.menu_node_info.isChecked() is True:
                self.menu_node_info.setChecked(False)
        else:
            if self.menu_node_info.isChecked() is False:
                self.menu_node_info.setChecked(True)
            self._splitter_pos = width

    @Slot(str)
    def info_table_update_component(self, graph_id: GraphID) -> None:
        """
        Fill the 'Operation' part of the info table.

        SLOT(str) for SIGNAL(_graph._signals.component_selected)
        Takes in an operator-id, first clears the 'Operator' part of the info
        table and then fill in the table with new values from the operator
        associated with *graph_id*.

        Parameters
        ----------
        graph_id : GraphID
            GraphID of operation to fill information table with.
        """
        self.info_table_clear_component()
        self._info_table_fill_component(graph_id)

    @Slot()
    def info_table_update_schedule(self) -> None:
        """
        Update the 'Schedule' part of the info table.

        SLOT() for SIGNAL(_graph._signals.schedule_time_changed)
        Updates the 'Schedule' part of the info table.
        """
        if self.schedule is not None:
            self.info_table.item(1, 1).setText(str(self.schedule.schedule_time))

    @Slot(QRectF)
    def shrink_scene_to_min_size(self, rect: QRectF) -> None:
        """
        Make scene minimum size.

        SLOT(QRectF) for SIGNAL(_scene.sceneRectChanged)
        Takes in a QRectF (unused) and shrink the scene bounding rectangle to
        its minimum size, when the bounding rectangle signals a change in
        geometry.
        """
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    ##########
    # Events #
    ##########
    def _close_event(self, event: QCloseEvent) -> None:
        """
        EVENT: Replaces QMainWindow default closeEvent(QCloseEvent) event.
        Takes in a QCloseEvent and display an exit dialog, depending on
        'hide_exit_dialog' in settings.
        """
        settings = QSettings()
        hide_dialog = settings.value("scheduler/hide_exit_dialog", True, bool)
        ret = QMessageBox.StandardButton.Yes

        if not hide_dialog:
            box = QMessageBox(self)
            box.setWindowTitle(self.tr("Confirm Exit"))
            box.setText(
                "<h3>"
                + self.tr("Confirm Exit")
                + "</h3><p><br>"
                + self.tr("Are you sure you want to exit?")
                + "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br></p>"
            )
            box.setIcon(QMessageBox.Question)
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            buttons: list[QAbstractButton] = box.buttons()
            buttons[0].setText(self.tr("&Exit"))
            buttons[1].setText(self.tr("&Cancel"))
            checkbox = QCheckBox(self.tr("Do not ask again"))
            box.setCheckBox(checkbox)
            ret = box.exec_()

        if ret == QMessageBox.StandardButton.Yes:
            if not hide_dialog:
                settings.setValue("scheduler/hide_exit_dialog", checkbox.isChecked())
            self._write_settings()
            log.info("Exit: %s", Path(__file__).name)
            if self._ports_accesses_for_storage:
                self._ports_accesses_for_storage.close()
            if self._execution_time_for_variables:
                self._execution_time_for_variables.close()
            if self._total_execution_time_for_variables:
                self._total_execution_time_for_variables.close()
            for dialog in self._execution_time_plot_dialogs.values():
                if dialog:
                    dialog.close()
            for dialog in self._total_execution_time_plot_dialogs.values():
                if dialog:
                    dialog.close()
            event.accept()
        else:
            event.ignore()

    def _open_about_window(self, event=None) -> None:
        self.about_page = AboutWindow(self)
        self.about_page.show()

    ###########################
    # Helper member functions #
    ###########################
    def _print_button_pressed(self, func_name: str) -> None:
        # TODO: remove

        alert = QMessageBox(self)
        alert.setText("Called from " + func_name + "!")
        alert.exec_()

    def open(self, schedule: Schedule) -> None:
        """Take a Schedule and create a SchedulerItem object."""
        self.close_schedule()
        self._schedule = copy.deepcopy(schedule)
        self._graph = SchedulerItem(self._schedule)
        self._graph.setPos(1 / self._scale, 1 / self._scale)
        self.menu_close_schedule.setEnabled(True)
        self.menu_save.setEnabled(True)
        self.menu_save_as.setEnabled(True)
        self._scene.addItem(self._graph)
        self._graph.installSceneEventFilters(self._graph.event_items)
        self._graph._signals.component_selected.connect(
            self.info_table_update_component
        )
        self._graph._signals.component_moved.connect(self.info_table_update_component)
        self._graph._signals.component_moved.connect(self._schedule_changed)
        self._graph._signals.schedule_time_changed.connect(
            self.info_table_update_schedule
        )
        self._graph._signals.schedule_time_changed.connect(self._schedule_changed)
        self._graph._signals.redraw_all.connect(self._redraw_all)
        self._graph._signals.reopen.connect(self._reopen_schedule)
        self._graph._signals.execution_time_plot.connect(self._execution_time_plot)
        self._graph._signals.total_execution_time_plot.connect(
            self._total_execution_time_plot
        )
        self.info_table_fill_schedule(self._schedule)
        self._update_operation_types()
        self.actionPreferences.setEnabled(True)
        self.load_preferences()
        self.action_view_variables.setEnabled(True)
        self.action_total_execution_times_of_variables.setEnabled(True)
        self.action_view_port_accesses.setEnabled(True)
        self.update_statusbar(self.tr("Schedule loaded successfully"))

    def _redraw_all(self) -> None:
        cast(SchedulerItem, self._graph)._redraw_all()

    @Slot()
    def _reopen_schedule(self) -> None:
        self.open(cast(Schedule, self._schedule))

    def update_statusbar(self, msg: str) -> None:
        """
        Write *msg* to the statusbar with temporarily policy.

        Parameters
        ----------
        msg : str
            The message to write.
        """
        self.statusbar.showMessage(msg)

    def _write_settings(self) -> None:
        """Write settings from MainWindow to Settings."""
        settings = QSettings()
        settings.setValue(
            "scheduler/maximized", self.isMaximized()
        )  # window: maximized, in X11 - always False
        settings.setValue("scheduler/pos", self.pos())  # window: pos
        settings.setValue("scheduler/size", self.size())  # window: size
        settings.setValue("scheduler/state", self.saveState())
        settings.setValue("scheduler/menu/node_info", self.menu_node_info.isChecked())
        settings.setValue("scheduler/splitter/state", self.splitter.saveState())
        settings.setValue("scheduler/splitter/pos", self.splitter.sizes()[1])

        settings.beginGroup("scheduler/preferences")
        write_to_settings(settings)
        self.save_colortype()
        settings.sync()

        if settings.isWritable():
            log.debug("Settings written to '%s'", settings.fileName())
        else:
            log.warning("Settings cannot be saved to file, read-only.")

    def _read_settings(self) -> None:
        """Read settings from Settings to MainWindow."""
        settings = QSettings()
        if settings.value("scheduler/maximized", defaultValue=False, type=bool):
            self.showMaximized()
        else:
            self.move(settings.value("scheduler/pos", self.pos()))
            self.resize(settings.value("scheduler/size", self.size()))
        self.restoreState(settings.value("scheduler/state", QByteArray()))
        self.menu_node_info.setChecked(
            settings.value("scheduler/menu/node_info", True, bool)
        )
        self.splitter.restoreState(
            settings.value("scheduler/splitter/state", QByteArray())
        )
        self._splitter_pos = settings.value("scheduler/splitter/pos", 200, int)
        self.menu_exit_dialog.setChecked(
            settings.value("scheduler/hide_exit_dialog", False, bool)
        )

        settings.beginGroup("scheduler/preferences")
        read_from_settings(settings)
        self._color_changed_per_type = settings.value(
            "_color_changed_per_type", False, bool
        )

        settings.endGroup()
        settings.sync()
        log.debug("Settings read from '%s'", settings.fileName())

    def info_table_fill_schedule(self, schedule: Schedule) -> None:
        """
        Fill the 'Schedule' part of the info table.

        Parameters
        ----------
        schedule : Schedule
            The Schedule to get information from.
        """
        self.info_table.insertRow(1)
        self.info_table.insertRow(1)
        self.info_table.setItem(1, 0, QTableWidgetItem("Schedule Time"))
        self.info_table.setItem(2, 0, QTableWidgetItem("Cyclic"))
        self.info_table.setItem(1, 1, QTableWidgetItem(str(schedule.schedule_time)))
        self.info_table.setItem(2, 1, QTableWidgetItem(str(schedule.cyclic)))

    def _info_table_fill_component(self, graph_id: GraphID) -> None:
        """
        Fill the 'Operator' part of the info table.

        Parameters
        ----------
        graph_id : GraphID
            The GraphID of the operator to get information from.
        """
        if self.schedule is None:
            return
        op: GraphComponent = cast(
            GraphComponent, self.schedule._sfg.find_by_id(graph_id)
        )
        si = self.info_table.rowCount()  # si = start index

        if op.graph_id:
            self.info_table.insertRow(si)
            self.info_table.setItem(si, 0, QTableWidgetItem("ID"))
            self.info_table.setItem(si, 1, QTableWidgetItem(str(op.graph_id)))
            si += 1
        if op.name:
            self.info_table.insertRow(si)
            self.info_table.setItem(si, 0, QTableWidgetItem("Name"))
            self.info_table.setItem(si, 1, QTableWidgetItem(str(op.name)))
            si += 1

        for key, value in op.params.items():
            self.info_table.insertRow(si)
            self.info_table.setItem(si, 0, QTableWidgetItem(key))
            self.info_table.setItem(si, 1, QTableWidgetItem(str(value)))
            si += 1

        self.info_table.insertRow(si)
        self.info_table.setItem(si, 0, QTableWidgetItem("Forward slack"))
        forward_slack = self.schedule.forward_slack(graph_id)
        if forward_slack < sys.maxsize:
            self.info_table.setItem(si, 1, QTableWidgetItem(str(forward_slack)))
        else:
            self.info_table.setItem(si, 1, QTableWidgetItem("∞"))
        si += 1

        self.info_table.insertRow(si)
        self.info_table.setItem(si, 0, QTableWidgetItem("Backward slack"))
        backward_slack = self.schedule.backward_slack(graph_id)
        if backward_slack < sys.maxsize:
            self.info_table.setItem(si, 1, QTableWidgetItem(str(backward_slack)))
        else:
            self.info_table.setItem(si, 1, QTableWidgetItem("∞"))
        si += 1

    def info_table_clear(self) -> None:
        """Clear the info table."""
        self.info_table_clear_component()
        self.info_table_clear_schedule()

    def info_table_clear_schedule(self) -> None:
        """Clear the schedule part of the info table."""
        row = self.info_table.findItems("Operator", Qt.MatchFlag.MatchExactly)
        if row:
            row = row[0].row()
            for _ in range(1, row):
                self.info_table.removeRow(1)
        else:
            log.error("'Operator' not found in info table. It may have been renamed.")

    def exit_app(self) -> None:
        """Exit application."""
        log.info("Exiting the application.")
        QApplication.quit()

    def info_table_clear_component(self) -> None:
        """Clear the component part of the info table."""
        row = self.info_table.findItems("Operator", Qt.MatchFlag.MatchExactly)
        if row:
            row = row[0].row()
            for _ in range(self.info_table.rowCount() - row + 1):
                self.info_table.removeRow(row + 1)
        else:
            log.error("'Operator' not found in info table. It may have been renamed.")

    def _create_recent_file_actions_and_menus(self) -> None:
        for _ in range(self._max_recent_files):
            recent_file_action = QAction(self.menu_Recent_Schedule)
            recent_file_action.setVisible(False)
            recent_file_action.triggered.connect(
                lambda b=0, x=recent_file_action: self._open_recent_file(x)
            )
            self._recent_files_actions.append(recent_file_action)
            self.menu_Recent_Schedule.addAction(recent_file_action)

        self._update_recent_file_list()

    def _update_operation_types(self) -> None:
        self.menu_view_execution_times.setEnabled(True)
        for action in self.menu_view_execution_times.actions():
            self.menu_view_execution_times.removeAction(action)
        for type_name in self._schedule.get_used_type_names():
            type_action = QAction(self.menu_view_execution_times)
            type_action.setText(type_name)
            type_action.triggered.connect(
                lambda b=0, x=type_name: self._show_execution_times_for_type(x)
            )
            self.menu_view_execution_times.addAction(type_action)

        self.menu_view_total_execution_times_of_type.setEnabled(True)
        for action in self.menu_view_total_execution_times_of_type.actions():
            self.menu_view_total_execution_times_of_type.removeAction(action)
        for type_name in self._schedule.get_used_type_names():
            type_action = QAction(self.menu_view_total_execution_times_of_type)
            type_action.setText(type_name)
            type_action.triggered.connect(
                lambda b=0, x=type_name: self._show_total_execution_times_for_type(x)
            )
            self.menu_view_total_execution_times_of_type.addAction(type_action)

    @Slot()
    def open_preferences_dialog(self) -> None:
        """Open the preferences dialog to customize fonts, colors, and settings."""
        self._preferences_dialog = PreferencesDialog(self)
        self._preferences_dialog.show()

    def load_preferences(self) -> None:
        """Load the last saved preferences from settings."""
        settings = QSettings()
        LATENCY_COLOR_TYPE.current_color = QColor(
            settings.value(
                f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}",
                defaultValue=LATENCY_COLOR_TYPE.DEFAULT,
                type=str,
            )
        )
        LATENCY_COLOR_TYPE.changed = settings.value(
            f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}_changed", False, bool
        )
        self._converted_color_per_type = settings.value(
            f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}/per_type",
            self._converted_color_per_type,
        )
        self._color_changed_per_type = settings.value(
            f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}/per_type_changed",
            False,
            bool,
        )
        settings.sync()

        for key, color_str in self._converted_color_per_type.items():
            color = QColor(color_str)
            self._color_per_type[key] = color
            Match = (
                (color == LATENCY_COLOR_TYPE.current_color)
                if LATENCY_COLOR_TYPE.changed
                else (color == LATENCY_COLOR_TYPE.DEFAULT)
            )
            if self._color_changed_per_type and not Match:
                self._changed_operation_colors[key] = color
        self.update_color_preferences()

        if FONT.changed:
            FONT.current_font.setPointSizeF(FONT.size)
            FONT.current_font.setItalic(FONT.italic)
            FONT.current_font.setBold(FONT.bold)
            self._graph._font_change(FONT.current_font)
            self._graph._font_color_change(FONT.color)
        else:
            self._graph._font_change(FONT.DEFAULT)
            self._graph._font_color_change(FONT.DEFAULT_COLOR)

        self.update_statusbar("Saved Preferences Loaded")

    def update_color_preferences(self) -> None:
        """Update preferences of Latency color per type."""
        if self._schedule is None:
            return
        used_type_names = self._schedule.get_used_type_names()
        match (LATENCY_COLOR_TYPE.changed, self._color_changed_per_type):
            case (True, False):
                for type_name in used_type_names:
                    self._color_per_type[type_name] = LATENCY_COLOR_TYPE.current_color
            case (False, False):
                for type_name in used_type_names:
                    self._color_per_type[type_name] = LATENCY_COLOR_TYPE.DEFAULT
            case (False, True):
                for type_name in used_type_names:
                    if type_name in self._changed_operation_colors:
                        self._color_per_type[type_name] = (
                            self._changed_operation_colors[type_name]
                        )
                    else:
                        self._color_per_type[type_name] = LATENCY_COLOR_TYPE.DEFAULT
            case (True, True):
                for type_name in used_type_names:
                    if type_name in self._changed_operation_colors:
                        self._color_per_type[type_name] = (
                            self._changed_operation_colors[type_name]
                        )
                    else:
                        self._color_per_type[type_name] = (
                            LATENCY_COLOR_TYPE.current_color
                        )
        self.save_colortype()

    def save_colortype(self) -> None:
        """Save preferences of Latency color per type in settings."""
        settings = QSettings()
        for key, color in self._color_per_type.items():
            if self._graph:
                self._graph._color_change(color, key)
            self._converted_color_per_type[key] = color.name()
        settings.setValue(
            f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}",
            LATENCY_COLOR_TYPE.current_color,
        )
        settings.setValue(
            f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}_changed",
            LATENCY_COLOR_TYPE.changed,
        )
        settings.setValue(
            f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}/per_type",
            self._converted_color_per_type,
        )
        settings.setValue(
            f"scheduler/preferences/{LATENCY_COLOR_TYPE.name}/per_type_changed",
            self._color_changed_per_type,
        )

    @Slot(str)
    def _show_execution_times_for_type(self, type_name) -> None:
        self._execution_time_plot(type_name)

    def _closed_execution_times_for_type(self, type_name) -> None:
        self._execution_time_plot_dialogs[type_name] = None

    def _execution_time_plot(self, type_name: str) -> None:
        self._execution_time_plot_dialogs[type_name] = MPLWindow(
            f"Execution times for {type_name}"
        )
        self._execution_time_plot_dialogs[type_name].finished.connect(
            lambda b=0, x=type_name: self._closed_execution_times_for_type(x)
        )
        self._update_execution_times_for_type(type_name)
        self._execution_time_plot_dialogs[type_name].show()

    def _update_execution_times_for_type(self, type_name) -> None:
        if self._execution_time_plot_dialogs[type_name]:
            self._execution_time_plot_dialogs[type_name].axes.clear()
            self._schedule.get_operations().get_by_type_name(type_name).plot(
                self._execution_time_plot_dialogs[type_name].axes
            )
            self._execution_time_plot_dialogs[type_name].redraw()

    @Slot(str)
    def _show_total_execution_times_for_type(self, type_name) -> None:
        self._total_execution_time_plot(type_name)

    def _closed_total_execution_times_for_type(self, type_name) -> None:
        self._total_execution_time_plot_dialogs[type_name] = None

    def _total_execution_time_plot(self, type_name: str) -> None:
        self._total_execution_time_plot_dialogs[type_name] = MPLWindow(
            f"Total execution times for {type_name}"
        )
        self._total_execution_time_plot_dialogs[type_name].finished.connect(
            lambda b=0, x=type_name: self._closed_total_execution_times_for_type(x)
        )
        self._update_total_execution_times_for_type(type_name)
        self._total_execution_time_plot_dialogs[type_name].show()

    def _update_total_execution_times_for_type(self, type_name) -> None:
        if self._total_execution_time_plot_dialogs[type_name]:
            self._total_execution_time_plot_dialogs[type_name].axes.clear()
            self._schedule.get_operations().get_by_type_name(
                type_name
            ).plot_total_execution_times(
                self._total_execution_time_plot_dialogs[type_name].axes
            )
            self._total_execution_time_plot_dialogs[type_name].redraw()

    def _show_execution_times_for_variables(self) -> None:
        self._execution_time_for_variables = MPLWindow("Execution times for variables")
        self._execution_time_for_variables.finished.connect(
            self._execution_times_for_variables_closed
        )
        self._update_execution_times_for_variables()
        self._execution_time_for_variables.show()

    def _update_execution_times_for_variables(self) -> None:
        if self._execution_time_for_variables:
            self._execution_time_for_variables.axes.clear()
            self._schedule.get_memory_variables().plot(
                self._execution_time_for_variables.axes, allow_excessive_lifetimes=True
            )
            self._execution_time_for_variables.redraw()

    @Slot()
    def _execution_times_for_variables_closed(self) -> None:
        self._execution_time_for_variables = None

    def _show_total_execution_times_for_variables(self) -> None:
        self._total_execution_time_for_variables = MPLWindow(
            "Total execution times for variables"
        )
        self._total_execution_time_for_variables.finished.connect(
            self._total_execution_times_for_variables_closed
        )
        self._update_total_execution_times_for_variables()
        self._total_execution_time_for_variables.show()

    def _update_total_execution_times_for_variables(self) -> None:
        if self._total_execution_time_for_variables:
            self._total_execution_time_for_variables.axes.clear()
            self._schedule.get_memory_variables().plot_total_execution_times(
                self._total_execution_time_for_variables.axes
            )
            self._total_execution_time_for_variables.redraw()

    @Slot()
    def _total_execution_times_for_variables_closed(self) -> None:
        self._total_execution_time_for_variables = None

    def _show_ports_accesses_for_storage(self) -> None:
        self._ports_accesses_for_storage = MPLWindow(
            "Port accesses for storage", subplots=(3, 1)
        )
        self._ports_accesses_for_storage.finished.connect(
            self._ports_accesses_for_storage_closed
        )
        self._update_ports_accesses_for_storage()
        self._ports_accesses_for_storage.show()

    def _update_ports_accesses_for_storage(self) -> None:
        if self._ports_accesses_for_storage:
            for ax in self._ports_accesses_for_storage.axes:
                ax.clear()
            mem_vars = self._schedule.get_memory_variables()
            _, mem_vars = mem_vars.split_on_length()
            mem_vars.plot_port_accesses(self._ports_accesses_for_storage.axes)
            self._ports_accesses_for_storage.redraw()

    @Slot()
    def _ports_accesses_for_storage_closed(self) -> None:
        self._ports_accesses_for_storage = None

    @Slot()
    @Slot(str)
    def _schedule_changed(self, type_name: str | None = None) -> None:
        self._update_execution_times_for_variables()
        self._update_ports_accesses_for_storage()
        for key, dialog in self._execution_time_plot_dialogs.items():
            if dialog:
                self._update_execution_times_for_type(key)

        for key, dialog in self._total_execution_time_plot_dialogs.items():
            if dialog:
                self._update_total_execution_times_for_type(key)

    def _update_recent_file_list(self) -> None:
        settings = QSettings()
        rfp = cast(deque, settings.value("scheduler/recentFiles"))
        if rfp:
            dequelen = len(rfp)
            if dequelen > 0:
                for i in range(dequelen):
                    action = self._recent_files_actions[i]
                    action.setText(rfp[i])
                    action.setData(QFileInfo(rfp[i]))
                    action.setVisible(True)

                for i in range(dequelen, self._max_recent_files):
                    self._recent_files_actions[i].setVisible(False)

    def _open_recent_file(self, action) -> None:
        if action.data().filePath().endswith(".bsc"):
            self._open_schedule_file(action.data().filePath())
        else:
            self._load_from_file(action.data().filePath())

    def _add_recent_file(self, filename) -> None:
        settings = QSettings()
        rfp = cast(deque, settings.value("scheduler/recentFiles"))
        if rfp:
            if filename not in rfp:
                rfp.append(filename)
        else:
            rfp = deque(maxlen=self._max_recent_files)
            rfp.append(filename)
        settings.setValue("scheduler/recentFiles", rfp)

        self._update_recent_file_list()

    def _zoom_to_fit(self, event=None) -> None:
        """Zoom to fit schedule in window keeping aspect ratio."""
        self.view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _zoom_to_fit_no_aspect(self, event=None) -> None:
        """Zoom to fit schedule in window ignoring aspect ratio."""
        self.view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio
        )

    def _reset_aspect_ratio(self, event=None) -> None:
        """Reset the aspect ratio."""
        self.view.setTransform(QTransform())
        self.view.scale(self._scale, self._scale)

    def _toggle_statusbar(self, event=None) -> None:
        """Toggle the status bar."""
        self.statusbar.setVisible(self.actionStatus_bar.isChecked())

    def _toggle_execution_time_warning(self, event=None) -> None:
        """Toggle whether to show the execution time warning."""
        self._show_incorrect_execution_time = (
            self.action_incorrect_execution_time.isChecked()
        )
        self._graph.set_warnings(self._show_incorrect_execution_time)

    def _toggle_port_number(self, event=None) -> None:
        """Toggle whether to show port numbers."""
        self._show_port_numbers = self.action_show_port_numbers.isChecked()
        self._graph.set_port_numbers(self._show_port_numbers)

    def _toggle_fullscreen(self, event=None) -> None:
        """Toggle full screen mode."""
        if self.isFullScreen():
            self.showNormal()
            self.actionToggle_full_screen.setIcon(get_icon("full-screen"))
        else:
            self.showFullScreen()
            self.actionToggle_full_screen.setIcon(get_icon("full-screen-exit"))


@overload
def start_scheduler(schedule: Schedule) -> Schedule: ...


@overload
def start_scheduler(schedule: None) -> Schedule | None: ...


@overload
def start_scheduler() -> Schedule | None: ...


def start_scheduler(schedule: Schedule | None = None) -> Schedule | None:
    """
    Start scheduler GUI.

    Parameters
    ----------
    schedule : Schedule, optional
        The schedule to start the editor with.

    Returns
    -------
    Schedule
        The edited schedule.
    """
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()

    # Enforce a light palette regardless of laptop theme
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QtCore.Qt.white)
    palette.setColor(QPalette.ColorRole.WindowText, QtCore.Qt.black)
    palette.setColor(QPalette.ColorRole.ButtonText, QtCore.Qt.black)
    palette.setColor(QPalette.ColorRole.Base, QtCore.Qt.white)
    palette.setColor(QPalette.ColorRole.AlternateBase, QtCore.Qt.lightGray)
    palette.setColor(QPalette.ColorRole.Text, QtCore.Qt.black)
    app.setPalette(palette)

    window = ScheduleMainWindow()
    if schedule:
        window.open(schedule)
    window.show()
    app.exec_()
    return window.schedule


if __name__ == "__main__":
    start_scheduler()
