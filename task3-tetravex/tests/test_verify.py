"""The independent verifier must catch every class of invalid solution.

Each test takes a known-good layout and breaks exactly one rule.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from tetravex.generator import generate
from tetravex.model import Instance, Placement, Solution, Tile
from tetravex.verify import verify


def _mutate(solution: Solution, row: int, col: int, placement: Placement) -> Solution:
    grid = [list(r) for r in solution.grid]
    grid[row][col] = placement
    return Solution(
        solution.instance_id, tuple(tuple(r) for r in grid), solution.engine
    )


# -- independence -----------------------------------------------------------


def test_verifier_does_not_import_any_solver():
    """Structural check: the verifier must not depend on the things it checks."""
    source = (Path(__file__).resolve().parent.parent / "tetravex" / "verify.py").read_text()
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported += [f"{node.module or ''}.{a.name}" for a in node.names]
    assert not any("solver" in name or "z3" in name or "prolog" in name
                   for name in imported), imported


# -- happy path -------------------------------------------------------------


def test_accepts_the_reference_layout():
    puzzle = generate(3, 3, symbols=6, seed=3)
    assert verify(puzzle.instance, puzzle.reference).ok


def test_report_is_falsey_when_invalid():
    puzzle = generate(2, 2, symbols=4, seed=3)
    broken = _mutate(puzzle.reference, 0, 0, Placement(99, 0))
    assert not verify(puzzle.instance, broken)


# -- one broken rule per test ----------------------------------------------


def test_detects_duplicate_tile_use():
    puzzle = generate(2, 2, symbols=4, seed=3)
    used = puzzle.reference.grid[0][0].tile
    broken = _mutate(puzzle.reference, 1, 1, Placement(used, 0))
    report = verify(puzzle.instance, broken)
    assert not report.ok
    kinds = {v.kind for v in report.violations}
    assert "tile-usage" in kinds
    assert any("used 2 times" in v.detail for v in report.violations)
    assert any("never placed" in v.detail for v in report.violations)


def test_detects_unknown_tile_id():
    puzzle = generate(2, 2, symbols=4, seed=3)
    broken = _mutate(puzzle.reference, 0, 0, Placement(42, 0))
    report = verify(puzzle.instance, broken)
    assert any("unknown tile id 42" in v.detail for v in report.violations)


def test_detects_rotation_when_not_permitted():
    puzzle = generate(2, 2, symbols=4, seed=3, allow_rotation=False)
    first = puzzle.reference.grid[0][0]
    broken = _mutate(puzzle.reference, 0, 0, Placement(first.tile, 1))
    report = verify(puzzle.instance, broken)
    assert any(v.kind == "rotation" for v in report.violations)
    assert any("does not permit rotation" in v.detail for v in report.violations)


def test_detects_out_of_range_rotation():
    puzzle = generate(2, 2, symbols=4, seed=3, allow_rotation=True)
    first = puzzle.reference.grid[0][0]
    broken = _mutate(puzzle.reference, 0, 0, Placement(first.tile, 7))
    report = verify(puzzle.instance, broken)
    assert any(v.kind == "rotation" for v in report.violations)


def test_detects_adjacency_mismatch():
    """Swap two tiles, which keeps the bijection but breaks the edges."""
    puzzle = generate(3, 3, symbols=8, seed=15)
    grid = [list(r) for r in puzzle.reference.grid]
    grid[0][0], grid[2][2] = grid[2][2], grid[0][0]
    broken = Solution(puzzle.instance.id, tuple(tuple(r) for r in grid))
    report = verify(puzzle.instance, broken)
    assert not report.ok
    assert any(v.kind == "adjacency" for v in report.violations)


def test_detects_border_mismatch():
    puzzle = generate(3, 3, symbols=8, seed=15, bordered=True)
    assert verify(puzzle.instance, puzzle.reference).ok
    # Use a legal-but-wrong symbol: an out-of-range value would trip the
    # instance check first and never reach the border comparison.
    wrong = (puzzle.instance.border.top[0] + 1) % puzzle.instance.symbols
    tampered = replace(
        puzzle.instance,
        border=replace(puzzle.instance.border, top=(wrong,) + puzzle.instance.border.top[1:]),
    )
    report = verify(tampered, puzzle.reference)
    assert any(v.kind == "border" for v in report.violations)


def test_detects_wrong_row_count():
    puzzle = generate(3, 3, symbols=6, seed=3)
    broken = Solution(puzzle.instance.id, puzzle.reference.grid[:2])
    report = verify(puzzle.instance, broken)
    assert any(v.kind == "shape" for v in report.violations)


def test_detects_wrong_column_count():
    puzzle = generate(3, 3, symbols=6, seed=3)
    grid = [list(r) for r in puzzle.reference.grid]
    grid[1] = grid[1][:2]
    broken = Solution(puzzle.instance.id, tuple(tuple(r) for r in grid))
    report = verify(puzzle.instance, broken)
    assert any(v.kind == "shape" for v in report.violations)


def test_detects_instance_id_mismatch():
    puzzle = generate(2, 2, symbols=4, seed=3)
    broken = Solution("some-other-instance", puzzle.reference.grid)
    report = verify(puzzle.instance, broken)
    assert any(v.kind == "identity" for v in report.violations)


def test_detects_malformed_instance():
    bad = Instance("x", 2, 2, 4, False, (Tile(0, 0, 0, 0, 0),))
    report = verify(bad, Solution("x", ()))
    assert any(v.kind == "instance" for v in report.violations)


def test_reports_every_violation_not_just_the_first():
    """Three separate adjacency breaks should all be listed."""
    puzzle = generate(3, 3, symbols=9, seed=19)
    grid = [list(r) for r in puzzle.reference.grid]
    grid[0][0], grid[0][1] = grid[0][1], grid[0][0]
    grid[2][0], grid[2][1] = grid[2][1], grid[2][0]
    broken = Solution(puzzle.instance.id, tuple(tuple(r) for r in grid))
    report = verify(puzzle.instance, broken)
    adjacency = [v for v in report.violations if v.kind == "adjacency"]
    assert len(adjacency) >= 3
    assert "violation" in report.summary
