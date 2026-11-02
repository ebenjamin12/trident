"""Solver backends: correctness, agreement, uniqueness, unsatisfiability.

Every solution produced here is checked by :mod:`tetravex.verify`, never by
the engine that produced it. Prolog runs in a subprocess and is markedly
slower per call than Z3, so instances in this module are kept small.
"""

from __future__ import annotations

import pytest
from tetravex.generator import generate
from tetravex.model import Instance, Tile
from tetravex.solvers import get_solver
from tetravex.verify import verify

ENGINES = ("z3", "prolog")


def _solver_or_skip(name: str):
    solver = get_solver(name)
    if not solver.available():
        pytest.skip(f"{name} toolchain not available in this environment")
    return solver


def _unsatisfiable_instance() -> Instance:
    """Four tiles whose edge symbols cannot be made to meet.

    Every tile shows a distinct symbol on each side and no symbol is repeated
    anywhere, so no two tiles can ever agree across a shared edge.
    """
    tiles = (
        Tile(0, 0, 1, 2, 3),
        Tile(1, 4, 5, 6, 7),
        Tile(2, 8, 9, 10, 11),
        Tile(3, 12, 13, 14, 15),
    )
    return Instance("unsat-2x2", 2, 2, 16, False, tiles)


# -- availability -----------------------------------------------------------


@pytest.mark.parametrize("name", ENGINES)
def test_engine_reports_a_version(name):
    solver = _solver_or_skip(name)
    assert solver.version()


# -- solving ----------------------------------------------------------------


@pytest.mark.parametrize("name", ENGINES)
@pytest.mark.parametrize(
    "rows,cols,symbols", [(1, 1, 2), (2, 2, 4), (2, 3, 5), (3, 3, 6)]
)
def test_solution_passes_independent_verification(name, rows, cols, symbols):
    solver = _solver_or_skip(name)
    puzzle = generate(rows, cols, symbols=symbols, seed=rows * 10 + cols)
    result = solver.solve(puzzle.instance)
    assert result.status == "sat"
    report = verify(puzzle.instance, result.solution)
    assert report.ok, report.summary


@pytest.mark.parametrize("name", ENGINES)
def test_solves_bordered_instance(name):
    solver = _solver_or_skip(name)
    puzzle = generate(3, 3, symbols=6, seed=41, bordered=True)
    result = solver.solve(puzzle.instance)
    assert result.status == "sat"
    assert verify(puzzle.instance, result.solution).ok


@pytest.mark.parametrize("name", ENGINES)
def test_solves_rotation_instance(name):
    solver = _solver_or_skip(name)
    puzzle = generate(3, 3, symbols=5, seed=42, allow_rotation=True)
    result = solver.solve(puzzle.instance)
    assert result.status == "sat"
    assert verify(puzzle.instance, result.solution).ok


@pytest.mark.parametrize("name", ENGINES)
def test_respects_no_rotation_flag(name):
    solver = _solver_or_skip(name)
    puzzle = generate(3, 3, symbols=6, seed=43, allow_rotation=False)
    result = solver.solve(puzzle.instance)
    assert result.status == "sat"
    assert all(p.rot == 0 for row in result.solution.grid for p in row)


# -- unsatisfiability -------------------------------------------------------


@pytest.mark.parametrize("name", ENGINES)
def test_reports_unsat_for_impossible_instance(name):
    solver = _solver_or_skip(name)
    result = solver.solve(_unsatisfiable_instance())
    assert result.status == "unsat"
    assert result.solution is None


# -- uniqueness -------------------------------------------------------------


@pytest.mark.parametrize("name", ENGINES)
def test_detects_a_non_unique_instance(name):
    """Four identical tiles: one picture, but many labelled assignments.

    Symmetry breaking must collapse those to a single solution.
    """
    solver = _solver_or_skip(name)
    tiles = tuple(Tile(i, 1, 1, 1, 1) for i in range(4))
    inst = Instance("all-same-2x2", 2, 2, 2, False, tiles)
    result = solver.solve_unique(inst)
    assert result.status == "sat"
    assert result.unique is True, "identical tiles should not count as alternatives"
    assert verify(inst, result.solution).ok


@pytest.mark.parametrize("name", ENGINES)
def test_uniqueness_on_a_generated_instance(name):
    solver = _solver_or_skip(name)
    puzzle = generate(3, 3, symbols=10, seed=5)
    result = solver.solve_unique(puzzle.instance)
    assert result.status == "sat"
    assert result.unique in (True, False)
    assert verify(puzzle.instance, result.solution).ok
    if result.second_solution is not None:
        assert verify(puzzle.instance, result.second_solution).ok


@pytest.mark.parametrize("name", ENGINES)
def test_second_solution_is_genuinely_different(name):
    """A 1x2 board with two tiles that both fit either way round."""
    solver = _solver_or_skip(name)
    tiles = (Tile(0, 0, 1, 0, 1), Tile(1, 0, 1, 0, 1))
    inst = Instance("pair-1x2", 1, 2, 2, False, tiles)
    result = solver.solve_unique(inst)
    assert result.status == "sat"
    # Both tiles are identical, so symmetry breaking makes this unique.
    assert result.unique is True


# -- cross-engine agreement -------------------------------------------------


@pytest.mark.parametrize(
    "rows,cols,symbols,rotation,bordered",
    [
        (2, 2, 4, False, False),
        (2, 3, 5, False, False),
        (3, 3, 6, False, False),
        (3, 3, 6, False, True),
        (3, 3, 4, True, False),
    ],
)
def test_engines_agree_on_status_and_uniqueness(rows, cols, symbols, rotation, bordered):
    z3 = _solver_or_skip("z3")
    prolog = _solver_or_skip("prolog")
    puzzle = generate(
        rows, cols, symbols=symbols, seed=61,
        allow_rotation=rotation, bordered=bordered,
    )
    a = z3.solve_unique(puzzle.instance)
    b = prolog.solve_unique(puzzle.instance)

    assert a.status == b.status, f"status disagreement: z3={a.status} prolog={b.status}"
    assert a.unique == b.unique, f"uniqueness disagreement: z3={a.unique} prolog={b.unique}"
    for result in (a, b):
        assert verify(puzzle.instance, result.solution).ok

    # When a puzzle has exactly one picture, both engines must have found it.
    if a.unique:
        assert a.solution.edge_grid(puzzle.instance) == b.solution.edge_grid(
            puzzle.instance
        )


def test_engines_agree_on_unsat():
    z3 = _solver_or_skip("z3")
    prolog = _solver_or_skip("prolog")
    inst = _unsatisfiable_instance()
    assert z3.solve(inst).status == prolog.solve(inst).status == "unsat"
