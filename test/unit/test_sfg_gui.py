import warnings

import pytest

try:
    from qtpy import QtCore
    from qtpy.QtWidgets import QInputDialog

    from b_asic.sfg_gui.main_window import SFGMainWindow
except ImportError:
    pytest.skip("Qt not setup", allow_module_level=True)

from b_asic.core_operations import SquareRoot
from b_asic.special_operations import Input, Output


def test_start(qtbot):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


@pytest.mark.parametrize("initial", [[], ["first.py", "second.py"]])
def test_recent_files_use_builtin_settings_values(
    qtbot, monkeypatch, tmp_path, initial
):
    from b_asic.sfg_gui import main_window

    settings = QtCore.QSettings(
        str(tmp_path / "recent.ini"), QtCore.QSettings.IniFormat
    )
    settings.setValue("SFG/recentFiles", initial)
    monkeypatch.setattr(main_window, "QSettings", lambda: settings)
    window = SFGMainWindow()
    qtbot.addWidget(window)
    for path in ("third.py", "fourth.py", "fifth.py", "fifth.py"):
        window._add_recent_file(path)
    settings.sync()
    restored = QtCore.QSettings(settings.fileName(), QtCore.QSettings.IniFormat)
    expected = [*initial, "third.py", "fourth.py", "fifth.py"][-4:]
    assert restored.value("SFG/recentFiles") == expected
    assert [
        action.text() for action in window._recent_files_actions if action.isVisible()
    ] == expected


def test_recent_files_recover_from_unreadable_history(qtbot, monkeypatch, tmp_path):
    from b_asic.sfg_gui import main_window

    settings = QtCore.QSettings(
        str(tmp_path / "recent.ini"), QtCore.QSettings.IniFormat
    )
    settings.setValue("SFG/recentFiles", "unreadable legacy object")
    settings.setValue("unrelated", 42)
    read_value = settings.value

    def read(key, default=None):
        if key == "SFG/recentFiles" and settings.contains(key):
            raise RuntimeError("Failed to deserialize Python object from QDataStream")
        return read_value(key, default)

    monkeypatch.setattr(settings, "value", read)
    monkeypatch.setattr(main_window, "QSettings", lambda: settings)
    window = SFGMainWindow()
    qtbot.addWidget(window)
    assert not settings.contains("SFG/recentFiles")
    assert settings.value("unrelated") == 42
    assert all(not action.isVisible() for action in window._recent_files_actions)
    monkeypatch.setattr(settings, "value", read_value)
    window._add_recent_file("new.py")
    assert settings.value("SFG/recentFiles") == ["new.py"]


def test_load(qtbot, datadir):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join("twotapfir.py"))
    assert "twotapfir" in widget._sfg_dict
    widget._clear_workspace()
    assert "twotapfir" not in widget._sfg_dict
    assert not widget._sfg_dict

    widget.exit_app()


def test_flip(qtbot, datadir):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join("twotapfir.py"))
    sfg = widget._sfg_dict["twotapfir"]
    op = sfg.find_by_name("cmul2")
    dragbutton = widget._drag_buttons[op[0]]
    assert dragbutton.label.font().family() == "DejaVu Serif"
    assert not dragbutton.is_flipped()
    dragbutton._flip()
    assert dragbutton.is_flipped()
    widget.exit_app()


def test_sfg_invalidated_by_remove_of_operation(qtbot, datadir):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join("twotapfir.py"))
    sfg = widget._sfg_dict["twotapfir"]
    ops_before_remove = len(widget._drag_buttons)
    op = sfg.find_by_name("cmul2")
    dragbutton = widget._drag_buttons[op[0]]
    dragbutton.remove()
    assert not widget._sfg_dict
    assert ops_before_remove - 1 == len(widget._drag_buttons)

    widget.exit_app()


def test_sfg_invalidated_by_deleting_of_operation(qtbot, datadir):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join("twotapfir.py"))
    sfg = widget._sfg_dict["twotapfir"]
    ops_before_remove = len(widget._drag_buttons)
    op = sfg.find_by_name("cmul2")
    dragbutton = widget._drag_buttons[op[0]]
    # Click
    qtbot.mouseClick(dragbutton, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(widget, QtCore.Qt.Key.Key_Delete)
    assert not widget._sfg_dict
    assert ops_before_remove - 1 == len(widget._drag_buttons)

    widget.exit_app()


def test_select_operation(qtbot, datadir):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join("twotapfir.py"))
    sfg = widget._sfg_dict["twotapfir"]
    op = sfg.find_by_name("cmul2")[0]
    dragbutton = widget._drag_buttons[op]
    assert not dragbutton.pressed
    assert not widget._pressed_operations

    # Click
    qtbot.mouseClick(dragbutton, QtCore.Qt.MouseButton.LeftButton)
    assert dragbutton.pressed
    assert len(widget._pressed_operations) == 1

    # Click again, should unselect
    qtbot.mouseClick(dragbutton, QtCore.Qt.MouseButton.LeftButton)
    # Currently failing
    # assert not dragbutton.pressed
    # assert not widget._pressed_operations

    # Select another operation
    op2 = sfg.find_by_name("add1")[0]
    dragbutton2 = widget._drag_buttons[op2]
    assert not dragbutton2.pressed

    # Click
    qtbot.mouseClick(dragbutton2, QtCore.Qt.MouseButton.LeftButton)
    assert dragbutton2.pressed
    # Unselect previous
    assert not dragbutton.pressed
    assert len(widget._pressed_operations) == 1

    # Control-click first
    qtbot.mouseClick(
        dragbutton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    assert dragbutton2.pressed
    assert dragbutton.pressed
    assert len(widget._pressed_operations) == 2

    # Control-click second
    qtbot.mouseClick(
        dragbutton2,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    assert not dragbutton2.pressed
    assert dragbutton.pressed
    assert len(widget._pressed_operations) == 1

    widget.exit_app()


def test_help_dialogs(qtbot):
    # Smoke test to open up the "help dialogs"
    # Should really test doing this through the menus an/or closing them
    widget = SFGMainWindow()
    qtbot.addWidget(widget)

    widget.display_faq_page()
    widget.display_about_page()
    widget.display_keybindings_page()
    qtbot.wait(100)
    widget._faq_page.close()
    widget._about_page.close()
    widget._keybindings_page.close()

    widget.exit_app()


# failing right now sometimes on pyside6
# def test_simulate(qtbot, datadir):
#     # Smoke test to open up the "Simulate SFG" and run default simulation
#     # Should really test all different tests
#     widget = SFGMainWindow()
#     qtbot.addWidget(widget)
#     widget._load_from_file(datadir.join('twotapfir.py'))
#     assert 'twotapfir' in widget._sfg_dict
#     widget.simulate_sfg()
#     qtbot.wait(100)
#     widget._simulation_dialog.save_properties()
#     qtbot.wait(100)
#     widget._simulation_dialog.close()

#     widget.exit_app()


def test_properties_window_smoke_test(qtbot, datadir):
    # Smoke test to open up the _properties window
    # Should really check that the contents are correct and changes works etc
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join("twotapfir.py"))
    sfg = widget._sfg_dict["twotapfir"]
    op = sfg.find_by_name("cmul2")[0]
    dragbutton = widget._drag_buttons[op]
    dragbutton.show_properties_window()
    assert dragbutton._properties_window.operation == dragbutton
    qtbot.mouseClick(
        dragbutton._properties_window._ok_button, QtCore.Qt.MouseButton.LeftButton
    )
    widget.exit_app()


def test_properties_window_change_name(qtbot, datadir):
    # Smoke test to open up the _properties window
    # Should really check that the contents are correct and changes works etc
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    widget._load_from_file(datadir.join("twotapfir.py"))
    sfg = widget._sfg_dict["twotapfir"]
    op = sfg.find_by_name("cmul2")[0]
    dragbutton = widget._drag_buttons[op]
    assert dragbutton.name == "cmul2"
    assert dragbutton.operation.name == "cmul2"
    dragbutton.show_properties_window()
    assert dragbutton._properties_window._edit_name.text() == "cmul2"
    dragbutton._properties_window._edit_name.setText("cmul73")
    qtbot.mouseClick(
        dragbutton._properties_window._ok_button, QtCore.Qt.MouseButton.LeftButton
    )
    dragbutton._properties_window.save_properties()
    assert dragbutton.name == "cmul73"
    assert dragbutton.operation.name == "cmul73"

    widget.exit_app()


def test_add_operation_and_create_sfg(qtbot, monkeypatch):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    in1 = Input()
    sqrt = SquareRoot()
    out1 = Output()
    # Create operations
    widget.add_operation(in1)
    widget.add_operation(sqrt)
    widget.add_operation(out1)
    widget.show()
    widget.auto_layout()
    qtbot.wait(10)
    # Should be three operations
    assert len(widget._drag_buttons) == 3
    # These particular three
    for op in (in1, sqrt, out1):
        assert op in widget._drag_buttons
    # No signals
    assert not widget._arrow_ports

    # Click on first port
    in1_port = widget._drag_buttons[in1].port_list[0]
    click_port(
        qtbot,
        widget,
        in1_port,
        QtCore.Qt.MouseButton.LeftButton,
    )
    assert len(widget._pressed_ports) == 1

    # Click on second port
    sqrt_in_port = widget._drag_buttons[sqrt].port_list[0]
    click_port(
        qtbot,
        widget,
        sqrt_in_port,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    assert len(widget._pressed_ports) == 2

    # Connect ports
    widget._connect_callback()
    # Not sure why this won't work
    # qtbot.keyClick(widget, QtCore.Qt.Key.Key_Space, delay=10)
    # Still one selected!?
    assert len(widget._arrow_ports) == 1

    # Click on first port
    sqrt_out_port = widget._drag_buttons[sqrt].port_list[1]
    click_port(
        qtbot,
        widget,
        sqrt_out_port,
        QtCore.Qt.MouseButton.LeftButton,
    )
    # Click on second port
    out1_port = widget._drag_buttons[out1].port_list[0]
    click_port(
        qtbot,
        widget,
        out1_port,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    # Connect
    widget._connect_callback()
    assert len(widget._arrow_ports) == 2

    # Select input op
    qtbot.mouseClick(
        widget._drag_buttons[in1],
        QtCore.Qt.MouseButton.LeftButton,
    )

    # And output op
    qtbot.mouseClick(
        widget._drag_buttons[out1],
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )

    # Monkey patch dialog to return the expected thing
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("foo", True))

    # Create SFG
    widget.create_sfg_from_toolbar()

    # Should be in _sfg_dict now
    assert "foo" in widget._sfg_dict
    assert len(widget._sfg_dict) == 1

    widget.auto_layout()
    for arrow in widget._arrow_ports:
        assert arrow.source_operation in widget._drag_buttons
        assert arrow.destination_operation in widget._drag_buttons
        assert arrow.signal.source is arrow.source_port
        assert arrow.signal.destination is arrow.destination_port

    widget.exit_app()


def click_port(
    qtbot, window, port, button=QtCore.Qt.LeftButton, modifiers=QtCore.Qt.NoModifier
):
    view = window._graphics_view
    qtbot.mouseClick(
        view.viewport(), button, modifiers, pos=view.mapFromScene(port.anchor())
    )


def make_connected_window(qtbot):
    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, destination, branch = Input(), Output(), Output()
    for op in (source, destination, branch):
        window.add_operation(op)
    window._connect_button(
        window._drag_buttons[source].port_list[0],
        window._drag_buttons[destination].port_list[0],
    )
    window.show()
    window.auto_layout()
    qtbot.wait(10)
    return window, source, destination, branch


def activate_test_window(qtbot, window):
    from qtpy.QtWidgets import QApplication

    window.raise_()
    window.windowHandle().requestActivate()
    # Drain native activation events before setting the widget shortcut context.
    # Headless window managers may ignore the native activation request.
    QApplication.processEvents()
    # Qt 6 deprecates this application API, but it lets these widget tests set
    # Qt's active window without requiring native window-manager activation.
    with warnings.catch_warnings(action="ignore", category=DeprecationWarning):
        QApplication.setActiveWindow(window)
    qtbot.waitUntil(window.isActiveWindow)


def press_canvas_shortcut(qtbot, window, key, modifiers=QtCore.Qt.NoModifier):
    # QTest injects Qt events rather than Cocoa menu key equivalents. Keep
    # menu shortcuts in the widget event path, including on macOS/PySide6.
    window.menuBar().setNativeMenuBar(False)
    activate_test_window(qtbot, window)
    view = window._graphics_view
    view.setFocus()
    qtbot.waitUntil(view.hasFocus)
    # The QWindow overload includes Qt's macOS shortcut-processing step in
    # qt_handleKeyEvent; the QWidget overload directly notifies the widget.
    qtbot.keyClick(window.windowHandle(), key, modifiers)


@pytest.mark.parametrize("start_at", ["background", "operation", "port", "wire"])
@pytest.mark.parametrize("zoom", [0.5, 1.5])
def test_middle_drag_pans_without_editing_graph(qtbot, start_at, zoom):
    from qtpy.QtWidgets import QGraphicsView

    window, source, _, _ = make_connected_window(qtbot)
    view = window._graphics_view
    view.scale(zoom, zoom)
    button = window._drag_buttons[source]
    proxy = button.graphicsProxyWidget()
    arrow = next(iter(window._arrow_ports))
    point = {
        "background": proxy.scenePos() - QtCore.QPointF(50, 50),
        "operation": proxy.sceneBoundingRect().center(),
        "port": button.port_list[0].anchor(),
        "wire": arrow.mapToScene(arrow.path().pointAtPercent(0.5)),
    }[start_at]
    position = proxy.pos()
    transform = view.transform()
    cursor = view.viewport().cursor().shape()
    start = view.mapFromScene(point)
    delta = QtCore.QPoint(40, 30)
    before_press = view.mapFromScene(point)
    qtbot.mousePress(view.viewport(), QtCore.Qt.MiddleButton, pos=start)
    before = view.mapFromScene(point)
    assert (before - before_press).manhattanLength() <= 1
    assert view.viewport().cursor().shape() == QtCore.Qt.ClosedHandCursor
    qtbot.mouseMove(view.viewport(), start + delta)
    qtbot.mouseRelease(view.viewport(), QtCore.Qt.MiddleButton, pos=start + delta)
    movement = view.mapFromScene(point) - before
    assert (movement.x(), movement.y()) == pytest.approx((40, 30), abs=1)
    assert view.viewport().cursor().shape() == cursor
    assert view.transform() == transform
    assert proxy.pos() == position
    assert not window._pressed_operations
    assert not window._pressed_ports
    assert window._starting_port is None
    assert len(window._arrow_ports) == 1
    assert view.dragMode() == QGraphicsView.RubberBandDrag
    # New content must remain reachable after the view acquires a pan area.
    distant = Output()
    window.add_operation(distant, (10000, 10000))
    qtbot.wait(10)
    rect = window._drag_buttons[distant].graphicsProxyWidget().sceneBoundingRect()
    assert view.sceneRect().contains(rect)


def test_pan_many_small_moves_does_not_drift(qtbot):
    window, source, _, _ = make_connected_window(qtbot)
    view = window._graphics_view
    view.scale(0.5, 0.5)
    point = (
        window._drag_buttons[source].graphicsProxyWidget().sceneBoundingRect().center()
    )
    start = view.mapFromScene(point)
    rect = view.sceneRect()
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MiddleButton, pos=start)
    assert view.mapFromScene(point) == start
    assert view.sceneRect() == rect
    qtbot.mousePress(view.viewport(), QtCore.Qt.MiddleButton, pos=start)
    for step in range(1, 31):
        qtbot.mouseMove(view.viewport(), start + QtCore.QPoint(step, step))
    qtbot.mouseRelease(
        view.viewport(), QtCore.Qt.MiddleButton, pos=start + QtCore.QPoint(30, 30)
    )
    delta = view.mapFromScene(point) - start
    assert (delta.x(), delta.y()) == pytest.approx((30, 30), abs=1)


@pytest.mark.parametrize("control", [False, True])
@pytest.mark.parametrize("panned", [False, True])
def test_wheel_after_panning(qtbot, control, panned):
    from qtpy.QtGui import QWheelEvent
    from qtpy.QtWidgets import QApplication

    window, _, _, _ = make_connected_window(qtbot)
    view = window._graphics_view
    start = view.viewport().rect().center()
    if panned:
        qtbot.mousePress(view.viewport(), QtCore.Qt.MiddleButton, pos=start)
        qtbot.mouseMove(view.viewport(), start + QtCore.QPoint(40, 30))
        qtbot.mouseRelease(
            view.viewport(), QtCore.Qt.MiddleButton, pos=start + QtCore.QPoint(40, 30)
        )
    transform = view.transform()
    scroll = view.verticalScrollBar().value()
    event = QWheelEvent(
        QtCore.QPointF(start),
        QtCore.QPointF(view.viewport().mapToGlobal(start)),
        QtCore.QPoint(),
        QtCore.QPoint(0, 120),
        QtCore.Qt.NoButton,
        QtCore.Qt.ControlModifier if control else QtCore.Qt.NoModifier,
        QtCore.Qt.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(view.viewport(), event)
    if control:
        assert view.transform().m11() > transform.m11()
    else:
        assert view.verticalScrollBar().value() != scroll
        assert view.transform() == transform


def test_pan_stops_when_middle_button_is_no_longer_held(qtbot):
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication

    window, _, _, _ = make_connected_window(qtbot)
    view = window._graphics_view
    start = view.viewport().rect().center()
    cursor = view.viewport().cursor().shape()
    qtbot.mousePress(view.viewport(), QtCore.Qt.MiddleButton, pos=start)
    origin = view.mapToScene(QtCore.QPoint())
    # Simulate a release outside the window, followed by hovering back inside.
    position = start + QtCore.QPoint(40, 30)
    event = QMouseEvent(
        QtCore.QEvent.MouseMove,
        QtCore.QPointF(position),
        QtCore.QPointF(view.viewport().mapToGlobal(position)),
        QtCore.Qt.NoButton,
        QtCore.Qt.NoButton,
        QtCore.Qt.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), event)
    assert view._pan_position is None
    assert view.mapToScene(QtCore.QPoint()) == origin
    assert view.viewport().cursor().shape() == cursor
    qtbot.mouseRelease(view.viewport(), QtCore.Qt.MiddleButton, pos=position)


def test_click_connect_preview_and_cancel(qtbot):
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication

    window, source, _, branch = make_connected_window(qtbot)
    output = window._drag_buttons[source].port_list[0]
    target = window._drag_buttons[branch].port_list[0]
    click_port(qtbot, window, output)
    assert window._starting_port is output
    view = window._graphics_view
    position = view.mapFromScene(target.anchor())
    # QTest.mouseMove can depend on asynchronous native cursor delivery.
    event = QMouseEvent(
        QtCore.QEvent.MouseMove,
        QtCore.QPointF(position),
        QtCore.QPointF(view.viewport().mapToGlobal(position)),
        QtCore.Qt.NoButton,
        QtCore.Qt.NoButton,
        QtCore.Qt.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), event)
    assert not window._connection_preview.path().isEmpty()
    click_port(qtbot, window, target)
    assert len(window._arrow_ports) == 2
    assert target.port.signals[0].source is output.port
    assert window._starting_port is None
    click_port(qtbot, window, output)
    qtbot.keyClick(window, QtCore.Qt.Key_Escape)
    assert window._connection_preview is None
    assert window._starting_port is None


def test_branch_existing_signal(qtbot):
    window, source, _, branch = make_connected_window(qtbot)
    target = window._drag_buttons[branch].port_list[0]
    arrow = next(iter(window._arrow_ports))
    click_port(qtbot, window, target)
    point = arrow.path().pointAtPercent(0.5)
    view = window._graphics_view
    qtbot.mouseClick(
        view.viewport(), QtCore.Qt.LeftButton, pos=view.mapFromScene(point)
    )
    assert len(window._arrow_ports) == 2
    assert target.port.signals[0].source.operation is source
    assert window._starting_port is None


def test_drag_connect_and_reject_occupied_input(qtbot):
    window, source, destination, branch = make_connected_window(qtbot)
    output = window._drag_buttons[source].port_list[0]
    target = window._drag_buttons[branch].port_list[0]
    view = window._graphics_view
    qtbot.mousePress(
        view.viewport(), QtCore.Qt.LeftButton, pos=view.mapFromScene(output.anchor())
    )
    qtbot.mouseMove(view.viewport(), view.mapFromScene(target.anchor()))
    qtbot.mouseRelease(
        view.viewport(), QtCore.Qt.LeftButton, pos=view.mapFromScene(target.anchor())
    )
    assert len(window._arrow_ports) == 2
    other = Input()
    window.add_operation(other, (0, 400))
    window._connect_button(
        window._drag_buttons[other].port_list[0],
        window._drag_buttons[destination].port_list[0],
    )
    assert len(window._arrow_ports) == 2
    assert "already" in window._statusbar.currentMessage()


def test_external_ports_flip_and_obstacle_reroute(qtbot):
    window, source, _destination, branch = make_connected_window(qtbot)
    output = window._drag_buttons[source].port_list[0]
    assert output.pos().x() > output._operation_button.width()
    arrow = next(iter(window._arrow_ports))
    arrow.destination_operation_button.graphicsProxyWidget().moveBy(200, 0)
    window._update()
    old_path = arrow.path()
    obstacle = window._drag_operation_scenes[window._drag_buttons[branch]]
    obstacle.setPos(old_path.pointAtPercent(0.5) - QtCore.QPointF(28, 28))
    qtbot.wait(20)
    assert arrow.path() != old_path
    assert arrow.path().elementCount() > 1
    rect = obstacle.sceneBoundingRect()
    for i in range(1, arrow.path().elementCount()):
        a, b = arrow.path().elementAt(i - 1), arrow.path().elementAt(i)
        assert a.x == b.x or a.y == b.y
        assert not rect.contains(QtCore.QPointF((a.x + b.x) / 2, (a.y + b.y) / 2))
    window._drag_buttons[source]._flip()
    assert output.pos().x() < 0


def test_auto_layout_cycles_and_saved_positions(qtbot):
    from b_asic.core_operations import Addition
    from b_asic.sfg import SFG
    from b_asic.special_operations import Delay

    source = Input()
    add = Addition(source)
    delay = Delay(add)
    add.input(1).connect(delay)
    graph = SFG(inputs=[source], outputs=[Output(add)])
    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_sfg(graph)
    assert len(window._drag_buttons) == 4
    rects = [p.sceneBoundingRect() for p in window._drag_operation_scenes.values()]
    for i, rect in enumerate(rects):
        assert all(not rect.intersects(other) for other in rects[i + 1 :])
    first = {
        op: proxy.pos()
        for op, button in window._drag_buttons.items()
        for proxy in [window._drag_operation_scenes[button]]
    }
    window.auto_layout()
    assert all(
        window._drag_operation_scenes[window._drag_buttons[op]].pos() == pos
        for op, pos in first.items()
    )


@pytest.mark.parametrize(
    ("start", "end", "obstacles"),
    [
        ((0, 0), (100, 0), [(40, -20, 60, 20)]),
        ((100, 0), (0, 0), [(40, -20, 60, 20)]),
        ((0, 0), (100, 100), [(20, -10, 80, 80), (-10, 20, 10, 80)]),
        ((0, 0), (0, 0), []),
    ],
)
def test_orthogonal_router(start, end, obstacles):
    from itertools import pairwise

    from test.sfg_gui_helpers import route_orthogonal

    path = route_orthogonal(start, end, obstacles)
    assert path[0] == start
    assert path[-1] == end
    for a, b in pairwise(path):
        assert a[0] == b[0] or a[1] == b[1]
        for l, t, r, bottom in obstacles:
            if a[1] == b[1]:
                assert not (
                    t < a[1] < bottom
                    and max(min(a[0], b[0]), l) < min(max(a[0], b[0]), r)
                )
            else:
                assert not (
                    l < a[0] < r
                    and max(min(a[1], b[1]), t) < min(max(a[1], b[1]), bottom)
                )


def test_saved_positions_and_free_placement(qtbot, datadir):
    from b_asic.save_load_structure import python_to_sfg

    graph, positions = python_to_sfg(datadir.join("twotapfir.py"))
    window = SFGMainWindow()
    qtbot.addWidget(window)
    positions = {
        op.graph_id: (i * 133, 57, bool(i % 2)) for i, op in enumerate(graph.split())
    }
    window._load_sfg(graph, positions)
    for op, button in window._drag_buttons.items():
        pos = window._drag_operation_scenes[button].pos()
        assert (pos.x(), pos.y()) == positions[op.graph_id][:2]
        assert button.is_flipped() == positions[op.graph_id][2]
    for _ in range(3):
        window.add_operation(Input())
    rects = [
        proxy.sceneBoundingRect() for proxy in window._drag_operation_scenes.values()
    ]
    for i in range(len(rects) - 3, len(rects)):
        assert all(not rects[i].intersects(other) for other in rects[:i])


def test_self_loop_and_flipped_routing(qtbot):
    from b_asic.special_operations import Delay

    window = SFGMainWindow()
    qtbot.addWidget(window)
    op = Delay()
    window.add_operation(op, (100, 100))
    button = window._drag_buttons[op]
    window._connect_button(button.port_list[1], button.port_list[0])
    arrow = next(iter(window._arrow_ports))
    for _ in range(2):
        path = arrow.path()
        assert path.elementCount() >= 5
        assert path.pointAtPercent(0) == button.port_list[1].anchor()
        assert path.pointAtPercent(1) == button.port_list[0].anchor()
        button._flip()


def test_delete_multiple_operations_and_clear_pending_connection(qtbot):
    window, source, destination, _ = make_connected_window(qtbot)
    selected = [window._drag_buttons[op] for op in (source, destination)]
    window._pressed_operations = selected
    window._port_clicked(selected[0].port_list[0])
    qtbot.keyClick(window, QtCore.Qt.Key_Delete)
    assert len(window._drag_buttons) == 1
    assert not window._arrow_ports
    assert window._starting_port is None
    window._port_clicked(next(iter(window._drag_buttons.values())).port_list[0])
    window._clear_workspace()
    assert window._starting_port is None
    assert window._connection_preview is None
    assert not window._ports
    assert not window._operation_to_sfg


def test_new_connection_invalidates_cached_graph(qtbot, datadir):
    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_from_file(datadir.join("twotapfir.py"))
    graph = window._sfg_dict["twotapfir"]
    branch = Output()
    window.add_operation(branch)
    output = window._drag_buttons[graph.input_operations[0]].port_list[0]
    window._connect_button(output, window._drag_buttons[branch].port_list[0])
    assert not window._sfg_dict
    assert not window._operation_to_sfg


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("flipped", [False, True])
def test_rotation_ports_and_routing(qtbot, angle, flipped):
    from b_asic.sfg_gui._preferences import GRID

    window, source, _, _ = make_connected_window(qtbot)
    button = window._drag_buttons[source]
    if flipped:
        button._flip()
    button.set_rotation(angle)
    terminal = button.port_list[0]
    expected = [(1, 0), (0, 1), (-1, 0), (0, -1)][angle // 90]
    if flipped:
        expected = (-expected[0], -expected[1])
    assert terminal.scene_direction() == expected
    assert button.graphicsProxyWidget().rotation() == angle
    assert (
        button.label.sceneTransform().m12(),
        button.label.sceneTransform().m21(),
    ) == pytest.approx((0, 0))
    arrow = next(iter(window._arrow_ports))
    path = arrow.path()
    assert not path.isEmpty()
    assert path.pointAtPercent(0) == terminal.anchor()
    first, second = path.elementAt(0), path.elementAt(1)
    if path.elementCount() == 2:
        assert path.pointAtPercent(1) == arrow.destination_port_button.anchor()
    else:
        assert (second.x - first.x, second.y - first.y) == (
            expected[0] * GRID,
            expected[1] * GRID,
        )
    for i in range(1, path.elementCount()):
        a, b = path.elementAt(i - 1), path.elementAt(i)
        assert a.x == b.x or a.y == b.y
    button.set_rotation(angle + 360)
    assert button.rotation_angle() == angle


@pytest.mark.parametrize("other_window_active", [False, True])
def test_rotation_shortcuts(qtbot, monkeypatch, other_window_active):
    window, source, _, _ = make_connected_window(qtbot)
    button = window._drag_buttons[source]
    button.select_button()
    if other_window_active:
        from qtpy.QtWidgets import QWidget

        other = QWidget()
        qtbot.addWidget(other)
        other.show()
        activate_test_window(qtbot, other)
        assert not window.isActiveWindow()
        # Model a backend that cannot grant native activation to the editor.
        monkeypatch.setattr(window, "activateWindow", lambda: None)
    press_canvas_shortcut(qtbot, window, QtCore.Qt.Key_R)
    assert button.rotation_angle() == 90
    press_canvas_shortcut(qtbot, window, QtCore.Qt.Key_R, QtCore.Qt.ShiftModifier)
    assert button.rotation_angle() == 0
    for _ in range(4):
        button.rotate_clockwise()
    assert button.rotation_angle() == 0


@pytest.mark.parametrize("vertical", [False, True])
def test_flip_menu_actions_and_shortcuts(qtbot, vertical):
    window, source, destination, branch = make_connected_window(qtbot)
    selected = [window._drag_buttons[op] for op in (source, destination)]
    window._pressed_operations = selected
    untouched = window._drag_buttons[branch]
    action = (
        window._flip_vertical_action if vertical else window._flip_horizontal_action
    )
    assert action in window._ui.edit_menu.actions()
    original = [(b.rotation_angle(), b.is_flipped()) for b in selected]
    action.trigger()
    assert [(b.rotation_angle(), b.is_flipped()) for b in selected] != original
    press_canvas_shortcut(
        qtbot, window, QtCore.Qt.Key_V if vertical else QtCore.Qt.Key_H
    )
    assert [(b.rotation_angle(), b.is_flipped()) for b in selected] == original
    assert (untouched.rotation_angle(), untouched.is_flipped()) == (0, False)


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("flipped", [False, True])
@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("adaptor", [False, True])
def test_flip_reflects_ports_in_canvas_axes(qtbot, angle, flipped, vertical, adaptor):
    from b_asic.core_operations import Addition
    from b_asic.wdf_operations import ReflectionFreeSeriesThreeportAdaptor

    window = SFGMainWindow()
    qtbot.addWidget(window)
    op = ReflectionFreeSeriesThreeportAdaptor() if adaptor else Addition()
    window.add_operation(op, (100, 100), rotation=angle, is_flipped=flipped)
    button = window._drag_buttons[op]
    center = button.graphicsProxyWidget().sceneBoundingRect().center()
    original = [(p.anchor(), p.scene_direction()) for p in button.port_list]
    reflect = button.flip_vertical if vertical else button.flip_horizontal
    reflect()
    for port, (position, direction) in zip(button.port_list, original, strict=True):
        expected_x = position.x() if vertical else 2 * center.x() - position.x()
        expected_y = 2 * center.y() - position.y() if vertical else position.y()
        assert (port.anchor().x(), port.anchor().y()) == pytest.approx(
            (expected_x, expected_y)
        )
        dx, dy = direction
        assert port.scene_direction() == ((dx, -dy) if vertical else (-dx, dy))
    assert button.label.sceneTransform().m11() == pytest.approx(1)
    assert button._symbol.sceneTransform().m11() == pytest.approx(1)
    reflect()
    assert (button.rotation_angle(), button.is_flipped()) == (angle, flipped)


def test_zoom_to_fit_shortcut(qtbot):
    window, _, _, _ = make_connected_window(qtbot)
    view = window._graphics_view
    view.scale(0.25, 0.25)
    previous_zoom = view.transform().m11()
    press_canvas_shortcut(qtbot, window, QtCore.Qt.Key_F)
    assert view.transform().m11() > previous_zoom * 3
    visible = view.mapToScene(view.viewport().rect()).boundingRect()
    assert visible.contains(window._scene.itemsBoundingRect())


def test_grid_menu_and_shortcut(qtbot):
    window, source, _, _ = make_connected_window(qtbot)
    action = window._grid_action
    view = window._graphics_view
    assert action in window._ui.view_menu.actions()
    assert action.isCheckable()
    assert not action.isChecked()
    button = window._drag_buttons[source]
    position = button.graphicsProxyWidget().pos()
    press_canvas_shortcut(qtbot, window, QtCore.Qt.Key_G)
    assert action.isChecked()
    assert view._grid_visible
    action.trigger()
    assert not action.isChecked()
    assert not view._grid_visible
    assert button.graphicsProxyWidget().pos() == position


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize(
    "operation_name", ["Input", "Delay", "Addition", "SymmetricTwoportAdaptor"]
)
def test_drag_snaps_visible_corner_to_grid(qtbot, angle, operation_name):
    import b_asic
    from b_asic.sfg_gui._preferences import GRID

    window = SFGMainWindow()
    qtbot.addWidget(window)
    op = getattr(b_asic, operation_name)()
    window.add_operation(op, (100.25, 100.75), rotation=angle)
    button = window._drag_buttons[op]
    proxy = button.graphicsProxyWidget()
    qtbot.mousePress(button, QtCore.Qt.LeftButton)
    proxy.setPos(-105.25, 123.75)
    button._m_drag = True
    before = proxy.sceneBoundingRect().topLeft()
    qtbot.mouseRelease(button, QtCore.Qt.LeftButton)
    after = proxy.sceneBoundingRect().topLeft()
    assert (after.x(), after.y()) == pytest.approx(
        (GRID * round(before.x() / GRID), GRID * round(before.y() / GRID))
    )


def test_automatic_positions_match_grid(qtbot):
    from b_asic.sfg_gui._preferences import GRID
    from b_asic.special_operations import Delay

    window = SFGMainWindow()
    qtbot.addWidget(window)
    for operation_type in (Input, Delay, Output, Delay, Input, Delay):
        window.add_operation(operation_type())
    for automatic_layout in (False, True):
        if automatic_layout:
            window.auto_layout()
        for proxy in window._drag_operation_scenes.values():
            corner = proxy.sceneBoundingRect().topLeft()
            assert (corner.x() / GRID, corner.y() / GRID) == pytest.approx(
                (round(corner.x() / GRID), round(corner.y() / GRID))
            )


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize(
    "operation_name",
    [
        "Input",
        "Output",
        "Delay",
        "Addition",
        "DontCare",
        "Sink",
        "SymmetricTwoportAdaptor",
        "ReflectionFreeSeriesThreeportAdaptor",
        "R4Butterfly",
    ],
)
def test_node_sizes_and_pins_use_grid_units(qtbot, angle, operation_name):
    import b_asic
    from b_asic import fft_operations, utility_operations
    from b_asic.sfg_gui._preferences import GRID

    operation_type = next(
        getattr(module, operation_name)
        for module in (b_asic, fft_operations, utility_operations)
        if hasattr(module, operation_name)
    )
    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = operation_type()
    window.add_operation(operation, rotation=angle, is_flipped=True)
    button = window._drag_buttons[operation]
    assert button.width() % GRID == button.height() % GRID == 0
    for _ in range(4):
        for port in button.port_list:
            assert (
                port.anchor().x() / GRID,
                port.anchor().y() / GRID,
            ) == pytest.approx(
                (round(port.anchor().x() / GRID), round(port.anchor().y() / GRID))
            )
        button.rotate_clockwise()


def test_drag_group_snaps_together_without_moving_on_selection(qtbot):
    from b_asic.sfg_gui._preferences import GRID

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operations = [Input(), Output()]
    for i, operation in enumerate(operations):
        window.add_operation(operation, (i * 10 * GRID, 0))
    buttons = [window._drag_buttons[operation] for operation in operations]
    proxies = [button.graphicsProxyWidget() for button in buttons]
    window._pressed_operations = buttons
    for proxy in proxies:
        proxy.moveBy(3.5, 5.25)
    relative = proxies[1].pos() - proxies[0].pos()
    qtbot.mousePress(buttons[0], QtCore.Qt.LeftButton)
    buttons[0]._m_drag = True
    qtbot.mouseRelease(buttons[0], QtCore.Qt.LeftButton)
    assert proxies[1].pos() - proxies[0].pos() == relative
    assert all(proxy.x() % GRID == proxy.y() % GRID == 0 for proxy in proxies)
    proxies[0].setPos(3.5, 5.25)
    qtbot.mouseClick(buttons[0], QtCore.Qt.LeftButton)
    assert proxies[0].pos() == QtCore.QPointF(3.5, 5.25)


@pytest.mark.parametrize("zoom", [0.02, 0.1, 1, 4])
@pytest.mark.parametrize("pixel_ratio", [1, 2])
def test_grid_dots_are_single_pixels_and_subsampled(qtbot, zoom, pixel_ratio):
    from itertools import pairwise
    from math import ceil

    from qtpy.QtGui import QColor, QImage, QPainter

    from b_asic.sfg_gui._preferences import GRID

    window = SFGMainWindow()
    qtbot.addWidget(window)
    view = window._graphics_view
    view.set_grid_visible(True)
    image = QImage(200, 200, QImage.Format_ARGB32)
    image.setDevicePixelRatio(pixel_ratio)
    image.fill(QtCore.Qt.white)
    painter = QPainter(image)
    painter.scale(zoom, zoom)
    # Include negative coordinates to check that subsampling stays on the grid.
    painter.translate(50 / (zoom * pixel_ratio), 50 / (zoom * pixel_ratio))
    inverse, _ = painter.worldTransform().inverted()
    rect = inverse.mapRect(QtCore.QRectF(0, 0, 200 / pixel_ratio, 200 / pixel_ratio))
    view.drawBackground(painter, rect)
    painter.end()
    dots = {
        (x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y) != QColor(QtCore.Qt.white)
    }
    assert dots
    for x, y in dots:
        assert image.pixelColor(x, y) == QColor(105, 105, 105)
        assert not any(
            (x + dx, y + dy) in dots for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1))
        )
    xs, ys = sorted({x for x, _ in dots}), sorted({y for _, y in dots})
    assert all(b - a >= 5 for values in (xs, ys) for a, b in pairwise(values))
    step = GRID * max(1, ceil(5 / (GRID * zoom * pixel_ratio)))
    for value in xs + ys:
        grid_index = (value - 50) / (step * zoom * pixel_ratio)
        assert abs(grid_index - round(grid_index)) <= 1 / (step * zoom * pixel_ratio)


def test_rotation_and_flips_saved_and_loaded(qtbot, datadir, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from qtpy.QtWidgets import QFileDialog

    from b_asic.save_load_structure import python_to_sfg

    graph, _ = python_to_sfg(datadir.join("twotapfir.py"))
    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_sfg(graph)
    expected = {}
    for i, (op, button) in enumerate(window._drag_buttons.items()):
        button.set_rotation((i % 4) * 90)
        if i % 2:
            button.flip_horizontal()
        else:
            button.flip_vertical()
        expected[op.graph_id] = (button.rotation_angle(), button.is_flipped())
    window.sfg_widget = SimpleNamespace(sfg=graph)
    path = tmp_path / "rotated_graph.py"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), True))
    window._save_work()
    graph, positions = python_to_sfg(str(path))
    other = SFGMainWindow()
    qtbot.addWidget(other)
    other._load_sfg(graph, positions)
    assert {
        op.graph_id: (b.rotation_angle(), b.is_flipped())
        for op, b in other._drag_buttons.items()
    } == expected


def test_router_separates_collinear_wires():
    from itertools import pairwise

    from test.sfg_gui_helpers import overlap_length, route_orthogonal

    occupied = [((-20, 0), (120, 0))]
    path = route_orthogonal((0, 0), (100, 0), [], occupied)
    assert path[0] == (0, 0)
    assert path[-1] == (100, 0)
    assert len(path) >= 4
    assert all(
        overlap_length(a, b, c, d) == 0 for a, b in pairwise(path) for c, d in occupied
    )


def test_router_uses_multibend_detour_to_avoid_overlap():
    from itertools import pairwise

    from test.sfg_gui_helpers import overlap_length, route_is_clear, route_orthogonal

    obstacles = [(-10, 40, 10, 110), (90, -10, 110, 60)]
    occupied = [((-40, 0), (140, 0)), ((-40, 100), (140, 100))]
    path = route_orthogonal((0, 0), (100, 100), obstacles, occupied)
    assert path[0] == (0, 0)
    assert path[-1] == (100, 100)
    assert route_is_clear(path, obstacles)
    assert all(
        overlap_length(a, b, c, d) == 0 for a, b in pairwise(path) for c, d in occupied
    )


def test_router_keeps_parallel_lanes_apart():
    from b_asic.sfg_gui._preferences import GRID
    from test.sfg_gui_helpers import route_cost, route_orthogonal

    occupied = [((-20, 2), (120, 2))]
    path = route_orthogonal((0, 0), (100, 0), [], occupied)
    assert route_cost(path, occupied)[0] == 0
    assert any(abs(y - 2) >= GRID for _, y in path)


def test_signal_can_leave_ports_sideways_when_exits_are_blocked(qtbot):
    from b_asic.special_operations import Delay
    from test.sfg_gui_helpers import route_is_clear

    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, target = Input(), Output()
    for operation, position in (
        (source, (0, 100)),
        (target, (240, 100)),
        (Delay(), (90, 100)),
        (Delay(), (170, 100)),
    ):
        window.add_operation(operation, position)
    output = window._drag_buttons[source].port_list[0]
    incoming = window._drag_buttons[target].port_list[0]
    window._connect_button(output, incoming)
    arrow = next(iter(window._arrow_ports))
    path = arrow.path()
    assert path.elementCount() > 1
    assert path.pointAtPercent(0) == output.anchor()
    assert path.pointAtPercent(1) == incoming.anchor()
    assert path.elementAt(1).x == output.anchor().x()
    obstacles = [
        (r.left(), r.top(), r.right(), r.bottom())
        for proxy in window._drag_operation_scenes.values()
        for r in [proxy.sceneBoundingRect()]
    ]
    assert route_is_clear(
        [
            (path.elementAt(i).x, path.elementAt(i).y)
            for i in range(path.elementCount())
        ],
        obstacles,
    )


@pytest.mark.parametrize("horizontal", [False, True])
def test_aligned_ports_connect_directly_when_facing_sideways(qtbot, horizontal):
    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, target = Input(), Output()
    angle = 90 if horizontal else 0
    window.add_operation(source, (0, 0), rotation=angle)
    window.add_operation(
        target, (160, 0) if horizontal else (0, 160), rotation=angle, is_flipped=True
    )
    output = window._drag_buttons[source].port_list[0]
    incoming = window._drag_buttons[target].port_list[0]
    window._connect_button(output, incoming)
    path = next(iter(window._arrow_ports)).path()
    assert path.elementCount() == 2
    assert path.pointAtPercent(0) == output.anchor()
    assert path.pointAtPercent(1) == incoming.anchor()


@pytest.mark.parametrize("connected", [False, True])
def test_wire_avoids_intermediate_port_even_when_box_is_clear(qtbot, connected):
    from test.sfg_gui_helpers import route_is_clear

    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, target, intermediate = Input(), Output(), Input()
    window.add_operation(source, (0, 0))
    window.add_operation(target, (0, 320), is_flipped=True)
    window.add_operation(intermediate, (0, 160))
    port = window._drag_buttons[intermediate].port_list[0]
    if connected:
        other_target = Output()
        window.add_operation(other_target, (240, 160))
        window._connect_button(port, window._drag_buttons[other_target].port_list[0])
    source_port = window._drag_buttons[source].port_list[0]
    target_port = window._drag_buttons[target].port_list[0]
    assert source_port.anchor().x() == port.anchor().x() == target_port.anchor().x()
    window._connect_button(source_port, target_port)
    arrow = next(
        arrow
        for arrow in window._arrow_ports
        if arrow.source_port_button is source_port
    )
    path = arrow.path()
    assert path.length() > 0
    center = port.anchor()
    assert route_is_clear(
        [
            (path.elementAt(i).x, path.elementAt(i).y)
            for i in range(path.elementCount())
        ],
        [(center.x() - 6, center.y() - 6, center.x() + 6, center.y() + 6)],
    )


def test_drag_reuses_remote_routes_and_finishes_with_full_routing(qtbot):

    from b_asic.sfg_gui._preferences import GRID

    window = SFGMainWindow()
    qtbot.addWidget(window)
    sources = []
    for y in (0, 400, 800):
        source, target = Input(), Output()
        sources.append(source)
        window.add_operation(source, (0, y))
        window.add_operation(target, (400, y))
        window._connect_button(
            window._drag_buttons[source].port_list[0],
            window._drag_buttons[target].port_list[0],
        )
    arrows = list(window._arrow_ports)
    original = [arrow.path() for arrow in arrows]
    button = window._drag_buttons[sources[0]]
    button._m_drag = True
    button.graphicsProxyWidget().moveBy(0, GRID)
    window._update()
    assert window._native.engine.routed_ids() == [id(arrows[0])]
    assert [arrow.path() for arrow in arrows[1:]] == original[1:]
    assert arrows[0].path().pointAtPercent(0) == button.port_list[0].anchor()
    button._m_drag = False
    window._update()
    assert set(window._native.engine.routed_ids()) == {id(arrow) for arrow in arrows}
    final = [arrow.path() for arrow in arrows]
    window._reroute_arrows(force=True)
    assert [arrow.path() for arrow in arrows] == final


def test_dragging_unconnected_obstacle_reroutes_intersecting_wire(qtbot):
    from test.sfg_gui_helpers import route_is_clear

    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, target, obstacle = Input(), Output(), SquareRoot()
    for operation, pos in (
        (source, (0, 0)),
        (target, (400, 0)),
        (obstacle, (800, 800)),
    ):
        window.add_operation(operation, pos)
    window._connect_button(
        window._drag_buttons[source].port_list[0],
        window._drag_buttons[target].port_list[0],
    )
    arrow = next(iter(window._arrow_ports))
    before = arrow.path()
    button = window._drag_buttons[obstacle]
    button._m_drag = True
    button.graphicsProxyWidget().setPos(200, -16)
    window._update()
    path = arrow.path()
    assert path != before
    assert path.length() > 0
    rect = button.graphicsProxyWidget().sceneBoundingRect()
    assert route_is_clear(
        [
            (path.elementAt(i).x, path.elementAt(i).y)
            for i in range(path.elementCount())
        ],
        [(rect.left(), rect.top(), rect.right(), rect.bottom())],
    )


def test_drag_updates_shared_trunk_and_pinned_branch_together(qtbot):

    from b_asic.sfg_gui._preferences import GRID

    window, source, _, branch = make_connected_window(qtbot)
    source_port = window._drag_buttons[source].port_list[0]
    window._connect_button(source_port, window._drag_buttons[branch].port_list[0])
    parent, child = list(window._arrow_ports)
    child.branch_parent = parent
    child.branch_fraction = 0.5
    window._update()
    button = window._drag_buttons[branch]
    button._m_drag = True
    button.graphicsProxyWidget().moveBy(GRID, GRID)
    window._update()
    assert set(window._native.engine.routed_ids()) == {id(parent), id(child)}
    prefix = parent.branch_prefix(child.branch_fraction)
    junction = prefix[-1]
    assert any(
        (child.path().elementAt(i).x, child.path().elementAt(i).y) == junction
        for i in range(child.path().elementCount())
    )
    assert child.path().pointAtPercent(1) == child.destination_port_button.anchor()
    assert not window._junction_item.path().isEmpty()
    window._clear_workspace()
    assert window._native.engine.statistics()["nodes"] == 0
    assert window._native.engine.statistics()["ports"] == 0
    assert window._native.engine.statistics()["wires"] == 0


@pytest.mark.parametrize("dragging", [False, True])
def test_flipping_unconnected_port_invalidates_route_cache(qtbot, dragging):
    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, target, obstacle = Input(), Output(), Input()
    window.add_operation(source, (0, 0))
    window.add_operation(target, (0, 320), is_flipped=True)
    window.add_operation(obstacle, (0, 160))
    window._connect_button(
        window._drag_buttons[source].port_list[0],
        window._drag_buttons[target].port_list[0],
    )
    arrow = next(iter(window._arrow_ports))
    assert arrow.path().elementCount() > 2
    button = window._drag_buttons[obstacle]
    button._m_drag = dragging
    button._flip()
    assert arrow.path().elementCount() == 2


def test_covered_terminal_shows_blocked_signal_instead_of_disappearing(qtbot):
    from b_asic.special_operations import Delay

    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, target, obstacle = Input(), Output(), Delay()
    for operation, position in (
        (source, (0, 100)),
        (target, (240, 100)),
        (obstacle, (72, 100)),
    ):
        window.add_operation(operation, position)
    window._connect_button(
        window._drag_buttons[source].port_list[0],
        window._drag_buttons[target].port_list[0],
    )
    arrow = next(iter(window._arrow_ports))
    assert arrow.path().length() > 0
    assert arrow.pen().style() == QtCore.Qt.DashLine
    window._drag_buttons[obstacle].graphicsProxyWidget().moveBy(0, 200)
    window._update()
    assert arrow.path().length() > 0
    assert arrow.pen().style() == QtCore.Qt.SolidLine


def test_coincident_terminals_have_a_visible_signal(qtbot):
    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, target = Input(), Output()
    window.add_operation(source, (0, 100))
    window.add_operation(target, (96, 100))
    output = window._drag_buttons[source].port_list[0]
    incoming = window._drag_buttons[target].port_list[0]
    assert output.anchor() == incoming.anchor()
    window._connect_button(output, incoming)
    arrow = next(iter(window._arrow_ports))
    assert arrow.path().length() > 0
    assert arrow.path().pointAtPercent(0) == output.anchor()
    assert arrow.path().pointAtPercent(1) == incoming.anchor()


def test_fanout_shares_trunk_and_marks_junction(qtbot):
    from itertools import pairwise

    from test.sfg_gui_helpers import overlap_length

    window, source, _, branch = make_connected_window(qtbot)
    window._connect_button(
        window._drag_buttons[source].port_list[0],
        window._drag_buttons[branch].port_list[0],
    )
    window.auto_layout()
    # Use an aligned source/target to exercise a long shared trunk, regardless
    # of the automatic layout's choice of branch centering.
    source_proxy = window._drag_buttons[source].graphicsProxyWidget()
    source_proxy.setPos(0, 0)
    for arrow, y in zip(window._arrow_ports, (0, 200), strict=True):
        target = arrow.destination_operation_button.graphicsProxyWidget()
        target.setPos(500, y)
    window._update()
    paths = []
    for arrow in window._arrow_ports:
        path = arrow.path()
        # The shared trunk can extend well beyond the terminal exit stub.
        points = [
            (path.elementAt(i).x, path.elementAt(i).y)
            for i in range(path.elementCount())
        ]
        paths.append(list(pairwise(points)))
    assert (
        sum(overlap_length(a, b, c, d) for a, b in paths[0] for c, d in paths[1]) > 12
    )
    assert window._junction_item is not None
    assert not window._junction_item.path().isEmpty()
    old_dots = window._junction_item.path()
    for op, button in window._drag_buttons.items():
        if op is not source:
            proxy = window._drag_operation_scenes[button]
            proxy.setPos(proxy.pos() + QtCore.QPointF(100, 0))
    window._update()
    assert window._junction_item.path() != old_dots
    assert not window._junction_item.path().isEmpty()
    # Removing one branch removes the junction marker as well.
    list(window._arrow_ports)[-1].remove()
    assert window._junction_item.path().isEmpty()
    window._clear_workspace()
    assert window._junction_item is None


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ([[(0, 0), (100, 0)], [(0, 0), (60, 0), (60, 40)]], {(60, 0)}),
        (
            [[(0, 0), (40, 0), (40, 80)], [(0, 0), (40, 0), (40, 40), (80, 40)]],
            {(40, 40)},
        ),
        ([[(0, 0), (100, 0)], [(0, 0), (100, 0)]], set()),
        ([[(0, 0), (40, 0), (40, 40)]], set()),
        (
            [
                [(0, 0), (100, 0)],
                [(0, 0), (50, 0), (50, -40)],
                [(0, 0), (80, 0), (80, 40)],
            ],
            {(50, 0), (80, 0)},
        ),
    ],
)
def test_junction_geometry(paths, expected):
    from test.sfg_gui_helpers import junction_points

    assert junction_points(paths) == expected


def test_router_prefers_shared_trunk():
    from itertools import pairwise

    from test.sfg_gui_helpers import overlap_length, route_orthogonal

    trunk = [((0, 0), (300, 0))]
    path = route_orthogonal((0, 0), (300, 100), [], shared=trunk)
    assert (
        sum(overlap_length(a, b, c, d) for a, b in pairwise(path) for c, d in trunk)
        == 300
    )


def test_unrelated_wires_have_no_junctions(qtbot):
    window, _, _, branch = make_connected_window(qtbot)
    other = Input()
    window.add_operation(other, (50, 300))
    window._connect_button(
        window._drag_buttons[other].port_list[0],
        window._drag_buttons[branch].port_list[0],
    )
    assert window._junction_item.path().isEmpty()


@pytest.mark.parametrize(
    ("start", "end", "obstacles"),
    [
        ((0, 0), (100, 0), []),
        ((0, 0), (100, 100), []),
        ((0, 0), (100, 0), [(40, -20, 60, 20)]),
    ],
)
def test_native_simple_routes_have_at_most_two_bends(start, end, obstacles):
    from test import sfg_gui_helpers as routing

    path = routing.route_orthogonal(start, end, obstacles)
    assert path[0] == start
    assert path[-1] == end
    assert len(path) <= 4


def test_obstacle_maze_uses_fallback():
    from itertools import pairwise

    from test import sfg_gui_helpers as routing

    obstacles = [
        (-10, -20, 30, -10),
        (-10, 10, 30, 20),
        (-20, -20, -10, 20),
        (70, -20, 110, -10),
        (70, 10, 110, 20),
        (110, -20, 120, 20),
        (40, -30, 60, 30),
    ]
    path = routing.route_orthogonal((0, 0), (100, 0), obstacles)
    assert path[0] == (0, 0)
    assert path[-1] == (100, 0)
    assert len(path) > 4
    for a, b in pairwise(path):
        assert a[0] == b[0] or a[1] == b[1]
        for left, top, right, bottom in obstacles:
            if a[1] == b[1]:
                assert not (
                    top < a[1] < bottom
                    and max(min(a[0], b[0]), left) < min(max(a[0], b[0]), right)
                )
            else:
                assert not (
                    left < a[0] < right
                    and max(min(a[1], b[1]), top) < min(max(a[1], b[1]), bottom)
                )


@pytest.mark.parametrize(
    "coefficients",
    [[0.1, 0.2, 0.3, 0.4], [0.1, 0.2, 0.3, 0.4, 0.5], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
)
def test_lattice_allpass_branches_stay_separate(qtbot, coefficients):
    import networkx as nx

    from b_asic.sfg_generators.wave_digital_filters import lattice_wdf

    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_sfg(lattice_wdf(coefficients))
    graph = nx.DiGraph()
    graph.add_nodes_from(window._drag_buttons)
    graph.add_edges_from(
        (a.source_operation, a.destination_operation) for a in window._arrow_ports
    )
    condensed = nx.condensation(graph)
    source = next(op for op in graph if isinstance(op, Input))
    fork = condensed.graph["mapping"][source]
    branches = [nx.descendants(condensed, n) | {n} for n in condensed.successors(fork)]
    assert len(branches) == 2
    common = branches[0] & branches[1]
    regions = []
    for branch in branches:
        operations = [
            op for n in branch - common for op in condensed.nodes[n]["members"]
        ]
        rects = [
            window._drag_buttons[op].graphicsProxyWidget().sceneBoundingRect()
            for op in operations
        ]
        regions.append((min(r.top() for r in rects), max(r.bottom() for r in rects)))
    regions.sort()
    assert regions[0][1] + 38 <= regions[1][0]
    from b_asic.special_operations import Delay
    from b_asic.wdf_operations import SymmetricTwoportAdaptor

    for component in nx.strongly_connected_components(graph):
        if len(component) >= 4:
            adaptors = [
                window._drag_buttons[op].graphicsProxyWidget().sceneBoundingRect()
                for op in component
                if isinstance(op, SymmetricTwoportAdaptor)
            ]
            delays = [
                window._drag_buttons[op].graphicsProxyWidget().sceneBoundingRect()
                for op in component
                if isinstance(op, Delay)
            ]
            assert len({rect.center().x() for rect in adaptors}) == 1
            assert len({rect.center().y() for rect in adaptors}) > 1
            assert all(
                delay.left() > max(rect.right() for rect in adaptors)
                for delay in delays
            )
    rects = [
        proxy.sceneBoundingRect() for proxy in window._drag_operation_scenes.values()
    ]
    assert all(
        not rect.intersects(other)
        for i, rect in enumerate(rects)
        for other in rects[i + 1 :]
    )
    original = {
        op: button.graphicsProxyWidget().pos()
        for op, button in window._drag_buttons.items()
    }
    window.auto_layout()
    assert all(
        window._drag_buttons[op].graphicsProxyWidget().pos() == position
        for op, position in original.items()
    )


def test_placement_separates_disconnected_graphs_and_orients_forward(qtbot):
    window = SFGMainWindow()
    qtbot.addWidget(window)
    sources, outputs = [Input(), Input()], [Output(), Output()]
    for op in (*sources, *outputs):
        window.add_operation(op)
    for source, output in zip(sources, outputs, strict=True):
        window._connect_button(
            window._drag_buttons[source].port_list[0],
            window._drag_buttons[output].port_list[0],
        )
    button = window._drag_buttons[sources[0]]
    button._flip()
    button.set_rotation(90)
    window.auto_layout()
    assert not button.is_flipped()
    assert button.rotation_angle() == 0
    regions = []
    for source, output in zip(sources, outputs, strict=True):
        rects = [
            window._drag_buttons[op].graphicsProxyWidget().sceneBoundingRect()
            for op in (source, output)
        ]
        regions.append((min(r.top() for r in rects), max(r.bottom() for r in rects)))
    regions.sort()
    assert regions[0][1] < regions[1][0]


def test_feedback_delays_are_parallel_and_flipped(qtbot):
    from b_asic.core_operations import Addition
    from b_asic.sfg import SFG
    from b_asic.special_operations import Delay

    source = Input()
    add = Addition(source)
    delay = Delay(add)
    add.input(1).connect(delay)
    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_sfg(SFG(inputs=[source], outputs=[Output(add)]))
    delay_button = next(
        b for op, b in window._drag_buttons.items() if isinstance(op, Delay)
    )
    add_button = next(
        b for op, b in window._drag_buttons.items() if isinstance(op, Addition)
    )
    assert delay_button.is_flipped()
    assert delay_button.rotation_angle() == 0
    assert delay_button.port_list[1].scene_direction() == (-1, 0)
    delay_rect = delay_button.graphicsProxyWidget().sceneBoundingRect()
    add_rect = add_button.graphicsProxyWidget().sceneBoundingRect()
    assert delay_rect.center().x() == add_rect.center().x()
    assert delay_rect.top() > add_rect.bottom()
    for op, button in window._drag_buttons.items():
        if not isinstance(op, Delay):
            assert button.rotation_angle() == 0
            assert not button.is_flipped()


def test_orientation_can_rotate_vertical_feedback_delay():
    from b_asic import _sfg_gui as native

    result = native.choose_orientations(
        3,
        [(0, 1), (1, 2)],
        [(0, 0), (0, 100), (0, 200)],
        [(57, 57)] * 3,
        [False, True, False],
        19,
    )
    assert result[1] == (90, False)
    assert result[0] == (0, False)


def make_branching_window(qtbot):
    window, source, _, branch = make_connected_window(qtbot)
    parent = next(iter(window._arrow_ports))
    parent.destination_operation_button.graphicsProxyWidget().setPos(500, 57)
    target = window._drag_buttons[branch].port_list[0]
    target._operation_button.graphicsProxyWidget().setPos(500, 220)
    window._update()
    window._zoom_to_fit()
    qtbot.wait(10)
    return window, source, parent, target


@pytest.mark.parametrize("drag", [False, True])
def test_start_branch_anywhere_on_wire(qtbot, drag):
    window, source, parent, target = make_branching_window(qtbot)
    view = window._graphics_view
    point = parent.path().pointAtPercent(0.6)
    if drag:
        qtbot.mousePress(
            view.viewport(), QtCore.Qt.LeftButton, pos=view.mapFromScene(point)
        )
        qtbot.mouseMove(view.viewport(), view.mapFromScene(target.anchor()))
        qtbot.mouseRelease(
            view.viewport(),
            QtCore.Qt.LeftButton,
            pos=view.mapFromScene(target.anchor()),
        )
    else:
        qtbot.mouseClick(
            view.viewport(), QtCore.Qt.LeftButton, pos=view.mapFromScene(point)
        )
        assert window._branch_start[0] is parent
        preview = window._connection_preview.path().elementAt(0)
        assert (preview.x, preview.y) == pytest.approx((point.x(), point.y()), abs=1)
        click_port(qtbot, window, target)
    child = list(window._arrow_ports)[-1]
    assert len(window._arrow_ports) == 2
    assert child.branch_parent is parent
    assert child.branch_fraction == pytest.approx(0.6, abs=0.01)
    assert child.signal.source.operation is source
    junction = QtCore.QPointF(*parent.branch_prefix(child.branch_fraction)[-1])
    assert window._junction_item.path().contains(junction)
    assert window._starting_port is None
    # The chosen junction stays on its parent after moving an endpoint.
    proxy = parent.destination_operation_button.graphicsProxyWidget()
    proxy.setX(proxy.x() + 100)
    window._update()
    moved_junction = QtCore.QPointF(*parent.branch_prefix(child.branch_fraction)[-1])
    assert window._junction_item.path().contains(moved_junction)
    assert moved_junction != junction
    parent.remove()
    assert child.branch_parent is None
    assert not child.path().isEmpty()


def test_cancel_wire_branch(qtbot):
    window, _, parent, _ = make_branching_window(qtbot)
    view = window._graphics_view
    point = parent.path().pointAtPercent(0.5)
    qtbot.mouseClick(
        view.viewport(), QtCore.Qt.LeftButton, pos=view.mapFromScene(point)
    )
    assert window._branch_start is not None
    qtbot.keyClick(window, QtCore.Qt.Key_Escape)
    assert window._branch_start is None
    assert window._starting_port is None
    assert len(window._arrow_ports) == 1


@pytest.mark.parametrize(
    "adaptor_name",
    [
        "SymmetricTwoportAdaptor",
        "SeriesTwoportAdaptor",
        "ParallelTwoportAdaptor",
        "SeriesThreeportAdaptor",
        "ReflectionFreeSeriesThreeportAdaptor",
    ],
)
def test_adaptor_icon_survives_selection(qtbot, adaptor_name):
    import b_asic.wdf_operations as wdf

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = getattr(wdf, adaptor_name)()
    window.add_operation(operation)
    button = window._drag_buttons[operation]
    key = button.icon().cacheKey()
    for _ in range(2):
        qtbot.mouseClick(button, QtCore.Qt.LeftButton)
        assert button.icon().cacheKey() == key
        pixmap = button.icon().pixmap(64, 64)
        assert not pixmap.isNull()
        image = pixmap.toImage()
        assert any(image.pixelColor(x, y).alpha() for x in range(64) for y in range(64))


def test_svg_icons_render_and_custom_fallback(qtbot):
    from pathlib import Path

    from qtpy.QtCore import Qt
    from qtpy.QtGui import QImage, QPainter
    from qtpy.QtSvg import QSvgRenderer

    from b_asic.sfg_gui import operation_icon as icons

    directory = Path(icons.__file__).with_name("operation_icons")
    for path in directory.glob("*.svg"):
        assert "<image" not in path.read_text(), path.name
        renderer = QSvgRenderer(str(path))
        assert renderer.isValid(), path.name
        image = QImage(64, 64, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        assert any(
            image.pixelColor(x, y).alpha() for x in range(64) for y in range(64)
        ), path.name
    fallback = icons.operation_icon("unknown_custom_type").pixmap(64, 64)
    assert not fallback.isNull()
    assert (
        fallback.toImage()
        == icons.operation_icon("custom_operation").pixmap(64, 64).toImage()
    )
    # The delay glyph is drawn with two vector strokes forming T.
    assert "M15 14H49M32 14V50" in (directory / "t.svg").read_text()


@pytest.mark.parametrize("operation_name", ["DontCare", "Sink"])
def test_unused_terminals_have_circular_bodies_without_symbols(qtbot, operation_name):
    from qtpy.QtGui import QColor, QImage, QPainter

    from b_asic import utility_operations
    from b_asic.sfg_gui._preferences import PORT_STUB, PORTHEIGHT

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = getattr(utility_operations, operation_name)()
    window.add_operation(operation, (100, 100))
    button = window._drag_buttons[operation]
    assert button.width() == button.height() == PORTHEIGHT
    assert button._symbol is None
    assert button._circular_body is not None

    for selected in (False, True):
        button._toggle_button(not selected)
        image = QImage(190, 190, QImage.Format_ARGB32)
        image.fill(QtCore.Qt.green)
        painter = QPainter(image)
        window._scene.render(
            painter,
            QtCore.QRectF(0, 0, 190, 190),
            button.graphicsProxyWidget().sceneBoundingRect(),
        )
        painter.end()
        assert image.pixelColor(95, 95) == QColor(
            QtCore.Qt.gray if selected else QtCore.Qt.white
        )
        for x, y in ((0, 0), (189, 0), (0, 189), (189, 189)):
            assert image.pixelColor(x, y) == QColor(QtCore.Qt.green)

    port = button.port_list[0]
    assert port.y() == button.height() / 2
    expected_x = -PORT_STUB if operation_name == "Sink" else button.width() + PORT_STUB
    assert port.x() == expected_x
    button.set_rotation(90)
    button._flip()
    assert button._symbol is None
    assert button._circular_body.rect().width() == PORTHEIGHT - 2


@pytest.mark.parametrize("operation_type", [Input, Output])
@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("flipped", [False, True])
def test_input_output_use_road_sign_bodies(qtbot, operation_type, angle, flipped):
    from qtpy.QtGui import QColor, QImage, QPainter

    from b_asic.sfg_gui._preferences import MINBUTTONSIZE, PORT_STUB

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = operation_type()
    window.add_operation(operation, (100, 100), rotation=angle, is_flipped=flipped)
    button = window._drag_buttons[operation]
    assert button.width() == MINBUTTONSIZE
    assert button.height() == MINBUTTONSIZE // 2
    assert button._symbol is None
    body = button._road_sign_body
    assert body is not None
    right = (operation_type is Input) != flipped
    tip_x = button.width() - 3 if right else 3
    assert body.path().contains(QtCore.QPointF(tip_x, button.height() / 2))
    corner = QtCore.QPointF(tip_x, 3)
    assert not body.path().contains(corner)
    port = button.port_list[0]
    assert port.x() == (button.width() + PORT_STUB if right else -PORT_STUB)
    assert port.y() == button.height() / 2

    proxy = button.graphicsProxyWidget()
    source = proxy.sceneBoundingRect()
    for selected in (False, True):
        button._toggle_button(not selected)
        image = QImage(
            round(source.width() * 4), round(source.height() * 4), QImage.Format_ARGB32
        )
        image.fill(QtCore.Qt.green)
        painter = QPainter(image)
        window._scene.render(painter, QtCore.QRectF(image.rect()), source)
        painter.end()
        assert image.pixelColor(image.width() // 2, image.height() // 2) == QColor(
            QtCore.Qt.gray if selected else QtCore.Qt.white
        )
        position = proxy.mapToScene(corner) - source.topLeft()
        assert image.pixelColor(
            round(position.x() * 4), round(position.y() * 4)
        ) == QColor(QtCore.Qt.green)
    original = body.path()
    button._flip()
    assert body.path() != original
    button._flip()
    assert body.path() == original


@pytest.mark.parametrize("operation_name", ["Delay", "SquareRoot", "Addition"])
def test_scene_symbols_render_as_vectors_at_high_zoom(qtbot, operation_name):
    from qtpy.QtGui import QImage, QPainter
    from qtpy.QtSvg import QSvgRenderer
    from qtpy.QtWidgets import QGraphicsItem

    import b_asic
    from b_asic.sfg_gui.operation_icon import operation_svg_path

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = getattr(b_asic, operation_name)()
    window.add_operation(operation, (100, 100), rotation=90)
    symbol = window._drag_buttons[operation]._symbol
    assert symbol.cacheMode() == QGraphicsItem.NoCache
    assert symbol.acceptedMouseButtons() == QtCore.Qt.NoButton

    # A scene zoom must retain the same detail as rendering the SVG directly at
    # the target resolution, rather than enlarging a button-sized icon pixmap.
    actual = QImage(768, 768, QImage.Format_ARGB32)
    actual.fill(QtCore.Qt.white)
    painter = QPainter(actual)
    window._scene.render(
        painter, QtCore.QRectF(0, 0, 768, 768), symbol.sceneBoundingRect()
    )
    painter.end()

    expected = QImage(768, 768, QImage.Format_ARGB32)
    expected.fill(QtCore.Qt.white)
    painter = QPainter(expected)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer = QSvgRenderer(str(operation_svg_path(operation.type_name())))
    renderer.render(painter)
    painter.end()
    assert actual == expected


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("flipped", [False, True])
def test_port_arrowheads_follow_signal_direction(qtbot, angle, flipped):
    from unittest.mock import Mock

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = SquareRoot()
    window.add_operation(operation, rotation=angle, is_flipped=flipped)
    button = window._drag_buttons[operation]
    expected = [(1, 0), (0, 1), (-1, 0), (0, -1)][angle // 90]
    if flipped:
        expected = (-expected[0], -expected[1])
    for port in button.port_list:
        painter = Mock()
        port.paint(painter, None)
        lines = painter.drawLine.call_args_list
        assert len(lines) == 3  # Stem and the two sides of its arrowhead.
        base = (lines[1].args[0] + lines[2].args[0]) * 0.5
        tip = lines[1].args[1]
        vector = port.mapToScene(tip) - port.mapToScene(base)
        norm = max(abs(vector.x()), abs(vector.y()))
        assert (vector.x() / norm, vector.y() / norm) == pytest.approx(expected)


@pytest.mark.parametrize(
    "adaptor_name",
    [
        "SymmetricTwoportAdaptor",
        "SeriesTwoportAdaptor",
        "ParallelTwoportAdaptor",
        "SeriesThreeportAdaptor",
        "ReflectionFreeSeriesThreeportAdaptor",
    ],
)
@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("flipped", [False, True])
def test_adaptor_input_output_pairs(qtbot, adaptor_name, angle, flipped):
    from unittest.mock import Mock

    import b_asic.wdf_operations as wdf
    from b_asic.sfg_gui._preferences import PORTHEIGHT

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = getattr(wdf, adaptor_name)()
    window.add_operation(operation, rotation=angle, is_flipped=flipped)
    button = window._drag_buttons[operation]
    for index in range(operation.input_count):
        incoming = button.port_list[index]
        outgoing = button.port_list[operation.input_count + index]
        dx, dy = [(-1, 0), (1, 0), (0, 1)][index]
        if flipped:
            dx = -dx
        expected = [(dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx)][angle // 90]
        assert incoming.scene_direction() == expected
        assert outgoing.scene_direction() == expected
        delta = incoming.anchor() - outgoing.anchor()
        side_length = button.width() if index == 2 else button.height()
        assert delta.manhattanLength() == pytest.approx(side_length - 2 * PORTHEIGHT)
        coordinates = (
            [incoming.x(), outgoing.x()] if index == 2 else [incoming.y(), outgoing.y()]
        )
        assert sorted(coordinates) == pytest.approx(
            [PORTHEIGHT, side_length - PORTHEIGHT]
        )
        assert not incoming.sceneBoundingRect().intersects(outgoing.sceneBoundingRect())
        for port, sign in ((incoming, -1), (outgoing, 1)):
            painter = Mock()
            port.paint(painter, None)
            lines = painter.drawLine.call_args_list
            base = (lines[1].args[0] + lines[2].args[0]) * 0.5
            vector = port.mapToScene(lines[1].args[1]) - port.mapToScene(base)
            norm = max(abs(vector.x()), abs(vector.y()))
            assert (vector.x() / norm, vector.y() / norm) == pytest.approx(
                (expected[0] * sign, expected[1] * sign)
            )


@pytest.mark.parametrize("angle", [0, 90])
@pytest.mark.parametrize("flipped", [False, True])
def test_routes_connect_to_paired_adaptor_ports(qtbot, angle, flipped):
    from itertools import pairwise

    from b_asic.wdf_operations import SeriesThreeportAdaptor

    window = SFGMainWindow()
    qtbot.addWidget(window)
    adaptor = SeriesThreeportAdaptor()
    window.add_operation(adaptor, (400, 300), is_flipped=flipped, rotation=angle)
    button = window._drag_buttons[adaptor]
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    for index in range(3):
        incoming = button.port_list[index]
        outgoing = button.port_list[index + 3]
        dx, dy = incoming.scene_direction()
        anchor = incoming.anchor()
        source, target = Input(), Output()
        window.add_operation(
            source,
            (anchor.x() + dx * 250 - dy * 80, anchor.y() + dy * 250 + dx * 80),
            rotation=directions.index((-dx, -dy)) * 90,
        )
        window.add_operation(
            target,
            (anchor.x() + dx * 250 + dy * 80, anchor.y() + dy * 250 - dx * 80),
            rotation=directions.index((dx, dy)) * 90,
        )
        window._connect_button(window._drag_buttons[source].port_list[0], incoming)
        window._connect_button(outgoing, window._drag_buttons[target].port_list[0])
    window._update()
    assert len(window._arrow_ports) == 6
    for arrow in window._arrow_ports:
        path = arrow.path()
        assert not path.isEmpty()
        assert path.pointAtPercent(0) == arrow.source_port_button.anchor()
        assert path.pointAtPercent(1) == arrow.destination_port_button.anchor()
        points = [
            (path.elementAt(i).x, path.elementAt(i).y)
            for i in range(path.elementCount())
        ]
        assert all(a[0] == b[0] or a[1] == b[1] for a, b in pairwise(points))


@pytest.mark.parametrize(
    "adaptor_name",
    ["SymmetricTwoportAdaptor", "SeriesTwoportAdaptor", "ParallelTwoportAdaptor"],
)
def test_twoport_default_has_top_bottom_pairs_reading_left_to_right(
    qtbot, adaptor_name
):
    import b_asic.wdf_operations as wdf

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = getattr(wdf, adaptor_name)()
    window.add_operation(operation)
    button = window._drag_buttons[operation]
    for automatic in (False, True):
        if automatic:
            button.set_rotation(270)
            button._flip()
            window.auto_layout()
        assert button.rotation_angle() == 90
        assert not button.is_flipped()
        rect = button.graphicsProxyWidget().sceneBoundingRect()
        for index, side in ((0, (0, -1)), (1, (0, 1))):
            incoming, outgoing = button.port_list[index], button.port_list[index + 2]
            assert incoming.scene_direction() == side
            assert outgoing.scene_direction() == side
            assert incoming.anchor().x() < outgoing.anchor().x()
            assert incoming.anchor().y() == pytest.approx(outgoing.anchor().y())
            if index == 0:
                assert incoming.anchor().y() < rect.top()
            else:
                assert incoming.anchor().y() > rect.bottom()


def test_saved_explicit_twoport_rotation_overrides_default(qtbot):
    from b_asic.sfg_generators.wave_digital_filters import lattice_wdf
    from b_asic.wdf_operations import SymmetricTwoportAdaptor

    graph = lattice_wdf([0.1, 0.2, 0.3, 0.4])
    positions = {
        op.graph_id: (i * 133, 57, False, 0) for i, op in enumerate(graph.split())
    }
    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_sfg(graph, positions)
    adaptors = [
        button
        for op, button in window._drag_buttons.items()
        if isinstance(op, SymmetricTwoportAdaptor)
    ]
    assert adaptors
    assert all(button.rotation_angle() == 0 for button in adaptors)
    window.auto_layout()
    assert all(button.rotation_angle() == 90 for button in adaptors)


@pytest.mark.parametrize(
    "operation_name", ["Delay", "SquareRoot", "ConstantMultiplication"]
)
@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_operation_glyph_remains_upright_when_box_rotates(qtbot, operation_name, angle):
    from qtpy.QtGui import QImage, QPainter

    import b_asic

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = getattr(b_asic, operation_name)()
    window.add_operation(operation, (100, 100), rotation=0)
    button = window._drag_buttons[operation]
    proxy = button.graphicsProxyWidget()

    def render():
        image = QImage(64, 64, QImage.Format_ARGB32)
        image.fill(QtCore.Qt.white)
        painter = QPainter(image)
        window._scene.render(
            painter, QtCore.QRectF(0, 0, 64, 64), proxy.sceneBoundingRect()
        )
        painter.end()
        return image

    baseline = render()
    button.set_rotation(angle)
    actual = render()
    # Compare the glyph area, excluding the rotating border and port terminals.
    differences = [
        abs(actual.pixelColor(x, y).red() - baseline.pixelColor(x, y).red())
        for x in range(12, 52)
        for y in range(12, 52)
    ]
    assert sum(differences) / len(differences) < 3
    button._flip()
    flipped = render()
    assert all(
        flipped.pixelColor(x, y) == actual.pixelColor(x, y)
        for x in range(12, 52)
        for y in range(12, 52)
    )


def test_wdf_and_fft_operation_palettes(qtbot):
    from b_asic.fft_operations import R2Butterfly
    from b_asic.wdf_operations import SymmetricTwoportAdaptor

    window = SFGMainWindow()
    qtbot.addWidget(window)
    expected_wdf = {
        "SymmetricTwoportAdaptor",
        "SeriesTwoportAdaptor",
        "ParallelTwoportAdaptor",
        "SeriesThreeportAdaptor",
        "ReflectionFreeSeriesThreeportAdaptor",
    }
    wdf_list, fft_list = window._ui.wdf_operations_list, window._ui.fft_operations_list

    def names(widget):
        return [widget.item(i).text() for i in range(widget.count())]

    assert set(names(wdf_list)) == expected_wdf
    assert "R2Butterfly" in names(fft_list)
    assert "Addition" not in names(fft_list)
    assert "_Adaptor" not in names(wdf_list)
    for palette, name, kind in (
        (wdf_list, "SymmetricTwoportAdaptor", SymmetricTwoportAdaptor),
        (fft_list, "R2Butterfly", R2Butterfly),
    ):
        item = palette.item(names(palette).index(name))
        palette.itemClicked.emit(item)
        assert any(isinstance(op, kind) for op in window._drag_buttons)
    original = (names(wdf_list), names(fft_list))
    window._refresh_operations_list_from_namespace()
    assert (names(wdf_list), names(fft_list)) == original
    toolbox = window._ui.operation_list
    assert (
        toolbox.itemText(toolbox.indexOf(window._ui.wdf_operations_page))
        == "WDF operations"
    )
    assert (
        toolbox.itemText(toolbox.indexOf(window._ui.fft_operations_page))
        == "FFT operations"
    )


def test_reflection_free_marker_tracks_port_side(qtbot):
    from b_asic.wdf_operations import ReflectionFreeSeriesThreeportAdaptor

    window = SFGMainWindow()
    qtbot.addWidget(window)
    operation = ReflectionFreeSeriesThreeportAdaptor()
    window.add_operation(operation)
    button = window._drag_buttons[operation]
    marker = button._reflection_marker
    assert marker is not None
    for flipped in (False, True):
        if flipped:
            button._flip()
        for angle in (0, 90, 180, 270):
            button.set_rotation(angle)
            port = button.port_list[1]
            dx, dy = port.scene_direction()
            center = button.graphicsProxyWidget().sceneBoundingRect().center()
            position = marker.mapToScene(marker.path().boundingRect().center())
            body = button.graphicsProxyWidget().sceneBoundingRect()
            assert not body.contains(position)
            output = button.port_list[button.operation.input_count + 1]
            pair_center = (port.anchor() + output.anchor()) * 0.5
            assert (pair_center - position).manhattanLength() < 12
            assert (position.x() - center.x()) * dx + (
                position.y() - center.y()
            ) * dy > 0


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_adaptor_dimensions_match_io_sides(qtbot, angle):
    from b_asic.wdf_operations import SeriesThreeportAdaptor, SymmetricTwoportAdaptor

    window = SFGMainWindow()
    qtbot.addWidget(window)
    twoport, threeport = SymmetricTwoportAdaptor(), SeriesThreeportAdaptor()
    window.add_operation(twoport, (100, 100), rotation=angle)
    window.add_operation(threeport, (400, 100), rotation=angle)
    button = window._drag_buttons[twoport]
    rect = button.graphicsProxyWidget().sceneBoundingRect()
    square = window._drag_buttons[threeport].graphicsProxyWidget().sceneBoundingRect()
    assert square.width() == pytest.approx(square.height())
    assert max(rect.width(), rect.height()) == pytest.approx(square.width())
    assert max(rect.width(), rect.height()) > 1.5 * min(rect.width(), rect.height())
    dx, _ = button.port_list[0].scene_direction()
    if dx:
        assert rect.height() > rect.width()
    else:
        assert rect.width() > rect.height()


def test_free_placement_avoids_large_adaptor_boxes(qtbot):
    from b_asic.wdf_operations import SeriesThreeportAdaptor, SymmetricTwoportAdaptor

    window = SFGMainWindow()
    qtbot.addWidget(window)
    for op in (
        SymmetricTwoportAdaptor(),
        SeriesThreeportAdaptor(),
        SymmetricTwoportAdaptor(),
        Input(),
    ):
        window.add_operation(op)
    rects = [
        proxy.sceneBoundingRect() for proxy in window._drag_operation_scenes.values()
    ]
    assert all(not a.intersects(b) for i, a in enumerate(rects) for b in rects[i + 1 :])


def test_reflection_free_symbol_does_not_include_port_marker(qtbot):
    from b_asic.sfg_gui.operation_icon import operation_icon

    assert (
        operation_icon("rfs3p").pixmap(64, 64).toImage()
        == operation_icon("ser3p").pixmap(64, 64).toImage()
    )


@pytest.mark.parametrize("zoom", [0.17, 0.37, 0.63, 1.23])
def test_middle_pan_keeps_grabbed_point_when_view_adjusts(qtbot, zoom):
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication

    window, _, _, _ = make_connected_window(qtbot)
    view = window._graphics_view
    view.scale(zoom, zoom)
    start = view.viewport().rect().center() - QtCore.QPoint(90, 60)
    grabbed = view.mapToScene(start)
    qtbot.mousePress(view.viewport(), QtCore.Qt.MiddleButton, pos=start)
    position = start + QtCore.QPoint(40, 30)
    qtbot.mouseMove(view.viewport(), position)
    # A scroll offset adjustment must not become extra movement on the next
    # event. Keep the original scene point under the pointer throughout the grab.
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() + 13)
    view.verticalScrollBar().setValue(view.verticalScrollBar().value() - 9)
    for _ in range(5):
        event = QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(position),
            QtCore.QPointF(view.viewport().mapToGlobal(position)),
            QtCore.Qt.NoButton,
            QtCore.Qt.MiddleButton,
            QtCore.Qt.NoModifier,
        )
        QApplication.sendEvent(view.viewport(), event)
        qtbot.wait(1)
        delta = view.mapFromScene(grabbed) - position
        assert delta.manhattanLength() <= 1
    qtbot.mouseRelease(view.viewport(), QtCore.Qt.MiddleButton, pos=position)
    before = view.mapFromScene(grabbed)
    qtbot.mouseMove(view.viewport(), position + QtCore.QPoint(40, 30))
    assert view.mapFromScene(grabbed) == before


@pytest.mark.parametrize("order", [2, 3, 5])
def test_return_to_entry_loop_stacks_with_terminals_at_head(qtbot, order):
    from itertools import pairwise

    from b_asic.sfg_generators.wave_digital_filters import richards
    from b_asic.special_operations import Delay
    from b_asic.wdf_operations import SymmetricTwoportAdaptor

    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_sfg(richards([0.1 + 0.05 * n for n in range(order)]))
    adaptors = [
        b
        for op, b in window._drag_buttons.items()
        if isinstance(op, SymmetricTwoportAdaptor)
    ]
    adaptors.sort(key=lambda b: b.graphicsProxyWidget().sceneBoundingRect().top())
    rects = [b.graphicsProxyWidget().sceneBoundingRect() for b in adaptors]
    assert len({rect.center().x() for rect in rects}) == 1
    assert all(a.bottom() < b.top() for a, b in pairwise(rects))
    source = next(b for op, b in window._drag_buttons.items() if isinstance(op, Input))
    output = next(b for op, b in window._drag_buttons.items() if isinstance(op, Output))
    assert source.port_list[0].anchor().y() == output.port_list[0].anchor().y()
    assert (
        source.graphicsProxyWidget().sceneBoundingRect().center().y() < rects[0].top()
    )
    for op, button in window._drag_buttons.items():
        if isinstance(op, Delay):
            assert (
                button.graphicsProxyWidget().sceneBoundingRect().left()
                > rects[0].right()
            )
    original = {
        op: (
            b.graphicsProxyWidget().sceneBoundingRect(),
            b.rotation_angle(),
            b.is_flipped(),
        )
        for op, b in window._drag_buttons.items()
    }
    window.auto_layout()
    assert original == {
        op: (
            b.graphicsProxyWidget().sceneBoundingRect(),
            b.rotation_angle(),
            b.is_flipped(),
        )
        for op, b in window._drag_buttons.items()
    }


def test_local_sources_and_terminals_follow_actual_pin_heights(qtbot):
    from b_asic.core_operations import Addition, Constant
    from b_asic.utility_operations import DontCare, Sink

    window = SFGMainWindow()
    qtbot.addWidget(window)
    source, first, second = Input(), SquareRoot(), SquareRoot()
    constant, dontcare = Constant(2), DontCare()
    add, finish, output, sink = Addition(), Addition(), Output(), Sink()
    for op in (source, first, second, constant, dontcare, add, finish, output, sink):
        window.add_operation(op)

    def connect(a, b, index=0):
        window._connect_button(
            window._drag_buttons[a].port_list[a.input_count],
            window._drag_buttons[b].port_list[index],
        )

    for a, b, index in [
        (source, first, 0),
        (first, second, 0),
        (second, add, 0),
        (constant, add, 1),
        (add, finish, 0),
        (dontcare, finish, 1),
        (finish, output, 0),
        (finish, sink, 0),
    ]:
        connect(a, b, index)
    window.auto_layout()
    for arrow in window._arrow_ports:
        if arrow.source_operation in (
            constant,
            dontcare,
        ) or arrow.destination_operation in (output, sink):
            assert (
                arrow.source_port_button.anchor().y()
                == arrow.destination_port_button.anchor().y()
            )
    for op in (constant, dontcare):
        assert (
            window._drag_buttons[op].graphicsProxyWidget().sceneBoundingRect().left()
            > window._drag_buttons[first]
            .graphicsProxyWidget()
            .sceneBoundingRect()
            .right()
        )
    rects = [
        b.graphicsProxyWidget().sceneBoundingRect()
        for b in window._drag_buttons.values()
    ]
    assert all(not a.intersects(b) for i, a in enumerate(rects) for b in rects[i + 1 :])


def test_sink_can_follow_left_facing_feedback_port(qtbot):
    from b_asic.core_operations import Addition
    from b_asic.sfg import SFG
    from b_asic.special_operations import Delay
    from b_asic.utility_operations import Sink

    source = Input()
    add = Addition(source)
    delay = Delay(add)
    add.input(1).connect(delay)
    Sink(delay)
    window = SFGMainWindow()
    qtbot.addWidget(window)
    window._load_sfg(SFG(inputs=[source], outputs=[Output(add)]))
    sink = next(b for op, b in window._drag_buttons.items() if isinstance(op, Sink))
    delay_button = next(
        b for op, b in window._drag_buttons.items() if isinstance(op, Delay)
    )
    assert (
        sink.graphicsProxyWidget().sceneBoundingRect().right()
        < delay_button.graphicsProxyWidget().sceneBoundingRect().left()
    )
    assert sink.port_list[0].anchor().y() == delay_button.port_list[1].anchor().y()


def test_terminal_kinds_are_defined_by_native_extension():
    from b_asic._sfg_gui import TerminalKind
    from b_asic.core_operations import Constant
    from b_asic.sfg_gui.native import _terminal_kind
    from b_asic.utility_operations import DontCare, Sink

    assert TerminalKind.__module__ == "b_asic._sfg_gui"
    for operation, kind in [
        (Input(), TerminalKind.INPUT),
        (Output(), TerminalKind.OUTPUT),
        (Sink(), TerminalKind.SINK),
        (Constant(1), TerminalKind.LOCAL_SOURCE),
        (DontCare(), TerminalKind.LOCAL_SOURCE),
        (SquareRoot(), TerminalKind.OPERATION),
    ]:
        assert _terminal_kind(operation) == kind
