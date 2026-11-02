"""End-to-end CLI behaviour, including exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from blocksworld.cli import (
    EXIT_BAD_PLAN,
    EXIT_NO_PLAN,
    EXIT_OK,
    main,
)
from blocksworld.engines import get_engine
from blocksworld.model import Instance, Plan

ENGINES = ("prolog", "z3")


def _available(name: str) -> bool:
    return get_engine(name).available()


def _problem(tmp_path: Path, **kwargs) -> Path:
    target = tmp_path / "p.json"
    args = ["generate", "--blocks", "4", "--seed", "3", "-o", str(target)]
    for key, value in kwargs.items():
        args += [f"--{key.replace('_', '-')}", str(value)]
    assert main(args) == EXIT_OK
    return target


def test_generate_writes_a_valid_instance(tmp_path):
    path = _problem(tmp_path)
    instance = Instance.loads(path.read_text())
    assert instance.n_blocks == 4


def test_generate_walk_mode_reports_the_bound(tmp_path, capsys):
    main(["generate", "--blocks", "4", "--seed", "1", "--walk", "5", "-o", "-"])
    assert "random move" in capsys.readouterr().err


def test_engines_command_lists_backends(capsys):
    assert main(["engines"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "prolog" in out and "z3" in out


@pytest.mark.parametrize("engine", ENGINES)
def test_solve_verify_round_trip(tmp_path, engine):
    if not _available(engine):
        pytest.skip(f"{engine} unavailable")
    problem = _problem(tmp_path)
    plan_path = tmp_path / "plan.json"
    assert main(["solve", str(problem), "--engine", engine,
                 "-o", str(plan_path)]) == EXIT_OK
    assert main(["verify", str(problem), str(plan_path)]) == EXIT_OK
    plan = Plan.loads(plan_path.read_text())
    assert plan.engine == engine
    assert plan.status == "sat"


@pytest.mark.parametrize("engine", ENGINES)
def test_solve_explain_narrates_the_plan(tmp_path, capsys, engine):
    if not _available(engine):
        pytest.skip(f"{engine} unavailable")
    problem = _problem(tmp_path)
    main(["solve", str(problem), "--engine", engine, "--explain",
          "-o", str(tmp_path / "plan.json")])
    err = capsys.readouterr().err
    assert "1." in err or "already holds" in err


def test_verify_rejects_a_tampered_plan(tmp_path, capsys):
    if not _available("z3"):
        pytest.skip("z3 unavailable")
    # The Sussman anomaly, written out directly: its optimum is exactly three
    # moves, so there is always something to reorder.
    problem = tmp_path / "sussman.json"
    problem.write_text(json.dumps({
        "format": "blocksworld-instance", "version": 1, "id": "sus",
        "blocks": ["A", "B", "C"],
        "initial": [["C", "A"], ["B"]], "goal": [["A", "B", "C"]],
        "table_capacity": 3,
    }))
    plan_path = tmp_path / "plan.json"
    main(["solve", str(problem), "--engine", "z3", "-o", str(plan_path)])

    doc = json.loads(plan_path.read_text())
    assert len(doc["actions"]) == 3
    doc["actions"][0], doc["actions"][1] = doc["actions"][1], doc["actions"][0]
    plan_path.write_text(json.dumps(doc))

    assert main(["verify", str(problem), str(plan_path)]) == EXIT_BAD_PLAN
    assert "INVALID" in capsys.readouterr().out


def test_verify_optimal_flag_rejects_a_wrong_optimum(tmp_path, capsys):
    if not _available("z3"):
        pytest.skip("z3 unavailable")
    problem = _problem(tmp_path)
    plan_path = tmp_path / "plan.json"
    main(["solve", str(problem), "--engine", "z3", "-o", str(plan_path)])
    length = Plan.loads(plan_path.read_text()).length
    assert main(["verify", str(problem), str(plan_path),
                 "--optimal", str(length)]) == EXIT_OK
    assert main(["verify", str(problem), str(plan_path),
                 "--optimal", str(length + 1)]) == EXIT_BAD_PLAN


def test_solve_reports_unsolvable_without_claiming_a_plan(tmp_path):
    if not _available("prolog"):
        pytest.skip("prolog unavailable")
    problem = tmp_path / "u.json"
    problem.write_text(json.dumps({
        "format": "blocksworld-instance", "version": 1, "id": "u1",
        "blocks": ["A", "B", "C"],
        "initial": [["A", "B", "C"]], "goal": [["C", "B", "A"]],
        "table_capacity": 1,
    }))
    out = tmp_path / "plan.json"
    code = main(["solve", str(problem), "--engine", "prolog",
                 "--strategy", "bfs", "-o", str(out)])
    assert code == EXIT_OK
    assert Plan.loads(out.read_text()).status == "unsat"


def test_solve_limit_exits_nonzero(tmp_path):
    if not _available("z3"):
        pytest.skip("z3 unavailable")
    problem = _problem(tmp_path)
    out = tmp_path / "plan.json"
    code = main(["solve", str(problem), "--engine", "z3",
                 "--max-depth", "0", "-o", str(out)])
    plan = Plan.loads(out.read_text())
    if plan.status == "sat":
        pytest.skip("this instance needs no moves")
    assert code == EXIT_NO_PLAN
    assert plan.status in {"limit", "unsat"}


def test_render_problem_as_ascii(tmp_path):
    problem = _problem(tmp_path)
    out = tmp_path / "p.txt"
    assert main(["render", str(problem), "-o", str(out)]) == EXIT_OK
    assert "INITIAL" in out.read_text()


@pytest.mark.parametrize("fmt", ["ascii", "svg", "filmstrip", "animated-svg"])
def test_render_plan_formats(tmp_path, fmt):
    if not _available("z3"):
        pytest.skip("z3 unavailable")
    problem = _problem(tmp_path)
    plan_path = tmp_path / "plan.json"
    main(["solve", str(problem), "--engine", "z3", "-o", str(plan_path)])
    out = tmp_path / f"out.{fmt}"
    assert main(["render", str(problem), "--solution", str(plan_path),
                 "--format", fmt, "-o", str(out)]) == EXIT_OK
    assert out.read_text().strip()


def test_render_gif(tmp_path):
    if not _available("z3"):
        pytest.skip("z3 unavailable")
    from blocksworld.render import gif_available

    if not gif_available():
        pytest.skip("Pillow not installed")
    problem = _problem(tmp_path)
    plan_path = tmp_path / "plan.json"
    main(["solve", str(problem), "--engine", "z3", "-o", str(plan_path)])
    out = tmp_path / "plan.gif"
    assert main(["render", str(problem), "--solution", str(plan_path),
                 "--format", "gif", "-o", str(out)]) == EXIT_OK
    assert out.is_file() and out.stat().st_size > 0


def test_render_refuses_an_invalid_plan(tmp_path, capsys):
    problem = _problem(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "format": "blocksworld-plan", "version": 1,
        "instance_id": Instance.loads(problem.read_text()).id,
        "status": "sat", "length": 1,
        "actions": [{"block": "A", "from": "table", "to": "Z"}],
    }))
    assert main(["render", str(problem), "--solution", str(bad),
                 "--format", "ascii"]) == EXIT_BAD_PLAN
    assert "refusing to render" in capsys.readouterr().err


def test_animated_formats_require_a_solution(tmp_path, capsys):
    problem = _problem(tmp_path)
    assert main(["render", str(problem), "--format", "gif"]) == EXIT_NO_PLAN
    assert "needs --solution" in capsys.readouterr().err
