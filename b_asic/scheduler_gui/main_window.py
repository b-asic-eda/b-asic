#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B-ASIC Scheduler-GUI Module.

Contains the scheduler_gui MainWindow class for scheduling operations in an SFG.

Start main-window with ``start_gui()``.
"""
import inspect
import os
import sys
import webbrowser
from collections import deque
from copy import deepcopy
from importlib.machinery import SourceFileLoader
from typing import List, Optional, Union, cast

# Qt/qtpy
import qtpy

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
from qtpy.QtGui import QCloseEvent
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
import b_asic.scheduler_gui.logger as logger
from b_asic._version import __version__
from b_asic.graph_component import GraphComponent, GraphID
from b_asic.gui_utils.about_window import AboutWindow
from b_asic.schedule import Schedule
from b_asic.scheduler_gui.axes_item import AxesItem
from b_asic.scheduler_gui.operation_item import OperationItem
from b_asic.scheduler_gui.scheduler_item import SchedulerItem

sys.path.insert(0, "icons/")  # Needed for *.rc.py files in ui_main_window
from b_asic.scheduler_gui.ui_main_window import Ui_MainWindow

log = logger.getLogger()
sys.excepthook = logger.handle_exceptions


# Debug stuff
if __debug__:
    log.setLevel("DEBUG")

if __debug__:
    # Print some system version information
    from qtpy import QtCore

    QT_API = os.environ.get("QT_API", "")
    log.debug("Qt version (runtime):      {}".format(QtCore.qVersion()))
    log.debug("Qt version (compile time): {}".format(QtCore.__version__))
    log.debug("QT_API:                    {}".format(QT_API))
    if QT_API.lower().startswith("pyside"):
        import PySide2

        log.debug("PySide version:           {}".format(PySide2.__version__))
    if QT_API.lower().startswith("pyqt"):
        from qtpy.QtCore import PYQT_VERSION_STR

        log.debug("PyQt version:             {}".format(PYQT_VERSION_STR))
    log.debug("QtPy version:             {}".format(qtpy.__version__))


# The following QCoreApplication values is used for QSettings among others
QCoreApplication.setOrganizationName("Linköping University")
QCoreApplication.setOrganizationDomain("liu.se")
QCoreApplication.setApplicationName("B-ASIC Scheduling GUI")
QCoreApplication.setApplicationVersion(__version__)


class MainWindow(QMainWindow, Ui_MainWindow):
    """Schedule of an SFG with scheduled Operations."""

    _scene: QGraphicsScene
    _schedule: Optional[Schedule]
    _graph: Optional[SchedulerItem]
    _scale: float
    _debug_rectangles: QGraphicsItemGroup
    _splitter_pos: int
    _splitter_min: int
    _zoom: float

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
        self._init_graphics()

    def _init_ui(self) -> None:
        """Initialize the ui"""

        # Connect signals to slots
        self.menu_load_from_file.triggered.connect(self._load_schedule_from_pyfile)
        self.menu_close_schedule.triggered.connect(self.close_schedule)
        self.menu_save.triggered.connect(self.save)
        self.menu_save_as.triggered.connect(self.save_as)
        self.menu_quit.triggered.connect(self.close)
        self.menu_node_info.triggered.connect(self.show_info_table)
        self.menu_exit_dialog.triggered.connect(self.hide_exit_dialog)
        self.actionReorder.triggered.connect(self._action_reorder)
        self.actionPlot_schedule.triggered.connect(self._plot_schedule)
        self.splitter.splitterMoved.connect(self._splitter_moved)
        self.actionDocumentation.triggered.connect(self._open_documentation)
        self.actionAbout.triggered.connect(self._open_about_window)

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

        # Recent files
        self.maxFileNr = 4
        self.recentFilesList: List[QAction] = []
        self.recentFilePaths = deque(maxlen=self.maxFileNr)
        self._create_recent_file_actions_and_menus()

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
        # TODO: remove
        if self.schedule is None:
            return
        self.schedule.show()
        if self._graph is not None:
            print(f"filtersChildEvents(): {self._graph.filtersChildEvents()}")
        # self._print_button_pressed('callback_pushButton()')

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
        Load a python script as a module and search for a Schedule object. If
        found, opens it.
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
        log.debug("abs_path_filename = {}.".format(abs_path_filename))

        module_name = inspect.getmodulename(abs_path_filename)
        if not module_name:  # return if empty module name
            log.error("Could not load module from file '{}'.".format(abs_path_filename))
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

    @Slot()
    def save(self) -> None:
        """
        Save current schedule.

        SLOT() for SIGNAL(menu_save.triggered)
        """
        # TODO: all
        self._print_button_pressed("save_schedule()")
        self.update_statusbar(self.tr("Schedule saved successfully"))

    @Slot()
    def save_as(self) -> None:
        """
        Save current schedule asking for file name.

        SLOT() for SIGNAL(menu_save_as.triggered)
        """
        # TODO: Implement
        self._print_button_pressed("save_schedule()")
        self.update_statusbar(self.tr("Schedule saved successfully"))

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

    @Slot(bool)
    def hide_exit_dialog(self, checked: bool) -> None:
        """
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
        SLOT() for SIGNAL(_graph._signals.schedule_time_changed)
        Updates the 'Schedule' part of the info table.
        """
        if self.schedule is not None:
            self.info_table.item(1, 1).setText(str(self.schedule.schedule_time))

    @Slot(QRectF)
    def shrink_scene_to_min_size(self, rect: QRectF) -> None:
        """
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
        hide_dialog = settings.value("scheduler/hide_exit_dialog", False, bool)
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
            log.info("Exit: {}".format(os.path.basename(__file__)))
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
        self._graph._signals.schedule_time_changed.connect(
            self.info_table_update_schedule
        )
        self._graph._signals.redraw_all.connect(self._redraw_all)
        self.info_table_fill_schedule(self._schedule)
        self.update_statusbar(self.tr("Schedule loaded successfully"))

    def _redraw_all(self) -> None:
        self._graph._redraw_all()

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
        settings.setValue(
            "scheduler/state", self.saveState()
        )  # toolbars, dockwidgets: pos, size
        settings.setValue("scheduler/menu/node_info", self.menu_node_info.isChecked())
        settings.setValue("scheduler/splitter/state", self.splitter.saveState())
        settings.setValue("scheduler/splitter/pos", self.splitter.sizes()[1])

        if settings.isWritable():
            log.debug("Settings written to '{}'.".format(settings.fileName()))
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

        log.debug("Settings read from '{}'.".format(settings.fileName()))

    def info_table_fill_schedule(self, schedule: Schedule) -> None:
        """
        Take a Schedule and fill in the 'Schedule' part of the info table
        with values from *schedule*.
        """
        self.info_table.insertRow(1)
        self.info_table.insertRow(1)
        self.info_table.setItem(1, 0, QTableWidgetItem("Schedule Time"))
        self.info_table.setItem(2, 0, QTableWidgetItem("Cyclic"))
        self.info_table.setItem(1, 1, QTableWidgetItem(str(schedule.schedule_time)))
        self.info_table.setItem(2, 1, QTableWidgetItem(str(schedule.cyclic)))

    def _info_table_fill_component(self, graph_id: GraphID) -> None:
        """
        Take an operator-id and fill in the 'Operator' part of the info
        table with values from the operator associated with *graph_id*.
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
        """Clears the info table."""
        self.info_table_clear_component()
        self.info_table_clear_schedule()

    def info_table_clear_schedule(self) -> None:
        """Clears the schedule part of the info table."""
        row = self.info_table.findItems("Operator", Qt.MatchFlag.MatchExactly)
        if row:
            row = row[0].row()
            if row > 2:
                for _ in range(3):
                    self.info_table.removeRow(1)
        else:
            log.error("'Operator' not found in info table. It may have been renamed.")

    def exit_app(self) -> None:
        """Exit application."""
        log.info("Exiting the application.")
        QApplication.quit()

    def info_table_clear_component(self) -> None:
        """Clears the component part of the info table."""
        row = self.info_table.findItems("Operator", Qt.MatchFlag.MatchExactly)
        if row:
            row = row[0].row()
            for _ in range(self.info_table.rowCount() - row + 1):
                self.info_table.removeRow(row + 1)
        else:
            log.error("'Operator' not found in info table. It may have been renamed.")

    def _create_recent_file_actions_and_menus(self):
        for i in range(self.maxFileNr):
            recentFileAction = QAction(self.menu_Recent_Schedule)
            recentFileAction.setVisible(False)
            recentFileAction.triggered.connect(
                lambda b=0, x=recentFileAction: self._open_recent_file(x)
            )
            self.recentFilesList.append(recentFileAction)
            self.menu_Recent_Schedule.addAction(recentFileAction)

        self._update_recent_file_list()

    def _update_recent_file_list(self):
        settings = QSettings()

        rfp = settings.value("scheduler/recentFiles")

        # print(rfp)
        if rfp:
            dequelen = len(rfp)
            if dequelen > 0:
                for i in range(dequelen):
                    action = self.recentFilesList[i]
                    action.setText(rfp[i])
                    action.setData(QFileInfo(rfp[i]))
                    action.setVisible(True)

                for i in range(dequelen, self.maxFileNr):
                    self.recentFilesList[i].setVisible(False)

    def _open_recent_file(self, action):
        self._load_from_file(action.data().filePath())

    def _add_recent_file(self, module):
        settings = QSettings()

        rfp = settings.value("scheduler/recentFiles")

        if rfp:
            if module not in rfp:
                rfp.append(module)
        else:
            rfp = deque(maxlen=self.maxFileNr)
            rfp.append(module)

        settings.setValue("scheduler/recentFiles", rfp)

        self._update_recent_file_list()


def start_scheduler(schedule: Optional[Schedule] = None) -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    if schedule:
        window.open(schedule)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start_scheduler()
