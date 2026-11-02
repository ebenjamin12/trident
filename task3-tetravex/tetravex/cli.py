"""Command line interface: ``python -m tetravex <command>``.

Subcommands
-----------
``generate``  write a puzzle instance (and optionally its reference layout)
``solve``     solve an instance with a chosen engine
``verify``    check a solution against an instance, independently
``render``    draw an instance or a solution as ASCII or SVG
``engines``   report which backends are usable on this machine
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .generator import DIFFICULTY_PRESETS, generate
from .model import Instance, Solution
from .render import render_ascii, render_svg
from .solvers import ENGINES, get_solver
from .solvers.base import SolverUnavailable
from .verify import verify


def _read_instance(path: str) -> Instance:
    return Instance.loads(Path(path).read_text())


def _read_solution(path: str) -> Solution:
    return Solution.loads(Path(path).read_text())


def _write(path: str | None, text: str) -> None:
    if path is None or path == "-":
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    else:
        Path(path).write_text(text if text.endswith("\n") else text + "\n")
        print(f"wrote {path}", file=sys.stderr)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_generate(args: argparse.Namespace) -> int:
    puzzle = generate(
        args.rows,
        args.cols,
        symbols=args.symbols,
        seed=args.seed,
        allow_rotation=args.rotation,
        bordered=args.border,
        difficulty=args.difficulty,
    )
    if args.unique:
        solver = get_solver(args.engine)
        if not solver.available():
            print(
                f"engine {args.engine!r} unavailable; cannot filter for uniqueness",
                file=sys.stderr,
            )
            return 2
        attempts = 0
        seed = args.seed
        while attempts < args.max_attempts:
            result = solver.solve_unique(puzzle.instance, timeout=args.timeout)
            if result.sat and result.unique:
                break
            attempts += 1
            seed += 1
            puzzle = generate(
                args.rows,
                args.cols,
                symbols=args.symbols,
                seed=seed,
                allow_rotation=args.rotation,
                bordered=args.border,
                difficulty=args.difficulty,
            )
        else:
            print(
                f"no uniquely-solvable instance found in {args.max_attempts} attempts; "
                f"try more symbols or a fixed border",
                file=sys.stderr,
            )
            return 1
        print(f"found a uniquely-solvable instance after {attempts} retries", file=sys.stderr)

    _write(args.output, puzzle.instance.dumps())
    if args.with_solution:
        target = (
            args.with_solution
            if isinstance(args.with_solution, str)
            else (args.output or "instance") + ".solution.json"
        )
        Path(target).write_text(puzzle.reference.dumps() + "\n")
        print(f"wrote {target}", file=sys.stderr)
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    instance = _read_instance(args.instance)
    solver = get_solver(args.engine)
    try:
        if not solver.available():
            raise SolverUnavailable(f"engine {args.engine!r} is not available")
        result = (
            solver.solve_unique(instance, timeout=args.timeout)
            if args.unique
            else solver.solve(instance, timeout=args.timeout)
        )
    except SolverUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"engine={result.engine} status={result.status} "
        f"wall={result.elapsed * 1000:.1f}ms "
        + (f"unique={result.unique} " if args.unique else "")
        + f"stats={json.dumps(result.stats)}",
        file=sys.stderr,
    )

    if result.solution is None:
        if args.output and args.output != "-":
            Path(args.output).write_text(
                json.dumps({"status": result.status}, indent=2) + "\n"
            )
        return 0 if result.status == "unsat" else 1

    # Self-check before writing: the CLI refuses to emit a solution the
    # independent verifier rejects, whichever engine produced it.
    report = verify(instance, result.solution)
    if not report.ok:
        print(f"error: engine produced an invalid solution: {report.summary}",
              file=sys.stderr)
        for violation in report.violations[:10]:
            print(f"  {violation}", file=sys.stderr)
        return 3

    _write(args.output, result.solution.dumps())
    if args.ascii:
        print(render_ascii(instance, result.solution), file=sys.stderr)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    instance = _read_instance(args.instance)
    solution = _read_solution(args.solution)
    report = verify(instance, solution)
    print(report.summary)
    for violation in report.violations:
        print(f"  {violation}")
    return 0 if report.ok else 1


def cmd_render(args: argparse.Namespace) -> int:
    instance = _read_instance(args.instance)
    solution = _read_solution(args.solution) if args.solution else None
    if args.format == "ascii":
        text = render_ascii(instance, solution, show_ids=args.ids)
    else:
        text = render_svg(
            instance, solution, size=args.size, title=args.title
        )
    _write(args.output, text)
    return 0


def cmd_engines(_args: argparse.Namespace) -> int:
    for name in ENGINES:
        solver = get_solver(name)
        if solver.available():
            extra = ""
            if name == "prolog":
                extra = f"  [mode: {solver.mode()}]"  # type: ignore[attr-defined]
            print(f"{name:8s} available   {solver.version()}{extra}")
        else:
            print(f"{name:8s} UNAVAILABLE")
    return 0


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tetravex",
        description="TetraVex: generate, solve, verify and render edge-matching puzzles.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a puzzle instance")
    gen.add_argument("--rows", type=int, default=3)
    gen.add_argument("--cols", type=int, default=3)
    gen.add_argument("--symbols", type=int, default=10,
                     help="size of the edge alphabet (default: 10)")
    gen.add_argument("--seed", type=int, default=0)
    gen.add_argument("--rotation", action="store_true",
                     help="allow tiles to be rotated")
    gen.add_argument("--border", action="store_true",
                     help="pin the outer edges of the grid")
    gen.add_argument("--difficulty", choices=sorted(DIFFICULTY_PRESETS),
                     help="preset overriding --symbols and --border")
    gen.add_argument("--unique", action="store_true",
                     help="retry seeds until the instance has exactly one solution")
    gen.add_argument("--engine", choices=ENGINES, default="z3",
                     help="engine used by --unique (default: z3)")
    gen.add_argument("--max-attempts", type=int, default=50)
    gen.add_argument("--timeout", type=float, default=30.0)
    gen.add_argument("--with-solution", nargs="?", const=True, default=False,
                     help="also write the reference layout")
    gen.add_argument("-o", "--output", default="-")
    gen.set_defaults(func=cmd_generate)

    slv = sub.add_parser("solve", help="solve an instance")
    slv.add_argument("instance")
    slv.add_argument("--engine", choices=ENGINES, default="z3")
    slv.add_argument("--unique", action="store_true",
                     help="also report whether the solution is unique")
    slv.add_argument("--timeout", type=float, default=None)
    slv.add_argument("--ascii", action="store_true",
                     help="also print the solved board to stderr")
    slv.add_argument("-o", "--output", default="-")
    slv.set_defaults(func=cmd_solve)

    ver = sub.add_parser("verify", help="independently check a solution")
    ver.add_argument("instance")
    ver.add_argument("solution")
    ver.set_defaults(func=cmd_verify)

    ren = sub.add_parser("render", help="draw an instance or solution")
    ren.add_argument("instance")
    ren.add_argument("--solution", help="draw this solution instead of the tray")
    ren.add_argument("--format", choices=("ascii", "svg"), default="ascii")
    ren.add_argument("--ids", action="store_true",
                     help="label each cell with its tile id (ascii only)")
    ren.add_argument("--size", type=float, default=72.0, help="svg tile size in px")
    ren.add_argument("--title", default=None)
    ren.add_argument("-o", "--output", default="-")
    ren.set_defaults(func=cmd_render)

    eng = sub.add_parser("engines", help="report available backends")
    eng.set_defaults(func=cmd_engines)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
