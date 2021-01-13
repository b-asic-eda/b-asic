"""B-ASIC Main Window Module.

This file opens the main window of the GUI for B-ASIC when run.
"""


from pprint import pprint
from os import getcwd, path
import importlib
import logging
import sys

from b_asic.GUI.about_window import AboutWindow, FaqWindow, KeybindsWindow
from b_asic.GUI.drag_button import DragButton
from b_asic.GUI.gui_interface import Ui_main_window
from b_asic.GUI.arrow import Arrow
from b_asic.GUI.port_button import PortButton
from b_asic.GUI.show_pc_window import ShowPCWindow
from b_asic.GUI.utils import decorate_class, handle_error
from b_asic.GUI.simulate_sfg_window import SimulateSFGWindow, Plot
from b_asic.GUI.select_sfg_window import SelectSFGWindow

from b_asic import FastSimulation
from b_asic.simulation import Simulation
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Input, Output
import b_asic.core_operations as c_oper
import b_asic.special_operations as s_oper
from b_asic.save_load_structure import *

from numpy import linspace

from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QAction,\
    QStatusBar, QMenuBar, QLineEdit, QPushButton, QSlider, QScrollArea, QVBoxLayout,\
    QHBoxLayout, QDockWidget, QToolBar, QMenu, QLayout, QSizePolicy, QListWidget,\
    QListWidgetItem, QGraphicsView, QGraphicsScene, QShortcut, QGraphicsTextItem,\
    QGraphicsProxyWidget, QInputDialog, QTextEdit, QFileDialog
from qtpy.QtCore import Qt, QSize, QFileInfo
from qtpy.QtGui import QIcon, QFont, QPainter, QPen, QBrush, QKeySequence


MIN_WIDTH_SCENE = 600
MIN_HEIGHT_SCENE = 520
logging.basicConfig(level=logging.INFO)


@decorate_class(handle_error)
class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_main_window()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon('small_logo.png'))
        self.scene = None
        self._operations_from_name = dict()
        self.zoom = 1
        self.sfg_name_i = 0
        self.dragOperationSceneDict = dict()
        self.operationDragDict = dict()
        self.operationItemSceneList = []
        self.signalList = []
        self.pressed_operations = []
        self.portDict = dict()
        self.signalPortDict = dict()
        self.opToSFG = dict()
        self.pressed_ports = []
        self.sfg_dict = dict()
        self._window = self
        self.logger = logging.getLogger(__name__)
        self.init_ui()
        self.add_operations_from_namespace(
            c_oper, self.ui.core_operations_list)
        self.add_operations_from_namespace(
            s_oper, self.ui.special_operations_list)

        self.shortcut_core = QShortcut(
            QKeySequence("Ctrl+R"), self.ui.operation_box)
        self.shortcut_core.activated.connect(
            self._refresh_operations_list_from_namespace)
        self.scene.selectionChanged.connect(self._select_operations)

        self.move_button_index = 0
        self.is_show_names = True

        self.check_show_names = QAction("Show operation names")
        self.check_show_names.triggered.connect(self.view_operation_names)
        self.check_show_names.setCheckable(True)
        self.check_show_names.setChecked(1)
        self.ui.view_menu.addAction(self.check_show_names)

        self.ui.actionShowPC.triggered.connect(self.show_precedence_chart)
        self.ui.actionSimulateSFG.triggered.connect(self.simulate_sfg)
        self.ui.faqBASIC.triggered.connect(self.display_faq_page)
        self.ui.aboutBASIC.triggered.connect(self.display_about_page)
        self.ui.keybindsBASIC.triggered.connect(self.display_keybinds_page)
        self.ui.core_operations_list.itemClicked.connect(
            self.on_list_widget_item_clicked)
        self.ui.special_operations_list.itemClicked.connect(
            self.on_list_widget_item_clicked)
        self.ui.custom_operations_list.itemClicked.connect(
            self.on_list_widget_item_clicked)
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
        self.shortcut_signal.activated.connect(self._connect_button)

        self.logger.info("Finished setting up GUI")
        self.logger.info(
            "For questions please refer to 'Ctrl+?', or visit the 'Help' section on the toolbar.")

    def init_ui(self):
        self.create_toolbar_view()
        self.create_graphics_view()

    def create_graphics_view(self):
        self.scene = QGraphicsScene(self)
        self.graphic_view = QGraphicsView(self.scene, self)
        self.graphic_view.setRenderHint(QPainter.Antialiasing)
        self.graphic_view.setGeometry(
            self.ui.operation_box.width(), 20, self.width(), self.height())
        self.graphic_view.setDragMode(QGraphicsView.RubberBandDrag)

    def create_toolbar_view(self):
        self.toolbar = self.addToolBar("Toolbar")
        self.toolbar.addAction("Create SFG", self.create_SFG_from_toolbar)
        self.toolbar.addAction("Clear workspace", self.clear_workspace)

    def resizeEvent(self, event):
        self.ui.operation_box.setGeometry(
            10, 10, self.ui.operation_box.width(), self.height())
        self.graphic_view.setGeometry(self.ui.operation_box.width(
        ) + 20, 60, self.width() - self.ui.operation_box.width() - 20, self.height()-30)
        super(MainWindow, self).resizeEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            old_zoom = self.zoom
            self.zoom += event.angleDelta().y()/2500
            self.graphic_view.scale(self.zoom, self.zoom)
            self.zoom = old_zoom

    def view_operation_names(self):
        if self.check_show_names.isChecked():
            self.is_show_names = True
        else:
            self.is_show_names = False

        for operation in self.dragOperationSceneDict.keys():
            operation.label.setOpacity(self.is_show_names)
            operation.is_show_name = self.is_show_names

    def _save_work(self):
        sfg = self.sfg_widget.sfg
        file_dialog = QFileDialog()
        file_dialog.setDefaultSuffix(".py")
        module, accepted = file_dialog.getSaveFileName()
        if not accepted:
            return

        self.logger.info(f"Saving SFG to path: {module}.")
        operation_positions = dict()
        for operation_drag, operation_scene in self.dragOperationSceneDict.items():
            operation_positions[operation_drag.operation.graph_id] = (
                operation_scene.x(), operation_scene.y())

        try:
            with open(module, "w+") as file_obj:
                file_obj.write(sfg_to_python(
                    sfg, suffix=f"positions = {str(operation_positions)}"))
        except Exception as e:
            self.logger.error(
                f"Failed to save SFG to path: {module}, with error: {e}.")
            return

        self.logger.info(f"Saved SFG to path: {module}.")

    def save_work(self):
        self.sfg_widget = SelectSFGWindow(self)
        self.sfg_widget.show()

        # Wait for input to dialog.
        self.sfg_widget.ok.connect(self._save_work)

    def load_work(self):
        module, accepted = QFileDialog().getOpenFileName()
        if not accepted:
            return

        self.logger.info(f"Loading SFG from path: {module}.")
        try:
            sfg, positions = python_to_sfg(module)
        except ImportError as e:
            self.logger.error(
                f"Failed to load module: {module} with the following error: {e}.")
            return

        while sfg.name in self.sfg_dict:
            self.logger.warning(
                f"Duplicate SFG with name: {sfg.name} detected. Please choose a new name.")
            name, accepted = QInputDialog.getText(
                self, "Change SFG Name", "Name: ", QLineEdit.Normal)
            if not accepted:
                return

            sfg.name = name

        for op in sfg.split():
            self.create_operation(
                op, positions[op.graph_id] if op.graph_id in positions else None)

        def connect_ports(ports):
            for port in ports:
                for signal in port.signals:
                    source = [source for source in self.portDict[self.operationDragDict[signal.source.operation]]
                              if source.port is signal.source]
                    destination = [destination for destination in self.portDict[self.operationDragDict[
                        signal.destination.operation]] if destination.port is signal.destination]

                    if source and destination:
                        self.connect_button(source[0], destination[0])

            for port in self.pressed_ports:
                port.select_port()

        for op in sfg.split():
            connect_ports(op.inputs)

        for op in sfg.split():
            self.operationDragDict[op].setToolTip(sfg.name)
            self.opToSFG[self.operationDragDict[op]] = sfg

        self.sfg_dict[sfg.name] = sfg
        self.logger.info(f"Loaded SFG from path: {module}.")
        self.update()

    def exit_app(self):
        self.logger.info("Exiting the application.")
        QApplication.quit()

    def clear_workspace(self):
        self.logger.info("Clearing workspace from operations and SFGs.")
        self.pressed_operations.clear()
        self.pressed_ports.clear()
        self.operationItemSceneList.clear()
        self.operationDragDict.clear()
        self.dragOperationSceneDict.clear()
        self.signalList.clear()
        self.portDict.clear()
        self.signalPortDict.clear()
        self.sfg_dict.clear()
        self.scene.clear()
        self.logger.info("Workspace cleared.")

    def create_SFG_from_toolbar(self):
        inputs = []
        outputs = []
        for op in self.pressed_operations:
            if isinstance(op.operation, Input):
                inputs.append(op.operation)
            elif isinstance(op.operation, Output):
                outputs.append(op.operation)

        name, accepted = QInputDialog.getText(
            self, "Create SFG", "Name: ", QLineEdit.Normal)
        if not accepted:
            return

        if name == "":
            self.logger.warning(f"Failed to initialize SFG with empty name.")
            return

        self.logger.info(
            f"Creating SFG with name: {name} from selected operations.")

        sfg = SFG(inputs=inputs, outputs=outputs, name=name)
        self.logger.info(
            f"Created SFG with name: {name} from selected operations.")

        def check_equality(signal, signal_2):
            if not (signal.source.operation.type_name() == signal_2.source.operation.type_name()
                    and signal.destination.operation.type_name() == signal_2.destination.operation.type_name()):
                return False

            if hasattr(signal.source.operation, "value") and hasattr(signal_2.source.operation, "value") \
                    and hasattr(signal.destination.operation, "value") and hasattr(signal_2.destination.operation, "value"):
                if not (signal.source.operation.value == signal_2.source.operation.value
                        and signal.destination.operation.value == signal_2.destination.operation.value):
                    return False

            if hasattr(signal.source.operation, "name") and hasattr(signal_2.source.operation, "name") \
                    and hasattr(signal.destination.operation, "name") and hasattr(signal_2.destination.operation, "name"):
                if not (signal.source.operation.name == signal_2.source.operation.name
                        and signal.destination.operation.name == signal_2.destination.operation.name):
                    return False

            try:
                _signal_source_index = [signal.source.operation.outputs.index(
                    port) for port in signal.source.operation.outputs if signal in port.signals]
                _signal_2_source_index = [signal_2.source.operation.outputs.index(
                    port) for port in signal_2.source.operation.outputs if signal_2 in port.signals]
            except ValueError:
                return False  # Signal output connections not matching

            try:
                _signal_destination_index = [signal.destination.operation.inputs.index(
                    port) for port in signal.destination.operation.inputs if signal in port.signals]
                _signal_2_destination_index = [signal_2.destination.operation.inputs.index(
                    port) for port in signal_2.destination.operation.inputs if signal_2 in port.signals]
            except ValueError:
                return False  # Signal input connections not matching

            if not (_signal_source_index == _signal_2_source_index and _signal_destination_index == _signal_2_destination_index):
                return False

            return True

        for pressed_op in self.pressed_operations:
            for operation in sfg.operations:
                for input_ in operation.inputs:
                    for signal in input_.signals:
                        for line in self.signalPortDict:
                            if check_equality(line.signal, signal):
                                line.source.operation.operation = signal.source.operation
                                line.destination.operation.operation = signal.destination.operation

                for output_ in operation.outputs:
                    for signal in output_.signals:
                        for line in self.signalPortDict:
                            if check_equality(line.signal, signal):
                                line.source.operation.operation = signal.source.operation
                                line.destination.operation.operation = signal.destination.operation

        for op in self.pressed_operations:
            op.setToolTip(sfg.name)
            self.opToSFG[op] = sfg

        self.sfg_dict[sfg.name] = sfg

    def show_precedence_chart(self):
        self.dialog = ShowPCWindow(self)
        self.dialog.add_sfg_to_dialog()
        self.dialog.show()

    def _determine_port_distance(self, length, ports):
        """Determine the distance between each port on the side of an operation.
        The method returns the distance that each port should have from 0.
        """
        return [length / 2] if ports == 1 else linspace(0, length, ports)

    def add_ports(self, operation):
        _output_ports_dist = self._determine_port_distance(
            55 - 17, operation.operation.output_count)
        _input_ports_dist = self._determine_port_distance(
            55 - 17, operation.operation.input_count)
        self.portDict[operation] = list()

        for i, dist in enumerate(_input_ports_dist):
            port = PortButton(
                ">", operation, operation.operation.input(i), self)
            self.portDict[operation].append(port)
            operation.ports.append(port)
            port.move(0, dist)
            port.show()

        for i, dist in enumerate(_output_ports_dist):
            port = PortButton(
                ">", operation, operation.operation.output(i), self)
            self.portDict[operation].append(port)
            operation.ports.append(port)
            port.move(55 - 12, dist)
            port.show()

    def get_operations_from_namespace(self, namespace):
        self.logger.info(
            f"Fetching operations from namespace: {namespace.__name__}.")
        return [comp for comp in dir(namespace) if hasattr(getattr(namespace, comp), "type_name")]

    def add_operations_from_namespace(self, namespace, _list):
        for attr_name in self.get_operations_from_namespace(namespace):
            attr = getattr(namespace, attr_name)
            try:
                attr.type_name()
                item = QListWidgetItem(attr_name)
                _list.addItem(item)
                self._operations_from_name[attr_name] = attr
            except NotImplementedError:
                pass

        self.logger.info(
            f"Added operations from namespace: {namespace.__name__}.")

    def add_namespace(self):
        module, accepted = QFileDialog().getOpenFileName()
        if not accepted:
            return

        spec = importlib.util.spec_from_file_location(
            f"{QFileInfo(module).fileName()}", module)
        namespace = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(namespace)

        self.add_operations_from_namespace(
            namespace, self.ui.custom_operations_list)

    def create_operation(self, op, position=None):
        try:
            attr_button = DragButton(
                op.graph_id, op, op.type_name().lower(), True, window=self)
            if position is None:
                attr_button.move(250, 100)
            else:
                attr_button.move(*position)

            attr_button.setFixedSize(55, 55)
            attr_button.setStyleSheet("background-color: white; border-style: solid;\
            border-color: black; border-width: 2px")
            self.add_ports(attr_button)

            icon_path = path.join(path.dirname(
                __file__), "operation_icons", f"{op.type_name().lower()}.png")
            if not path.exists(icon_path):
                icon_path = path.join(path.dirname(
                    __file__), "operation_icons", f"custom_operation.png")
            attr_button.setIcon(QIcon(icon_path))
            attr_button.setIconSize(QSize(55, 55))
            attr_button.setToolTip("No SFG")
            attr_button.setStyleSheet(""" QToolTip { background-color: white;
            color: black }""")
            attr_button.setParent(None)
            attr_button_scene = self.scene.addWidget(attr_button)
            if position is None:
                attr_button_scene.moveBy(
                    int(self.scene.width() / 2), int(self.scene.height() / 2))
            attr_button_scene.setFlag(attr_button_scene.ItemIsSelectable, True)
            operation_label = QGraphicsTextItem(op.name, attr_button_scene)
            if not self.is_show_names:
                operation_label.setOpacity(0)
            operation_label.setTransformOriginPoint(
                operation_label.boundingRect().center())
            operation_label.moveBy(10, -20)
            attr_button.add_label(operation_label)
            self.operationDragDict[op] = attr_button
            self.dragOperationSceneDict[attr_button] = attr_button_scene
        except Exception as e:
            self.logger.error(
                f"Unexpected error occured while creating operation: {e}.")

    def _create_operation_item(self, item):
        self.logger.info(f"Creating operation of type: {item.text()}.")
        try:
            attr_oper = self._operations_from_name[item.text()]()
            self.create_operation(attr_oper)
        except Exception as e:
            self.logger.error(
                f"Unexpected error occured while creating operation: {e}.")

    def _refresh_operations_list_from_namespace(self):
        self.logger.info("Refreshing operation list.")
        self.ui.core_operations_list.clear()
        self.ui.special_operations_list.clear()

        self.add_operations_from_namespace(
            c_oper, self.ui.core_operations_list)
        self.add_operations_from_namespace(
            s_oper, self.ui.special_operations_list)
        self.logger.info("Finished refreshing operation list.")

    def on_list_widget_item_clicked(self, item):
        self._create_operation_item(item)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            for pressed_op in self.pressed_operations:
                pressed_op.remove()
                self.move_button_index -= 1
            self.pressed_operations.clear()
        super().keyPressEvent(event)

    def _connect_button(self, *event):
        if len(self.pressed_ports) < 2:
            self.logger.warning(
                "Cannot connect less than two ports. Please select at least two.")
            return

        for i in range(len(self.pressed_ports) - 1):
            source = self.pressed_ports[i] if isinstance(
                self.pressed_ports[i].port, OutputPort) else self.pressed_ports[i + 1]
            destination = self.pressed_ports[i +
                                             1] if source is not self.pressed_ports[i + 1] else self.pressed_ports[i]
            if source.port.operation is destination.port.operation:
                self.logger.warning("Cannot connect to the same port")
                continue

            if type(source.port) == type(destination.port):
                self.logger.warning(
                    f"Cannot connect port of type: {type(source.port).__name__} to port of type: {type(destination.port).__name__}.")
                continue

            self.connect_button(source, destination)

        for port in self.pressed_ports:
            port.select_port()

    def connect_button(self, source, destination):
        signal_exists = (
            signal for signal in source.port.signals if signal.destination is destination.port)
        self.logger.info(
            f"Connecting: {source.operation.operation.type_name()} -> {destination.operation.operation.type_name()}.")
        try:
            line = Arrow(source, destination, self, signal=next(signal_exists))
        except StopIteration:
            line = Arrow(source, destination, self)

        if line not in self.signalPortDict:
            self.signalPortDict[line] = []

        self.signalPortDict[line].append((source, destination))
        self.scene.addItem(line)
        self.signalList.append(line)

        self.update()

    def paintEvent(self, event):
        for signal in self.signalPortDict.keys():
            signal.moveLine()

    def _select_operations(self):
        selected = [button.widget() for button in self.scene.selectedItems()]
        for button in selected:
            button._toggle_button(pressed=False)

        for button in self.pressed_operations:
            if button not in selected:
                button._toggle_button(pressed=True)

        self.pressed_operations = selected

    def _simulate_sfg(self):
        for sfg, properties in self.dialog.properties.items():
            self.logger.info(f"Simulating SFG with name: {sfg.name}.")
            simulation = FastSimulation(
                sfg, input_providers=properties["input_values"])
            l_result = simulation.run_for(
                properties["iteration_count"], save_results=properties["all_results"])

            print(f"{'=' * 10} {sfg.name} {'=' * 10}")
            pprint(
                simulation.results if properties["all_results"] else l_result)
            print(f"{'=' * 10} /{sfg.name} {'=' * 10}")

            if properties["show_plot"]:
                self.logger.info(
                    f"Opening plot for SFG with name: {sfg.name}.")
                self.logger.info(
                    "To save the plot press 'Ctrl+S' when the plot is focused.")
                self.plot = Plot(simulation, sfg, self)
                self.plot.show()

    def simulate_sfg(self):
        self.dialog = SimulateSFGWindow(self)

        for _, sfg in self.sfg_dict.items():
            self.dialog.add_sfg_to_dialog(sfg)

        self.dialog.show()

        # Wait for input to dialog. Kinda buggy because of the separate window in the same thread.
        self.dialog.simulate.connect(self._simulate_sfg)

    def display_faq_page(self):
        self.faq_page = FaqWindow(self)
        self.faq_page.scroll_area.show()

    def display_about_page(self):
        self.about_page = AboutWindow(self)
        self.about_page.show()

    def display_keybinds_page(self):
        self.keybinds_page = KeybindsWindow(self)
        self.keybinds_page.show()


def start_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start_gui()
