import pulp
import pytest

from b_asic._ilp_utils import _solve_ilp_problem
from b_asic.core_operations import ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ILPScheduler
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output


class _InterruptedSolver(pulp.LpSolver):
    def __init__(self, recovered_values=None):
        super().__init__(msg=False)
        self.recovered_values = recovered_values

    def actualSolve(self, problem, **kwargs):
        # Some solvers clear the warm-start values before interruption.
        for var in problem.variables():
            var.varValue = None
        raise KeyboardInterrupt

    def findSolutionValues(self, problem):
        if self.recovered_values is not None:
            problem.assignVarsVals(self.recovered_values)
        return pulp.LpSolveStatus.Interrupted, None


def _problem():
    problem = pulp.LpProblem()
    x = problem.add_variable("x", cat=pulp.LpBinary)
    y = problem.add_variable("y", cat=pulp.LpBinary)
    problem += x + y >= 1
    problem += x
    return problem, x, y


def test_interrupted_solve_returns_recovered_statistics():
    problem, x, y = _problem()
    stats = _solve_ilp_problem(problem, _InterruptedSolver({"x": 1, "y": 0}))
    assert isinstance(stats, pulp.LpSolveStats)
    assert stats.has_solution
    assert stats.status == pulp.LpSolveStatus.Interrupted
    assert stats.objective == 1
    assert (x.varValue, y.varValue) == (1, 0)
    assert problem.valid()


@pytest.mark.parametrize(
    "recovered_values",
    [None, {"x": 1}, {"x": 0, "y": 0}, {"x": 0.5, "y": 0.5}],
)
def test_interrupted_solve_rejects_missing_or_infeasible_values(recovered_values):
    problem, _, _ = _problem()
    with pytest.raises(ValueError, match="No feasible ILP solution"):
        _solve_ilp_problem(problem, _InterruptedSolver(recovered_values))


def test_interrupted_solve_restores_feasible_warm_start():
    problem, x, y = _problem()
    x.setInitialValue(1)
    y.setInitialValue(0)
    stats = _solve_ilp_problem(
        problem, _InterruptedSolver({"x": 0, "y": 0}), warm_start=True
    )
    assert stats.has_solution
    assert stats.status == pulp.LpSolveStatus.Interrupted
    assert (x.varValue, y.varValue) == (1, 0)
    assert problem.valid()


def test_completed_solve_preserves_statistics():
    problem, _, _ = _problem()
    stats = _solve_ilp_problem(problem, pulp.HiGHS(msg=False))
    assert stats.has_solution
    assert stats.status == pulp.LpSolveStatus.Optimal
    assert stats.objective == 0


def test_scheduler_recovers_initial_schedule_after_interruption():
    input_op = Input()
    multiplications = [
        ConstantMultiplication(value, input_op, latency=1, execution_time=1)
        for value in (2, 3)
    ]
    sfg = SFG(inputs=[input_op], outputs=[Output(op) for op in multiplications])
    schedule = Schedule(
        sfg,
        ILPScheduler(
            solver=_InterruptedSolver(),
            input_times={"in0": 0},
            output_delta_times={"out0": 0, "out1": 1},
        ),
        schedule_time=5,
    )
    assert schedule.start_times["cmul0"] == 0
    assert schedule.start_times["cmul1"] == 0
    assert schedule.start_times["out0"] == 4
    assert schedule.start_times["out1"] == 5
