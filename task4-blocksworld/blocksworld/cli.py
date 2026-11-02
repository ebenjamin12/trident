"""Command line interface: ``python -m blocksworld <command>``.

Follows the conventions established by ``tetravex/cli.py``: the same
subcommand names where they mean the same thing, the same exit codes, results
to stdout and diagnostics to stderr.

Subcommands
-----------
``generate``  write a planning problem
``solve``     plan with a chosen engine; refuses to emit an unverified plan
``verify``    check a plan against a problem, independently
``render``    draw the problem or a plan (ascii, svg, filmstrip, animation, gif)
``engines``   report which backends are usable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engines import ENGINES, get_engine
from .engines.base import EngineUnavailable
from .engines.prolog_engine import STRATEGIES
from .generator import generate
from .model import Instance, Plan
from .render import (
    GifUnavailable,
    render_ascii_plan,
    render_ascii_problem,
    render_gif,
    render_svg_animated,
    render_svg_filmstrip,
    render_svg_state,
)
from .verify import verify

EXIT_OK = 0
EXIT_NO_PLAN = 1
EXIT_UNAVAILABLE = 2
EXIT_BAD_PLAN = 3


def _read_instance(path: str) -> Instance:
    return Instance.loads(Path(path).read_text())


def _read_plan(path: str) -> Plan:
    return Plan.loads(Path(path).read_text())


def _write(path: str | None, text: str) -> None:
    if path is None or path == "-":
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    else:
        Path(path).write_text(text if text.endswith("\n") else text + "\n")
        print(f"wrote {path}", file=sys.stderr)


def _engine_for(args: argparse.Namespace):
    if args.engine == "prolog":
        return get_engine("prolog", strategy=args.strategy)
    return get_engine(args.engine)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_generate(args: argparse.Namespace) -> int:
    problem = generate(
        args.blocks,
        seed=args.seed,
        table_capacity=args.capacity,
        max_stacks=args.max_stacks,
        walk=args.walk,
    )
    _write(args.output, problem.instance.dumps())
    if problem.walk_length is not None:
        print(
            f"goal built by {problem.walk_length} random move(s); "
            f"the optimum is at most that",
            file=sys.stderr,
        )
    if args.ascii:
        print(render_ascii_problem(problem.instance), file=sys.stderr)
    return EXIT_OK


def cmd_solve(args: argparse.Namespace) -> int:
    instance = _read_instance(args.instance)
    try:
        engine = _engine_for(args)
        if not engine.available():
            raise EngineUnavailable(f"engine {args.engine!r} is not available")
        result = engine.plan(
            instance, timeout=args.timeout, max_depth=args.max_depth
        )
    except EngineUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    print(
        f"engine={result.engine} status={result.status} "
        f"length={result.length} wall={result.elapsed * 1000:.1f}ms "
        f"stats={json.dumps(result.stats, default=str)}",
        file=sys.stderr,
    )

    if not result.plan.sat:
        _write(args.output, result.plan.dumps())
        if result.status == "unsat":
            print(
                "proved unsolvable: "
                + str(result.stats.get("proof", "no justification recorded")),
                file=sys.stderr,
            )
            return EXIT_OK
        print(
            f"no plan found ({result.status}); this is NOT a proof that none exists",
            file=sys.stderr,
        )
        return EXIT_NO_PLAN

    # Independent check before anything is emitted. A plan that fails here is
    # an engine bug, and publishing it would hide that.
    report = verify(instance, result.plan)
    if not report.ok:
        print(
            f"error: engine produced an invalid plan: {report.summary}",
            file=sys.stderr,
        )
        for violation in report.violations[:10]:
            print(f"  {violation}", file=sys.stderr)
        return EXIT_BAD_PLAN

    _write(args.output, result.plan.dumps())
    if args.explain:
        print("\n".join(result.plan.explain()), file=sys.stderr)
    if args.ascii:
        print(
            render_ascii_plan(instance, report.states, result.plan.actions),
            file=sys.stderr,
        )
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    instance = _read_instance(args.instance)
    plan = _read_plan(args.solution)
    report = verify(instance, plan)
    print(report.summary)
    for violation in report.violations:
        print(f"  {violation}")
    if report.ok and args.optimal is not None:
        if plan.length != args.optimal:
            print(
                f"  [optimality] plan has {plan.length} moves "
                f"but the stated optimum is {args.optimal}"
            )
            return EXIT_BAD_PLAN
        print(f"  optimality confirmed against stated optimum {args.optimal}")
    return EXIT_OK if report.ok else EXIT_BAD_PLAN


def cmd_render(args: argparse.Namespace) -> int:
    instance = _read_instance(args.instance)

    if args.solution is None:
        if args.format in {"filmstrip", "animated-svg", "gif"}:
            print(
                f"error: --format {args.format} needs --solution",
                file=sys.stderr,
            )
            return EXIT_NO_PLAN
        text = (
            render_ascii_problem(instance)
            if args.format == "ascii"
            else render_svg_state(instance, instance.initial, title="initial")
        )
        _write(args.output, text)
        return EXIT_OK

    plan = _read_plan(args.solution)
    report = verify(instance, plan)
    if not report.ok:
        # Rendering an unverified plan would draw a picture of something that
        # cannot happen, so the renderers are gated on verification.
        print(
            f"error: refusing to render an invalid plan: {report.summary}",
            file=sys.stderr,
        )
        for violation in report.violations[:10]:
            print(f"  {violation}", file=sys.stderr)
        return EXIT_BAD_PLAN

    states, actions = report.states, plan.actions

    if args.format == "ascii":
        _write(args.output, render_ascii_plan(instance, states, actions))
    elif args.format == "svg":
        _write(
            args.output,
            render_svg_state(instance, states[-1], title="final state"),
        )
    elif args.format == "filmstrip":
        _write(args.output, render_svg_filmstrip(instance, states, actions))
    elif args.format == "animated-svg":
        _write(
            args.output,
            render_svg_animated(
                instance, states, actions, seconds_per_step=args.seconds
            ),
        )
    elif args.format == "gif":
        target = args.output if args.output not in (None, "-") else "plan.gif"
        try:
            render_gif(
                instance, states, actions, target,
                ms_per_step=int(args.seconds * 1000),
            )
        except GifUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_UNAVAILABLE
        print(f"wrote {target}", file=sys.stderr)
    return EXIT_OK


def cmd_engines(_args: argparse.Namespace) -> int:
    for name in ENGINES:
        engine = get_engine(name)
        if engine.available():
            extra = ""
            if name == "prolog":
                extra = f"  [mode: {engine.mode()}]"  # type: ignore[attr-defined]
            print(f"{name:8s} available   {engine.version()}{extra}")
        else:
            print(f"{name:8s} UNAVAILABLE")
    return EXIT_OK


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m blocksworld",
        description="Blocks World: generate, plan, verify and render.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a planning problem")
    gen.add_argument("--blocks", type=int, default=5)
    gen.add_argument("--seed", type=int, default=0)
    gen.add_argument("--capacity", type=int, default=None,
                     help="table capacity (default: one slot per block)")
    gen.add_argument("--max-stacks", type=int, default=None,
                     help="cap stacks used by the random states")
    gen.add_argument("--walk", type=int, default=None,
                     help="build the goal with N random moves, bounding the optimum")
    gen.add_argument("--ascii", action="store_true", help="also print the problem")
    gen.add_argument("-o", "--output", default="-")
    gen.set_defaults(func=cmd_generate)

    slv = sub.add_parser("solve", help="plan with a chosen engine")
    slv.add_argument("instance")
    slv.add_argument("--engine", choices=ENGINES, default="prolog")
    slv.add_argument("--strategy", choices=STRATEGIES, default="idastar",
                     help="prolog search strategy (default: idastar)")
    slv.add_argument("--max-depth", type=int, default=None,
                     help="search/horizon ceiling (default: completeness bound)")
    slv.add_argument("--timeout", type=float, default=None)
    slv.add_argument("--optimal", action="store_true",
                     help="accepted for symmetry with the brief; both engines are "
                          "always optimal, so this flag changes nothing")
    slv.add_argument("--explain", action="store_true",
                     help="narrate the plan in domain terms")
    slv.add_argument("--ascii", action="store_true",
                     help="also draw every state to stderr")
    slv.add_argument("-o", "--output", default="-")
    slv.set_defaults(func=cmd_solve)

    ver = sub.add_parser("verify", help="independently check a plan")
    ver.add_argument("instance")
    ver.add_argument("solution")
    ver.add_argument("--optimal", type=int, default=None,
                     help="also require this plan length")
    ver.set_defaults(func=cmd_verify)

    ren = sub.add_parser("render", help="draw a problem or a plan")
    ren.add_argument("instance")
    ren.add_argument("--solution")
    ren.add_argument(
        "--format",
        choices=("ascii", "svg", "filmstrip", "animated-svg", "gif"),
        default="ascii",
    )
    ren.add_argument("--seconds", type=float, default=1.2,
                     help="seconds per step for animations")
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
