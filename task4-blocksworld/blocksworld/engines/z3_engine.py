"""Blocks World planning as satisfiability, solved with Z3.

This is the Kautz & Selman formulation: rather than searching the state space,
assert "there is a plan of exactly ``T`` steps" as a constraint system and ask
the solver. Start at ``T = 0`` and increment until a model appears.

The encoding
------------
Blocks are indexed ``0..n-1``; the integer ``n`` denotes the table. For each
time step ``t`` in ``0..T``:

``on[b][t]``
    what block ``b`` rests on: another block's index, or ``n`` for the table.
``height[b][t]``
    how far ``b`` sits above the table, in ``0..n-1``.

State validity, asserted at *every* step including the first and last:

1. ``on[b][t] != b`` -- nothing rests on itself.
2. For ``b1 != b2``: if ``on[b1][t]`` is not the table then
   ``on[b1][t] != on[b2][t]`` -- a block supports at most one other block.
   The table is exempt, since many stacks may share it.
3. ``on[b][t] == table  ->  height[b][t] == 0`` and
   ``on[b][t] == c      ->  height[b][t] == height[c][t] + 1``.
4. ``Sum(on[b][t] == table) <= table_capacity``.

Why constraint 3 is needed, and why it is enough. Constraints 1 and 2 alone
permit a cycle: ``A`` on ``B`` and ``B`` on ``A`` satisfies both, yet describes
no physical arrangement. Requiring each block to sit exactly one unit above its
support makes any cycle demand ``h = h + k`` for ``k >= 1``, which no finite
integer satisfies. With cycles ruled out, the ``on`` relation is a forest of
chains rooted at the table -- which is precisely a set of stacks.

For each transition ``t`` in ``0..T-1`` there is exactly one action, expressed
by two variables rather than by a set of mutually exclusive booleans:

``mover[t]`` in ``0..n-1`` and ``dest[t]`` in ``0..n``

Making the action a single integer gives action exclusivity for free -- there
is no way to express two simultaneous moves, so no at-most-one constraint is
needed and no two actions can interfere. Preconditions:

* ``on[b][t] != mover[t]`` for every ``b`` -- the moved block is clear.
* ``dest[t] != table -> on[b][t] != dest[t]`` for every ``b`` -- the
  destination is clear.
* ``dest[t] != mover[t]``.
* ``mover[t] == b  ->  dest[t] != on[b][t]`` -- the destination differs from
  where the block already is, so every step is a genuine move.

Effects and frame, for every block ``b``:

* ``mover[t] == b  ->  on[b][t+1] == dest[t]``
* ``mover[t] != b  ->  on[b][t+1] == on[b][t]``

Optimality
----------
Because every step is forced to be a real move, a model at horizon ``T``
corresponds to a plan of exactly ``T`` moves, and conversely any ``T``-move
plan yields a model. Horizons are tried in increasing order from 0, so the
first satisfiable horizon is the minimum number of moves -- the optimal plan
length under the unit-cost model. No separate optimisation step is required.

Unsatisfiability
----------------
Exhausting horizons proves nothing in general: a plan might simply be longer
than the horizons tried. The result is therefore reported as ``limit`` unless
the horizon reached is at least the instance's completeness bound (``2n`` when
the table can hold every block), in which case no longer plan can exist and
``unsat`` is justified. Timeouts are reported as ``unknown`` and never confused
with either.
"""

from __future__ import annotations

import time
from typing import Any

from ..model import TABLE, Action, Instance, Plan
from .base import Engine, EngineUnavailable, PlanResult

#: Z3 statistics worth reporting; it emits dozens, these describe search effort.
_STAT_KEYS = ("conflicts", "decisions", "propagations", "restarts", "max memory")


def _import_z3():
    try:
        import z3  # noqa: PLC0415 - imported lazily so the package works without it
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise EngineUnavailable(
            "z3-solver is not installed; run `pip install -r requirements.txt`"
        ) from exc
    return z3


class Z3Engine(Engine):
    """Bounded-horizon SAT planning backend."""

    name = "z3"

    def available(self) -> bool:
        try:
            _import_z3()
        except EngineUnavailable:
            return False
        return True

    def version(self) -> str:
        z3 = _import_z3()
        return f"Z3 {z3.get_version_string()}"

    # -- encoding -----------------------------------------------------------

    def _encode(self, instance: Instance, horizon: int):
        """Build the constraint system for exactly ``horizon`` moves."""
        z3 = _import_z3()
        blocks = list(instance.blocks)
        n = len(blocks)
        index = {name: i for i, name in enumerate(blocks)}
        table = n

        def support_index(name: str) -> int:
            return table if name == TABLE else index[name]

        solver = z3.Solver()

        on = [
            [z3.Int(f"on_{b}_{t}") for t in range(horizon + 1)] for b in range(n)
        ]
        height = [
            [z3.Int(f"h_{b}_{t}") for t in range(horizon + 1)] for b in range(n)
        ]

        # -- state validity at every step ---------------------------------
        for t in range(horizon + 1):
            for b in range(n):
                solver.add(on[b][t] >= 0, on[b][t] <= table)
                solver.add(on[b][t] != b)
                solver.add(height[b][t] >= 0, height[b][t] <= n - 1)
                # Well-founded heights rule out cycles (see module docstring).
                solver.add(z3.Implies(on[b][t] == table, height[b][t] == 0))
                for c in range(n):
                    if c != b:
                        solver.add(
                            z3.Implies(
                                on[b][t] == c, height[b][t] == height[c][t] + 1
                            )
                        )
            # A block supports at most one other block; the table is exempt.
            for b1 in range(n):
                for b2 in range(b1 + 1, n):
                    solver.add(
                        z3.Implies(on[b1][t] != table, on[b1][t] != on[b2][t])
                    )
            # Finite table.
            solver.add(
                z3.Sum([z3.If(on[b][t] == table, 1, 0) for b in range(n)])
                <= instance.table_capacity
            )

        # -- initial and goal ----------------------------------------------
        initial_supports = instance.initial.supports()
        goal_supports = instance.goal.supports()
        for name, i in index.items():
            solver.add(on[i][0] == support_index(initial_supports[name]))
            solver.add(on[i][horizon] == support_index(goal_supports[name]))

        # -- actions --------------------------------------------------------
        movers = [z3.Int(f"mover_{t}") for t in range(horizon)]
        dests = [z3.Int(f"dest_{t}") for t in range(horizon)]

        for t in range(horizon):
            solver.add(movers[t] >= 0, movers[t] <= n - 1)
            solver.add(dests[t] >= 0, dests[t] <= table)
            solver.add(dests[t] != movers[t])
            for b in range(n):
                # the moved block is clear
                solver.add(on[b][t] != movers[t])
                # the destination is clear, when it is a block
                solver.add(z3.Implies(dests[t] != table, on[b][t] != dests[t]))
                # the move must change something
                solver.add(z3.Implies(movers[t] == b, dests[t] != on[b][t]))
                # effect and frame
                solver.add(z3.Implies(movers[t] == b, on[b][t + 1] == dests[t]))
                solver.add(z3.Implies(movers[t] != b, on[b][t + 1] == on[b][t]))

        return solver, movers, dests, blocks, table

    @staticmethod
    def _extract(model, movers, dests, blocks, table, on_at_step) -> tuple[Action, ...]:
        actions: list[Action] = []
        for t in range(len(movers)):
            mover = model[movers[t]].as_long()
            dest = model[dests[t]].as_long()
            source = on_at_step(model, mover, t)
            actions.append(
                Action(
                    block=blocks[mover],
                    source=TABLE if source == table else blocks[source],
                    destination=TABLE if dest == table else blocks[dest],
                )
            )
        return tuple(actions)

    @staticmethod
    def _stats(solver) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            raw = solver.statistics()
            for key in _STAT_KEYS:
                try:
                    out[key.replace(" ", "_")] = raw.get_key_value(key)
                except Exception:  # noqa: BLE001 - key absent for this run
                    pass
        except Exception:  # noqa: BLE001 - statistics are best effort
            pass
        return out

    # -- public API ---------------------------------------------------------

    def plan(
        self,
        instance: Instance,
        *,
        timeout: float | None = None,
        max_depth: int | None = None,
    ) -> PlanResult:
        z3 = _import_z3()

        structural = instance.structurally_unsolvable()
        if structural is not None:
            plan = Plan(
                instance.id, "unsat", (), self.name,
                {"reason": structural, "proof": "structural", "horizons": 0},
            )
            return PlanResult(plan, 0.0, self.name, plan.stats)

        bound = max_depth
        if bound is None:
            bound = instance.completeness_bound
        if bound is None:
            bound = 4 * instance.n_blocks

        start = time.perf_counter()
        horizons: list[dict[str, Any]] = []
        last_stats: dict[str, Any] = {}

        for horizon in range(bound + 1):
            remaining = None
            if timeout is not None:
                remaining = timeout - (time.perf_counter() - start)
                if remaining <= 0:
                    stats = {
                        "horizons_attempted": len(horizons),
                        "per_horizon": horizons,
                        "max_horizon": bound,
                        **last_stats,
                    }
                    plan = Plan(instance.id, "unknown", (), self.name, stats)
                    return PlanResult(
                        plan, time.perf_counter() - start, self.name, stats
                    )

            solver, movers, dests, blocks, table = self._encode(instance, horizon)
            if remaining is not None:
                solver.set("timeout", max(int(remaining * 1000), 1))

            step_start = time.perf_counter()
            check = solver.check()
            step_elapsed = (time.perf_counter() - step_start) * 1000
            last_stats = self._stats(solver)
            horizons.append(
                {"horizon": horizon, "result": str(check), "ms": round(step_elapsed, 3)}
            )

            if check == z3.sat:
                model = solver.model()

                def on_at_step(m, block_index: int, t: int) -> int:
                    return m[z3.Int(f"on_{block_index}_{t}")].as_long()

                actions = self._extract(
                    model, movers, dests, blocks, table, on_at_step
                )
                stats = {
                    "horizons_attempted": len(horizons),
                    "per_horizon": horizons,
                    "max_horizon": bound,
                    "optimal_horizon": horizon,
                    **last_stats,
                }
                plan = Plan(instance.id, "sat", actions, self.name, stats)
                return PlanResult(
                    plan, time.perf_counter() - start, self.name, stats
                )

            if check != z3.unsat:
                # unknown: the solver gave up on this horizon, so nothing can
                # be concluded about longer ones either.
                stats = {
                    "horizons_attempted": len(horizons),
                    "per_horizon": horizons,
                    "max_horizon": bound,
                    **last_stats,
                }
                plan = Plan(instance.id, "unknown", (), self.name, stats)
                return PlanResult(
                    plan, time.perf_counter() - start, self.name, stats
                )

        # Every horizon up to `bound` was unsatisfiable.
        elapsed = time.perf_counter() - start
        stats = {
            "horizons_attempted": len(horizons),
            "per_horizon": horizons,
            "max_horizon": bound,
            **last_stats,
        }
        completeness = instance.completeness_bound
        if completeness is not None and bound >= completeness:
            stats["proof"] = f"no plan within completeness bound {completeness}"
            plan = Plan(instance.id, "unsat", (), self.name, stats)
        else:
            plan = Plan(instance.id, "limit", (), self.name, stats)
        return PlanResult(plan, elapsed, self.name, stats)
