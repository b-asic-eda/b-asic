"""
B-ASIC CP solver and interrupted-solution recovery utilities.

CPMpy remains optional: importing this module does not import CPMpy or a solver.
OR-Tools incumbents are saved during search, before user display callbacks run.
Other solvers can recover values already mapped to CPMpy variables, or fall back
on an explicitly supplied feasible warm start.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from numbers import Integral
from time import perf_counter
from typing import TYPE_CHECKING

import b_asic.logger

if TYPE_CHECKING:
    from cpmpy import Model
    from cpmpy.expressions.variables import _NumVarImpl
    from cpmpy.solvers.solver_interface import ExitStatus, SolverInterface

log = b_asic.logger.getLogger()


@dataclass(frozen=True)
class _CPSolveStats:
    """Outcome of a successful solve, including a recovered feasible solution."""

    solver: str
    status: ExitStatus
    has_solution: bool
    objective: int | float | None
    interrupted: bool = False


def _resolve_solver(
    model: Model, solver: str | SolverInterface | None = None
) -> SolverInterface:
    """Resolve a solver and add the model, preserving supplied native settings."""
    import cpmpy as cp  # noqa: PLC0415
    from cpmpy.solvers.solver_interface import SolverInterface  # noqa: PLC0415

    if solver is None or isinstance(solver, str):
        return cp.SolverLookup.get(solver or "ortools", model)
    if not isinstance(solver, SolverInterface):
        raise TypeError("CP requires a CPMpy solver name or instance")
    solver += model.constraints
    if model.objective_ is not None:
        solver.objective(model.objective_, minimize=model.objective_is_min)
    return solver


def _has_feasible_solution(model: Model, variables: list, assumptions=()) -> bool:
    """Check completeness, integer domains, assumptions, and every constraint."""
    from cpmpy.expressions.utils import argval  # noqa: PLC0415

    return (
        all(
            isinstance(var.value(), Integral) and var.lb <= var.value() <= var.ub
            for var in variables
        )
        and all(argval(constraint) for constraint in model.constraints)
        and all(argval(assumption) for assumption in assumptions)
    )


def _validated_solution(model, variables, values, assumptions=()) -> dict | None:
    """Validate candidate values without changing the current assignment."""
    previous = {var: var.value() for var in variables}
    try:
        for var in variables:
            var._value = values.get(var)
        if _has_feasible_solution(model, variables, assumptions):
            return {var: var.value() for var in variables}
        return None
    finally:
        for var, value in previous.items():
            var._value = value


def _recover_ortools_solution(solver, variables) -> dict | None:
    """Read a native response if interruption occurred before CPMpy mapped it."""
    from ortools.sat.python import cp_model  # noqa: PLC0415

    try:
        response = solver.ort_solver.ResponseProto()
        if response.status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            return None
        return {
            var: solver.ort_solver.Value(solver.solver_var(var)) for var in variables
        }
    except Exception as exc:
        log.info("Failed to recover interrupted CP native solution: %s", exc)
        return None


def _solve_cp_problem(
    model: Model,
    solver: str | SolverInterface | None = None,
    *,
    initial_values: dict[_NumVarImpl, int | bool] | None = None,
    **solver_options,
) -> _CPSolveStats:
    """
    Solve a CP model, retaining feasible incumbents after an abort or limit.

    Named solvers default to OR-Tools. Supplied instances receive constraints and
    the objective in place, and retain native settings. Solver options (including
    limits and callbacks) are forwarded. Initial values are hinted only when they
    satisfy the entire model, and remain available as a recovery fallback even
    for solvers without hint support.

    A KeyboardInterrupt or UNKNOWN result can recover a validated incumbent or
    warm start. A proven infeasible model never falls back to an earlier solution.
    Recovered solutions are reported as feasible, without claiming optimality.
    """
    from cpmpy.exceptions import NotSupportedError  # noqa: PLC0415
    from cpmpy.solvers.ortools import CPM_ortools  # noqa: PLC0415
    from cpmpy.solvers.solver_interface import ExitStatus, SolverStatus  # noqa: PLC0415
    from cpmpy.transformations.get_variables import (  # noqa: PLC0415
        get_variables,
        get_variables_model,
    )

    started = perf_counter()
    named_solver = solver is None or isinstance(solver, str)
    solver = _resolve_solver(model, solver)
    variables = get_variables_model(model)
    assumptions = solver_options.get("assumptions")
    if assumptions is None:
        assumptions = ()
    else:
        assumptions = list(assumptions)
        solver_options["assumptions"] = assumptions
        seen = set(variables)
        variables.extend(var for var in get_variables(assumptions) if var not in seen)
    # Values from a previous solve must never masquerade as a new incumbent.
    for var in variables:
        var.clear()
    initial_solution = _validated_solution(
        model, variables, initial_values or {}, assumptions
    )
    if initial_solution is not None:
        with suppress(NotSupportedError):
            solver.solution_hint(
                list(initial_solution), list(initial_solution.values())
            )

    incumbent = None
    incumbent_objective = None
    if isinstance(solver, CPM_ortools):
        if named_solver:
            solver_options.setdefault(
                "log_search_progress", log.isEnabledFor(b_asic.logger.logging.DEBUG)
            )
        # Keep explicit native callbacks intact. Their final native response can
        # still be recovered if CPMpy is interrupted before mapping the values.
        if solver_options.get("solution_callback") is None:
            display = solver_options.get("display")

            def save_incumbent():
                nonlocal incumbent, incumbent_objective
                objective = model.objective_value()
                if (
                    incumbent is None
                    or objective is None
                    or (
                        objective < incumbent_objective
                        if model.objective_is_min
                        else objective > incumbent_objective
                    )
                ):
                    incumbent = {var: var.value() for var in variables}
                    incumbent_objective = objective
                if display is not None:
                    solver.print_display(display)

            solver_options["display"] = save_incumbent

    interrupted = False
    try:
        solved = solver.solve(**solver_options)
    except KeyboardInterrupt:
        interrupted = True
        solved = False
        log.warning("CP solver interrupted; attempting to keep best feasible solution.")

    if interrupted:
        solver.cpm_status = SolverStatus(solver.name)
        solver.cpm_status.exitstatus = ExitStatus.UNKNOWN
    model.cpm_status = solver.status()
    model.cpm_status.runtime = perf_counter() - started
    status = model.cpm_status.exitstatus
    if solved and _has_feasible_solution(model, variables, assumptions):
        return _CPSolveStats(solver.name, status, True, model.objective_value())

    if interrupted or status == ExitStatus.UNKNOWN:
        candidates = [
            {var: var.value() for var in variables},
            incumbent,
            initial_solution,
        ]
        if isinstance(solver, CPM_ortools):
            candidates.insert(0, _recover_ortools_solution(solver, variables))
        best = None
        best_objective = None
        for candidate in candidates:
            if candidate is None:
                continue
            candidate = _validated_solution(model, variables, candidate, assumptions)
            if candidate is None:
                continue
            for var, value in candidate.items():
                var._value = value
            objective = model.objective_value()
            if (
                best is None
                or objective is None
                or (
                    objective < best_objective
                    if model.objective_is_min
                    else objective > best_objective
                )
            ):
                best, best_objective = candidate, objective
        if best is not None:
            for var, value in best.items():
                var._value = value
            solver.cpm_status = SolverStatus(solver.name)
            solver.cpm_status.exitstatus = ExitStatus.FEASIBLE
            solver.cpm_status.runtime = perf_counter() - started
            solver.objective_value_ = best_objective
            model.cpm_status = solver.cpm_status
            log.warning("Using best feasible CP solution found before solver stopped.")
            return _CPSolveStats(
                solver.name, ExitStatus.FEASIBLE, True, best_objective, interrupted
            )
        for var in variables:
            var.clear()
        raise ValueError("No feasible CP solution was found before the solver stopped.")

    for var in variables:
        var.clear()
    raise ValueError("Solution could not be found via CP, use another method.")
