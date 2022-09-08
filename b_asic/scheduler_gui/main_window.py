#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-ASIC Scheduler-gui Module.

Contains the scheduler-gui MainWindow class for scheduling operations in an SFG.

Start main-window with start_gui().
"""
import inspect
import os
import sys
from copy import deepcopy
from importlib.machinery import SourceFileLoader
from typing import Union

# Qt/qtpy
import qtpy

# QGraphics and QPainter imports
from qtpy.QtCore import (
    QByteArray,
    QCoreApplication,
    QRectF,
    QSettings,
    QStandardPaths,
    Qt,
    Slot,
)
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import (
    QAbstractButton,
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
from b_asic.graph_component import GraphComponent
from b_asic.schedule import Schedule
from b_asic.scheduler_gui.graphics_axes_item import GraphicsAxesItem
from b_asic.scheduler_gui.graphics_component_item import GraphicsComponentItem
from b_asic.scheduler_gui.graphics_graph_item import GraphicsGraphItem
sys.path.insert(0, "icons/")  # Needed for *.rc.py files in ui_main_window
from b_asic.scheduler_gui.ui_main_window import Ui_MainWindow

log = logger.getLogger()
sys.excepthook = logger.handle_exceptions


# Debug struff
if __debug__:
    log.setLevel("DEBUG")

if __debug__:
    # Print some system version information
    from qtpy import QtCore

    QT_API = os.environ.get("QT_API")
    log.debug("Qt version (runtime):     {}".format(QtCore.qVersion()))
    log.debug("Qt version (compiletime): {}".format(QtCore.__version__))
    log.debug("QT_API:                   {}".format(QT_API))
    if QT_API.lower().startswith("pyside"):
        import PySide2

        log.debug("PySide version:           {}".format(PySide2.__version__))
    if QT_API.lower().startswith("pyqt"):
        from qtpy.QtCore import PYQT_VERSION_STR

        log.debug("PyQt version:             {}".format(PYQT_VERSION_STR))
    log.debug("QtPy version:             {}".format(qtpy.__version__))


# The following QCoreApplication values is used for QSettings among others
QCoreApplication.setOrganizationName("Linöping University")
QCoreApplication.setOrganizationDomain("liu.se")
QCoreApplication.setApplicationName("B-ASIC Scheduler")
# QCoreApplication.setApplicationVersion(__version__)     # TODO: read from packet __version__


class MainWindow(QMainWindow, Ui_MainWindow):
    """Schedule of an SFG with scheduled Operations."""

    _scene: QGraphicsScene
    _schedule: Union[Schedule, None]
    _graph: Union[GraphicsGraphItem, None]
    _scale: float
    _debug_rects: QGraphicsItemGroup
    _splitter_pos: int
    _splitter_min: int

    def __init__(self):
        """Initialize Scheduler-gui."""
        super().__init__()
        self._schedule = None
        self._graph = None
        self._scale = 75.0
        self._debug_rects = None

        self.setupUi(self)
        self._read_settings()
        self._init_ui()
        self._init_graphics()

    def _init_ui(self) -> None:
        """Initialize the ui"""

        # Connect signals to slots
        self.menu_load_from_file.triggered.connect(
            self._load_schedule_from_pyfile
        )
        self.menu_close_schedule.triggered.connect(self.close_schedule)
        self.menu_save.triggered.connect(self.save)
        self.menu_save_as.triggered.connect(self.save_as)
        self.menu_quit.triggered.connect(self.close)
        self.menu_node_info.triggered.connect(self.show_info_table)
        self.menu_exit_dialog.triggered.connect(self.hide_exit_dialog)
        self.actionT.triggered.connect(self._actionTbtn)
        self.splitter.splitterMoved.connect(self._splitter_moved)

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
        self._scene.addRect(
            0, 0, 0, 0
        )  # dummy rect to be able to setPos() graph
        self.view.setScene(self._scene)
        self.view.scale(self._scale, self._scale)
        GraphicsComponentItem._scale = self._scale
        GraphicsAxesItem._scale = self._scale
        self._scene.sceneRectChanged.connect(self.shrink_scene_to_min_size)

    @property
    def schedule(self) -> Schedule:
        """Get the current schedule."""
        return self._schedule

    ###############
    #### Slots ####
    ###############
    @Slot()
    def _actionTbtn(self) -> None:
        # TODO: remove
        self.schedule.plot_schedule()
        print(f"filtersChildEvents(): {self._graph.filtersChildEvents()}")
        # self._printButtonPressed('callback_pushButton()')

    @Slot()
    def _load_schedule_from_pyfile(self) -> None:
        """SLOT() for SIGNAL(menu_load_from_file.triggered)
        Load a python script as a module and search for a Schedule object. If
        found, opens it."""
        settings = QSettings()
        last_file = settings.value(
            "mainwindow/last_opened_file",
            QStandardPaths.standardLocations(QStandardPaths.HomeLocation)[0],
            str,
        )
        if not os.path.exists(last_file):  # if filename does not exist
            last_file = os.path.dirname(last_file) + "/"
            if not os.path.exists(last_file):  # if path does not exist
                last_file = QStandardPaths.standardLocations(
                    QStandardPaths.HomeLocation
                )[0]

        abs_path_filename, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open python file"),
            last_file,
            self.tr("Python Files (*.py *.py3)"),
        )

        if (
            not abs_path_filename
        ):  # return if empty filename (QFileDialog was canceled)
            return
        log.debug("abs_path_filename = {}.".format(abs_path_filename))

        module_name = inspect.getmodulename(abs_path_filename)
        if not module_name:  # return if empty module name
            log.error(
                "Could not load module from file '{}'.".format(
                    abs_path_filename
                )
            )
            return

        try:
            module = SourceFileLoader(
                module_name, abs_path_filename
            ).load_module()
        except:
            log.exception(
                "Exception occurred. Could not load module from file '{}'."
                .format(abs_path_filename)
            )
            return

        schedule_obj_list = dict(
            inspect.getmembers(module, (lambda x: isinstance(x, Schedule)))
        )

        if not schedule_obj_list:  # return if no Schedule objects in script
            QMessageBox.warning(
                self,
                self.tr("File not found"),
                self.tr(
                    "Could not find any Schedule object in file '{}'."
                ).format(os.path.basename(abs_path_filename)),
            )
            log.info(
                "Could not find any Schedule object in file '{}'.".format(
                    os.path.basename(abs_path_filename)
                )
            )
            del module
            return

        ret_tuple = QInputDialog.getItem(
            self,
            self.tr("Load object"),
            self.tr(
                "Found the following Schedule object(s) in file.\n\n"
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

        self.open(schedule_obj_list[ret_tuple[0]])
        del module
        settings.setValue("mainwindow/last_opened_file", abs_path_filename)

    @Slot()
    def close_schedule(self) -> None:
        """SLOT() for SIGNAL(menu_close_schedule.triggered)
        Closes current schedule."""
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
            del self._graph
            self._graph = None
            del self._schedule
            self._schedule = None
            self.info_table_clear()

    @Slot()
    def save(self) -> None:
        """SLOT() for SIGNAL(menu_save.triggered)
        This method save an schedule."""
        # TODO: all
        self._printButtonPressed("save_schedule()")
        self.update_statusbar(self.tr("Schedule saved successfully"))

    @Slot()
    def save_as(self) -> None:
        """SLOT() for SIGNAL(menu_save_as.triggered)
        This method save as an schedule."""
        # TODO: all
        self._printButtonPressed("save_schedule()")
        self.update_statusbar(self.tr("Schedule saved successfully"))

    @Slot(bool)
    def show_info_table(self, checked: bool) -> None:
        """SLOT(bool) for SIGNAL(menu_node_info.triggered)
        Takes in a boolean and hide or show the info table accordingly with
        'checked'."""
        # Note: splitter handler index 0 is a hidden splitter handle far most left, use index 1
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
        """SLOT(bool) for SIGNAL(menu_exit_dialog.triggered)
        Takes in a boolean and stores 'checked' in 'hide_exit_dialog' item in
        settings."""
        s = QSettings()
        s.setValue("mainwindow/hide_exit_dialog", checked)

    @Slot(int, int)
    def _splitter_moved(self, pos: int, index: int) -> None:
        """SLOT(int, int) for SIGNAL(splitter.splitterMoved)
        Callback method used to check if the right widget (info window)
        has collapsed. Update the checkbutton accordingly."""
        width = self.splitter.sizes()[1]

        if width == 0:
            if self.menu_node_info.isChecked() is True:
                self.menu_node_info.setChecked(False)
        else:
            if self.menu_node_info.isChecked() is False:
                self.menu_node_info.setChecked(True)
            self._splitter_pos = width

    @Slot(str)
    def info_table_update_component(self, op_id: str) -> None:
        """SLOT(str) for SIGNAL(_graph._signals.component_selected)
        Taked in an operator-id, first clears the 'Operator' part of the info
        table and then fill in the table with new values from the operator
        associated with 'op_id'."""
        self.info_table_clear_component()
        self._info_table_fill_component(op_id)

    @Slot()
    def info_table_update_schedule(self) -> None:
        """SLOT() for SIGNAL(_graph._signals.schedule_time_changed)
        Updates the 'Schedule' part of the info table."""
        self.info_table.item(1, 1).setText(str(self.schedule.schedule_time))

    @Slot(QRectF)
    def shrink_scene_to_min_size(self, rect: QRectF) -> None:
        """SLOT(QRectF) for SIGNAL(_scene.sceneRectChanged)
        Takes in a QRectF (unused) and shrink the scene bounding rectangle to
        it's minimum size, when the bounding rectangle signals a change in
        geometry."""
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    ################
    #### Events ####
    ################
    def _close_event(self, event: QCloseEvent) -> None:
        """EVENT: Replaces QMainWindow default closeEvent(QCloseEvent) event. Takes
        in a QCloseEvent and display an exit dialog, depending on
        'hide_exit_dialog' in settings."""
        s = QSettings()
        hide_dialog = s.value("mainwindow/hide_exit_dialog", False, bool)
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
            checkbox = QCheckBox(self.tr("Don't ask again"))
            box.setCheckBox(checkbox)
            ret = box.exec_()

        if ret == QMessageBox.StandardButton.Yes:
            if not hide_dialog:
                s.setValue("mainwindow/hide_exit_dialog", checkbox.isChecked())
            self._write_settings()
            log.info("Exit: {}".format(os.path.basename(__file__)))
            event.accept()
        else:
            event.ignore()

    #################################
    #### Helper member functions ####
    #################################
    def _printButtonPressed(self, func_name: str) -> None:
        # TODO: remove

        alert = QMessageBox(self)
        alert.setText("Called from " + func_name + "!")
        alert.exec_()

    def open(self, schedule: Schedule) -> None:
        """Takes in an Schedule and creates a GraphicsGraphItem object."""
        self.close_schedule()
        self._schedule = deepcopy(schedule)
        self._graph = GraphicsGraphItem(self.schedule)
        self._graph.setPos(1 / self._scale, 1 / self._scale)
        self.menu_close_schedule.setEnabled(True)
        self._scene.addItem(self._graph)
        self._graph.installSceneEventFilters(self._graph.event_items)
        self._graph._signals.component_selected.connect(
            self.info_table_update_component
        )
        self._graph._signals.schedule_time_changed.connect(
            self.info_table_update_schedule
        )
        self.info_table_fill_schedule(self.schedule)
        self.update_statusbar(self.tr("Schedule loaded successfully"))

    def update_statusbar(self, msg: str) -> None:
        """Takes in an str and write 'msg' to the statusbar with temporarily policy."""
        self.statusbar.showMessage(msg)

    def _write_settings(self) -> None:
        """Write settings from MainWindow to Settings."""
        s = QSettings()
        s.setValue(
            "mainwindow/maximized", self.isMaximized()
        )  # window: maximized, in X11 - alwas False
        s.setValue("mainwindow/pos", self.pos())  # window: pos
        s.setValue("mainwindow/size", self.size())  # window: size
        s.setValue(
            "mainwindow/state", self.saveState()
        )  # toolbars, dockwidgets: pos, size
        s.setValue(
            "mainwindow/menu/node_info", self.menu_node_info.isChecked()
        )
        s.setValue("mainwindow/splitter/state", self.splitter.saveState())
        s.setValue("mainwindow/splitter/pos", self.splitter.sizes()[1])

        if s.isWritable():
            log.debug("Settings written to '{}'.".format(s.fileName()))
        else:
            log.warning("Settings cant be saved to file, read-only.")

    def _read_settings(self) -> None:
        """Read settings from Settings to MainWindow."""
        s = QSettings()
        if s.value("mainwindow/maximized", defaultValue=False, type=bool):
            self.showMaximized()
        else:
            self.move(s.value("mainwindow/pos", self.pos()))
            self.resize(s.value("mainwindow/size", self.size()))
        self.restoreState(s.value("mainwindow/state", QByteArray()))
        self.menu_node_info.setChecked(
            s.value("mainwindow/menu/node_info", True, bool)
        )
        self.splitter.restoreState(
            s.value("mainwindow/splitter/state", QByteArray())
        )
        self._splitter_pos = s.value("mainwindow/splitter/pos", 200, int)
        self.menu_exit_dialog.setChecked(
            s.value("mainwindow/hide_exit_dialog", False, bool)
        )

        log.debug("Settings read from '{}'.".format(s.fileName()))

    def info_table_fill_schedule(self, schedule: Schedule) -> None:
        """Takes in a Schedule and fill in the 'Schedule' part of the info table
        with values from 'schedule'"""
        self.info_table.insertRow(1)
        self.info_table.insertRow(1)
        self.info_table.insertRow(1)
        self.info_table.setItem(1, 0, QTableWidgetItem("Schedule Time"))
        self.info_table.setItem(2, 0, QTableWidgetItem("Cyclic"))
        self.info_table.setItem(3, 0, QTableWidgetItem("Resolution"))
        self.info_table.setItem(
            1, 1, QTableWidgetItem(str(schedule.schedule_time))
        )
        self.info_table.setItem(2, 1, QTableWidgetItem(str(schedule.cyclic)))
        self.info_table.setItem(
            3, 1, QTableWidgetItem(str(schedule.resolution))
        )

    def _info_table_fill_component(self, op_id: str) -> None:
        """Taked in an operator-id and fill in the 'Operator' part of the info
        table with values from the operator associated with 'op_id'."""
        op: GraphComponent = self.schedule.sfg.find_by_id(op_id)
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

    def info_table_clear(self) -> None:
        """Clears the info table."""
        self.info_table_clear_component()
        self.info_table_clear_schedule()

    def info_table_clear_schedule(self) -> None:
        """Clears the schedule part of the info table."""
        row = self.info_table.findItems("Operator", Qt.MatchExactly)
        if row:
            row = row[0].row()
            if row > 2:
                for _ in range(3):
                    self.info_table.removeRow(1)
        else:
            log.error(
                "'Operator' not found in info table. It may have been renamed."
            )

    def exit_app(self):
        """Exit application."""
        log.info("Exiting the application.")
        QApplication.quit()

    def info_table_clear_component(self) -> None:
        """Clears the component part of the info table."""
        row = self.info_table.findItems("Operator", Qt.MatchExactly)
        if row:
            row = row[0].row()
            for _ in range(self.info_table.rowCount() - row + 1):
                self.info_table.removeRow(row + 1)
        else:
            log.error(
                "'Operator' not found in info table. It may have been renamed."
            )


def start_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start_gui()
