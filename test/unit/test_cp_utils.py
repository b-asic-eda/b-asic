"""Shared CP solve handling and interrupted incumbent recovery."""

import pytest

from b_asic._cp_utils import _solve_cp_problem

cp = pytest.importorskip("cpmpy")
pytest.importorskip("ortools.sat.python.cp_model")

from cpmpy.solvers.solver_interface import ExitStatus, SolverInterface  # noqa: E402


class _InterruptedSolver(SolverInterface):
    def __init__(self, values=None, status=None, error=None):
        super().__init__(name="interrupted")
        self.values = values or {}
        self.result_status = status
        self.error = error

    def add(self, constraints):
        return self

    def objective(self, expr, minimize=True):
        pass

    def solve(self, **kwargs):
        for var, value in self.values.items():
            var._value = value
        if self.error is not None:
            raise self.error
        if self.result_status is not None:
            self.cpm_status.exitstatus = self.result_status
            return False
        raise KeyboardInterrupt


def _problem(maximize=False):
    x, y = cp.intvar(0, 2, shape=2, name="xy")
    model = cp.Model(x + y >= 2)
    if maximize:
        model.maximize(x)
    else:
        model.minimize(x)
    return model, x, y


def test_completed_solve_statistics_and_settings():
    model, x, y = _problem()
    solver = cp.SolverLookup.get("ortools")
    solver.ort_solver.parameters.num_search_workers = 1
    stats = _solve_cp_problem(model, solver, time_limit=10)
    assert stats.has_solution
    assert stats.status == ExitStatus.OPTIMAL
    assert not stats.interrupted
    assert stats.objective == x.value() == 0
    assert y.value() == 2
    assert model.status() is solver.status()
    assert solver.ort_solver.parameters.num_search_workers == 1


def test_interrupted_generic_solver_recovers_mapped_values():
    model, x, y = _problem()
    stats = _solve_cp_problem(model, _InterruptedSolver({x: 1, y: 1}))
    assert stats.has_solution
    assert stats.status == ExitStatus.FEASIBLE
    assert stats.interrupted
    assert stats.objective == 1
    assert (x.value(), y.value()) == (1, 1)


@pytest.mark.parametrize("values", [None, (1, None), (0, 0), (0.5, 1.5), (3, 0)])
def test_recovery_rejects_incomplete_infeasible_or_fractional_values(values):
    model, x, y = _problem()
    mapped = {} if values is None else {x: values[0], y: values[1]}
    with pytest.raises(ValueError, match="No feasible CP solution"):
        _solve_cp_problem(model, _InterruptedSolver(mapped))
    assert x.value() is y.value() is None


def test_interruption_restores_valid_warm_start_without_hint_support():
    model, x, y = _problem()
    stats = _solve_cp_problem(
        model,
        _InterruptedSolver({x: 0, y: 0}),
        initial_values={x: 1, y: 1},
    )
    assert stats.interrupted
    assert stats.objective == 1
    assert (x.value(), y.value()) == (1, 1)


def test_stale_values_are_not_recovered():
    model, x, y = _problem()
    x._value, y._value = 1, 1
    with pytest.raises(ValueError, match="No feasible CP solution"):
        _solve_cp_problem(model, _InterruptedSolver())


@pytest.mark.parametrize("maximize", [False, True])
def test_recovery_selects_best_feasible_candidate(maximize):
    model, x, y = _problem(maximize)
    stats = _solve_cp_problem(
        model,
        _InterruptedSolver({x: 2, y: 0}),
        initial_values={x: 0, y: 2},
    )
    assert stats.objective == (2 if maximize else 0)
    assert x.value() == stats.objective


def test_unknown_status_restores_warm_start():
    model, x, y = _problem()
    stats = _solve_cp_problem(
        model,
        _InterruptedSolver(status=ExitStatus.UNKNOWN),
        initial_values={x: 1, y: 1},
    )
    assert stats.status == ExitStatus.FEASIBLE
    assert not stats.interrupted
    assert stats.objective == 1


def test_unsatisfiable_status_never_restores_warm_start():
    model, x, y = _problem()
    with pytest.raises(ValueError, match="Solution could not be found via CP"):
        _solve_cp_problem(
            model,
            _InterruptedSolver(status=ExitStatus.UNSATISFIABLE),
            initial_values={x: 1, y: 1},
        )
    assert x.value() is y.value() is None


def test_invalid_options_and_solver_errors_propagate():
    model, _, _ = _problem()
    with pytest.raises(RuntimeError, match="broken solver"):
        _solve_cp_problem(
            model, _InterruptedSolver(error=RuntimeError("broken solver"))
        )
    with pytest.raises(ValueError, match="positive"):
        _solve_cp_problem(model, time_limit=-1)
    with pytest.raises(TypeError, match="CPMpy solver name or instance"):
        _solve_cp_problem(model, object())


@pytest.mark.parametrize("recovery_source", ["native", "callback"])
def test_interrupted_ortools_recovers_incumbent(monkeypatch, recovery_source):
    import b_asic._cp_utils as cp_utils

    model, x, y = _problem()
    solver = cp.SolverLookup.get("ortools")
    solve = solver.solve
    callbacks = []

    def interrupted_solve(**options):
        assert solve(**options)
        for var in (x, y):
            var.clear()
        raise KeyboardInterrupt

    monkeypatch.setattr(solver, "solve", interrupted_solve)
    options = {}
    if recovery_source == "callback":
        monkeypatch.setattr(cp_utils, "_recover_ortools_solution", lambda *args: None)
        options["display"] = lambda: callbacks.append(x.value())
    else:
        from ortools.sat.python.cp_model import CpSolverSolutionCallback

        class Callback(CpSolverSolutionCallback):
            def on_solution_callback(self):
                callbacks.append(self.ObjectiveValue())

        options["solution_callback"] = Callback()
    stats = _solve_cp_problem(model, solver, **options)
    assert callbacks
    assert stats.interrupted
    assert stats.status == ExitStatus.FEASIBLE
    assert stats.objective == x.value() == 0
    assert y.value() == 2
    assert solver.objective_value() == 0


def test_native_early_stop_returns_feasible_solution():
    from ortools.sat.python.cp_model import CpSolverSolutionCallback

    model, x, y = _problem()

    class StopAfterFirst(CpSolverSolutionCallback):
        def on_solution_callback(self):
            self.StopSearch()

    stats = _solve_cp_problem(model, solution_callback=StopAfterFirst())
    assert stats.has_solution
    assert stats.status in (ExitStatus.FEASIBLE, ExitStatus.OPTIMAL)
    assert x.value() + y.value() >= 2


def test_empty_satisfaction_model():
    stats = _solve_cp_problem(cp.Model())
    assert stats.has_solution
    assert stats.objective is None


def test_assumptions_reject_conflicting_recovery():
    x = cp.boolvar(name="assumption")
    model = cp.Model(x | ~x)
    with pytest.raises(ValueError, match="No feasible CP solution"):
        _solve_cp_problem(
            model,
            _InterruptedSolver({x: False}),
            assumptions=[x],
            initial_values={x: False},
        )


def test_scheduler_recovers_warm_start_after_interruption(monkeypatch):
    from b_asic import SFG, ConstantMultiplication, Input, Output
    from b_asic.schedule import Schedule
    from b_asic.scheduler import CPScheduler

    source = Input()
    ops = [
        ConstantMultiplication(value, source, latency=1, execution_time=1)
        for value in (2, 3)
    ]
    solver = cp.SolverLookup.get("ortools")

    def interrupt(**options):
        raise KeyboardInterrupt

    monkeypatch.setattr(solver, "solve", interrupt)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op) for op in ops]),
        CPScheduler(
            solver=solver,
            input_times={"in0": 0},
            output_delta_times={"out0": 0, "out1": 1},
        ),
        schedule_time=5,
    )
    assert schedule.start_times == {
        "in0": 0,
        "cmul0": 0,
        "cmul1": 0,
        "out0": 4,
        "out1": 5,
    }


def test_unknown_without_solution_fails():
    model, _, _ = _problem()
    with pytest.raises(ValueError, match="No feasible CP solution"):
        _solve_cp_problem(model, _InterruptedSolver(status=ExitStatus.UNKNOWN))


def test_assumption_variable_outside_model_is_recovered():
    x = cp.boolvar(name="extra_assumption")
    model, first, second = _problem()
    stats = _solve_cp_problem(
        model,
        _InterruptedSolver({first: 1, second: 1, x: True}),
        assumptions=(item for item in [x]),
    )
    assert stats.has_solution
    assert x.value() is True


def test_display_expression_is_preserved(capsys):
    model, x, _ = _problem()
    stats = _solve_cp_problem(model, display=[x])
    assert stats.has_solution
    assert "[0]" in capsys.readouterr().out


def test_import_does_not_require_cpmpy(monkeypatch):
    import builtins
    import runpy

    import b_asic._cp_utils as cp_utils

    original_import = builtins.__import__

    def without_cpmpy(name, *args, **kwargs):
        if name == "cpmpy" or name.startswith("cpmpy."):
            raise ImportError("CPMpy unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_cpmpy)
    namespace = runpy.run_path(cp_utils.__file__)
    assert callable(namespace["_solve_cp_problem"])
