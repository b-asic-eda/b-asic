"""B-ASIC ILP solver and interrupted-solution recovery utilities."""

import contextlib
import shutil
import tempfile
from pathlib import Path
from typing import cast
from uuid import uuid4

from pulp import HiGHS, LpProblem, LpSolver, LpSolveStatus, value

import b_asic.logger

log = b_asic.logger.getLogger()


def _resolve_solver(
    solver: LpSolver | None = None,
    warm_start: bool = False,
) -> LpSolver:
    """Resolve an ILP solver, defaulting to HiGHS with logging-aware output."""
    if solver is None:
        msg = 1 if log.isEnabledFor(b_asic.logger.logging.DEBUG) else 0
        solver = HiGHS(msg=msg, warmStart=warm_start)
    elif warm_start and isinstance(solver, HiGHS):
        solver.optionsDict["warmStart"] = True
    return solver


def _solve_ilp_problem(
    problem: LpProblem,
    solver: LpSolver | None,
    warm_start: bool = False,
) -> None:
    solver = _resolve_solver(solver, warm_start=warm_start)

    recovery_state = _prepare_interrupted_recovery(problem, solver)

    # Solve the ILP problem
    stats = None
    status = None
    interrupted = False
    try:
        stats = problem.solve(solver)
        status = stats.status
    except KeyboardInterrupt:
        interrupted = True
        log.warning(
            "ILP solver interrupted; attempting to keep best feasible solution."
        )
        status = _recover_interrupted_solution(problem, solver, recovery_state)
    finally:
        _restore_interrupted_recovery(problem, solver, recovery_state)

    if (stats is not None and stats.has_solution) or (
        interrupted and _has_feasible_solution(problem)
    ):
        if interrupted or status == LpSolveStatus.NotSolved:
            log.warning("Using best feasible ILP solution found before solver stopped.")
        return

    if interrupted:
        raise ValueError(
            "No feasible ILP solution was found before the solver stopped."
        )

    if status not in (LpSolveStatus.Optimal, LpSolveStatus.NotSolved):
        raise ValueError("Solution could not be found via ILP, use another method.")

    raise ValueError("No feasible ILP solution was found before the solver stopped.")


def _recover_interrupted_solution(
    problem: LpProblem,
    solver: LpSolver,
    recovery_state: dict[str, object] | None,
) -> LpSolveStatus | None:
    solution_path = None
    if recovery_state is not None:
        solution_path = cast(str | None, recovery_state.get("solution_path"))
    if solution_path and _recover_cmd_solution_file(problem, solver, solution_path):
        return LpSolveStatus.Interrupted

    find_solution_values = getattr(solver, "findSolutionValues", None)
    if not callable(find_solution_values):
        return None

    try:
        status, _ = find_solution_values(problem)
        return cast(LpSolveStatus, status)
    except Exception as exc:
        log.info("Failed to recover interrupted ILP solution: %s", exc)
        return None


def _prepare_interrupted_recovery(
    problem: LpProblem,
    solver: LpSolver,
) -> dict[str, object] | None:
    if not hasattr(solver, "keepFiles") or not hasattr(solver, "create_tmp_files"):
        return None

    original_keep_files = cast(bool, solver.keepFiles)
    original_name = problem.name
    recovery_dir = tempfile.mkdtemp(prefix="b_asic_ilp_recovery_")
    recovery_name = str(Path(recovery_dir) / f"{problem.name}-{uuid4().hex}")

    solver.keepFiles = True
    problem.name = recovery_name
    solution_path = next(solver.create_tmp_files(recovery_name, "sol"))

    return {
        "original_keep_files": original_keep_files,
        "original_name": original_name,
        "recovery_name": recovery_name,
        "recovery_dir": recovery_dir,
        "solution_path": solution_path,
        "temp_paths": tuple(solver.create_tmp_files(recovery_name, "lp", "sol", "mst")),
    }


def _restore_interrupted_recovery(
    problem: LpProblem,
    solver: LpSolver,
    recovery_state: dict[str, object] | None,
) -> None:
    if recovery_state is None:
        return

    problem.name = cast(str, recovery_state["original_name"])
    solver.keepFiles = recovery_state["original_keep_files"]

    if cast(bool, recovery_state["original_keep_files"]):
        return

    for path in cast(tuple[str, ...], recovery_state["temp_paths"]):
        with contextlib.suppress(FileNotFoundError):
            Path(path).unlink()
    recovery_dir = cast(str | None, recovery_state.get("recovery_dir"))
    if recovery_dir is not None:
        shutil.rmtree(recovery_dir, ignore_errors=True)
    with contextlib.suppress(FileNotFoundError):
        Path("gurobi.log").unlink()


def _recover_cmd_solution_file(
    problem: LpProblem,
    solver: LpSolver,
    solution_path: str,
) -> bool:
    read_solution = getattr(solver, "readsol", None)
    if not callable(read_solution) or not Path(solution_path).exists():
        return False

    try:
        solution = read_solution(solution_path)
    except Exception as exc:
        log.info(
            "Failed to parse interrupted solver solution file %s: %s",
            solution_path,
            exc,
        )
        return False

    if not isinstance(solution, tuple) or len(solution) < 2:
        return False

    status = cast(LpSolveStatus, solution[0])
    values = cast(dict[str, float], solution[1])
    reduced_costs = cast(dict[str, float], solution[2]) if len(solution) > 2 else {}
    shadow_prices = cast(dict[str, float], solution[3]) if len(solution) > 3 else {}
    slacks = cast(dict[str, float], solution[4]) if len(solution) > 4 else {}

    if status != LpSolveStatus.Infeasible:
        problem.assignVarsVals(values)
        if reduced_costs:
            problem.assignVarsDj(reduced_costs)
        if shadow_prices:
            problem.assignConsPi(shadow_prices)
        if slacks:
            problem.assignConsSlack(slacks)
    return _has_feasible_solution(problem)


def _has_feasible_solution(problem: LpProblem) -> bool:
    if value(problem.objective) is not None:
        return True

    variables = problem.variables()
    return bool(variables) and all(var.varValue is not None for var in variables)
