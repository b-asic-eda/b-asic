#!/usr/bin/env python3
"""
B-ASIC Scheduler-GUI Module.

Contains the scheduler_gui MainWindow class for scheduling operations in an SFG.

Start main-window with ``start_gui()``.
"""
import inspect
import os
import pickle
import sys
import webbrowser
from collections import defaultdict, deque
from copy import deepcopy
from importlib.machinery import SourceFileLoader
from typing import TYPE_CHECKING, Deque, Dict, List, Optional, cast, overload

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
from qtpy.QtGui import QCloseEvent, QColor, QFont, QIcon, QIntValidator
from qtpy.QtWidgets import (
    QAbstractButton,
    QAction,
    QApplication,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontDialog,
    QGraphicsItemGroup,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
)

# B-ASIC
import b_asic.scheduler_gui.logger as logger
from b_asic._version import __version__
from b_asic.graph_component import GraphComponent, GraphID
from b_asic.gui_utils.about_window import AboutWindow
from b_asic.gui_utils.color_button import ColorButton
from b_asic.gui_utils.icons import get_icon
from b_asic.gui_utils.mpl_window import MPLWindow
from b_asic.schedule import Schedule
from b_asic.scheduler_gui._preferences import (
    Active_Color,
    ColorDataType,
    Execution_Time_Color,
    Font,
    Latency_Color,
    Signal_Color,
    Signal_Warning_Color,
)
from b_asic.scheduler_gui.axes_item import AxesItem
from b_asic.scheduler_gui.operation_item import OperationItem
from b_asic.scheduler_gui.scheduler_item import SchedulerItem
from b_asic.scheduler_gui.ui_main_window import Ui_MainWindow

if TYPE_CHECKING:
    from logging import Logger

log: "Logger" = logger.getLogger()
sys.excepthook = logger.handle_exceptions


# Debug stuff
if __debug__:
    log.setLevel("DEBUG")

if __debug__:
    # Print some system version information
    from qtpy import QtCore

    QT_API = os.environ.get("QT_API", "")
    log.debug(f"Qt version (runtime):      {QtCore.qVersion()}")
    log.debug(f"Qt version (compile time): {QtCore.__version__}")
    log.debug(f"QT_API:                    {QT_API}")
    if QT_API.lower().startswith("pyside"):
        import PySide2

        log.debug(f"PySide version:           {PySide2.__version__}")
    if QT_API.lower().startswith("pyqt"):
        from qtpy.QtCore import PYQT_VERSION_STR

        log.debug(f"PyQt version:             {PYQT_VERSION_STR}")
    log.debug(f"QtPy version:             {qtpy.__version__}")


# The following QCoreApplication values is used for QSettings among others
QCoreApplication.setOrganizationName("Linköping University")
QCoreApplication.setOrganizationDomain("liu.se")
QCoreApplication.setApplicationName("B-ASIC Scheduling GUI")
QCoreApplication.setApplicationVersion(__version__)


class ScheduleMainWindow(QMainWindow, Ui_MainWindow):
    """Schedule of an SFG with scheduled Operations."""

    _scene: QGraphicsScene
    _schedule: Optional[Schedule]
    _graph: Optional[SchedulerItem]
    _scale: float
    _debug_rectangles: QGraphicsItemGroup
    _splitter_pos: int
    _splitter_min: int
    _zoom: float
    _color_per_type: Dict[str, QColor] = dict()
    converted_colorPerType: Dict[str, str] = dict()

    def __init__(self):
        """Initialize Scheduler-GUI."""
        super().__init__()
        self._schedule = None
        self._graph = None
        self._scale = 75.0
        self._debug_rectangles = None
        self._zoom = 1.0

        self.setupUi(self)
        self._read_settings()
        self._init_ui()
        self._file_name = None
        self._show_incorrect_execution_time = True
        self._show_port_numbers = True
        self._execution_time_for_variables = None
        self._execution_time_plot_dialogs = defaultdict(lambda: None)
        self._ports_accesses_for_storage = None
        self._color_changed_perType = False
        self.changed_operation_colors: Dict[str, QColor] = dict()

        # Recent files
        self._max_recent_files = 4
        self._recent_files_actions: List[QAction] = []
        self._recent_file_paths: Deque[str] = deque(maxlen=self._max_recent_files)
        self._create_recent_file_actions_and_menus()

        self._init_graphics()

    def _init_ui(self) -> None:
        """Initialize the ui"""

        # Connect signals to slots
        self.menu_load_from_file.triggered.connect(self._load_schedule_from_pyfile)
        self.menu_load_from_file.setIcon(get_icon('import'))
        self.menu_open.setIcon(get_icon('open'))
        self.menu_open.triggered.connect(self.open_schedule)
        self.menu_close_schedule.triggered.connect(self.close_schedule)
        self.menu_close_schedule.setIcon(get_icon('close'))
        self.menu_save.triggered.connect(self.save)
        self.menu_save.setIcon(get_icon('save'))
        self.menu_save_as.triggered.connect(self.save_as)
        self.menu_save_as.setIcon(get_icon('save-as'))
        self.actionPreferences.triggered.connect(self.Preferences_Dialog_clicked)
        self.menu_quit.triggered.connect(self.close)
        self.menu_quit.setIcon(get_icon('quit'))
        self.menu_node_info.triggered.connect(self.show_info_table)
        self.menu_node_info.setIcon(get_icon('info'))
        self.menu_exit_dialog.triggered.connect(self.hide_exit_dialog)
        self.actionReorder.triggered.connect(self._action_reorder)
        self.actionReorder.setIcon(get_icon('reorder'))
        self.actionStatus_bar.triggered.connect(self._toggle_statusbar)
        self.action_incorrect_execution_time.setIcon(get_icon('warning'))
        self.action_incorrect_execution_time.triggered.connect(
            self._toggle_execution_time_warning
        )
        self.action_show_port_numbers.setIcon(get_icon('port-numbers'))
        self.action_show_port_numbers.triggered.connect(self._toggle_port_number)
        self.actionPlot_schedule.setIcon(get_icon('plot-schedule'))
        self.actionPlot_schedule.triggered.connect(self._plot_schedule)
        self.action_view_variables.triggered.connect(
            self._show_execution_times_for_variables
        )
        self.action_view_port_accesses.triggered.connect(
            self._show_ports_accesses_for_storage
        )
        self.actionZoom_to_fit.setIcon(get_icon('zoom-to-fit'))
        self.actionZoom_to_fit.triggered.connect(self._zoom_to_fit)
        self.actionToggle_full_screen.setIcon(get_icon('full-screen'))
        self.actionToggle_full_screen.triggered.connect(self._toggle_fullscreen)
        self.actionUndo.setIcon(get_icon('undo'))
        self.actionRedo.setIcon(get_icon('redo'))
        self.splitter.splitterMoved.connect(self._splitter_moved)
        self.actionDocumentation.triggered.connect(self._open_documentation)
        self.actionDocumentation.setIcon(get_icon('docs'))
        self.actionAbout.triggered.connect(self._open_about_window)
        self.actionAbout.setIcon(get_icon('about'))
        self.actionDecrease_time_resolution.triggered.connect(
            self._decrease_time_resolution
        )
        self.actionDecrease_time_resolution.setIcon(get_icon('decrease-timeresolution'))
        self.actionIncrease_time_resolution.triggered.connect(
            self._increase_time_resolution
        )
        self.actionIncrease_time_resolution.setIcon(get_icon('increase-timeresolution'))
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
        """Initialize the QGraphics framework"""
        self._scene = QGraphicsScene()
        self._scene.addRect(0, 0, 0, 0)  # dummy rect to be able to setPos() graph
        self.view.setScene(self._scene)
        self.view.scale(self._scale, self._scale)
        OperationItem._scale = self._scale
        AxesItem._scale = self._scale
        self._scene.sceneRectChanged.connect(self.shrink_scene_to_min_size)

    @property
    def schedule(self) -> Optional[Schedule]:
        """The current schedule."""
        return self._schedule

    #########
    # Slots #
    #########
    @Slot()
    def _plot_schedule(self) -> None:
        """Callback for plotting schedule using Matplotlib."""
        if self.schedule is None:
            return
        self.schedule.show()

    @Slot()
    def _open_documentation(self) -> None:
        """Callback to open documentation web page."""
        webbrowser.open_new_tab("https://da.gitlab-pages.liu.se/B-ASIC/")

    @Slot()
    def _action_reorder(self) -> None:
        """Callback to reorder all operations vertically based on start time."""
        if self.schedule is None:
            return
        if self._graph is not None:
            self._graph._redraw_from_start()
            self.update_statusbar("Operations reordered based on start time")

    @Slot()
    def _increase_time_resolution(self) -> None:
        """Callback for increasing time resolution."""
        # Create dialog asking for int
        factor, ok = QInputDialog.getInt(
            self, "Increase time resolution", "Factor", 1, 1
        )
        # Check return value
        if ok:
            if factor > 1:
                self.schedule.increase_time_resolution(factor)
                self.open(self.schedule)
                print(f"schedule.increase_time_resolution({factor})")
                self.update_statusbar(f"Time resolution increased by a factor {factor}")
        else:  # Cancelled
            self.update_statusbar("Cancelled")

    @Slot()
    def _decrease_time_resolution(self) -> None:
        """Callback for decreasing time resolution."""
        # Get possible factors
        vals = [str(v) for v in self.schedule.get_possible_time_resolution_decrements()]
        # Create dialog
        factor, ok = QInputDialog.getItem(
            self, "Decrease time resolution", "Factor", vals, editable=False
        )
        # Check return value
        if ok:
            if int(factor) > 1:
                self.schedule.decrease_time_resolution(int(factor))
                self.open(self.schedule)
                print(f"schedule.decrease_time_resolution({factor})")
                self.update_statusbar(f"Time resolution decreased by a factor {factor}")
        else:  # Cancelled
            self.update_statusbar("Cancelled")

    def wheelEvent(self, event) -> None:
        """Zoom in or out using mouse wheel if control is pressed."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            old_zoom = self._zoom
            self._zoom += event.angleDelta().y() / 2500
            self.view.scale(self._zoom, self._zoom)
            self._zoom = old_zoom

    @Slot()
    def _load_schedule_from_pyfile(self) -> None:
        """
        SLOT() for SIGNAL(menu_load_from_file.triggered)
        """
        settings = QSettings()
        last_file = settings.value(
            "scheduler/last_opened_file",
            QStandardPaths.standardLocations(QStandardPaths.HomeLocation)[0],
            str,
        )
        if not os.path.exists(last_file):  # if filename does not exist
            last_file = os.path.dirname(last_file) + "/"
            if not os.path.exists(last_file):  # if path does not exist
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

    def _load_from_file(self, abs_path_filename):
        """
        Import from Python-file.

        Load a python script as a module and search for a Schedule object. If
        found, opens it.
        """
        log.debug(f"abs_path_filename = {abs_path_filename}.")

        module_name = inspect.getmodulename(abs_path_filename)
        if not module_name:  # return if empty module name
            log.error(f"Could not load module from file '{abs_path_filename}'.")
            return

        try:
            module = SourceFileLoader(module_name, abs_path_filename).load_module()
        except Exception as e:
            log.exception(
                "Exception occurred. Could not load module from file"
                " '{}'.\n\n{}".format(abs_path_filename, e)
            )
            return

        self._add_recent_file(abs_path_filename)

        schedule_obj_list = dict(
            inspect.getmembers(module, (lambda x: isinstance(x, Schedule)))
        )

        if not schedule_obj_list:  # return if no Schedule objects in script
            QMessageBox.warning(
                self,
                self.tr("File not found"),
                self.tr("Cannot find any Schedule object in file '{}'.").format(
                    os.path.basename(abs_path_filename)
                ),
            )
            log.info(
                "Cannot find any Schedule object in file '{}'.".format(
                    os.path.basename(abs_path_filename)
                )
            )
            del module
            return

        if len(schedule_obj_list) == 1:
            schedule = [val for val in schedule_obj_list.values()][0]
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
            self.action_view_port_accesses.setEnabled(False)
            self.menu_view_execution_times.setEnabled(False)
            self.actionPreferences.setEnabled(False)

    @Slot()
    def save(self) -> None:
        """
        Save current schedule.

        SLOT() for SIGNAL(menu_save.triggered)
        """
        # TODO: all
        if self._file_name is None:
            self.save_as()
            return
        self._schedule._sfg._graph_id_generator = None
        with open(self._file_name, 'wb') as f:
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
        filename, extension = QFileDialog.getSaveFileName(
            self, 'Save File', '.', filter=self.tr("B-ASIC schedule (*.bsc)")
        )
        if not filename:
            return
        if not filename.endswith('.bsc'):
            filename += '.bsc'
        self._file_name = filename
        self._schedule._sfg._graph_id_generator = None
        with open(self._file_name, 'wb') as f:
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

    def _open_schedule_file(self, abs_path_filename: str):
        """Open a saved schedule (*.bsc-file), which is a pickled Schedule."""
        self._file_name = abs_path_filename
        self._add_recent_file(abs_path_filename)

        with open(self._file_name, 'rb') as f:
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

    def _toggle_file_loaded(self, enable: bool):
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
        EVENT: Replaces QMainWindow default closeEvent(QCloseEvent) event. Takes
        in a QCloseEvent and display an exit dialog, depending on
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
            log.info(f"Exit: {os.path.basename(__file__)}")
            if self._ports_accesses_for_storage:
                self._ports_accesses_for_storage.close()
            if self._execution_time_for_variables:
                self._execution_time_for_variables.close()
            for dialog in self._execution_time_plot_dialogs.values():
                if dialog:
                    dialog.close()
            event.accept()
        else:
            event.ignore()

    def _open_about_window(self, event=None):
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
        self._schedule = deepcopy(schedule)
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
        self.info_table_fill_schedule(self._schedule)
        self._update_operation_types()
        self.actionPreferences.setEnabled(True)
        self.load_preferences()
        self.action_view_variables.setEnabled(True)
        self.action_view_port_accesses.setEnabled(True)
        self.update_statusbar(self.tr("Schedule loaded successfully"))

    def _redraw_all(self) -> None:
        self._graph._redraw_all()

    @Slot()
    def _reopen_schedule(self) -> None:
        self.open(self._schedule)

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
        settings.setValue("font", Font.current_font.toString())
        settings.setValue("fontSize", Font.size)
        settings.setValue("fontColor", Font.color)
        settings.setValue("fontBold", Font.current_font.bold())
        settings.setValue("fontItalic", Font.current_font.italic())
        settings.setValue("fontChanged", Font.changed)

        settings.setValue(Signal_Color.name, Signal_Color.current_color.name())
        settings.setValue(Active_Color.name, Active_Color.current_color.name())
        settings.setValue(
            Signal_Warning_Color.name, Signal_Warning_Color.current_color.name()
        )
        settings.setValue(
            Execution_Time_Color.name, Execution_Time_Color.current_color.name()
        )

        settings.setValue(f"{Signal_Color.name}_changed", Signal_Color.changed)
        settings.setValue(f"{Active_Color.name}_changed", Active_Color.changed)
        settings.setValue(
            f"{Signal_Warning_Color.name}_changed", Signal_Warning_Color.changed
        )
        self.Save_colortype()
        settings.sync()

        if settings.isWritable():
            log.debug(f"Settings written to '{settings.fileName()}'.")
        else:
            log.warning("Settings cant be saved to file, read-only.")

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
        Font.current_font = QFont(
            settings.value("font", defaultValue=Font.DEFAULT.toString(), type=str)
        )
        Font.size = settings.value(
            "fontSize", defaultValue=Font.DEFAULT.pointSizeF(), type=int
        )
        Font.color = QColor(
            settings.value("fontColor", defaultValue=Font.DEFAULT_COLOR, type=str)
        )
        Font.bold = settings.value(
            "fontBold", defaultValue=Font.DEFAULT.bold(), type=bool
        )
        Font.italic = settings.value(
            "fontItalic", defaultValue=Font.DEFAULT.italic(), type=bool
        )
        Font.changed = settings.value("fontChanged", Font.changed, bool)

        Signal_Color.current_color = QColor(
            settings.value(
                "Signal Color", defaultValue=Signal_Color.DEFAULT.name(), type=str
            )
        )
        Active_Color.current_color = QColor(
            settings.value(
                "Active Color", defaultValue=Active_Color.DEFAULT.name(), type=str
            )
        )
        Signal_Warning_Color.current_color = QColor(
            settings.value(
                "Warning Color",
                defaultValue=Signal_Warning_Color.DEFAULT.name(),
                type=str,
            )
        )
        Latency_Color.current_color = QColor(
            settings.value(
                "Latency Color", defaultValue=Latency_Color.DEFAULT.name(), type=str
            )
        )
        Execution_Time_Color.current_color = QColor(
            settings.value(
                "Execution Time Color",
                defaultValue=Execution_Time_Color.DEFAULT.name(),
                type=str,
            )
        )
        Signal_Color.changed = settings.value(
            f"{Signal_Color.name}_changed", False, bool
        )
        Active_Color.changed = settings.value(
            f"{Active_Color.name}_changed", False, bool
        )
        Signal_Warning_Color.changed = settings.value(
            f"{Signal_Warning_Color.name}_changed",
            False,
            bool,
        )
        Latency_Color.changed = settings.value(
            f"{Latency_Color.name}_changed", False, bool
        )
        Execution_Time_Color.changed = settings.value(
            f"{Execution_Time_Color.name}_changed",
            False,
            bool,
        )
        self._color_changed_perType = settings.value(
            "_color_changed_perType", False, bool
        )

        settings.endGroup()
        settings.sync()
        log.debug(f"Settings read from '{settings.fileName()}'.")

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
            GraphComponent, self.schedule.sfg.find_by_id(graph_id)
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
        self.info_table.setItem(
            si, 1, QTableWidgetItem(str(self.schedule.forward_slack(graph_id)))
        )
        si += 1

        self.info_table.insertRow(si)
        self.info_table.setItem(si, 0, QTableWidgetItem("Backward slack"))
        self.info_table.setItem(
            si,
            1,
            QTableWidgetItem(str(self.schedule.backward_slack(graph_id))),
        )
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

    def _create_recent_file_actions_and_menus(self):
        for i in range(self._max_recent_files):
            recent_file_action = QAction(self.menu_Recent_Schedule)
            recent_file_action.setVisible(False)
            recent_file_action.triggered.connect(
                lambda b=0, x=recent_file_action: self._open_recent_file(x)
            )
            self._recent_files_actions.append(recent_file_action)
            self.menu_Recent_Schedule.addAction(recent_file_action)

        self._update_recent_file_list()

    def _update_operation_types(self):
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

    def Preferences_Dialog_clicked(self):
        """Open the Preferences dialog to customize fonts, colors, and settings"""
        dialog = QDialog()
        dialog.setWindowTitle("Preferences")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Add label for the dialog
        label = QLabel("Personalize Your Fonts and Colors")
        layout.addWidget(label)

        groupbox = QGroupBox()
        Hlayout = QHBoxLayout()
        label = QLabel("Color Settings:")
        layout.addWidget(label)
        Hlayout.setSpacing(20)

        Hlayout.addWidget(self.creat_color_button(Execution_Time_Color))
        Hlayout.addWidget(self.creat_color_button(Latency_Color))
        Hlayout.addWidget(
            self.creat_color_button(
                ColorDataType(
                    current_color=Latency_Color.DEFAULT,
                    DEFAULT=QColor('skyblue'),
                    name="Latency Color per Type",
                )
            )
        )

        groupbox.setLayout(Hlayout)
        layout.addWidget(groupbox)

        label = QLabel("Signal Colors:")
        layout.addWidget(label)
        groupbox = QGroupBox()
        Hlayout = QHBoxLayout()
        Hlayout.setSpacing(20)

        Signal_button = self.creat_color_button(Signal_Color)
        Signal_button.setStyleSheet(
            f"color: {QColor(255,255,255,0).name()}; background-color: {Signal_Color.DEFAULT.name()}"
        )

        Hlayout.addWidget(Signal_button)
        Hlayout.addWidget(self.creat_color_button(Signal_Warning_Color))
        Hlayout.addWidget(self.creat_color_button(Active_Color))

        groupbox.setLayout(Hlayout)
        layout.addWidget(groupbox)

        Reset_Color_button = ColorButton(QColor('silver'))
        Reset_Color_button.setText('Reset All Color settings')
        Reset_Color_button.pressed.connect(self.reset_color_clicked)
        layout.addWidget(Reset_Color_button)

        label = QLabel("Font Settings:")
        layout.addWidget(label)

        groupbox = QGroupBox()
        Hlayout = QHBoxLayout()
        Hlayout.setSpacing(10)

        Font_button = ColorButton(QColor('moccasin'))
        Font_button.setText('Font Settings')
        Hlayout.addWidget(Font_button)

        Font_color_button = ColorButton(QColor('moccasin'))
        Font_color_button.setText('Font Color')
        Font_color_button.pressed.connect(self.font_color_clicked)
        Hlayout.addWidget(Font_color_button)

        groupbox2 = QGroupBox()
        Hlayout2 = QHBoxLayout()

        icon = QIcon.fromTheme("format-text-italic")
        Italicbutton = (
            ColorButton(QColor('silver'))
            if Font.italic
            else ColorButton(QColor('snow'))
        )
        Italicbutton.setIcon(icon)
        Italicbutton.pressed.connect(lambda: self.Italic_font_clicked(Italicbutton))
        Hlayout2.addWidget(Italicbutton)

        icon = QIcon.fromTheme("format-text-bold")
        Boldbutton = (
            ColorButton(QColor('silver')) if Font.bold else ColorButton(QColor('snow'))
        )
        Boldbutton.setIcon(icon)
        Boldbutton.pressed.connect(lambda: self.Bold_font_clicked(Boldbutton))
        Hlayout2.addWidget(Boldbutton)

        groupbox2.setLayout(Hlayout2)
        Hlayout.addWidget(groupbox2)

        groupbox2 = QGroupBox()
        Hlayout2 = QHBoxLayout()
        Font_Size_input = QLineEdit()
        Font_button.pressed.connect(
            lambda: self.font_clicked(Font_Size_input, Italicbutton, Boldbutton)
        )

        icon = QIcon.fromTheme("list-add")
        Incr_button = ColorButton(QColor('smoke'))
        Incr_button.setIcon(icon)
        Incr_button.pressed.connect(lambda: self.Incr_font_clicked(Font_Size_input))
        Incr_button.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl++"))
        Hlayout2.addWidget(Incr_button)

        Font_Size_input.setPlaceholderText('Font Size')
        Font_Size_input.setText(f'Font Size: {Font.size}')
        Font_Size_input.setValidator(QIntValidator(0, 99))
        Font_Size_input.setAlignment(Qt.AlignCenter)
        Font_Size_input.textChanged.connect(
            lambda: self.set_fontSize_clicked(Font_Size_input.text())
        )
        Font_Size_input.textChanged.connect(
            lambda: self.set_fontSize_clicked(Font_Size_input.text())
        )
        Hlayout2.addWidget(Font_Size_input)

        icon = QIcon.fromTheme("list-remove")
        Decr_button = ColorButton(QColor('smoke'))
        Decr_button.setIcon(icon)
        Decr_button.pressed.connect(lambda: self.Decr_font_clicked(Font_Size_input))
        Decr_button.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+-"))

        Hlayout2.addWidget(Decr_button)

        groupbox2.setLayout(Hlayout2)
        Hlayout.addWidget(groupbox2)

        groupbox.setLayout(Hlayout)
        layout.addWidget(groupbox)

        Reset_Font_button = ColorButton(QColor('silver'))
        Reset_Font_button.setText('Reset All Font Settings')
        Reset_Font_button.pressed.connect(
            lambda: self.reset_font_clicked(Font_Size_input, Italicbutton, Boldbutton)
        )
        layout.addWidget(Reset_Font_button)

        label = QLabel("")
        layout.addWidget(label)

        Reset_button = ColorButton(QColor('salmon'))
        Reset_button.setText('Reset All Settings')
        Reset_button.pressed.connect(
            lambda: self.reset_all_clicked(Font_Size_input, Italicbutton, Boldbutton)
        )
        layout.addWidget(Reset_button)

        dialog.setLayout(layout)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close)
        buttonBox.ButtonLayout(QDialogButtonBox.MacLayout)
        buttonBox.accepted.connect(dialog.accept)
        buttonBox.rejected.connect(dialog.close)
        layout.addWidget(buttonBox)

        dialog.exec_()

    def creat_color_button(self, color: ColorDataType) -> ColorButton:
        """Create a colored button to be used to modify a certain color
        color_type: ColorDataType
            The color_type assigned to the butten to be created.
        """
        button = ColorButton(color.DEFAULT)
        button.setText(color.name)
        if color.name == "Latency Color":
            button.pressed.connect(
                lambda: self.set_latency_color_by_type_name(all=True)
            )
        elif color.name == "Latency Color per Type":
            button.pressed.connect(
                lambda: self.set_latency_color_by_type_name(all=False)
            )
        else:
            button.pressed.connect(lambda: self.Color_button_clicked(color))
        return button

    def set_latency_color_by_type_name(self, all: bool):
        """Set latency color based on operation type names
        all: bool
            Indicates if the color of all type names to be modified.
        """
        if Latency_Color.changed:
            current_color = Latency_Color.current_color
        else:
            current_color = Latency_Color.DEFAULT

        # Prompt user to select operation type if not setting color for all types
        if not all:
            used_types = self._schedule.get_used_type_names()
            type, ok = QInputDialog.getItem(
                self, "Select Operation Type", "Type", used_types, editable=False
            )
        else:
            type = "all operations"
            ok = False

        # Open a color dialog to get the selected color
        if all or ok:
            color = QColorDialog.getColor(
                current_color, self, f"Select the color of {type}"
            )

            # If a valid color is selected, update color settings and graph
            if color.isValid():
                if all:
                    Latency_Color.changed = True
                    self._color_changed_perType = False
                    self.changed_operation_colors.clear()
                    Latency_Color.current_color = color
                # Save color settings for each operation type
                else:
                    self._color_changed_perType = True
                    self.changed_operation_colors[type] = color
                self.color_pref_update()
                self.update_statusbar("Preferences Updated")

    def color_pref_update(self):
        """Update preferences of Latency color per type"""
        for type in self._schedule.get_used_type_names():
            if Latency_Color.changed and not self._color_changed_perType:
                self._color_per_type[type] = Latency_Color.current_color
            elif not Latency_Color.changed and not self._color_changed_perType:
                self._color_per_type[type] = Latency_Color.DEFAULT
            elif not Latency_Color.changed and self._color_changed_perType:
                if type in self.changed_operation_colors.keys():
                    self._color_per_type[type] = self.changed_operation_colors[type]
                else:
                    self._color_per_type[type] = Latency_Color.DEFAULT
            else:
                if type in self.changed_operation_colors.keys():
                    self._color_per_type[type] = self.changed_operation_colors[type]
                else:
                    self._color_per_type[type] = Latency_Color.current_color
        self.Save_colortype()

    def Save_colortype(self):
        """Save preferences of Latency color per type in settings"""
        settings = QSettings()
        for key, color in self._color_per_type.items():
            self._graph._color_change(color, key)
            self.converted_colorPerType[key] = color.name()
        settings.setValue(
            f"scheduler/preferences/{Latency_Color.name}",
            Latency_Color.current_color,
        )
        settings.setValue(
            f"scheduler/preferences/{Latency_Color.name}_changed", Latency_Color.changed
        )
        settings.setValue(
            f"scheduler/preferences/{Latency_Color.name}/perType",
            self.converted_colorPerType,
        )
        settings.setValue(
            f"scheduler/preferences/{Latency_Color.name}/perType_changed",
            self._color_changed_perType,
        )

    def Color_button_clicked(self, color_type: ColorDataType):
        """Open a color dialog to select a color based on the specified color type
        color_type: ColorDataType
            The color_type to be changed.
        """
        settings = QSettings()
        if color_type.changed:
            current_color = color_type.current_color
        else:
            current_color = color_type.DEFAULT

        color = QColorDialog.getColor(current_color, self, f"Select {color_type.name}")
        # If a valid color is selected, update the current color and settings
        if color.isValid():
            color_type.current_color = color
            # colorbutton.set_color(color)
            color_type.changed = (
                False if color_type.current_color == color_type.DEFAULT else True
            )
            settings.setValue(f"scheduler/preferences/{color_type.name}", color.name())
            settings.sync()

        self._graph._signals.reopen.emit()
        self.update_statusbar("Preferences Updated")

    def font_clicked(
        self, Sizeline: QLineEdit, italicbutton: ColorButton, boldbutton: ColorButton
    ):
        """Open a font dialog to select a font and update the current font
        Sizeline: QLineEdit
            The line displaying the text size to be matched with the chosen font.
        italicbutton: ColorButton
            The button displaying the italic state to be matched with the chosen font.
        boldbutton: ColorButton
            The button displaying the bold state to be matched with the chosen font.
        """
        if Font.changed:
            current_font = Font.current_font
        else:
            current_font = Font.DEFAULT

        (ok, font) = QFontDialog.getFont(current_font, self)
        if ok:
            Font.current_font = font
            Font.size = int(font.pointSizeF())
            Font.bold = font.bold()
            Font.italic = font.italic()
            self.Update_font()
            self.Match_Dialog_Font(Sizeline, italicbutton, boldbutton)
            self.update_statusbar("Preferences Updated")

    def Update_font(self):
        """Update font preferences based on current Font settings"""
        settings = QSettings()
        Font.changed = (
            False
            if (
                Font.current_font == Font.DEFAULT
                and Font.size == int(Font.DEFAULT.pointSizeF())
                and Font.italic == Font.DEFAULT.italic()
                and Font.bold == Font.DEFAULT.bold()
            )
            else True
        )
        settings.setValue("scheduler/preferences/font", Font.current_font.toString())
        settings.setValue("scheduler/preferences/fontSize", Font.size)
        settings.setValue("scheduler/preferences/fontBold", Font.bold)
        settings.setValue("scheduler/preferences/fontItalic", Font.italic)
        settings.sync()
        self.load_preferences()

    def load_preferences(self):
        "Load the last saved preferences from settings"
        settings = QSettings()
        Latency_Color.current_color = QColor(
            settings.value(
                f"scheduler/preferences/{Latency_Color.name}",
                defaultValue=Latency_Color.DEFAULT,
                type=str,
            )
        )
        Latency_Color.changed = settings.value(
            f"scheduler/preferences/{Latency_Color.name}_changed", False, bool
        )
        self.converted_colorPerType = settings.value(
            f"scheduler/preferences/{Latency_Color.name}/perType",
            self.converted_colorPerType,
        )
        self._color_changed_perType = settings.value(
            f"scheduler/preferences/{Latency_Color.name}/perType_changed", False, bool
        )
        settings.sync()

        for key, color_str in self.converted_colorPerType.items():
            color = QColor(color_str)
            self._color_per_type[key] = color
            Match = (
                (color == Latency_Color.current_color)
                if Latency_Color.changed
                else (color == Latency_Color.DEFAULT)
            )
            if self._color_changed_perType and not Match:
                self.changed_operation_colors[key] = color
        self.color_pref_update()

        if Font.changed:
            Font.current_font.setPointSizeF(Font.size)
            Font.current_font.setItalic(Font.italic)
            Font.current_font.setBold(Font.bold)
            self._graph._font_change(Font.current_font)
            self._graph._font_color_change(Font.color)
        else:
            self._graph._font_change(Font.DEFAULT)
            self._graph._font_color_change(Font.DEFAULT_COLOR)

        self.update_statusbar("Saved Preferences Loaded")

    def font_color_clicked(self):
        """Select a font color and update preferences"""
        settings = QSettings()
        color = QColorDialog.getColor(Font.color, self, "Select Font Color")
        if color.isValid():
            Font.color = color
            Font.changed = True
        settings.setValue("scheduler/preferences/fontColor", Font.color.name())
        settings.sync()
        self._graph._font_color_change(Font.color)

    def set_fontSize_clicked(self, size):
        """Set the font size to the specified size and update the font
        size
            The font size to be set.
        """
        Font.size = int(size) if (not size == "") else 6
        Font.current_font.setPointSizeF(Font.size)
        self.Update_font()

    def Italic_font_clicked(self, button: ColorButton):
        """Toggle the font style to italic if not already italic, otherwise remove italic
        button: ColorButton
            The clicked button. Used to indicate state on/off.
        """
        Font.italic = not Font.italic
        Font.current_font.setItalic(Font.italic)
        (
            button.set_color(QColor('silver'))
            if Font.italic
            else button.set_color(QColor('snow'))
        )
        self.Update_font()

    def Bold_font_clicked(self, button: ColorButton):
        """Toggle the font style to bold if not already bold, otherwise unbold
        button: ColorButton
            The clicked button. Used to indicate state on/off.
        """
        Font.bold = not Font.bold
        Font.current_font.setBold(Font.bold)
        Font.current_font.setWeight(50)
        (
            button.set_color(QColor('silver'))
            if Font.bold
            else button.set_color(QColor('snow'))
        )
        self.Update_font()

    def Incr_font_clicked(self, line: QLineEdit):
        """
        Increase the font size by 1.
        line: QLineEdit
            The line displaying the text size to be matched.
        """
        (
            line.setText(str(Font.size + 1))
            if Font.size <= 71
            else line.setText(str(Font.size))
        )

    def Decr_font_clicked(self, line: QLineEdit):
        """
        Decrease the font size by 1.
        line: QLineEdit
            The line displaying the text size to be matched.
        """
        (
            line.setText(str(Font.size - 1))
            if Font.size >= 7
            else line.setText(str(Font.size))
        )

    def reset_color_clicked(self):
        """Reset the color settings"""
        settings = QSettings()
        Latency_Color.changed = False
        Active_Color.changed = False
        Signal_Warning_Color.changed = False
        Signal_Color.changed = False
        Execution_Time_Color.changed = False
        self._color_changed_perType = False
        self.color_pref_update()

        settings.beginGroup("scheduler/preferences")
        settings.setValue(Latency_Color.name, Latency_Color.DEFAULT.name())
        settings.setValue(Signal_Color.name, Signal_Color.DEFAULT.name())
        settings.setValue(Active_Color.name, Active_Color.DEFAULT.name())
        settings.setValue(
            Signal_Warning_Color.name, Signal_Warning_Color.DEFAULT.name()
        )
        settings.setValue(
            Execution_Time_Color.name, Execution_Time_Color.DEFAULT.name()
        )
        settings.endGroup()

        self._graph._color_change(Latency_Color.DEFAULT, "all operations")
        self._graph._signals.reopen.emit()
        self.load_preferences()

    def reset_font_clicked(
        self, Sizeline: QLineEdit, italicbutton: ColorButton, boldbutton: ColorButton
    ):
        """Reset the font settings.
        Sizeline: QLineEdit
            The line displaying the text size to be matched with the chosen font.
        italicbutton: ColorButton
            The button displaying the italic state to be matched with the chosen font.
        boldbutton: ColorButton
            The button displaying the bold state to be matched with the chosen font.
        """
        Font.current_font = QFont("Times", 12)
        Font.changed = False
        Font.color = Font.DEFAULT_COLOR
        Font.size = int(Font.DEFAULT.pointSizeF())
        Font.bold = Font.DEFAULT.bold()
        Font.italic = Font.DEFAULT.italic()
        self.Update_font()
        self.load_preferences()
        self.Match_Dialog_Font(Sizeline, italicbutton, boldbutton)

    def reset_all_clicked(
        self, Sizeline: QLineEdit, italicbutton: ColorButton, boldbutton: ColorButton
    ):
        """Reset both the color and the font settings"""
        self.reset_color_clicked()
        self.reset_font_clicked(Sizeline, italicbutton, boldbutton)

    def Match_Dialog_Font(
        self, Sizeline: QLineEdit, italicbutton: ColorButton, boldbutton: ColorButton
    ):
        """Update the widgets on the pref dialog to match the current font
        Sizeline: QLineEdit
            The line displaying the text size to be matched with the current font.
        italicbutton: ColorButton
            The button displaying the italic state to be matched with the current font.
        boldbutton: ColorButton
            The button displaying the bold state to be matched with the current font.
        """
        Sizeline.setText(str(Font.size))

        (
            italicbutton.set_color(QColor('silver'))
            if Font.italic
            else italicbutton.set_color(QColor('snow'))
        )
        (
            boldbutton.set_color(QColor('silver'))
            if Font.bold
            else boldbutton.set_color(QColor('snow'))
        )

    @Slot(str)
    def _show_execution_times_for_type(self, type_name):
        self._execution_time_plot(type_name)

    def _closed_execution_times_for_type(self, type_name):
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

    def _update_execution_times_for_type(self, type_name):
        if self._execution_time_plot_dialogs[type_name]:
            self._execution_time_plot_dialogs[type_name].axes.clear()
            self._schedule.get_operations().get_by_type_name(type_name).plot(
                self._execution_time_plot_dialogs[type_name].axes
            )
            self._execution_time_plot_dialogs[type_name].redraw()

    def _show_execution_times_for_variables(self):
        self._execution_time_for_variables = MPLWindow("Execution times for variables")
        self._execution_time_for_variables.finished.connect(
            self._execution_times_for_variables_closed
        )
        self._update_execution_times_for_variables()
        self._execution_time_for_variables.show()

    def _update_execution_times_for_variables(self):
        if self._execution_time_for_variables:
            self._execution_time_for_variables.axes.clear()
            self._schedule.get_memory_variables().plot(
                self._execution_time_for_variables.axes, allow_excessive_lifetimes=True
            )
            self._execution_time_for_variables.redraw()

    @Slot()
    def _execution_times_for_variables_closed(self):
        self._execution_time_for_variables = None

    def _show_ports_accesses_for_storage(self):
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
    def _schedule_changed(self, type_name: Optional[str] = None):
        self._update_execution_times_for_variables()
        self._update_ports_accesses_for_storage()
        for key, dialog in self._execution_time_plot_dialogs.items():
            if dialog:
                self._update_execution_times_for_type(key)

    def _update_recent_file_list(self):
        settings = QSettings()

        rfp = cast(deque, settings.value("scheduler/recentFiles"))

        # print(rfp)
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

    def _open_recent_file(self, action):
        if action.data().filePath().endswith('.bsc'):
            self._open_schedule_file(action.data().filePath())
        else:
            self._load_from_file(action.data().filePath())

    def _add_recent_file(self, filename):
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

    def _zoom_to_fit(self, event=None):
        """Callback for zoom to fit schedule in window."""
        self.view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _toggle_statusbar(self, event=None) -> None:
        """Callback for toggling the status bar."""
        self.statusbar.setVisible(self.actionStatus_bar.isChecked())

    def _toggle_execution_time_warning(self, event=None) -> None:
        """Callback for toggling the status bar."""
        self._show_incorrect_execution_time = (
            self.action_incorrect_execution_time.isChecked()
        )
        self._graph.set_warnings(self._show_incorrect_execution_time)

    def _toggle_port_number(self, event=None) -> None:
        """Callback for toggling the status bar."""
        self._show_port_numbers = self.action_show_port_numbers.isChecked()
        self._graph.set_port_numbers(self._show_port_numbers)

    def _toggle_fullscreen(self, event=None):
        """Callback for toggling full screen mode."""
        if self.isFullScreen():
            self.showNormal()
            self.actionToggle_full_screen.setIcon(get_icon('full-screen'))
        else:
            self.showFullScreen()
            self.actionToggle_full_screen.setIcon(get_icon('full-screen-exit'))


@overload
def start_scheduler(schedule: Schedule) -> Schedule: ...


@overload
def start_scheduler(schedule: None) -> Optional[Schedule]: ...


@overload
def start_scheduler() -> Optional[Schedule]: ...


def start_scheduler(schedule: Optional[Schedule] = None) -> Optional[Schedule]:
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
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    window = ScheduleMainWindow()
    if schedule:
        window.open(schedule)
    window.show()
    app.exec_()
    return window.schedule


if __name__ == "__main__":
    start_scheduler()
