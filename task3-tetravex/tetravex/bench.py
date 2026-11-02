"""Benchmark harness comparing TetraVex solver backends.

Measurement notes
-----------------
Two clocks are reported, because for this pair of engines they measure very
different things:

``wall``
    End-to-end time as the caller experiences it. For Z3 this is in-process.
    For Prolog it includes spawning a subprocess and, under the WASM fallback,
    booting the SWI-Prolog runtime -- on the order of a second before any
    constraint is posted.
``engine``
    Time reported by the engine itself: ``cputime`` from Prolog's
    ``statistics/2``. Z3 does not expose a comparable figure through the Python
    API, so this column is blank for Z3 and its ``wall`` is already close to
    pure solve time.

The harness therefore also measures startup overhead directly, by timing a
1x1 instance -- the smallest possible problem, where essentially all of the
wall time is fixed cost. That figure is reported alongside the results so
Prolog's numbers can be read with it subtracted.

Comparing ``wall`` across the two engines without that context overstates the
gap. Comparing ``engine`` understates it, because it excludes real costs the
Prolog path genuinely pays. Both are published; neither is presented alone.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .generator import generate
from .model import Instance
from .solvers import ENGINES, get_solver
from .solvers.base import Solver, SolverUnavailable
from .verify import verify

#: Board shapes, smallest first. Larger shapes are attempted only while the
#: previous one stayed inside the timeout.
DEFAULT_SIZES = ((2, 2), (2, 3), (3, 3), (3, 4), (4, 4), (4, 5), (5, 5))
DEFAULT_SEEDS = (1, 2, 3, 4, 5)
DEFAULT_SYMBOLS = 6


@dataclass
class Measurement:
    """One engine against one instance, repeated ``reps`` times."""

    engine: str
    instance_id: str
    rows: int
    cols: int
    symbols: int
    seed: int
    status: str
    verified: bool | None
    reps: int
    wall_ms: list[float] = field(default_factory=list)
    engine_ms: list[float] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def wall_median(self) -> float | None:
        return statistics.median(self.wall_ms) if self.wall_ms else None

    @property
    def wall_min(self) -> float | None:
        return min(self.wall_ms) if self.wall_ms else None

    @property
    def engine_median(self) -> float | None:
        return statistics.median(self.engine_ms) if self.engine_ms else None


def _engine_ms(result) -> float | None:
    value = result.stats.get("cputime_ms")
    return float(value) if isinstance(value, (int, float)) else None


def measure(
    solver: Solver,
    instance: Instance,
    *,
    reps: int,
    timeout: float,
    unique: bool,
) -> Measurement:
    m = Measurement(
        engine=solver.name,
        instance_id=instance.id,
        rows=instance.rows,
        cols=instance.cols,
        symbols=instance.symbols,
        seed=instance.seed if instance.seed is not None else -1,
        status="unknown",
        verified=None,
        reps=reps,
    )
    last = None
    for _ in range(reps):
        start = time.perf_counter()
        try:
            last = (
                solver.solve_unique(instance, timeout=timeout)
                if unique
                else solver.solve(instance, timeout=timeout)
            )
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            m.error = f"{type(exc).__name__}: {exc}"
            m.status = "error"
            return m
        m.wall_ms.append((time.perf_counter() - start) * 1000)
        engine_time = _engine_ms(last)
        if engine_time is not None:
            m.engine_ms.append(engine_time)

    assert last is not None
    m.status = last.status
    m.stats = dict(last.stats)
    if last.solution is not None:
        m.verified = verify(instance, last.solution).ok
    return m


def startup_overhead(solver: Solver, *, reps: int = 3) -> float | None:
    """Wall time for the smallest possible instance: almost all fixed cost."""
    tiny = generate(1, 1, symbols=2, seed=0).instance
    try:
        solver.solve(tiny)  # warm up, discarded
        samples = []
        for _ in range(reps):
            start = time.perf_counter()
            solver.solve(tiny)
            samples.append((time.perf_counter() - start) * 1000)
    except Exception:  # noqa: BLE001 - overhead is diagnostic only
        return None
    return statistics.median(samples)


def environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    for name in ENGINES:
        try:
            solver = get_solver(name)
            env[name] = solver.version() if solver.available() else "unavailable"
        except SolverUnavailable as exc:
            env[name] = f"unavailable ({exc})"
    return env


def run(
    *,
    engines: tuple[str, ...],
    sizes: tuple[tuple[int, int], ...],
    seeds: tuple[int, ...],
    symbols: int,
    reps: int,
    timeout: float,
    unique: bool,
    bordered: bool,
    rotation: bool,
) -> dict[str, Any]:
    solvers: dict[str, Solver] = {}
    for name in engines:
        solver = get_solver(name)
        if not solver.available():
            print(f"skipping {name}: toolchain unavailable", file=sys.stderr)
            continue
        solvers[name] = solver

    overheads = {}
    for name, solver in solvers.items():
        print(f"calibrating {name} startup overhead...", file=sys.stderr)
        overheads[name] = startup_overhead(solver)

    measurements: list[Measurement] = []
    # Engines that have blown the timeout stop being asked for larger boards.
    exhausted: set[str] = set()

    for rows, cols in sizes:
        for seed in seeds:
            puzzle = generate(
                rows, cols, symbols=symbols, seed=seed,
                allow_rotation=rotation, bordered=bordered,
            )
            for name, solver in solvers.items():
                if name in exhausted:
                    continue
                print(
                    f"  {name:7s} {rows}x{cols} seed={seed} ...",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )
                m = measure(
                    solver, puzzle.instance,
                    reps=reps, timeout=timeout, unique=unique,
                )
                measurements.append(m)
                median = m.wall_median
                print(
                    f" {m.status}"
                    + (f" {median:.1f}ms" if median is not None else "")
                    + (f" verified={m.verified}" if m.verified is not None else "")
                    + (f" ERROR {m.error}" if m.error else ""),
                    file=sys.stderr,
                )
                if m.status in {"unknown", "error"}:
                    exhausted.add(name)
                    print(
                        f"  -> {name} hit the {timeout}s limit; "
                        f"larger boards skipped for this engine",
                        file=sys.stderr,
                    )

    return {
        "environment": environment(),
        "config": {
            "engines": list(solvers),
            "sizes": [list(s) for s in sizes],
            "seeds": list(seeds),
            "symbols": symbols,
            "reps": reps,
            "timeout_s": timeout,
            "unique": unique,
            "bordered": bordered,
            "rotation": rotation,
        },
        "startup_overhead_ms": overheads,
        "measurements": [asdict(m) for m in measurements],
    }


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def to_markdown(report: dict[str, Any]) -> str:
    cfg = report["config"]
    env = report["environment"]
    rows_out: list[str] = []

    rows_out.append("## Benchmark results\n")
    rows_out.append(
        f"Each cell is the median of **{cfg['reps']} repetition(s)** over "
        f"**{len(cfg['seeds'])} seed(s)** per board size "
        f"(seeds {', '.join(map(str, cfg['seeds']))}), "
        f"{cfg['symbols']} edge symbols, "
        f"{'uniqueness checked' if cfg['unique'] else 'first solution only'}, "
        f"timeout {cfg['timeout_s']}s.\n"
    )

    overhead = report.get("startup_overhead_ms") or {}
    if overhead:
        parts = [
            f"`{k}` {v:.1f} ms" if isinstance(v, (int, float)) else f"`{k}` n/a"
            for k, v in overhead.items()
        ]
        rows_out.append(
            "**Fixed startup cost per call** (measured on a 1x1 board): "
            + ", ".join(parts)
            + ". Subtract this from the wall-clock column to compare search effort.\n"
        )

    # group by (rows, cols)
    grouped: dict[tuple[int, int], dict[str, list[dict[str, Any]]]] = {}
    for m in report["measurements"]:
        grouped.setdefault((m["rows"], m["cols"]), {}).setdefault(m["engine"], []).append(m)

    engines = cfg["engines"]
    header = "| Board | Cells | " + " | ".join(
        f"{e} wall (ms)" for e in engines
    ) + " | " + " | ".join(f"{e} engine (ms)" for e in engines) + " | solved | agree |"
    sep = "|" + "---|" * (2 + 2 * len(engines) + 2)
    rows_out.append(header)
    rows_out.append(sep)

    for (rows, cols) in sorted(grouped, key=lambda rc: rc[0] * rc[1]):
        per_engine = grouped[(rows, cols)]
        wall_cells, engine_cells = [], []
        statuses: dict[str, set[str]] = {}
        solved_total = attempted_total = 0
        for engine in engines:
            entries = per_engine.get(engine, [])
            if not entries:
                wall_cells.append("skipped")
                engine_cells.append("-")
                continue
            walls = [
                statistics.median(e["wall_ms"]) for e in entries if e["wall_ms"]
            ]
            engs = [
                statistics.median(e["engine_ms"]) for e in entries if e["engine_ms"]
            ]
            wall_cells.append(f"{statistics.median(walls):.1f}" if walls else "n/a")
            engine_cells.append(f"{statistics.median(engs):.1f}" if engs else "-")
            statuses[engine] = {e["status"] for e in entries}
            solved_total += sum(1 for e in entries if e["status"] == "sat")
            attempted_total += len(entries)

        agree = "yes" if len({frozenset(s) for s in statuses.values()}) <= 1 else "NO"
        rows_out.append(
            f"| {rows}x{cols} | {rows * cols} | "
            + " | ".join(wall_cells)
            + " | "
            + " | ".join(engine_cells)
            + f" | {solved_total}/{attempted_total} | {agree} |"
        )

    rows_out.append("")
    rows_out.append("### Environment\n")
    for key, value in env.items():
        rows_out.append(f"- **{key}**: {value}")
    return "\n".join(rows_out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tetravex.bench",
        description="Benchmark TetraVex solver backends on identical instances.",
    )
    parser.add_argument("--engines", default=",".join(ENGINES))
    parser.add_argument(
        "--sizes",
        default=",".join(f"{r}x{c}" for r, c in DEFAULT_SIZES),
        help="comma-separated RxC board sizes",
    )
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--symbols", type=int, default=DEFAULT_SYMBOLS)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--unique", action="store_true")
    parser.add_argument("--border", action="store_true")
    parser.add_argument("--rotation", action="store_true")
    parser.add_argument("-o", "--output", default="bench/results.json")
    parser.add_argument("--markdown", default="bench/results.md")
    args = parser.parse_args(argv)

    sizes = tuple(
        tuple(int(part) for part in spec.lower().split("x"))  # type: ignore[misc]
        for spec in args.sizes.split(",")
    )
    report = run(
        engines=tuple(args.engines.split(",")),
        sizes=sizes,  # type: ignore[arg-type]
        seeds=tuple(int(s) for s in args.seeds.split(",")),
        symbols=args.symbols,
        reps=args.reps,
        timeout=args.timeout,
        unique=args.unique,
        bordered=args.border,
        rotation=args.rotation,
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
