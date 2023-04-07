"""B-ASIC Main Window Module.

This file opens the main window of the GUI for B-ASIC when run.
"""


import importlib
import logging
import os
import sys
from collections import deque
from pprint import pprint
from typing import Dict, List, Optional, Tuple, cast

from qtpy.QtCore import QCoreApplication, QFileInfo, QSettings, QSize, Qt, QThread
from qtpy.QtGui import QCursor, QIcon, QKeySequence, QPainter
from qtpy.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QInputDialog,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QShortcut,
)

import b_asic.core_operations
import b_asic.special_operations
from b_asic._version import __version__
from b_asic.GUI._preferences import GAP, GRID, MINBUTTONSIZE, PORTHEIGHT
from b_asic.GUI.arrow import Arrow
from b_asic.GUI.drag_button import DragButton
from b_asic.GUI.gui_interface import Ui_main_window
from b_asic.GUI.port_button import PortButton
from b_asic.GUI.select_sfg_window import SelectSFGWindow
from b_asic.GUI.show_pc_window import ShowPCWindow
from b_asic.GUI.simulate_sfg_window import SimulateSFGWindow
from b_asic.GUI.simulation_worker import SimulationWorker
from b_asic.GUI.util_dialogs import FaqWindow, KeybindingsWindow
from b_asic.gui_utils.about_window import AboutWindow
from b_asic.gui_utils.decorators import decorate_class, handle_error
from b_asic.gui_utils.plot_window import PlotWindow
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.save_load_structure import python_to_sfg, sfg_to_python
from b_asic.signal import Signal
from b_asic.signal_flow_graph import SFG
from b_asic.simulation import Simulation
from b_asic.special_operations import Input, Output

logging.basicConfig(level=logging.INFO)

QCoreApplication.setOrganizationName("Linköping University")
QCoreApplication.setOrganizationDomain("liu.se")
QCoreApplication.setApplicationName("B-ASIC SFG GUI")
QCoreApplication.setApplicationVersion(__version__)


@decorate_class(handle_error)
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_main_window()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon("small_logo.png"))
        self.scene = QGraphicsScene(self)
        self._operations_from_name = {}
        self.zoom = 1
        self.sfg_name_i = 0
        self.dragOperationSceneDict = {}
        self._operation_drag_buttons: Dict[Operation, DragButton] = {}
        self._arrow_list: List[Arrow] = []
        self.mouse_pressed = False
        self.mouse_dragging = False
        self.starting_port = []
        self.pressed_operations = []
        self.portDict = {}
        self.signalPortDict = {}
        self._operation_to_sfg: Dict[DragButton, SFG] = {}
        self.pressed_ports = []
        self.sfg_dict = {}
        self._window = self
        self.logger = logging.getLogger(__name__)
        self._plot: Dict[Simulation, PlotWindow] = dict()

        # Create Graphics View
        self.graphic_view = QGraphicsView(self.scene, self)
        self.graphic_view.setRenderHint(QPainter.Antialiasing)
        self.graphic_view.setGeometry(
            self.ui.operation_box.width(), 20, self.width(), self.height()
        )
        self.graphic_view.setDragMode(QGraphicsView.RubberBandDrag)

        # Create toolbar
        self.toolbar = self.addToolBar("Toolbar")
        self.toolbar.addAction("Create SFG", self.create_sfg_from_toolbar)
        self.toolbar.addAction("Clear workspace", self.clear_workspace)

        # Add operations
        self.maxFileNr = 4
        self.recentFilesList = []
        self.recentFilePaths = deque(maxlen=self.maxFileNr)

        self.add_operations_from_namespace(
            b_asic.core_operations, self.ui.core_operations_list
        )
        self.add_operations_from_namespace(
            b_asic.special_operations, self.ui.special_operations_list
        )

        self.shortcut_core = QShortcut(QKeySequence("Ctrl+R"), self.ui.operation_box)
        self.shortcut_core.activated.connect(
            self._refresh_operations_list_from_namespace
        )
        self.scene.selectionChanged.connect(self._select_operations)

        self.move_button_index = 0
        self.is_show_names = True

        self.check_show_names = QAction("Show operation names")
        self.check_show_names.triggered.connect(self.view_operation_names)
        self.check_show_names.setCheckable(True)
        self.check_show_names.setChecked(1)
        self.ui.view_menu.addAction(self.check_show_names)

        self.ui.actionShowPC.triggered.connect(self._show_precedence_graph)
        self.ui.actionSimulateSFG.triggered.connect(self.simulate_sfg)
        self.ui.faqBASIC.triggered.connect(self.display_faq_page)
        self.ui.aboutBASIC.triggered.connect(self.display_about_page)
        self.ui.keybindsBASIC.triggered.connect(self.display_keybindings_page)
        self.ui.core_operations_list.itemClicked.connect(
            self.on_list_widget_item_clicked
        )
        self.ui.special_operations_list.itemClicked.connect(
            self.on_list_widget_item_clicked
        )
        self.ui.custom_operations_list.itemClicked.connect(
            self.on_list_widget_item_clicked
        )
        self.ui.save_menu.triggered.connect(self.save_work)
        self.ui.load_menu.triggered.connect(self.load_work)
        self.ui.load_operations.triggered.connect(self.add_namespace)
        self.ui.exit_menu.triggered.connect(self.exit_app)
        self.shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open.activated.connect(self.load_work)
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.save_work)
        self.shortcut_help = QShortcut(QKeySequence("Ctrl+?"), self)
        self.shortcut_help.activated.connect(self.display_faq_page)
        self.shortcut_signal = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_signal.activated.connect(self._connect_callback)
        self.createActionsAndMenus()

        self._keybindings_page = None
        self._about_page = None
        self._faq_page = None

        self.logger.info("Finished setting up GUI")
        self.logger.info(
            "For questions please refer to 'Ctrl+?', or visit the 'Help' "
            "section on the toolbar."
        )

        self.cursor = QCursor()

    def resizeEvent(self, event) -> None:
        ui_width = self.ui.operation_box.width()
        self.ui.operation_box.setGeometry(10, 10, ui_width, self.height())
        self.graphic_view.setGeometry(
            ui_width + 20,
            60,
            self.width() - ui_width - 20,
            self.height() - 30,
        )
        super().resizeEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            old_zoom = self.zoom
            self.zoom += event.angleDelta().y() / 2500
            self.graphic_view.scale(self.zoom, self.zoom)
            self.zoom = old_zoom

    def view_operation_names(self) -> None:
        if self.check_show_names.isChecked():
            self.is_show_names = True
        else:
            self.is_show_names = False

        for operation in self.dragOperationSceneDict:
            operation.label.setOpacity(self.is_show_names)
            operation.is_show_name = self.is_show_names

    def _save_work(self) -> None:
        sfg = cast(SFG, self.sfg_widget.sfg)
        file_dialog = QFileDialog()
        file_dialog.setDefaultSuffix(".py")
        module, accepted = file_dialog.getSaveFileName()
        if not accepted:
            return

        self.logger.info("Saving SFG to path: " + str(module))
        operation_positions = {}
        for op_drag, op_scene in self.dragOperationSceneDict.items():
            operation_positions[op_drag.operation.graph_id] = (
                int(op_scene.x()),
                int(op_scene.y()),
                op_drag.is_flipped(),
            )

        try:
            with open(module, "w+") as file_obj:
                file_obj.write(
                    sfg_to_python(sfg, suffix=f"positions = {operation_positions}")
                )
        except Exception as e:
            self.logger.error(f"Failed to save SFG to path: {module}, with error: {e}.")
            return

        self.logger.info("Saved SFG to path: " + str(module))

    def save_work(self, event=None) -> None:
        self.sfg_widget = SelectSFGWindow(self)
        self.sfg_widget.show()

        # Wait for input to dialog.
        self.sfg_widget.ok.connect(self._save_work)

    def load_work(self, event=None) -> None:
        module, accepted = QFileDialog().getOpenFileName()
        if not accepted:
            return
        self._load_from_file(module)

    def _load_from_file(self, module) -> None:
        self.logger.info("Loading SFG from path: " + str(module))
        try:
            sfg, positions = python_to_sfg(module)
        except ImportError as e:
            self.logger.error(
                f"Failed to load module: {module} with the following error: {e}."
            )
            return

        self.addRecentFile(module)

        while sfg.name in self.sfg_dict:
            self.logger.warning(
                f"Duplicate SFG with name: {sfg.name} detected. "
                "Please choose a new name."
            )
            name, accepted = QInputDialog.getText(
                self, "Change SFG Name", "Name: ", QLineEdit.Normal
            )
            if not accepted:
                return

            sfg.name = name
        self._load_sfg(sfg, positions)
        self.logger.info("Loaded SFG from path: " + str(module))

    def _load_sfg(self, sfg, positions=None) -> None:
        if positions is None:
            positions = {}

        for op in sfg.split():
            self.create_operation(
                op,
                positions[op.graph_id][0:2] if op.graph_id in positions else None,
                positions[op.graph_id][-1] if op.graph_id in positions else None,
            )

        def connect_ports(ports):
            for port in ports:
                for signal in port.signals:
                    source = [
                        source
                        for source in self.portDict[
                            self._operation_drag_buttons[signal.source.operation]
                        ]
                        if source.port is signal.source
                    ]
                    destination = [
                        destination
                        for destination in self.portDict[
                            self._operation_drag_buttons[signal.destination.operation]
                        ]
                        if destination.port is signal.destination
                    ]

                    if source and destination:
                        self._connect_button(source[0], destination[0])

            for port in self.pressed_ports:
                port.select_port()

        for op in sfg.split():
            connect_ports(op.inputs)

        for op in sfg.split():
            self._operation_drag_buttons[op].setToolTip(sfg.name)
            self._operation_to_sfg[self._operation_drag_buttons[op]] = sfg

        self.sfg_dict[sfg.name] = sfg
        self.update()

    def createActionsAndMenus(self):
        for i in range(self.maxFileNr):
            recentFileAction = QAction(self.ui.recent_sfg)
            recentFileAction.setVisible(False)
            recentFileAction.triggered.connect(
                lambda b=0, x=recentFileAction: self.openRecent(x)
            )
            self.recentFilesList.append(recentFileAction)
            self.ui.recent_sfg.addAction(recentFileAction)

        self.updateRecentActionList()

    def updateRecentActionList(self):
        settings = QSettings()

        rfp = settings.value("SFG/recentFiles")

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

    def openRecent(self, action):
        self._load_from_file(action.data().filePath())

    def addRecentFile(self, module):
        settings = QSettings()

        rfp = settings.value("SFG/recentFiles")

        if rfp:
            if module not in rfp:
                rfp.append(module)
        else:
            rfp = deque(maxlen=self.maxFileNr)
            rfp.append(module)

        settings.setValue("SFG/recentFiles", rfp)

        self.updateRecentActionList()

    def exit_app(self) -> None:
        self.logger.info("Exiting the application.")
        QApplication.quit()

    def clear_workspace(self) -> None:
        self.logger.info("Clearing workspace from operations and SFGs.")
        self.pressed_operations.clear()
        self.pressed_ports.clear()
        self._operation_drag_buttons.clear()
        self.dragOperationSceneDict.clear()
        self._arrow_list.clear()
        self.portDict.clear()
        self.signalPortDict.clear()
        self.sfg_dict.clear()
        self.scene.clear()
        self.logger.info("Workspace cleared.")

    def create_sfg_from_toolbar(self) -> None:
        inputs = []
        outputs = []
        for op in self.pressed_operations:
            if isinstance(op.operation, Input):
                inputs.append(op.operation)
            elif isinstance(op.operation, Output):
                outputs.append(op.operation)

        name, accepted = QInputDialog.getText(
            self, "Create SFG", "Name: ", QLineEdit.Normal
        )
        if not accepted:
            return

        if not name:
            self.logger.warning("Failed to initialize SFG with empty name.")
            return

        self.logger.info("Creating SFG with name: %s from selected operations." % name)

        sfg = SFG(inputs=inputs, outputs=outputs, name=name)
        self.logger.info("Created SFG with name: %s from selected operations." % name)

        def check_equality(signal: Signal, signal_2: Signal) -> bool:
            source = cast(OutputPort, signal.source)
            source2 = cast(OutputPort, signal_2.source)
            dest = cast(InputPort, signal.destination)
            dest2 = cast(InputPort, signal_2.destination)
            if not (
                source.operation.type_name() == source2.operation.type_name()
                and dest.operation.type_name() == dest2.operation.type_name()
            ):
                return False

            if (
                hasattr(source.operation, "value")
                and hasattr(source2.operation, "value")
                and hasattr(dest.operation, "value")
                and hasattr(dest2.operation, "value")
            ):
                if not (
                    source.operation.value == source2.operation.value
                    and dest.operation.value == dest2.operation.value
                ):
                    return False

            if (
                hasattr(source.operation, "name")
                and hasattr(source2.operation, "name")
                and hasattr(dest.operation, "name")
                and hasattr(dest2.operation, "name")
            ):
                if not (
                    source.operation.name == source2.operation.name
                    and dest.operation.name == dest2.operation.name
                ):
                    return False

            try:
                _signal_source_index = [
                    source.operation.outputs.index(port)
                    for port in source.operation.outputs
                    if signal in port.signals
                ]
                _signal_2_source_index = [
                    source2.operation.outputs.index(port)
                    for port in source2.operation.outputs
                    if signal_2 in port.signals
                ]
            except ValueError:
                return False  # Signal output connections not matching

            try:
                _signal_destination_index = [
                    dest.operation.inputs.index(port)
                    for port in dest.operation.inputs
                    if signal in port.signals
                ]
                _signal_2_destination_index = [
                    dest2.operation.inputs.index(port)
                    for port in dest2.operation.inputs
                    if signal_2 in port.signals
                ]
            except ValueError:
                return False  # Signal input connections not matching

            return (
                _signal_source_index == _signal_2_source_index
                and _signal_destination_index == _signal_2_destination_index
            )

        for _pressed_op in self.pressed_operations:
            for operation in sfg.operations:
                for input_ in operation.inputs:
                    for signal in input_.signals:
                        for line in self.signalPortDict:
                            if check_equality(line.signal, signal):
                                line.source.operation.operation = (
                                    signal.source.operation
                                )
                                line.destination.operation.operation = (
                                    signal.destination.operation
                                )

                for output_ in operation.outputs:
                    for signal in output_.signals:
                        for line in self.signalPortDict:
                            if check_equality(line.signal, signal):
                                line.source.operation.operation = (
                                    signal.source.operation
                                )
                                line.destination.operation.operation = (
                                    signal.destination.operation
                                )

        for op in self.pressed_operations:
            op.setToolTip(sfg.name)
            self._operation_to_sfg[op] = sfg

        self.sfg_dict[sfg.name] = sfg

    def _show_precedence_graph(self, event=None) -> None:
        self._precedence_graph_dialog = ShowPCWindow(self)
        self._precedence_graph_dialog.add_sfg_to_dialog()
        self._precedence_graph_dialog.show()

    def get_operations_from_namespace(self, namespace) -> List[str]:
        self.logger.info(
            "Fetching operations from namespace: " + str(namespace.__name__)
        )
        return [
            comp
            for comp in dir(namespace)
            if hasattr(getattr(namespace, comp), "type_name")
        ]

    def add_operations_from_namespace(self, namespace, _list) -> None:
        for attr_name in self.get_operations_from_namespace(namespace):
            attr = getattr(namespace, attr_name)
            try:
                attr.type_name()
                item = QListWidgetItem(attr_name)
                _list.addItem(item)
                self._operations_from_name[attr_name] = attr
            except NotImplementedError:
                pass

        self.logger.info("Added operations from namespace: " + str(namespace.__name__))

    def add_namespace(self, event=None) -> None:
        module, accepted = QFileDialog().getOpenFileName()
        if not accepted:
            return

        spec = importlib.util.spec_from_file_location(
            f"{QFileInfo(module).fileName()}", module
        )
        namespace = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(namespace)

        self.add_operations_from_namespace(namespace, self.ui.custom_operations_list)

    def create_operation(
        self,
        op: Operation,
        position: Optional[Tuple[float, float]] = None,
        is_flipped: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        op : Operation
        position : (float, float), optional
        is_flipped : bool, default: False
        """
        try:
            if op in self._operation_drag_buttons:
                self.logger.warning("Multiple instances of operation with same name")
                return

            attr_button = DragButton(op, True, window=self)
            if position is None:
                attr_button.move(GRID * 3, GRID * 2)
            else:
                attr_button.move(*position)

            max_ports = max(op.input_count, op.output_count)
            button_height = max(
                MINBUTTONSIZE, max_ports * PORTHEIGHT + (max_ports - 1) * GAP
            )

            attr_button.setFixedSize(MINBUTTONSIZE, button_height)
            attr_button.setStyleSheet(
                "background-color: white; border-style: solid;"
                "border-color: black; border-width: 2px"
            )
            attr_button.add_ports()
            self.portDict[attr_button] = attr_button.ports

            icon_path = os.path.join(
                os.path.dirname(__file__),
                "operation_icons",
                f"{op.type_name().lower()}.png",
            )
            if not os.path.exists(icon_path):
                icon_path = os.path.join(
                    os.path.dirname(__file__),
                    "operation_icons",
                    "custom_operation.png",
                )
            attr_button.setIcon(QIcon(icon_path))
            attr_button.setIconSize(QSize(MINBUTTONSIZE, MINBUTTONSIZE))
            attr_button.setToolTip("No SFG")
            attr_button.setStyleSheet(
                "QToolTip { background-color: white; color: black }"
            )
            attr_button.setParent(None)
            attr_button_scene = self.scene.addWidget(attr_button)
            if position is None:
                attr_button_scene.moveBy(
                    int(self.scene.width() / 4), int(self.scene.height() / 4)
                )
            attr_button_scene.setFlag(QGraphicsItem.ItemIsSelectable, True)
            operation_label = QGraphicsTextItem(op.name, attr_button_scene)
            if not self.is_show_names:
                operation_label.setOpacity(0)
            operation_label.setTransformOriginPoint(
                operation_label.boundingRect().center()
            )
            operation_label.moveBy(10, -20)
            attr_button.add_label(operation_label)

            if isinstance(is_flipped, bool):
                if is_flipped:
                    attr_button._flip()

            self._operation_drag_buttons[op] = attr_button
            self.dragOperationSceneDict[attr_button] = attr_button_scene

        except Exception as e:
            self.logger.error(
                "Unexpected error occurred while creating operation: " + str(e)
            )

    def _create_operation_item(self, item) -> None:
        self.logger.info("Creating operation of type: %s" % str(item.text()))
        try:
            attr_operation = self._operations_from_name[item.text()]()
            self.create_operation(attr_operation)
        except Exception as e:
            self.logger.error(
                "Unexpected error occurred while creating operation: " + str(e)
            )

    def _refresh_operations_list_from_namespace(self) -> None:
        self.logger.info("Refreshing operation list.")
        self.ui.core_operations_list.clear()
        self.ui.special_operations_list.clear()

        self.add_operations_from_namespace(
            b_asic.core_operations, self.ui.core_operations_list
        )
        self.add_operations_from_namespace(
            b_asic.special_operations, self.ui.special_operations_list
        )
        self.logger.info("Finished refreshing operation list.")

    def on_list_widget_item_clicked(self, item) -> None:
        self._create_operation_item(item)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            for pressed_op in self.pressed_operations:
                pressed_op.remove()
                self.move_button_index -= 1
            self.pressed_operations.clear()
        super().keyPressEvent(event)

    def _connect_callback(self, *event) -> None:
        if len(self.pressed_ports) < 2:
            self.logger.warning(
                "Cannot connect less than two ports. Please select at least two."
            )
            return

        pressed_op_inports = [
            pressed
            for pressed in self.pressed_ports
            if isinstance(pressed.port, InputPort)
        ]
        pressed_op_outports = [
            pressed
            for pressed in self.pressed_ports
            if isinstance(pressed.port, OutputPort)
        ]

        if len(pressed_op_outports) != 1:
            raise ValueError("Exactly one output port must be selected!")

        pressed_op_outport = pressed_op_outports[0]
        for pressed_op_inport in pressed_op_inports:
            self._connect_button(pressed_op_outport, pressed_op_inport)

        for port in self.pressed_ports:
            port.select_port()

    def _connect_button(self, source: PortButton, destination: PortButton) -> None:
        """
        Connect two PortButtons with an Arrow.

        Parameters
        ----------
        source : PortButton
            The PortButton to start the signal at.
        destination : PortButton
            The PortButton to end the signal at.

        Returns
        -------
        None.

        """
        signal_exists = (
            signal
            for signal in source.port.signals
            if signal.destination is destination.port
        )
        self.logger.info(
            "Connecting: %s -> %s."
            % (
                source.operation.operation.type_name(),
                destination.operation.operation.type_name(),
            )
        )
        try:
            arrow = Arrow(source, destination, self, signal=next(signal_exists))
        except StopIteration:
            arrow = Arrow(source, destination, self)

        if arrow not in self.signalPortDict:
            self.signalPortDict[arrow] = []

        self.signalPortDict[arrow].append((source, destination))
        self.scene.addItem(arrow)
        self._arrow_list.append(arrow)

        self.update()

    def paintEvent(self, event) -> None:
        for signal in self.signalPortDict.keys():
            signal.moveLine()

    def _select_operations(self) -> None:
        selected = [button.widget() for button in self.scene.selectedItems()]
        for button in selected:
            button._toggle_button(pressed=False)

        for button in self.pressed_operations:
            if button not in selected:
                button._toggle_button(pressed=True)

        self.pressed_operations = selected

    def _simulate_sfg(self) -> None:
        self._thread = dict()
        self._sim_worker = dict()
        for sfg, properties in self._simulation_dialog.properties.items():
            self.logger.info("Simulating SFG with name: %s" % str(sfg.name))
            self._sim_worker[sfg] = SimulationWorker(sfg, properties)
            self._thread[sfg] = QThread()
            self._sim_worker[sfg].moveToThread(self._thread[sfg])
            self._thread[sfg].started.connect(self._sim_worker[sfg].start_simulation)
            self._sim_worker[sfg].finished.connect(self._thread[sfg].quit)
            self._sim_worker[sfg].finished.connect(self._show_plot_window)
            self._sim_worker[sfg].finished.connect(self._sim_worker[sfg].deleteLater)
            self._thread[sfg].finished.connect(self._thread[sfg].deleteLater)
            self._thread[sfg].start()

    def _show_plot_window(self, sim: Simulation):
        self._plot[sim] = PlotWindow(sim.results, sfg_name=sim._sfg.name)
        self._plot[sim].show()

    def simulate_sfg(self, event=None) -> None:
        self._simulation_dialog = SimulateSFGWindow(self)

        for _, sfg in self.sfg_dict.items():
            self._simulation_dialog.add_sfg_to_dialog(sfg)

        self._simulation_dialog.show()

        # Wait for input to dialog.
        # Kinda buggy because of the separate window in the same thread.
        self._simulation_dialog.simulate.connect(self._simulate_sfg)

    def display_faq_page(self, event=None) -> None:
        if self._faq_page is None:
            self._faq_page = FaqWindow(self)
        self._faq_page.scroll_area.show()

    def display_about_page(self, event=None) -> None:
        if self._about_page is None:
            self._about_page = AboutWindow(self)
        self._about_page.show()

    def display_keybindings_page(self, event=None) -> None:
        if self._keybindings_page is None:
            self._keybindings_page = KeybindingsWindow(self)
        self._keybindings_page.show()


def start_editor(sfg: Optional[SFG] = None):
    app = QApplication(sys.argv)
    window = MainWindow()
    if sfg:
        window._load_sfg(sfg)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start_editor()
