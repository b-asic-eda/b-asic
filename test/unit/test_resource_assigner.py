import os

import pytest
from pulp import LpMinimize, LpProblem, LpVariable, value

from b_asic import resource_assigner


def test_solve_ilp_problem_keeps_best_solution_on_interrupt(monkeypatch):
    problem = LpProblem("interrupt_with_incumbent", LpMinimize)
    variable = LpVariable("x", lowBound=0, upBound=1, cat="Binary")
    problem += variable

    def interrupted_solve(self, solver):
        variable.varValue = 1
        raise KeyboardInterrupt

    monkeypatch.setattr(LpProblem, "solve", interrupted_solve)

    resource_assigner._solve_ilp_problem(problem, solver=object())

    assert value(problem.objective) == 1


def test_solve_ilp_problem_raises_without_feasible_solution_on_interrupt(monkeypatch):
    problem = LpProblem("interrupt_without_incumbent", LpMinimize)
    variable = LpVariable("x", lowBound=0, upBound=1, cat="Binary")
    problem += variable

    def interrupted_solve(self, solver):
        raise KeyboardInterrupt

    monkeypatch.setattr(LpProblem, "solve", interrupted_solve)

    with pytest.raises(
        ValueError, match="No feasible ILP solution was found before the solver stopped"
    ):
        resource_assigner._solve_ilp_problem(problem, solver=object())


def test_solve_ilp_problem_recovers_incumbent_via_solver_hook(monkeypatch):
    problem = LpProblem("interrupt_with_solver_recovery", LpMinimize)
    variable = LpVariable("x", lowBound=0, upBound=1, cat="Binary")
    problem += variable

    class RecoveringSolver:
        def findSolutionValues(self, lp):
            variable.varValue = 1
            return 0

    def interrupted_solve(self, solver):
        raise KeyboardInterrupt

    monkeypatch.setattr(LpProblem, "solve", interrupted_solve)

    resource_assigner._solve_ilp_problem(problem, solver=RecoveringSolver())

    assert value(problem.objective) == 1


def test_solve_ilp_problem_recovers_incumbent_from_solution_file(tmp_path):
    problem = LpProblem("interrupt_with_solution_file", LpMinimize)
    variable = LpVariable("x", lowBound=0, upBound=1, cat="Binary")
    problem += variable

    class RecoveringCmdSolver:
        def __init__(self):
            self.keepFiles = False
            self.tmpDir = str(tmp_path)

        def create_tmp_files(self, name, *args):
            prefix = name if self.keepFiles else os.path.join(self.tmpDir, name)
            return (f"{prefix}-pulp.{suffix}" for suffix in args)

        def readsol(self, filename):
            return 1, {"x": 1.0}, {}, {}, {}

        def actualSolve(self, lp):
            solution_path = next(self.create_tmp_files(lp.name, "sol"))
            with open(solution_path, "w", encoding="ascii") as solution_file:
                solution_file.write("# objective value = 1\n")
                solution_file.write("x 1\n")
            raise KeyboardInterrupt

    resource_assigner._solve_ilp_problem(problem, solver=RecoveringCmdSolver())

    assert value(problem.objective) == 1
