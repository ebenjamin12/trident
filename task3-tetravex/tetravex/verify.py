"""Independent verification of TetraVex solutions.

This module deliberately imports nothing from :mod:`tetravex.solvers`. It
re-derives every constraint from the instance and the proposed solution alone,
so a solver cannot pass verification by agreeing with itself. ``tests`` asserts
that this independence holds.

A report lists *every* violation found rather than stopping at the first, which
makes a broken encoding much easier to diagnose than a bare boolean.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import EDGE_NAMES, Instance, Solution


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule."""

    kind: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.kind}] {self.detail}"


@dataclass(frozen=True, slots=True)
class Report:
    """Outcome of checking one solution against one instance."""

    ok: bool
    violations: tuple[Violation, ...] = field(default_factory=tuple)

    @property
    def summary(self) -> str:
        if self.ok:
            return "VALID - all constraints satisfied"
        kinds = sorted({v.kind for v in self.violations})
        return (
            f"INVALID - {len(self.violations)} violation(s) "
            f"across {len(kinds)} category/categories: {', '.join(kinds)}"
        )

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.ok


def verify(instance: Instance, solution: Solution) -> Report:
    """Check ``solution`` against ``instance`` from first principles."""
    violations: list[Violation] = []
    add = violations.append

    # -- 1. the instance itself must be well formed ------------------------
    try:
        instance.validate()
    except Exception as exc:  # noqa: BLE001 - surfaced as a violation
        add(Violation("instance", str(exc)))
        return Report(False, tuple(violations))

    # -- 2. identity -------------------------------------------------------
    if solution.instance_id and solution.instance_id != instance.id:
        add(
            Violation(
                "identity",
                f"solution is for instance {solution.instance_id!r}, "
                f"not {instance.id!r}",
            )
        )

    # -- 3. shape ----------------------------------------------------------
    if solution.rows != instance.rows:
        add(
            Violation(
                "shape", f"solution has {solution.rows} rows, expected {instance.rows}"
            )
        )
    for r, row in enumerate(solution.grid):
        if len(row) != instance.cols:
            add(
                Violation(
                    "shape",
                    f"row {r} has {len(row)} cells, expected {instance.cols}",
                )
            )
    if violations and any(v.kind == "shape" for v in violations):
        # Adjacency checks below index the grid directly; bail out rather than
        # raising IndexError on a malformed board.
        return Report(False, tuple(violations))

    # -- 4. every tile used exactly once -----------------------------------
    by_id = {t.id: t for t in instance.tiles}
    seen: dict[int, list[tuple[int, int]]] = {}
    for r, c, placement in solution.placements():
        if placement.tile not in by_id:
            add(
                Violation(
                    "tile-usage",
                    f"cell ({r},{c}) references unknown tile id {placement.tile}",
                )
            )
            continue
        seen.setdefault(placement.tile, []).append((r, c))

    for tile_id, cells in sorted(seen.items()):
        if len(cells) > 1:
            where = ", ".join(f"({r},{c})" for r, c in cells)
            add(
                Violation(
                    "tile-usage", f"tile {tile_id} used {len(cells)} times: {where}"
                )
            )
    for tile_id in sorted(by_id):
        if tile_id not in seen:
            add(Violation("tile-usage", f"tile {tile_id} is never placed"))

    # -- 5. rotations ------------------------------------------------------
    allowed = set(instance.rotations)
    for r, c, placement in solution.placements():
        if placement.rot not in allowed:
            if instance.allow_rotation:
                detail = (
                    f"cell ({r},{c}) has rotation {placement.rot}, "
                    f"must be one of {sorted(allowed)}"
                )
            else:
                detail = (
                    f"cell ({r},{c}) has rotation {placement.rot} but this "
                    f"instance does not permit rotation"
                )
            add(Violation("rotation", detail))

    # Anything below needs resolved edges; skip if tiles or rotations are bad.
    if any(v.kind in {"tile-usage", "rotation"} for v in violations):
        return Report(False, tuple(violations))

    # -- 6. resolved edge values in range ----------------------------------
    resolved = [
        [by_id[p.tile].rotated(p.rot) for p in row] for row in solution.grid
    ]
    for r, row in enumerate(resolved):
        for c, tile in enumerate(row):
            for name, value in zip(EDGE_NAMES, tile.edges, strict=True):
                if not 0 <= value < instance.symbols:
                    add(
                        Violation(
                            "symbol-range",
                            f"cell ({r},{c}) {name} edge is {value}, "
                            f"outside 0..{instance.symbols - 1}",
                        )
                    )

    # -- 7. adjacency ------------------------------------------------------
    for r in range(instance.rows):
        for c in range(instance.cols):
            tile = resolved[r][c]
            if c + 1 < instance.cols:
                east = resolved[r][c + 1]
                if tile.right != east.left:
                    add(
                        Violation(
                            "adjacency",
                            f"horizontal mismatch between ({r},{c}) and ({r},{c + 1}): "
                            f"right={tile.right} vs left={east.left}",
                        )
                    )
            if r + 1 < instance.rows:
                south = resolved[r + 1][c]
                if tile.bottom != south.top:
                    add(
                        Violation(
                            "adjacency",
                            f"vertical mismatch between ({r},{c}) and ({r + 1},{c}): "
                            f"bottom={tile.bottom} vs top={south.top}",
                        )
                    )

    # -- 8. border ---------------------------------------------------------
    border = instance.border
    if border is not None:
        for c in range(instance.cols):
            got, want = resolved[0][c].top, border.top[c]
            if got != want:
                add(
                    Violation(
                        "border",
                        f"top border at column {c} is {got}, expected {want}",
                    )
                )
            got, want = resolved[instance.rows - 1][c].bottom, border.bottom[c]
            if got != want:
                add(
                    Violation(
                        "border",
                        f"bottom border at column {c} is {got}, expected {want}",
                    )
                )
        for r in range(instance.rows):
            got, want = resolved[r][0].left, border.left[r]
            if got != want:
                add(
                    Violation(
                        "border", f"left border at row {r} is {got}, expected {want}"
                    )
                )
            got, want = resolved[r][instance.cols - 1].right, border.right[r]
            if got != want:
                add(
                    Violation(
                        "border", f"right border at row {r} is {got}, expected {want}"
                    )
                )

    return Report(not violations, tuple(violations))
