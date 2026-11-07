import pytest

try:
    from qtpy import QtCore
    from qtpy.QtWidgets import QInputDialog

    from b_asic.sfg_gui.main_window import SFGMainWindow
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")

from b_asic.core_operations import SquareRoot
from b_asic.special_operations import Input, Output


def test_start(qtbot):
    widget = SFGMainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


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


def test_click_connect_preview_and_cancel(qtbot):
    window, source, _, branch = make_connected_window(qtbot)
    output = window._drag_buttons[source].port_list[0]
    target = window._drag_buttons[branch].port_list[0]
    click_port(qtbot, window, output)
    assert window._starting_port is output
    view = window._graphics_view
    qtbot.mouseMove(view.viewport(), view.mapFromScene(target.anchor()))
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
    old_path = arrow.path()
    obstacle = window._drag_operation_scenes[window._drag_buttons[branch]]
    obstacle.setPos(old_path.pointAtPercent(0.5) - QtCore.QPointF(28, 28))
    qtbot.wait(20)
    assert arrow.path() != old_path
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

    from b_asic.sfg_gui.routing import route_orthogonal

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
    assert (second.x - first.x, second.y - first.y) == (
        expected[0] * 12,
        expected[1] * 12,
    )
    for i in range(1, path.elementCount()):
        a, b = path.elementAt(i - 1), path.elementAt(i)
        assert a.x == b.x or a.y == b.y
    button.set_rotation(angle + 360)
    assert button.rotation_angle() == angle


def test_rotation_shortcuts(qtbot):
    window, source, _, _ = make_connected_window(qtbot)
    button = window._drag_buttons[source]
    button.select_button()
    qtbot.keyClick(window, QtCore.Qt.Key_R)
    assert button.rotation_angle() == 90
    qtbot.keyClick(window, QtCore.Qt.Key_R, QtCore.Qt.ShiftModifier)
    assert button.rotation_angle() == 0
    for _ in range(4):
        button.rotate_clockwise()
    assert button.rotation_angle() == 0


def test_rotation_saved_and_loaded(qtbot, datadir, tmp_path, monkeypatch):
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
        expected[op.graph_id] = button.rotation_angle()
    window.sfg_widget = SimpleNamespace(sfg=graph)
    path = tmp_path / "rotated_graph.py"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), True))
    window._save_work()
    graph, positions = python_to_sfg(str(path))
    other = SFGMainWindow()
    qtbot.addWidget(other)
    other._load_sfg(graph, positions)
    assert {
        op.graph_id: b.rotation_angle() for op, b in other._drag_buttons.items()
    } == expected


def test_router_separates_collinear_wires():
    from itertools import pairwise

    from b_asic.sfg_gui.routing import overlap_length, route_orthogonal

    occupied = [((-20, 0), (120, 0))]
    path = route_orthogonal((0, 0), (100, 0), [], occupied)
    assert path[0] == (0, 0)
    assert path[-1] == (100, 0)
    assert len(path) >= 4
    assert all(
        overlap_length(a, b, c, d) == 0 for a, b in pairwise(path) for c, d in occupied
    )


def test_fanout_shares_trunk_and_marks_junction(qtbot):
    from itertools import pairwise

    from b_asic.sfg_gui.routing import overlap_length

    window, source, _, branch = make_connected_window(qtbot)
    window._connect_button(
        window._drag_buttons[source].port_list[0],
        window._drag_buttons[branch].port_list[0],
    )
    window.auto_layout()
    paths = []
    for arrow in window._arrow_ports:
        path = arrow.path()
        # The shared trunk can extend well beyond the terminal exit stub.
        points = [
            (path.elementAt(i).x, path.elementAt(i).y)
            for i in range(1, path.elementCount())
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
    from b_asic.sfg_gui.routing import junction_points

    assert junction_points(paths) == expected


def test_router_prefers_shared_trunk():
    from itertools import pairwise

    from b_asic.sfg_gui.routing import overlap_length, route_orthogonal

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
