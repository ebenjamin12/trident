"""TetraVex as an SMT problem, solved with Z3.

Encoding
--------
The model is deliberately written to mirror the Prolog CLP(FD) model in
``tetravex/prolog/tetravex.pl`` one constraint at a time, so that the
comparison between the two is about the *solver*, not about two people having
modelled the puzzle differently.

Decision variables, for each cell ``c`` of the row-major grid:

``tile[c]``
    which tile id occupies the cell, in ``0..n-1``
``rot[c]``
    how far it has been turned, in ``0..3`` (pinned to ``0`` when the
    instance forbids rotation)
``top[c] right[c] bottom[c] left[c]``
    the resolved symbol on each side of the cell

Constraints:

1. ``Distinct(tile)`` -- the placement is a bijection onto the tiles.
2. For every cell, tile and permitted rotation, an implication fixing the four
   resolved edges. This is the table that links a choice of tile to the
   symbols it exposes.
3. ``right[c] == left[east]`` and ``bottom[c] == top[south]``.
4. Border equalities, when the instance pins them.
5. Symmetry breaking over groups of identical tiles.

Symmetry breaking is only materialised when the instance actually contains
duplicate tiles, which keeps the common case free of the channelling
constraints it needs.
"""

from __future__ import annotations

import time
from typing import Any

from ..model import Instance, Solution
from .base import Solver, SolveResult, SolverUnavailable

#: Z3 statistics worth reporting. Z3 emits dozens; these are the ones that say
#: something about search effort rather than memory layout.
_STAT_KEYS = ("conflicts", "decisions", "propagations", "restarts", "max memory")


def _import_z3():
    try:
        import z3  # noqa: PLC0415 - imported lazily so the package works without it
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SolverUnavailable(
            "z3-solver is not installed; run `pip install -r requirements.txt`"
        ) from exc
    return z3


class Z3Solver(Solver):
    """SMT backend."""

    name = "z3"

    def available(self) -> bool:
        try:
            _import_z3()
        except SolverUnavailable:
            return False
        return True

    def version(self) -> str:
        z3 = _import_z3()
        return f"Z3 {z3.get_version_string()}"

    # -- model construction -------------------------------------------------

    def _build(self, instance: Instance):
        """Return ``(solver, tile_vars, rot_vars)`` for ``instance``."""
        z3 = _import_z3()
        n = instance.n_cells
        tiles = list(instance.tiles)

        solver = z3.Solver()

        tile_v = [z3.Int(f"tile_{i}") for i in range(n)]
        rot_v = [z3.Int(f"rot_{i}") for i in range(n)]
        edge_v = {
            side: [z3.Int(f"{side}_{i}") for i in range(n)]
            for side in ("top", "right", "bottom", "left")
        }

        # 1. one tile per cell, every tile used once
        for v in tile_v:
            solver.add(v >= 0, v < n)
        solver.add(z3.Distinct(*tile_v))

        rotations = instance.rotations
        for v in rot_v:
            if instance.allow_rotation:
                solver.add(v >= 0, v <= 3)
            else:
                solver.add(v == 0)

        # 2. link a (tile, rotation) choice to the symbols it exposes
        for cell in range(n):
            for tile in tiles:
                for k in rotations:
                    turned = tile.rotated(k)
                    solver.add(
                        z3.Implies(
                            z3.And(tile_v[cell] == tile.id, rot_v[cell] == k),
                            z3.And(
                                edge_v["top"][cell] == turned.top,
                                edge_v["right"][cell] == turned.right,
                                edge_v["bottom"][cell] == turned.bottom,
                                edge_v["left"][cell] == turned.left,
                            ),
                        )
                    )

        # 3. adjacency
        for r in range(instance.rows):
            for c in range(instance.cols):
                here = instance.cell_index(r, c)
                if c + 1 < instance.cols:
                    east = instance.cell_index(r, c + 1)
                    solver.add(edge_v["right"][here] == edge_v["left"][east])
                if r + 1 < instance.rows:
                    south = instance.cell_index(r + 1, c)
                    solver.add(edge_v["bottom"][here] == edge_v["top"][south])

        # 4. border
        border = instance.border
        if border is not None:
            for c in range(instance.cols):
                solver.add(
                    edge_v["top"][instance.cell_index(0, c)] == border.top[c]
                )
                solver.add(
                    edge_v["bottom"][instance.cell_index(instance.rows - 1, c)]
                    == border.bottom[c]
                )
            for r in range(instance.rows):
                solver.add(edge_v["left"][instance.cell_index(r, 0)] == border.left[r])
                solver.add(
                    edge_v["right"][instance.cell_index(r, instance.cols - 1)]
                    == border.right[r]
                )

        # 5. symmetry breaking across identical tiles
        groups = instance.duplicate_groups()
        if groups:
            pos = [z3.Int(f"pos_{t.id}") for t in tiles]
            for p in pos:
                solver.add(p >= 0, p < n)
            # channelling: tile t sits in cell c exactly when pos[t] == c
            for cell in range(n):
                for tile in tiles:
                    solver.add((tile_v[cell] == tile.id) == (pos[tile.id] == cell))
            for group in groups:
                # Adjacent pairs, so the two sequences are deliberately of
                # different lengths: strict=False is the intent, not an
                # oversight.
                for a, b in zip(group, group[1:], strict=False):
                    solver.add(pos[a] < pos[b])

        return solver, tile_v, rot_v

    @staticmethod
    def _extract(
        instance: Instance, model, tile_v, rot_v, engine: str, stats: dict[str, Any]
    ) -> Solution:
        assignment = [
            (model[tile_v[i]].as_long(), model[rot_v[i]].as_long())
            for i in range(instance.n_cells)
        ]
        return Solution.from_assignment(instance, assignment, engine=engine, stats=stats)

    @staticmethod
    def _stats(solver) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            raw = solver.statistics()
            for key in _STAT_KEYS:
                try:
                    out[key.replace(" ", "_")] = raw.get_key_value(key)
                except Exception:  # noqa: BLE001 - key simply absent for this run
                    pass
        except Exception:  # noqa: BLE001 - statistics are best effort
            pass
        return out

    # -- public API ---------------------------------------------------------

    def solve(self, instance: Instance, *, timeout: float | None = None) -> SolveResult:
        z3 = _import_z3()
        start = time.perf_counter()
        solver, tile_v, rot_v = self._build(instance)
        if timeout is not None:
            solver.set("timeout", int(timeout * 1000))

        check = solver.check()
        elapsed = time.perf_counter() - start
        stats = self._stats(solver)

        if check == z3.sat:
            solution = self._extract(
                instance, solver.model(), tile_v, rot_v, self.name, stats
            )
            return SolveResult("sat", solution, None, None, elapsed, self.name, stats)
        if check == z3.unsat:
            return SolveResult("unsat", None, None, None, elapsed, self.name, stats)
        return SolveResult("unknown", None, None, None, elapsed, self.name, stats)

    def solve_unique(
        self, instance: Instance, *, timeout: float | None = None
    ) -> SolveResult:
        """Solve, then ask for a second solution with the first one blocked."""
        z3 = _import_z3()
        start = time.perf_counter()
        solver, tile_v, rot_v = self._build(instance)
        if timeout is not None:
            solver.set("timeout", int(timeout * 1000))

        first_check = solver.check()
        if first_check == z3.unsat:
            elapsed = time.perf_counter() - start
            return SolveResult(
                "unsat", None, None, None, elapsed, self.name, self._stats(solver)
            )
        if first_check != z3.sat:
            elapsed = time.perf_counter() - start
            return SolveResult(
                "unknown", None, None, None, elapsed, self.name, self._stats(solver)
            )

        model = solver.model()
        first = self._extract(instance, model, tile_v, rot_v, self.name, {})

        # Block this exact assignment and look for another.
        solver.add(
            z3.Not(
                z3.And(
                    *[
                        z3.And(
                            tile_v[i] == model[tile_v[i]].as_long(),
                            rot_v[i] == model[rot_v[i]].as_long(),
                        )
                        for i in range(instance.n_cells)
                    ]
                )
            )
        )
        second_check = solver.check()
        elapsed = time.perf_counter() - start
        stats = self._stats(solver)

        second: Solution | None = None
        if second_check == z3.sat:
            second = self._extract(
                instance, solver.model(), tile_v, rot_v, self.name, {}
            )
            unique: bool | None = False
        elif second_check == z3.unsat:
            unique = True
        else:
            unique = None  # timed out looking for a second solution

        first = Solution(first.instance_id, first.grid, self.name, stats)
        return SolveResult("sat", first, unique, second, elapsed, self.name, stats)
