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

from qtpy.QtCore import (
    QCoreApplication,
    QFileInfo,
    QRectF,
    QSettings,
    Qt,
    QThread,
    Slot,
)
from qtpy.QtGui import QCursor, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QGraphicsItem,
    QGraphicsPathItem,
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
import b_asic.fft_operations
import b_asic.special_operations
import b_asic.wdf_operations
from b_asic._preferences import DEFAULT_FONT_FAMILY
from b_asic._version import version
from b_asic.gui_utils.about_window import AboutWindow
from b_asic.gui_utils.decorators import decorate_class, handle_error
from b_asic.gui_utils.icons import get_icon
from b_asic.gui_utils.plot_window import PlotWindow
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.save_load_structure import python_to_sfg, sfg_to_python
from b_asic.sfg import SFG
from b_asic.sfg_gui._preferences import (
    ADAPTOR_LONG_SIDE,
    GAP,
    GRID,
    LAYOUT_SPACING,
    LINECOLOR,
    MINBUTTONSIZE,
    PORTHEIGHT,
)
from b_asic.sfg_gui.arrow import Arrow
from b_asic.sfg_gui.drag_button import DragButton
from b_asic.sfg_gui.gui_interface import Ui_main_window
from b_asic.sfg_gui.native import NativeDesign
from b_asic.sfg_gui.port_button import PortButton
from b_asic.sfg_gui.precedence_graph_window import PrecedenceGraphWindow
from b_asic.sfg_gui.scene import ConnectionScene
from b_asic.sfg_gui.select_sfg_window import SelectSFGWindow
from b_asic.sfg_gui.simulate_sfg_window import SimulateSFGWindow
from b_asic.sfg_gui.simulation_worker import SimulationWorker
from b_asic.sfg_gui.util_dialogs import FaqWindow, KeybindingsWindow
from b_asic.sfg_gui.view import SFGGraphicsView
from b_asic.signal import Signal
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output

if TYPE_CHECKING:
    from qtpy.QtWidgets import QGraphicsProxyWidget

logging.basicConfig(level=logging.INFO)

QCoreApplication.setOrganizationName("Linköping University")
QCoreApplication.setOrganizationDomain("liu.se")
QCoreApplication.setApplicationName("B-ASIC SFG GUI")
QCoreApplication.setApplicationVersion(version)


@decorate_class(handle_error)
class SFGMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._window = self
        self._ui = Ui_main_window()
        self._ui.setupUi(self)
        self.setWindowIcon(QIcon("small_logo.png"))
        self._scene = ConnectionScene(self, self._ui.splitter)
        self._operations_from_name: dict[str, Operation] = {}
        self._drag_operation_scenes: dict[DragButton, QGraphicsProxyWidget] = {}
        self._drag_buttons: dict[Operation, DragButton] = {}
        self._branch_start = None
        self._starting_port: PortButton | None = None
        self._connection_preview: QGraphicsPathItem | None = None
        self._pressed_operations: list[DragButton] = []
        self._routing_suspended = False
        self._native = NativeDesign()
        self._junction_item: QGraphicsPathItem | None = None
        self._arrow_ports: dict[Arrow, list[tuple[PortButton, PortButton]]] = {}
        self._operation_to_sfg: dict[DragButton, SFG] = {}
        self._pressed_ports: list[PortButton] = []
        self._sfg_dict: dict[str, SFG] = {}
        self._plot: dict[Simulation, PlotWindow] = {}
        self._ports: dict[DragButton, list[PortButton]] = {}

        # Create Graphics View
        self._graphics_view = SFGGraphicsView(self._scene, self._ui.splitter)
        self._graphics_view.setRenderHint(QPainter.Antialiasing)
        self._ui.operation_box.setMinimumWidth(200)
        self._ui.splitter.setStretchFactor(0, 0)
        self._ui.splitter.setStretchFactor(1, 1)
        self._ui.splitter.setSizes([200, 697])
        self._graphics_view.setMouseTracking(True)
        self._scene.changed.connect(self._reroute_arrows)
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

        self._operation_palettes = (
            (b_asic.core_operations, self._ui.core_operations_list),
            (b_asic.special_operations, self._ui.special_operations_list),
            (b_asic.utility_operations, self._ui.utility_operations_list),
            (b_asic.wdf_operations, self._ui.wdf_operations_list),
            (b_asic.fft_operations, self._ui.fft_operations_list),
        )
        self._refresh_operations_list_from_namespace()

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
        for _, operation_list in self._operation_palettes:
            operation_list.itemClicked.connect(self._on_list_widget_item_clicked)
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

        self._auto_layout_action = QAction("Automatic layout", self)
        self._auto_layout_action.setShortcut(QKeySequence("Ctrl+L"))
        self._auto_layout_action.triggered.connect(self.auto_layout)
        self._ui.edit_menu.addAction(self._auto_layout_action)
        self._toolbar.addAction(self._auto_layout_action)

        self._rotate_clockwise_action = QAction("Rotate 90° clockwise", self)
        self._rotate_clockwise_action.setShortcut(QKeySequence("R"))
        self._rotate_clockwise_action.triggered.connect(self._rotate_selected)
        self._rotate_counterclockwise_action = QAction(
            "Rotate 90° counterclockwise", self
        )
        self._rotate_counterclockwise_action.setShortcut(QKeySequence("Shift+R"))
        self._rotate_counterclockwise_action.triggered.connect(
            lambda: self._rotate_selected(clockwise=False)
        )
        self._ui.edit_menu.addAction(self._rotate_clockwise_action)
        self._ui.edit_menu.addAction(self._rotate_counterclockwise_action)

        self._flip_horizontal_action = QAction("Flip horizontal", self)
        self._flip_horizontal_action.setShortcut(QKeySequence("H"))
        self._flip_horizontal_action.triggered.connect(self._flip_selected)
        self._flip_vertical_action = QAction("Flip vertical", self)
        self._flip_vertical_action.setShortcut(QKeySequence("V"))
        self._flip_vertical_action.triggered.connect(
            lambda: self._flip_selected(vertical=True)
        )
        self._ui.edit_menu.addAction(self._flip_horizontal_action)
        self._ui.edit_menu.addAction(self._flip_vertical_action)

        # View menu

        self._grid_action = QAction("Show &grid", self)
        self._grid_action.setCheckable(True)
        self._grid_action.setShortcut(QKeySequence("G"))
        self._grid_action.toggled.connect(self._graphics_view.set_grid_visible)
        self._ui.view_menu.addAction(self._grid_action)

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
        self._zoom_to_fit_action.setShortcut(QKeySequence("F"))
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

    def view_operation_names(self, event=None) -> None:
        self._show_names = self._check_show_names.isChecked()

        for operation in self._drag_operation_scenes:
            operation.label.setOpacity(self._show_names)
            operation.show_name = self._show_names

    def _save_work(self) -> None:
        if not self.sfg_widget.sfg:
            self.update_statusbar("No SFG selected - saving cancelled")
            return
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
                op_drag.rotation_angle(),
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

        operations = list(sfg.split())
        for op in operations:
            self.add_operation(
                op,
                positions[op.graph_id][0:2] if op.graph_id in positions else None,
                (
                    positions[op.graph_id][2]
                    if op.graph_id in positions
                    and len(positions[op.graph_id]) >= 3
                    and isinstance(positions[op.graph_id][2], bool)
                    else False
                ),
                positions[op.graph_id][3]
                if op.graph_id in positions and len(positions[op.graph_id]) >= 4
                else None,
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
        if not positions:
            self.auto_layout()
        self._update()

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
        self._cancel_connection()
        self._operation_to_sfg.clear()
        self._pressed_operations.clear()
        self._pressed_ports.clear()
        self._drag_buttons.clear()
        self._drag_operation_scenes.clear()
        self._arrow_ports.clear()
        self._ports.clear()
        self._sfg_dict.clear()
        self._junction_item = None
        self._native.clear()
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

        # The SFG constructor copies its components. Rebind by identity using
        # its exact copy map, so equal-looking operations cannot be confused.
        copies = sfg._original_components_to_new
        for original, button in list(self._drag_buttons.items()):
            replacement = copies.get(original)
            if not isinstance(replacement, Operation):
                continue
            del self._drag_buttons[original]
            self._drag_buttons[replacement] = button
            button.operation = replacement
            for terminal in button.port_list:
                index = terminal.port.index
                terminal.port = (
                    replacement.input(index)
                    if isinstance(terminal.port, InputPort)
                    else replacement.output(index)
                )
            button.setToolTip(sfg.name)
            self._operation_to_sfg[button] = sfg
        for arrow in self._arrow_ports:
            replacement = copies.get(arrow.signal)
            if isinstance(replacement, Signal):
                arrow.signal = replacement

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
            and (
                namespace not in (b_asic.wdf_operations, b_asic.fft_operations)
                or (
                    not comp.startswith("_")
                    and getattr(getattr(namespace, comp), "__module__", None)
                    == namespace.__name__
                )
            )
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
        self._reroute_arrows()
        self._scene.update()
        self._graphics_view.update()

    def add_operation(
        self,
        op: Operation,
        position: tuple[float, float] | None = None,
        is_flipped: bool = False,
        rotation: int | None = None,
    ) -> None:
        """
        Add operation to GUI.

        Parameters
        ----------
        op : :class:`~b_asic.operation.Operation`
            The operation to add.
        position : (float, float), optional
            (x, y)-position for operation.
        is_flipped : bool, default: False
            Whether the operation is flipped.
        rotation : int, optional
            Clockwise rotation in degrees, in steps of 90. Defaults to 90 for
            twoport adaptors and 0 for other operations.
        """
        try:
            if op in self._drag_buttons:
                self._logger.warning("Multiple instances of operation with same name")
                return

            attr_button = DragButton(op, True, window=self)
            if rotation is None:
                rotation = attr_button.default_rotation()

            max_ports = max(op.input_count, op.output_count)
            button_height = max(
                MINBUTTONSIZE, max_ports * PORTHEIGHT + (max_ports - 1) * GAP
            )

            button_width = MINBUTTONSIZE
            if attr_button.is_circular():
                button_width = button_height = PORTHEIGHT
            elif attr_button.is_road_sign():
                button_height = MINBUTTONSIZE // 2
            elif isinstance(op, Delay):
                button_width = button_height = round(MINBUTTONSIZE * 0.75)
            elif isinstance(op, b_asic.wdf_operations._Adaptor):
                button_height = ADAPTOR_LONG_SIDE
                if op.input_count == 3:
                    button_width = ADAPTOR_LONG_SIDE
            attr_button.setFixedSize(button_width, button_height)
            attr_button.setStyleSheet(
                "QPushButton { background-color: white; border: 2px solid black; }"
                "QToolTip { background-color: white; color: black; }"
            )

            attr_button.setToolTip("No SFG")
            attr_button.setParent(None)
            attr_button_scene = self._scene.addWidget(attr_button)
            attr_button.add_ports()
            self._ports[attr_button] = attr_button.port_list
            automatic_position = position is None
            if automatic_position:
                display_width, display_height = (
                    (button_height, button_width)
                    if rotation % 180
                    else (button_width, button_height)
                )
                x, y = LAYOUT_SPACING * 3, LAYOUT_SPACING * 3
                while any(
                    QRectF(
                        x - 2 * LAYOUT_SPACING,
                        y - LAYOUT_SPACING,
                        display_width + 4 * LAYOUT_SPACING,
                        display_height + 2 * LAYOUT_SPACING,
                    ).intersects(proxy.sceneBoundingRect())
                    for proxy in self._drag_operation_scenes.values()
                ):
                    y += display_height + 3 * LAYOUT_SPACING
                    if y > max(400, self._graphics_view.height()):
                        x += display_width + 6 * LAYOUT_SPACING
                        y = LAYOUT_SPACING * 3
                position = (x, y)
            attr_button_scene.setPos(*position)
            attr_button_scene.setFlag(QGraphicsItem.ItemIsSelectable, True)
            operation_label = QGraphicsTextItem(op.name, attr_button_scene)
            operation_label.setFont(QFont(DEFAULT_FONT_FAMILY))
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
            attr_button.set_rotation(rotation)
            if automatic_position:
                rect = attr_button_scene.sceneBoundingRect()
                attr_button_scene.moveBy(
                    position[0] - rect.left(), position[1] - rect.top()
                )
            self._update()

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
                "Unexpected error occurred while creating operation: %s", e
            )

    def _refresh_operations_list_from_namespace(self) -> None:
        self._logger.info("Refreshing operation list.")
        for namespace, operation_list in self._operation_palettes:
            operation_list.clear()
            self.add_operations_from_namespace(namespace, operation_list)
        self._logger.info("Finished refreshing operation list.")

    def _on_list_widget_item_clicked(self, item) -> None:
        self._create_operation_item(item)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_connection()
        if event.key() == Qt.Key.Key_Delete:
            for pressed_op in list(self._pressed_operations):
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
            self.update_statusbar("Select exactly one output and one or more inputs")
            return

        pressed_op_outport = pressed_op_outports[0]
        for pressed_op_input_port in pressed_op_inports:
            self._connect_button(pressed_op_outport, pressed_op_input_port)

        self._cancel_connection()
        for port in self._pressed_ports:
            port._toggle_port(True)
        self._pressed_ports.clear()

    def _connect_button(
        self, source: PortButton, destination: PortButton, branch=None
    ) -> None:
        """
        Connect two PortButtons with an Arrow.

        Parameters
        ----------
        source : :class:`~b_asic.sfg_gui.port_button.PortButton`
            The PortButton to start the signal at.
        destination : :class:`~b_asic.sfg_gui.port_button.PortButton`
            The PortButton to end the signal at.
        branch : tuple[Arrow, float], optional
            Parent wire and relative distance of the requested junction.
        """
        if not isinstance(source.port, OutputPort) or not isinstance(
            destination.port, InputPort
        ):
            self.update_statusbar("Connect an output to an input")
            return
        if any(
            a.source_port_button is source and a.destination_port_button is destination
            for a in self._arrow_ports
        ):
            return
        if any(signal.source is not source.port for signal in destination.port.signals):
            self.update_statusbar(
                "This input already has a signal; delete it before reconnecting"
            )
            return
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
            self._invalidate_sfg(source._operation_button)
            self._invalidate_sfg(destination._operation_button)

        if branch is not None:
            arrow.branch_parent, arrow.branch_fraction = branch

        if arrow not in self._arrow_ports:
            self._arrow_ports[arrow] = []

        self._arrow_ports[arrow].append((source, destination))
        self._scene.addItem(arrow)

        self._reroute_arrows()
        self.update()

    def auto_layout(self, event=None) -> None:
        """Arrange operations in signal-flow layers, including feedback graphs."""
        if not self._drag_buttons:
            return
        self._native.sync(self)
        layout = self._native.engine.layout()
        buttons = {id(button): button for button in self._drag_buttons.values()}
        self._routing_suspended = True
        try:
            for identity, (x, y), angle, flipped in layout:
                button = buttons[identity]
                button.set_rotation(angle)
                if button.is_flipped() != flipped:
                    button._flip()
                proxy = self._drag_operation_scenes[button]
                offset = (
                    proxy.mapRectToParent(proxy.boundingRect()).topLeft() - proxy.pos()
                )
                proxy.setPos(
                    GRID * round(x / GRID) - offset.x(),
                    GRID * round(y / GRID) - offset.y(),
                )
        finally:
            self._routing_suspended = False
        self._update()
        self._zoom_to_fit()
        self.update_statusbar("Automatic layout applied")

    def _port_clicked(self, port: PortButton) -> None:
        if self._starting_port is not None:
            if port is self._starting_port:
                self._cancel_connection()
            else:
                self._complete_connection(port)
            return
        port.select_port()
        self._starting_port = port
        self._connection_preview = QGraphicsPathItem()
        self._connection_preview.setPen(QPen(Qt.darkGray, 2, Qt.DashLine))
        self._connection_preview.setZValue(-0.5)
        self._connection_preview.setAcceptedMouseButtons(Qt.NoButton)
        self._scene.addItem(self._connection_preview)
        self.update_statusbar("Choose a port or signal; Escape cancels")

    def _signal_clicked(self, arrow: Arrow, position) -> None:
        """Start a branch at the clicked point, rather than at the source port."""
        self._port_clicked(arrow.source_port_button)
        self._branch_start = (arrow, arrow.fraction_at(position))
        self._preview_connection(position)
        self.update_statusbar("Choose an input port for the branch; Escape cancels")

    def _preview_connection(self, position) -> None:
        if self._starting_port is None or self._connection_preview is None:
            return
        start = self._starting_port.anchor()
        if self._branch_start is not None:
            arrow, fraction = self._branch_start
            start = arrow.path().pointAtPercent(
                arrow.path().percentAtLength(fraction * arrow.path().length())
            )
        path = QPainterPath(start)
        mid = (start.x() + position.x()) / 2
        path.lineTo(mid, start.y())
        path.lineTo(mid, position.y())
        path.lineTo(position)
        self._connection_preview.setPath(path)

    def _finish_connection_at(self, position, ignore=None) -> None:
        for item in self._scene.items(position):
            if item is ignore:
                continue
            if isinstance(item, PortButton | Arrow):
                self._complete_connection(item, position)
                return

    def _complete_connection(self, target, position=None) -> None:
        start = self._starting_port
        if start is None:
            return
        branch = self._branch_start
        if isinstance(target, Arrow):
            if not isinstance(start.port, InputPort):
                self.update_statusbar("Branch a signal to an input port")
                return
            source, destination = target.source_port_button, start
            branch = (
                target,
                target.fraction_at(position) if position is not None else 0.5,
            )
        elif isinstance(start.port, OutputPort) and isinstance(target.port, InputPort):
            source, destination = start, target
        elif isinstance(start.port, InputPort) and isinstance(target.port, OutputPort):
            source, destination = target, start
        else:
            self.update_statusbar("Connect an output to an input")
            return
        self._cancel_connection()
        self._connect_button(source, destination, branch)

    def _cancel_connection(self) -> None:
        self._branch_start = None
        if self._starting_port is not None:
            self._starting_port._toggle_port(True)
            if self._starting_port in self._pressed_ports:
                self._pressed_ports.remove(self._starting_port)
        self._starting_port = None
        if self._connection_preview is not None:
            self._scene.removeItem(self._connection_preview)
            self._connection_preview = None

    def _invalidate_sfg(self, button: DragButton) -> None:
        """Discard a cached graph after its connections or operations change."""
        sfg = self._operation_to_sfg.get(button)
        if sfg is None:
            return
        self._sfg_dict.pop(sfg.name, None)
        for operation, graph in list(self._operation_to_sfg.items()):
            if graph is sfg:
                operation.setToolTip("No SFG")
                del self._operation_to_sfg[operation]

    def _rotate_selected(self, event=None, clockwise: bool = True) -> None:
        for button in list(self._pressed_operations):
            button.set_rotation(button.rotation_angle() + (90 if clockwise else -90))

    def _flip_selected(self, event=None, vertical: bool = False) -> None:
        """Reflect each selected operation about its own center."""
        for button in list(self._pressed_operations):
            if vertical:
                button.flip_vertical()
            else:
                button.flip_horizontal()

    def _reroute_arrows(self, *args, force: bool = False) -> None:
        if self._routing_suspended:
            return
        self._native.sync(self)
        dragging = any(button._m_drag for button in self._drag_buttons.values())
        updates, junctions = self._native.engine.route(
            incremental=dragging, force=force
        )
        for identity, points, blocked in updates:
            self._native.arrows[identity].apply_route(points, blocked)
        if junctions is None and self._junction_item is not None:
            return
        dots = QPainterPath()
        for x, y in junctions or ():
            dots.addEllipse(QRectF(x - 3.5, y - 3.5, 7, 7))
        if self._junction_item is None:
            self._junction_item = QGraphicsPathItem()
            self._junction_item.setPen(QPen(Qt.NoPen))
            self._junction_item.setBrush(LINECOLOR)
            self._junction_item.setZValue(-0.25)
            self._junction_item.setAcceptedMouseButtons(Qt.NoButton)
            self._scene.addItem(self._junction_item)
        if self._junction_item.path() != dots:
            self._junction_item.setPath(dots)

    def _select_operations(self) -> None:
        """Select an operation button."""
        selected = [
            item.widget()
            for item in self._scene.selectedItems()
            if hasattr(item, "widget") and isinstance(item.widget(), DragButton)
        ]
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
        self._pressed_operations = list(self._drag_buttons.values())
        self.update_statusbar("Selected all operations")

    def _unselect_all(self, event=None) -> None:
        """Unselect all operation buttons."""
        if not self._drag_buttons:
            self.update_statusbar("No operations to unselect")
            return

        for operation in self._drag_buttons.values():
            operation._toggle_button(pressed=True)
        self._pressed_operations.clear()
        self.update_statusbar("Unselected all operations")

    def _zoom_to_fit(self, event=None) -> None:
        """Zoom to fit SFGs in window."""
        rect = self._scene.itemsBoundingRect().adjusted(-30, -30, 30, 30)
        # Qt can clamp centering when the requested margin lies outside its
        # scrollable scene rectangle, clipping off-center terminals or labels.
        self._graphics_view.setSceneRect(self._graphics_view.sceneRect().united(rect))
        self._graphics_view.fitInView(
            rect,
            Qt.AspectRatioMode.KeepAspectRatio,
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
            if properties["show_plot"]:
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
        webbrowser.open_new_tab("https://b-asic.org/")

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
    sfg : :class:`~b_asic.sfg.SFG`, optional
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
