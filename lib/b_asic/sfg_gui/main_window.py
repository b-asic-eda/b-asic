"""
B-ASIC Signal Flow Graph Editor Module.

This file opens the main SFG editor window of the GUI for B-ASIC when run.
"""

import importlib.util
import logging
import sys
import webbrowser
from collections import deque
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QCoreApplication, QFileInfo, QSettings, QSize, Qt, QThread, Slot
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
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QShortcut,
    QStatusBar,
)

import b_asic.core_operations
import b_asic.special_operations
from b_asic._version import __version__
from b_asic.gui_utils.about_window import AboutWindow
from b_asic.gui_utils.decorators import decorate_class, handle_error
from b_asic.gui_utils.icons import get_icon
from b_asic.gui_utils.plot_window import PlotWindow
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.save_load_structure import python_to_sfg, sfg_to_python
from b_asic.sfg_gui._preferences import GAP, GRID, MINBUTTONSIZE, PORTHEIGHT
from b_asic.sfg_gui.arrow import Arrow
from b_asic.sfg_gui.drag_button import DragButton
from b_asic.sfg_gui.gui_interface import Ui_main_window
from b_asic.sfg_gui.port_button import PortButton
from b_asic.sfg_gui.precedence_graph_window import PrecedenceGraphWindow
from b_asic.sfg_gui.select_sfg_window import SelectSFGWindow
from b_asic.sfg_gui.simulate_sfg_window import SimulateSFGWindow
from b_asic.sfg_gui.simulation_worker import SimulationWorker
from b_asic.sfg_gui.util_dialogs import FaqWindow, KeybindingsWindow
from b_asic.signal import Signal
from b_asic.signal_flow_graph import SFG
from b_asic.simulation import Simulation
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from qtpy.QtWidgets import QGraphicsProxyWidget

logging.basicConfig(level=logging.INFO)

QCoreApplication.setOrganizationName("Linköping University")
QCoreApplication.setOrganizationDomain("liu.se")
QCoreApplication.setApplicationName("B-ASIC SFG GUI")
QCoreApplication.setApplicationVersion(__version__)


@decorate_class(handle_error)
class SFGMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._window = self
        self._ui = Ui_main_window()
        self._ui.setupUi(self)
        self.setWindowIcon(QIcon("small_logo.png"))
        self._scene = QGraphicsScene(self._ui.splitter)
        self._operations_from_name: dict[str, Operation] = {}
        self._zoom = 1
        self._drag_operation_scenes: dict[DragButton, QGraphicsProxyWidget] = {}
        self._drag_buttons: dict[Operation, DragButton] = {}
        self._mouse_pressed = False
        self._mouse_dragging = False
        self._starting_port = None
        self._pressed_operations: list[DragButton] = []
        self._arrow_ports: dict[Arrow, list[tuple[PortButton, PortButton]]] = {}
        self._operation_to_sfg: dict[DragButton, SFG] = {}
        self._pressed_ports: list[PortButton] = []
        self._sfg_dict: dict[str, SFG] = {}
        self._plot: dict[Simulation, PlotWindow] = {}
        self._ports: dict[DragButton, list[PortButton]] = {}

        # Create Graphics View
        self._graphics_view = QGraphicsView(self._scene, self._ui.splitter)
        self._graphics_view.setRenderHint(QPainter.Antialiasing)
        self._graphics_view.setGeometry(
            self._ui.operation_box.width(), 20, self.width(), self.height()
        )
        self._graphics_view.setDragMode(QGraphicsView.RubberBandDrag)

        # Create toolbar
        self._toolbar = self.addToolBar("Toolbar")
        self._toolbar.addAction(get_icon("open"), "Load SFG", self.load_work)
        self._toolbar.addAction(get_icon("save"), "Save SFG", self.save_work)
        self._toolbar.addSeparator()
        self._toolbar.addAction(
            get_icon("new-sfg"), "Create SFG", self.create_sfg_from_toolbar
        )
        self._toolbar.addAction(
            get_icon("close"), "Clear workspace", self._clear_workspace
        )

        # Create status bar
        self._statusbar = QStatusBar(self)
        self.setStatusBar(self._statusbar)

        # Add operations
        self._max_recent_files = 4
        self._recent_files_actions: list[QAction] = []
        self._recent_files_paths: deque[str] = deque(maxlen=self._max_recent_files)

        self.add_operations_from_namespace(
            b_asic.core_operations, self._ui.core_operations_list
        )
        self.add_operations_from_namespace(
            b_asic.special_operations, self._ui.special_operations_list
        )
        self.add_operations_from_namespace(
            b_asic.utility_operations, self._ui.utility_operations_list
        )

        self._shortcut_refresh_operations = QShortcut(
            QKeySequence("Ctrl+R"), self._ui.operation_box
        )
        self._shortcut_refresh_operations.activated.connect(
            self._refresh_operations_list_from_namespace
        )
        self._scene.selectionChanged.connect(self._select_operations)

        self.move_button_index = 0

        self._ui.actionShowPC.triggered.connect(self._show_precedence_graph)
        self._ui.actionSimulateSFG.triggered.connect(self.simulate_sfg)
        self._ui.actionSimulateSFG.setIcon(get_icon("sim"))

        # About menu
        self._ui.faqBASIC.triggered.connect(self.display_faq_page)
        self._ui.faqBASIC.setShortcut(QKeySequence("Ctrl+?"))
        self._ui.faqBASIC.setIcon(get_icon("faq"))
        self._ui.aboutBASIC.triggered.connect(self.display_about_page)
        self._ui.aboutBASIC.setIcon(get_icon("about"))
        self._ui.keybindsBASIC.triggered.connect(self.display_keybindings_page)
        self._ui.keybindsBASIC.setIcon(get_icon("keys"))
        self._ui.documentationBASIC.triggered.connect(self._open_documentation)
        self._ui.documentationBASIC.setIcon(get_icon("docs"))

        # Operation lists
        self._ui.core_operations_list.itemClicked.connect(
            self._on_list_widget_item_clicked
        )
        self._ui.special_operations_list.itemClicked.connect(
            self._on_list_widget_item_clicked
        )
        self._ui.utility_operations_list.itemClicked.connect(
            self._on_list_widget_item_clicked
        )
        self._ui.custom_operations_list.itemClicked.connect(
            self._on_list_widget_item_clicked
        )
        self._ui.save_menu.triggered.connect(self.save_work)
        self._ui.save_menu.setIcon(get_icon("save"))
        self._ui.save_menu.setShortcut(QKeySequence("Ctrl+S"))
        self._ui.load_menu.triggered.connect(self.load_work)
        self._ui.load_menu.setIcon(get_icon("open"))
        self._ui.load_menu.setShortcut(QKeySequence("Ctrl+O"))
        self._ui.load_operations.triggered.connect(self.add_namespace)
        self._ui.load_operations.setIcon(get_icon("add-operations"))
        self._ui.exit_menu.triggered.connect(self.exit_app)
        self._ui.exit_menu.setIcon(get_icon("quit"))
        self._ui.select_all.triggered.connect(self._select_all)
        self._ui.select_all.setShortcut(QKeySequence("Ctrl+A"))
        self._ui.select_all.setIcon(get_icon("all"))
        self._ui.unselect_all.triggered.connect(self._unselect_all)
        self._ui.unselect_all.setIcon(get_icon("none"))
        self._shortcut_signal = QShortcut(QKeySequence(Qt.Key_Space), self)
        self._shortcut_signal.activated.connect(self._connect_callback)
        self._create_recent_file_actions_and_menus()

        # View menu

        # Operation names
        self._show_names = True
        self._check_show_names = QAction("&Operation names")
        self._check_show_names.triggered.connect(self.view_operation_names)
        self._check_show_names.setCheckable(True)
        self._check_show_names.setChecked(True)
        self._ui.view_menu.addAction(self._check_show_names)

        self._ui.view_menu.addSeparator()

        # Toggle toolbar
        self._ui.view_menu.addAction(self._toolbar.toggleViewAction())

        # Toggle status bar
        self._statusbar_visible = QAction("&Status bar")
        self._statusbar_visible.setCheckable(True)
        self._statusbar_visible.setChecked(True)
        self._statusbar_visible.triggered.connect(self._toggle_statusbar)
        self._ui.view_menu.addAction(self._statusbar_visible)

        # Zoom to fit
        self._ui.view_menu.addSeparator()
        self._zoom_to_fit_action = QAction(get_icon("zoom-to-fit"), "Zoom to &fit")
        self._zoom_to_fit_action.triggered.connect(self._zoom_to_fit)
        self._ui.view_menu.addAction(self._zoom_to_fit_action)

        # Toggle full screen
        self._fullscreen_action = QAction(
            get_icon("full-screen"), "Toggle f&ull screen"
        )
        self._fullscreen_action.setCheckable(True)
        self._fullscreen_action.triggered.connect(self._toggle_fullscreen)
        self._fullscreen_action.setShortcut(QKeySequence("F11"))
        self._ui.view_menu.addAction(self._fullscreen_action)

        # Non-modal dialogs
        self._keybindings_page = None
        self._about_page = None
        self._faq_page = None

        self._logger.info("Finished setting up GUI")
        self._logger.info(
            "For questions please refer to 'Ctrl+?', or visit the 'Help' "
            "section on the _toolbar."
        )

        self.cursor = QCursor()

    def resizeEvent(self, event) -> None:
        ui_width = self._ui.operation_box.width()
        self._ui.operation_box.setGeometry(10, 10, ui_width, self.height())
        self._graphics_view.setGeometry(
            ui_width + 20,
            60,
            self.width() - ui_width - 20,
            self.height() - 30,
        )
        super().resizeEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            old_zoom = self._zoom
            self._zoom += event.angleDelta().y() / 2500
            self._graphics_view.scale(self._zoom, self._zoom)
            self._zoom = old_zoom

    def view_operation_names(self, event=None) -> None:
        self._show_names = self._check_show_names.isChecked()

        for operation in self._drag_operation_scenes:
            operation.label.setOpacity(self._show_names)
            operation.show_name = self._show_names

    def _save_work(self) -> None:
        if not self.sfg_widget.sfg:
            self.update_statusbar("No SFG selected - saving cancelled")
        sfg = cast(SFG, self.sfg_widget.sfg)
        file_dialog = QFileDialog()
        file_dialog.setDefaultSuffix(".py")
        module, accepted = file_dialog.getSaveFileName()
        if not accepted:
            return

        self._logger.info("Saving SFG to path: %s", module)
        operation_positions = {}
        for op_drag, op_scene in self._drag_operation_scenes.items():
            operation_positions[op_drag.operation.graph_id] = (
                int(op_scene.x()),
                int(op_scene.y()),
                op_drag.is_flipped(),
            )

        try:
            with Path(module).open("w+") as file_obj:
                file_obj.write(
                    sfg_to_python(sfg, suffix=f"positions = {operation_positions}")
                )
        except Exception as e:
            self._logger.error(
                "Failed to save SFG to path: %s, with error: %s.", module, e
            )
            return

        self._logger.info("Saved SFG to path: %s", module)
        self.update_statusbar(f"Saved SFG to path: {module}")

    def save_work(self, event=None) -> None:
        if not self._sfg_dict:
            self.update_statusbar("No SFG to save")
            return
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
        self._logger.info("Loading SFG from path: %s", module)
        try:
            sfg, positions = python_to_sfg(module)
        except ImportError as e:
            self._logger.error(
                "Failed to load module: %s with the following error: %s.", module, e
            )
            return

        self._add_recent_file(module)

        while sfg.name in self._sfg_dict:
            self._logger.warning(
                "Duplicate SFG with name: %s detected, please choose a new name",
                sfg.name,
            )
            name, accepted = QInputDialog.getText(
                self, "Change SFG Name", "Name: ", QLineEdit.Normal
            )
            if not accepted:
                return

            sfg.name = name
        self._load_sfg(sfg, positions)
        self._logger.info("Loaded SFG from path: %s ", module)
        self.update_statusbar(f"Loaded SFG from {module}")

    def _load_sfg(self, sfg: SFG, positions=None) -> None:
        if positions is None:
            positions = {}

        for op in sfg.split():
            self.add_operation(
                op,
                positions[op.graph_id][0:2] if op.graph_id in positions else None,
                positions[op.graph_id][-1] if op.graph_id in positions else None,
            )

        def connect_ports(ports: Sequence[InputPort]) -> None:
            for port in ports:
                for signal in port.signals:
                    sources = [
                        source
                        for source in self._drag_buttons[
                            signal.source_operation
                        ].port_list
                        if source.port is signal.source
                    ]
                    destinations = [
                        destination
                        for destination in self._drag_buttons[
                            signal.destination.operation
                        ].port_list
                        if destination.port is signal.destination
                    ]

                    if sources and destinations:
                        self._connect_button(sources[0], destinations[0])

            for pressed_port in self._pressed_ports:
                pressed_port.select_port()

        for op in sfg.split():
            connect_ports(op.inputs)

        for op in sfg.split():
            self._drag_buttons[op].setToolTip(sfg.name)
            self._operation_to_sfg[self._drag_buttons[op]] = sfg

        self._sfg_dict[sfg.name] = sfg
        self.update()

    def _create_recent_file_actions_and_menus(self) -> None:
        for _ in range(self._max_recent_files):
            recent_file_action = QAction(self._ui.recent_sfg)
            recent_file_action.setVisible(False)
            recent_file_action.triggered.connect(
                lambda b=0, x=recent_file_action: self._open_recent_file(x)
            )
            self._recent_files_actions.append(recent_file_action)
            self._ui.recent_sfg.addAction(recent_file_action)

        self._update_recent_file_list()

    def _toggle_fullscreen(self, event=None) -> None:
        """Toggle full screen mode."""
        if self.isFullScreen():
            self.showNormal()
            self._fullscreen_action.setIcon(get_icon("full-screen"))
        else:
            self.showFullScreen()
            self._fullscreen_action.setIcon(get_icon("full-screen-exit"))

    def _update_recent_file_list(self) -> None:
        settings = QSettings()
        rfp = cast(deque, settings.value("SFG/recentFiles"))
        if rfp:
            dequelen = len(rfp)
            if dequelen > 0:
                for i in range(dequelen):
                    action = self._recent_files_actions[i]
                    action.setText(str(rfp[i]))
                    action.setData(QFileInfo(str(rfp[i])))
                    action.setVisible(True)

                for i in range(dequelen, self._max_recent_files):
                    self._recent_files_actions[i].setVisible(False)

    def _open_recent_file(self, action) -> None:
        self._load_from_file(action.data().filePath())

    def _add_recent_file(self, module) -> None:
        settings = QSettings()
        rfp = cast(deque, settings.value("SFG/recentFiles"))
        if rfp:
            if module not in rfp:
                rfp.append(module)
        else:
            rfp = deque(maxlen=self._max_recent_files)
            rfp.append(module)

        settings.setValue("SFG/recentFiles", rfp)

        self._update_recent_file_list()

    def exit_app(self, event=None) -> None:
        """Exit the application."""
        self._logger.info("Exiting the application.")
        QApplication.quit()

    def update_statusbar(self, msg: str) -> None:
        """
        Write *msg* to the statusbar with temporarily policy.

        Parameters
        ----------
        msg : str
            The message to write.
        """
        self._statusbar.showMessage(msg)

    def _clear_workspace(self) -> None:
        self._logger.info("Clearing workspace from operations and SFGs.")
        self._pressed_operations.clear()
        self._pressed_ports.clear()
        self._drag_buttons.clear()
        self._drag_operation_scenes.clear()
        self._arrow_ports.clear()
        self._ports.clear()
        self._sfg_dict.clear()
        self._scene.clear()
        self._logger.info("Workspace cleared.")
        self.update_statusbar("Workspace cleared.")

    def create_sfg_from_toolbar(self) -> None:
        """Create an SFG."""
        inputs = []
        outputs = []
        for pressed_op in self._pressed_operations:
            if isinstance(pressed_op.operation, Input):
                inputs.append(pressed_op.operation)
            elif isinstance(pressed_op.operation, Output):
                outputs.append(pressed_op.operation)

        name, accepted = QInputDialog.getText(
            self, "Create SFG", "Name: ", QLineEdit.Normal
        )
        if not accepted:
            return

        if not name:
            self._logger.warning("Failed to initialize SFG with empty name.")
            return

        self._logger.info("Creating SFG with name: %s from selected operations.", name)

        sfg = SFG(inputs=inputs, outputs=outputs, name=name)
        self._logger.info("Created SFG with name: %s from selected operations.", name)
        self.update_statusbar(f"Created SFG: {name}")

        def check_equality(signal: Signal, signal_2: Signal) -> bool:
            source_operation = cast(Operation, signal.source_operation)
            source_operation2 = cast(Operation, signal_2.source_operation)
            dest_operation = cast(Operation, signal.destination_operation)
            dest_operation2 = cast(Operation, signal_2.destination_operation)
            if not (
                source_operation.type_name() == source_operation2.type_name()
                and dest_operation.type_name() == dest_operation2.type_name()
            ):
                return False

            if (
                hasattr(source_operation, "value")
                and hasattr(source_operation2, "value")
                and hasattr(dest_operation, "value")
                and hasattr(dest_operation2, "value")
                and not (
                    source_operation.value == source_operation2.value
                    and dest_operation.value == dest_operation2.value
                )
            ):
                return False

            if (
                hasattr(source_operation, "name")
                and hasattr(source_operation2, "name")
                and hasattr(dest_operation, "name")
                and hasattr(dest_operation2, "name")
                and not (
                    source_operation.name == source_operation2.name
                    and dest_operation.name == dest_operation2.name
                )
            ):
                return False

            try:
                signal_source_index = [
                    source_operation.outputs.index(port)
                    for port in source_operation.outputs
                    if signal in port.signals
                ]
                signal_2_source_index = [
                    source_operation2.outputs.index(port)
                    for port in source_operation2.outputs
                    if signal_2 in port.signals
                ]
            except ValueError:
                return False  # Signal output connections not matching

            try:
                signal_destination_index = [
                    dest_operation.inputs.index(port)
                    for port in dest_operation.inputs
                    if signal in port.signals
                ]
                signal_2_destination_index = [
                    dest_operation2.inputs.index(port)
                    for port in dest_operation2.inputs
                    if signal_2 in port.signals
                ]
            except ValueError:
                return False  # Signal input connections not matching

            return (
                signal_source_index == signal_2_source_index
                and signal_destination_index == signal_2_destination_index
            )

        for _ in self._pressed_operations:
            for operation in sfg.operations:
                for input_ in operation.inputs:
                    for signal in input_.signals:
                        for arrow in self._arrow_ports:
                            if check_equality(arrow.signal, signal):
                                arrow.set_source_operation(signal.source_operation)
                                arrow.set_destination_operation(
                                    signal.destination_operation
                                )

                for output_ in operation.outputs:
                    for signal in output_.signals:
                        for arrow in self._arrow_ports:
                            if check_equality(arrow.signal, signal):
                                arrow.set_source_operation(signal.source_operation)
                                arrow.set_destination_operation(
                                    signal.destination_operation
                                )

        for pressed_op in self._pressed_operations:
            pressed_op.setToolTip(sfg.name)
            self._operation_to_sfg[pressed_op] = sfg

        self._sfg_dict[sfg.name] = sfg

    def _show_precedence_graph(self, event=None) -> None:
        """Show the precedence graph."""
        if not self._sfg_dict:
            self.update_statusbar("No SFG to show")
            return
        self._precedence_graph_dialog = PrecedenceGraphWindow(self)
        self._precedence_graph_dialog.add_sfg_to_dialog()
        self._precedence_graph_dialog.show()

    def _toggle_statusbar(self, event=None) -> None:
        """Toggle the status bar."""
        self._statusbar.setVisible(self._statusbar_visible.isChecked())

    def get_operations_from_namespace(self, namespace: ModuleType) -> list[str]:
        """
        Return a list of all operations defined in a namespace (module).

        Parameters
        ----------
        namespace : module
            A loaded Python module containing operations.

        Returns
        -------
        list
            A list of names of all the operations in the module.
        """
        self._logger.info("Fetching operations from namespace: %s", namespace.__name__)
        return [
            comp
            for comp in dir(namespace)
            if hasattr(getattr(namespace, comp), "type_name")
        ]

    def add_operations_from_namespace(
        self, namespace: ModuleType, list_widget: QListWidget
    ) -> None:
        """
        Add operations from namespace (module) to a list widget.

        Parameters
        ----------
        namespace : module
            A loaded Python module containing operations.
        list_widget : QListWidget
            The widget to add operations to.
        """
        for attr_name in self.get_operations_from_namespace(namespace):
            attr = getattr(namespace, attr_name)
            try:
                attr.type_name()
                item = QListWidgetItem(attr_name)
                list_widget.addItem(item)
                self._operations_from_name[attr_name] = attr
            except NotImplementedError:
                pass

        self._logger.info("Added operations from namespace: %s", namespace.__name__)

    def add_namespace(self, event=None) -> None:
        """Add namespace."""
        module, accepted = QFileDialog().getOpenFileName()
        if not accepted:
            return
        self._add_namespace(module)

    def _add_namespace(self, module: str) -> None:
        spec = importlib.util.spec_from_file_location(
            f"{QFileInfo(module).fileName()}", module
        )
        namespace = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(namespace)

        self.add_operations_from_namespace(namespace, self._ui.custom_operations_list)

    def _update(self) -> None:
        self._scene.update()
        self._graphics_view.update()

    def add_operation(
        self,
        op: Operation,
        position: tuple[float, float] | None = None,
        is_flipped: bool = False,
    ) -> None:
        """
        Add operation to GUI.

        Parameters
        ----------
        op : Operation
            The operation to add.
        position : (float, float), optional
            (x, y)-position for operation.
        is_flipped : bool, default: False
            Whether the operation is flipped.
        """
        try:
            if op in self._drag_buttons:
                self._logger.warning("Multiple instances of operation with same name")
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
            self._ports[attr_button] = attr_button.port_list

            icon_path = (
                Path(__file__).parent
                / "operation_icons"
                / f"{op.type_name().lower()}.png"
            )

            print(icon_path)
            if not Path(icon_path).exists():
                icon_path = (
                    Path(__file__).parent / "operation_icons" / "custom_operation.png"
                )
            attr_button.setIcon(QIcon(str(icon_path)))
            attr_button.setIconSize(QSize(MINBUTTONSIZE, MINBUTTONSIZE))
            attr_button.setToolTip("No SFG")
            attr_button.setStyleSheet(
                "QToolTip { background-color: white; color: black }"
            )
            attr_button.setParent(None)
            attr_button_scene = self._scene.addWidget(attr_button)
            if position is None:
                attr_button_scene.moveBy(
                    int(self._scene.width() / 4), int(self._scene.height() / 4)
                )
            attr_button_scene.setFlag(QGraphicsItem.ItemIsSelectable, True)
            operation_label = QGraphicsTextItem(op.name, attr_button_scene)
            if not self._show_names:
                operation_label.setOpacity(0)
            operation_label.setTransformOriginPoint(
                operation_label.boundingRect().center()
            )
            operation_label.moveBy(10, -20)
            attr_button.add_label(operation_label)

            if isinstance(is_flipped, bool) and is_flipped:
                attr_button._flip()

            self._drag_buttons[op] = attr_button
            self._drag_operation_scenes[attr_button] = attr_button_scene

        except Exception as e:
            self._logger.error(
                "Unexpected error occurred while creating operation: %s", e
            )

    def _create_operation_item(self, item) -> None:
        self._logger.info("Creating operation of type: %s", item.text())
        try:
            attr_operation = self._operations_from_name[item.text()]()
            self.add_operation(attr_operation)
            self.update_statusbar(f"{item.text()} added.")
        except Exception as e:
            self._logger.error(
                "Unexpected error occurred while creating operation: %d", e
            )

    def _refresh_operations_list_from_namespace(self) -> None:
        self._logger.info("Refreshing operation list.")
        self._ui.core_operations_list.clear()
        self._ui.special_operations_list.clear()

        self.add_operations_from_namespace(
            b_asic.core_operations, self._ui.core_operations_list
        )
        self.add_operations_from_namespace(
            b_asic.special_operations, self._ui.special_operations_list
        )
        self._logger.info("Finished refreshing operation list.")

    def _on_list_widget_item_clicked(self, item) -> None:
        self._create_operation_item(item)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            for pressed_op in self._pressed_operations:
                pressed_op.remove()
                self.move_button_index -= 1
            self._pressed_operations.clear()
        super().keyPressEvent(event)

    def _connect_callback(self, *event) -> None:
        """Connect operation buttons."""
        if len(self._pressed_ports) < 2:
            self._logger.warning(
                "Cannot connect less than two ports. Please select at least two."
            )
            return

        pressed_op_inports = [
            pressed
            for pressed in self._pressed_ports
            if isinstance(pressed.port, InputPort)
        ]
        pressed_op_outports = [
            pressed
            for pressed in self._pressed_ports
            if isinstance(pressed.port, OutputPort)
        ]

        if len(pressed_op_outports) != 1:
            raise ValueError("Exactly one output port must be selected!")

        pressed_op_outport = pressed_op_outports[0]
        for pressed_op_input_port in pressed_op_inports:
            self._connect_button(pressed_op_outport, pressed_op_input_port)

        for port in self._pressed_ports:
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
        """
        signal_exists = (
            signal
            for signal in source.port.signals
            if signal.destination is destination.port
        )
        self._logger.info(
            "Connecting: %s -> %s",
            source.operation.type_name(),
            destination.operation.type_name(),
        )
        try:
            arrow = Arrow(source, destination, self, signal=next(signal_exists))
        except StopIteration:
            arrow = Arrow(source, destination, self)

        if arrow not in self._arrow_ports:
            self._arrow_ports[arrow] = []

        self._arrow_ports[arrow].append((source, destination))
        self._scene.addItem(arrow)

        self.update()

    def paintEvent(self, event) -> None:
        for arrow in self._arrow_ports:
            arrow.update_arrow()

    def _select_operations(self) -> None:
        """Select an operation button."""
        selected = [button.widget() for button in self._scene.selectedItems()]
        for button in selected:
            button._toggle_button(pressed=False)

        for button in self._pressed_operations:
            if button not in selected:
                button._toggle_button(pressed=True)

        self._pressed_operations = selected

    def _select_all(self, event=None) -> None:
        """Select all operation buttons."""
        if not self._drag_buttons:
            self.update_statusbar("No operations to select")
            return

        for operation in self._drag_buttons.values():
            operation._toggle_button(pressed=False)
        self.update_statusbar("Selected all operations")

    def _unselect_all(self, event=None) -> None:
        """Unselect all operation buttons."""
        if not self._drag_buttons:
            self.update_statusbar("No operations to unselect")
            return

        for operation in self._drag_buttons.values():
            operation._toggle_button(pressed=True)
        self.update_statusbar("Unselected all operations")

    def _zoom_to_fit(self, event=None) -> None:
        """Zoom to fit SFGs in window."""
        self._graphics_view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    def _simulate_sfg(self) -> None:
        """Simulate SFGs in separate threads."""
        self._thread = {}
        self._sim_worker = {}
        for sfg, properties in self._simulation_dialog._properties.items():
            self._logger.info("Simulating SFG with name: %s", sfg.name)
            self._sim_worker[sfg] = SimulationWorker(sfg, properties)
            self._thread[sfg] = QThread()
            self._sim_worker[sfg].moveToThread(self._thread[sfg])
            self._thread[sfg].started.connect(self._sim_worker[sfg].start_simulation)
            self._sim_worker[sfg].finished.connect(self._thread[sfg].quit)
            self._sim_worker[sfg].finished.connect(self._show_plot_window)
            self._sim_worker[sfg].finished.connect(self._sim_worker[sfg].deleteLater)
            self._thread[sfg].finished.connect(self._thread[sfg].deleteLater)
            self._thread[sfg].start()

    def _show_plot_window(self, sim: Simulation) -> None:
        """Show the simulation results window."""
        self._plot[sim] = PlotWindow(sim.results, sfg_name=sim.sfg.name)
        self._plot[sim].show()

    def simulate_sfg(self, event=None) -> None:
        """Show the simulation dialog."""
        if not self._sfg_dict:
            self.update_statusbar("No SFG to simulate")
            return

        self._simulation_dialog = SimulateSFGWindow(self)

        for sfg in self._sfg_dict.values():
            self._simulation_dialog.add_sfg_to_dialog(sfg)

        self._simulation_dialog.show()

        # Wait for input to dialog.
        # Kinda buggy because of the separate window in the same thread.
        self._simulation_dialog.simulate.connect(self._simulate_sfg)

    @Slot()
    def _open_documentation(self, event=None) -> None:
        """Open the documentation web page."""
        webbrowser.open_new_tab("https://da.gitlab-pages.liu.se/B-ASIC/")

    def display_faq_page(self, event=None) -> None:
        """Display the FAQ dialog."""
        if self._faq_page is None:
            self._faq_page = FaqWindow(self)
        self._faq_page._scroll_area.show()

    def display_about_page(self, event=None) -> None:
        """Display the about dialog."""
        if self._about_page is None:
            self._about_page = AboutWindow(self)
        self._about_page.show()

    def display_keybindings_page(self, event=None) -> None:
        """Display the keybindings dialog."""
        if self._keybindings_page is None:
            self._keybindings_page = KeybindingsWindow(self)
        self._keybindings_page.show()


def start_editor(sfg: SFG | None = None) -> dict[str, SFG]:
    """
    Start the SFG editor.

    Parameters
    ----------
    sfg : SFG, optional
        The SFG to start the editor with.

    Returns
    -------
    dict
        All SFGs currently in the editor.
    """
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    window = SFGMainWindow()
    if sfg:
        window._load_sfg(sfg)
    window.show()
    app.exec_()
    return window._sfg_dict


if __name__ == "__main__":
    start_editor()
