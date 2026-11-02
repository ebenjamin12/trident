"""Benchmark harness comparing Blocks World planning engines.

Methodology
-----------
Both engines see **identical instances**, generated from recorded seeds, and
both are held to the same optimality criterion: every plan they return is
checked by the independent verifier, and the plan length is recorded so that a
disagreement shows up in the results table rather than being averaged away.

Two clocks are reported, because they measure different things here:

``wall``
    End-to-end, as the caller experiences it. For Z3 this is in-process. For
    Prolog it includes spawning a subprocess and, under the WASM fallback,
    booting the SWI-Prolog runtime before a single state is expanded.
``engine``
    What the engine reports about itself: ``cputime`` from Prolog's
    ``statistics/2``, and the sum of the per-horizon solve times for Z3.

Fixed startup cost is measured separately on a trivial instance -- one block,
goal equal to initial, where essentially all of the wall time is overhead --
and published alongside the table so Prolog's figures can be read with it
subtracted. Quoting the wall column alone would overstate the gap by about a
second per call; quoting the engine column alone would understate it by
ignoring a real cost. Both are given.

Search effort is recorded in each engine's own currency, and the two are *not*
comparable: Prolog counts expanded states, Z3 counts horizons attempted and
SAT conflicts. There is no honest conversion between them, so no ratio is
computed.

Suites
------
``blocks``       block count sweep: the headline scaling curve
``distance``     fixed block count, goals built by random walks of varying length
``branching``    fixed block count, varying how many stacks the states use
``unsolvable``   restricted-table instances with no plan
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics as stats_mod
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .engines import ENGINES, get_engine
from .engines.base import Engine, EngineUnavailable
from .generator import generate
from .model import Instance
from .verify import verify

DEFAULT_SEEDS = (1, 2, 3)


@dataclass
class Measurement:
    """One engine against one instance, repeated ``reps`` times."""

    engine: str
    strategy: str | None
    suite: str
    #: What the suite varied for this instance ("6 blocks", "walk 4", ...).
    #: This, not the block count, is the row key in the results table: the
    #: distance and branching suites hold the block count fixed and vary
    #: something else, so grouping by block count would merge unrelated
    #: configurations into one row.
    label: str
    instance_id: str
    n_blocks: int
    table_capacity: int
    seed: int
    initial_stacks: int
    heuristic: int
    status: str
    plan_length: int | None
    verified: bool | None
    reps: int
    wall_ms: list[float] = field(default_factory=list)
    engine_ms: list[float] = field(default_factory=list)
    nodes: int | None = None
    inferences: int | None = None
    horizons: int | None = None
    conflicts: int | None = None
    memory: float | None = None
    memory_unit: str | None = None
    error: str | None = None

    @property
    def wall_median(self) -> float | None:
        return stats_mod.median(self.wall_ms) if self.wall_ms else None


def _engine_ms(result) -> float | None:
    """Self-reported solve time, in whichever form the engine provides it."""
    cpu = result.stats.get("cputime_ms")
    if isinstance(cpu, (int, float)):
        return float(cpu)
    per_horizon = result.stats.get("per_horizon")
    if isinstance(per_horizon, list):
        return float(sum(h.get("ms", 0.0) for h in per_horizon))
    return None


def measure(
    engine: Engine,
    instance: Instance,
    *,
    suite: str,
    label: str,
    strategy: str | None,
    reps: int,
    timeout: float,
) -> Measurement:
    m = Measurement(
        engine=engine.name,
        strategy=strategy,
        suite=suite,
        label=label,
        instance_id=instance.id,
        n_blocks=instance.n_blocks,
        table_capacity=instance.table_capacity,
        seed=instance.seed if instance.seed is not None else -1,
        initial_stacks=instance.initial.n_stacks,
        heuristic=instance.heuristic(instance.initial),
        status="unknown",
        plan_length=None,
        verified=None,
        reps=reps,
    )
    last = None
    for _ in range(reps):
        start = time.perf_counter()
        try:
            last = engine.plan(instance, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            m.error = f"{type(exc).__name__}: {exc}"
            m.status = "error"
            return m
        m.wall_ms.append((time.perf_counter() - start) * 1000)
        reported = _engine_ms(last)
        if reported is not None:
            m.engine_ms.append(reported)

    assert last is not None
    m.status = last.status
    if last.plan.sat:
        m.plan_length = last.plan.length
        # Nothing is recorded as a success until the independent verifier
        # agrees it is one.
        m.verified = verify(instance, last.plan).ok
    s = last.stats
    m.nodes = s.get("nodes")
    m.inferences = s.get("inferences")
    m.horizons = s.get("horizons_attempted")
    m.conflicts = s.get("conflicts")
    if "max_memory" in s:
        m.memory, m.memory_unit = s["max_memory"], "MB (z3 max memory)"
    elif "global_stack_bytes" in s and s["global_stack_bytes"] not in (None, -1):
        m.memory = round(s["global_stack_bytes"] / 1024, 1)
        m.memory_unit = "KB (prolog global stack at exit)"
    return m


def startup_overhead(engine: Engine, *, reps: int = 3) -> float | None:
    """Wall time on a one-block instance whose goal already holds."""
    trivial = generate(1, seed=0).instance
    try:
        engine.plan(trivial)  # warm up, discarded
        samples = []
        for _ in range(reps):
            start = time.perf_counter()
            engine.plan(trivial)
            samples.append((time.perf_counter() - start) * 1000)
    except Exception:  # noqa: BLE001 - overhead is diagnostic only
        return None
    return stats_mod.median(samples)


def environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    for name in ENGINES:
        try:
            engine = get_engine(name)
            env[name] = engine.version() if engine.available() else "unavailable"
        except EngineUnavailable as exc:
            env[name] = f"unavailable ({exc})"
    return env


# --------------------------------------------------------------------------
# suites
# --------------------------------------------------------------------------


def suite_instances(
    suite: str,
    seeds: Iterable[int],
    sizes: Iterable[int],
    *,
    max_stacks: int | None = 2,
) -> list[tuple[str, Instance]]:
    """Instances for a named suite, as ``(label, instance)`` pairs.

    ``max_stacks`` matters more than it looks. Left unconstrained, a random
    partition of n blocks scatters most of them into singleton stacks, so both
    the initial and goal states already have most blocks resting on the table
    and the optimal plan is short -- measured at 0 to 6 moves for 3 to 8
    blocks, which barely exercises either engine. Forcing the blocks into two
    tall stacks produces the deadlocks that make the domain interesting (a
    block that must be moved twice because what it needs to sit on is itself
    buried), and optimal lengths rise to 6 to 12 over the same range. The
    default is therefore 2, and it is recorded in the config block of every
    results file.
    """
    out: list[tuple[str, Instance]] = []
    if suite == "blocks":
        for n in sizes:
            for seed in seeds:
                out.append((
                    f"{n} blocks",
                    generate(n, seed=seed, max_stacks=max_stacks).instance,
                ))
    elif suite == "distance":
        for walk in sizes:
            for seed in seeds:
                problem = generate(
                    6, seed=seed, walk=walk, max_stacks=max_stacks
                )
                out.append((f"walk {walk}", problem.instance))
    elif suite == "branching":
        for max_stacks in sizes:
            for seed in seeds:
                out.append((
                    f"{max_stacks} stacks",
                    generate(6, seed=seed, max_stacks=max_stacks).instance,
                ))
    elif suite == "unsolvable":
        for n in sizes:
            for seed in seeds:
                out.append((
                    f"{n} blocks cap 1",
                    generate(n, seed=seed, table_capacity=1, max_stacks=1).instance,
                ))
    else:
        raise ValueError(f"unknown suite {suite!r}")
    return out


DEFAULT_SIZES = {
    "blocks": (3, 4, 5, 6, 7, 8),
    "distance": (2, 4, 6, 8, 10),
    "branching": (1, 2, 3, 6),
    "unsolvable": (3, 4, 5),
}


def run(
    *,
    suites: tuple[str, ...],
    engine_specs: tuple[tuple[str, str | None], ...],
    seeds: tuple[int, ...],
    sizes: dict[str, tuple[int, ...]],
    reps: int,
    timeout: float,
    max_stacks: int | None = 2,
) -> dict[str, Any]:
    engines: list[tuple[str, str | None, Engine]] = []
    for name, strategy in engine_specs:
        kwargs = {"strategy": strategy} if (name == "prolog" and strategy) else {}
        engine = get_engine(name, **kwargs)
        if not engine.available():
            print(f"skipping {name}: toolchain unavailable", file=sys.stderr)
            continue
        engines.append((name, strategy, engine))

    overheads: dict[str, float | None] = {}
    for name, strategy, engine in engines:
        label = f"{name}:{strategy}" if strategy else name
        print(f"calibrating {label} startup overhead...", file=sys.stderr)
        overheads[label] = startup_overhead(engine)

    measurements: list[Measurement] = []
    for suite in suites:
        exhausted: set[str] = set()
        for label, instance in suite_instances(
            suite, seeds, sizes[suite], max_stacks=max_stacks
        ):
            for name, strategy, engine in engines:
                key = f"{name}:{strategy}" if strategy else name
                if key in exhausted:
                    continue
                print(
                    f"  [{suite}] {key:16s} {label:14s} seed={instance.seed} ...",
                    end="", file=sys.stderr, flush=True,
                )
                m = measure(
                    engine, instance, suite=suite, label=label,
                    strategy=strategy, reps=reps, timeout=timeout,
                )
                measurements.append(m)
                median = m.wall_median
                print(
                    f" {m.status}"
                    + (f" len={m.plan_length}" if m.plan_length is not None else "")
                    + (f" {median:.0f}ms" if median is not None else "")
                    + (f" verified={m.verified}" if m.verified is not None else "")
                    + (f" ERROR {m.error}" if m.error else ""),
                    file=sys.stderr,
                )
                if m.status in {"unknown", "error"}:
                    exhausted.add(key)
                    print(
                        f"  -> {key} hit the {timeout}s limit; "
                        f"larger instances skipped for this engine in this suite",
                        file=sys.stderr,
                    )

    return {
        "environment": environment(),
        "config": {
            "suites": list(suites),
            "engines": [f"{n}:{s}" if s else n for n, s, _ in engines],
            "seeds": list(seeds),
            "sizes": {k: list(v) for k, v in sizes.items() if k in suites},
            "reps": reps,
            "timeout_s": timeout,
            "max_stacks": max_stacks,
        },
        "startup_overhead_ms": overheads,
        "measurements": [asdict(m) for m in measurements],
    }


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _spread(values: list[float]) -> str:
    """Median plus observed range, so variability is visible."""
    if not values:
        return "n/a"
    if len(values) == 1:
        return f"{values[0]:.0f}"
    return f"{stats_mod.median(values):.0f} [{min(values):.0f}-{max(values):.0f}]"


def to_markdown(report: dict[str, Any]) -> str:
    cfg = report["config"]
    lines: list[str] = ["## Blocks World benchmark results\n"]
    lines.append(
        f"Every engine saw identical instances from seeds "
        f"{', '.join(map(str, cfg['seeds']))}, "
        f"{cfg['reps']} repetition(s) each, timeout {cfg['timeout_s']}s, "
        f"states limited to {cfg.get('max_stacks')} stack(s). "
        f"Every plan counted as a success was checked by the independent "
        f"verifier.\n"
    )

    overhead = report.get("startup_overhead_ms") or {}
    if overhead:
        parts = [
            f"`{k}` {v:.0f} ms" if isinstance(v, (int, float)) else f"`{k}` n/a"
            for k, v in overhead.items()
        ]
        lines.append(
            "**Fixed startup cost per call** (one-block instance, goal already "
            "satisfied): " + ", ".join(parts)
            + ". This is measured once per run and varies by tens of "
            "milliseconds between runs, so it is context for reading the wall "
            "column rather than a quantity to subtract from it -- the "
            "`engine ms` column is the engine's own directly measured solve "
            "time and is the figure to compare.\n"
        )

    by_suite: dict[str, list[dict[str, Any]]] = {}
    for m in report["measurements"]:
        by_suite.setdefault(m["suite"], []).append(m)

    for suite, rows in by_suite.items():
        lines.append(f"\n### Suite: `{suite}`\n")
        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        order: list[str] = []
        for m in rows:
            key = m.get("label") or f"{m['n_blocks']} blocks"
            if key not in grouped:
                order.append(key)
            grouped.setdefault(key, {}).setdefault(
                f"{m['engine']}:{m['strategy']}" if m["strategy"] else m["engine"], []
            ).append(m)

        engine_keys = cfg["engines"]
        header = (
            "| Configuration | Blocks | Optimal length | "
            + " | ".join(f"{e} wall ms" for e in engine_keys)
            + " | "
            + " | ".join(f"{e} engine ms" for e in engine_keys)
            + " | "
            + " | ".join(f"{e} effort" for e in engine_keys)
            + " | lengths agree | all verified |"
        )
        lines.append(header)
        lines.append("|" + "---|" * (3 + 3 * len(engine_keys) + 2))

        for config_label in order:
            per_engine = grouped[config_label]
            group_rows = [
                m for m in rows if (m.get("label") or "") == config_label
            ]
            n_blocks = group_rows[0]["n_blocks"] if group_rows else 0
            wall_cells, engine_cells, effort_cells = [], [], []
            lengths: set[int | None] = set()
            verified_flags: list[bool | None] = []
            for engine_key in engine_keys:
                entries = per_engine.get(engine_key, [])
                if not entries:
                    wall_cells.append("skipped")
                    engine_cells.append("-")
                    effort_cells.append("-")
                    continue
                walls = [
                    stats_mod.median(e["wall_ms"]) for e in entries if e["wall_ms"]
                ]
                wall_cells.append(_spread(walls))
                engine_times = [
                    stats_mod.median(e["engine_ms"])
                    for e in entries
                    if e.get("engine_ms")
                ]
                engine_cells.append(_spread(engine_times) if engine_times else "-")
                nodes = [e["nodes"] for e in entries if e["nodes"] is not None]
                horizons = [
                    e["horizons"] for e in entries if e["horizons"] is not None
                ]
                if nodes:
                    effort_cells.append(f"{int(stats_mod.median(nodes))} states")
                elif horizons:
                    effort_cells.append(f"{int(stats_mod.median(horizons))} horizons")
                else:
                    effort_cells.append("-")
                lengths |= {e["plan_length"] for e in entries}
                verified_flags += [
                    e["verified"] for e in entries if e["verified"] is not None
                ]

            observed = sorted(
                {x for x in lengths if x is not None}
            )
            length_text = (
                ", ".join(str(x) for x in observed) if observed else "no plan"
            )
            # Agreement is checked per *instance id*. Comparing a pooled
            # set of lengths would be wrong, since different seeds legitimately
            # have different optima, and comparing per seed would be wrong too
            # when a suite varies something else while reusing seed numbers.
            agree = "yes"
            instance_ids = {e["instance_id"] for e in group_rows}
            for instance_id in instance_ids:
                per_instance = {
                    e["plan_length"]
                    for entries in per_engine.values()
                    for e in entries
                    if e["instance_id"] == instance_id
                }
                if len(per_instance) > 1:
                    agree = "NO"
            all_verified = (
                "yes" if verified_flags and all(verified_flags) else
                ("n/a" if not verified_flags else "NO")
            )
            lines.append(
                f"| {config_label} | {n_blocks} | {length_text} | "
                + " | ".join(wall_cells)
                + " | "
                + " | ".join(engine_cells)
                + " | "
                + " | ".join(effort_cells)
                + f" | {agree} | {all_verified} |"
            )

    lines.append("\n### Environment\n")
    for key, value in report["environment"].items():
        lines.append(f"- **{key}**: {value}")
    lines.append(
        "\n`wall ms` includes each engine's fixed startup cost. `engine ms` is "
        "self-reported solve time: `cputime` from Prolog's `statistics/2`, and "
        "the sum of per-horizon solve times for Z3. Search-effort columns are "
        "in each engine's own units and are **not** comparable with one "
        "another -- there is no honest conversion between states expanded and "
        "horizons attempted, so no ratio is computed."
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m blocksworld.bench",
        description="Benchmark Blocks World planning engines on identical instances.",
    )
    parser.add_argument("--suites", default="blocks",
                        help="comma-separated: blocks,distance,branching,unsolvable")
    parser.add_argument("--engines", default="prolog:idastar,z3",
                        help="comma-separated engine[:strategy] specs")
    parser.add_argument("--blocks", default=None,
                        help="comma-separated sizes for the active suite")
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-stacks", type=int, default=2,
                        help="stacks the random states may use; 2 produces the "
                             "deadlock-heavy instances worth measuring")
    parser.add_argument("-o", "--output", default="bench/results.json")
    parser.add_argument("--markdown", default="bench/results.md")
    args = parser.parse_args(argv)

    suites = tuple(s.strip() for s in args.suites.split(",") if s.strip())
    specs: list[tuple[str, str | None]] = []
    for raw in args.engines.split(","):
        raw = raw.strip()
        if not raw:
            continue
        name, _, strategy = raw.partition(":")
        specs.append((name, strategy or None))

    sizes = dict(DEFAULT_SIZES)
    if args.blocks:
        explicit = tuple(int(x) for x in args.blocks.split(","))
        for suite in suites:
            sizes[suite] = explicit

    report = run(
        suites=suites,
        engine_specs=tuple(specs),
        seeds=tuple(int(s) for s in args.seeds.split(",")),
        sizes=sizes,
        reps=args.reps,
        timeout=args.timeout,
        max_stacks=args.max_stacks,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {out}", file=sys.stderr)

    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(to_markdown(report))
    print(f"wrote {md}", file=sys.stderr)

    print()
    print(to_markdown(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
