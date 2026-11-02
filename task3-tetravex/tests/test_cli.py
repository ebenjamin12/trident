"""End-to-end CLI behaviour, including exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tetravex.cli import main
from tetravex.model import Instance, Solution
from tetravex.solvers import get_solver


def _available(name: str) -> bool:
    return get_solver(name).available()


def test_generate_writes_a_valid_instance(tmp_path: Path):
    out = tmp_path / "i.json"
    assert main(["generate", "--rows", "3", "--cols", "3", "--seed", "7",
                 "-o", str(out)]) == 0
    instance = Instance.loads(out.read_text())
    assert instance.rows == 3 and instance.cols == 3
    assert len(instance.tiles) == 9


def test_generate_with_solution_writes_both(tmp_path: Path):
    inst = tmp_path / "i.json"
    ref = tmp_path / "ref.json"
    assert main(["generate", "--rows", "2", "--cols", "2", "--seed", "1",
                 "-o", str(inst), "--with-solution", str(ref)]) == 0
    assert main(["verify", str(inst), str(ref)]) == 0


def test_generate_difficulty_preset(tmp_path: Path):
    out = tmp_path / "i.json"
    assert main(["generate", "--difficulty", "hard", "--seed", "2",
                 "-o", str(out)]) == 0
    instance = Instance.loads(out.read_text())
    assert instance.difficulty == "hard"
    assert instance.symbols == 4


def test_verify_rejects_a_tampered_solution(tmp_path: Path, capsys):
    inst = tmp_path / "i.json"
    ref = tmp_path / "ref.json"
    main(["generate", "--rows", "3", "--cols", "3", "--symbols", "9",
          "--seed", "19", "-o", str(inst), "--with-solution", str(ref)])

    doc = json.loads(ref.read_text())
    doc["grid"][0][0], doc["grid"][2][2] = doc["grid"][2][2], doc["grid"][0][0]
    ref.write_text(json.dumps(doc))

    assert main(["verify", str(inst), str(ref)]) == 1
    assert "INVALID" in capsys.readouterr().out


def test_render_ascii_to_file(tmp_path: Path):
    inst = tmp_path / "i.json"
    out = tmp_path / "board.txt"
    main(["generate", "--rows", "2", "--cols", "2", "--seed", "3", "-o", str(inst)])
    assert main(["render", str(inst), "-o", str(out)]) == 0
    assert "Empty grid:" in out.read_text()


def test_render_svg_to_file(tmp_path: Path):
    inst = tmp_path / "i.json"
    ref = tmp_path / "ref.json"
    out = tmp_path / "board.svg"
    main(["generate", "--rows", "2", "--cols", "2", "--seed", "3",
          "-o", str(inst), "--with-solution", str(ref)])
    assert main(["render", str(inst), "--solution", str(ref), "--format", "svg",
                 "-o", str(out)]) == 0
    text = out.read_text()
    assert text.lstrip().startswith("<?xml")
    assert "<polygon" in text


def test_engines_command_lists_backends(capsys):
    assert main(["engines"]) == 0
    out = capsys.readouterr().out
    assert "z3" in out and "prolog" in out


@pytest.mark.parametrize("engine", ["z3", "prolog"])
def test_solve_round_trip(tmp_path: Path, engine):
    if not _available(engine):
        pytest.skip(f"{engine} unavailable")
    inst = tmp_path / "i.json"
    sol = tmp_path / "s.json"
    main(["generate", "--rows", "3", "--cols", "3", "--symbols", "6",
          "--seed", "11", "-o", str(inst)])
    assert main(["solve", str(inst), "--engine", engine, "-o", str(sol)]) == 0
    assert main(["verify", str(inst), str(sol)]) == 0
    assert Solution.loads(sol.read_text()).engine == engine


@pytest.mark.parametrize("engine", ["z3", "prolog"])
def test_solve_unique_reports_uniqueness(tmp_path: Path, capsys, engine):
    if not _available(engine):
        pytest.skip(f"{engine} unavailable")
    inst = tmp_path / "i.json"
    sol = tmp_path / "s.json"
    main(["generate", "--rows", "3", "--cols", "3", "--symbols", "10",
          "--seed", "5", "-o", str(inst)])
    assert main(["solve", str(inst), "--engine", engine, "--unique",
                 "-o", str(sol)]) == 0
    assert "unique=" in capsys.readouterr().err


def test_generate_unique_filter(tmp_path: Path):
    if not _available("z3"):
        pytest.skip("z3 unavailable")
    out = tmp_path / "i.json"
    code = main(["generate", "--rows", "3", "--cols", "3", "--symbols", "10",
                 "--seed", "1", "--unique", "--engine", "z3",
                 "--max-attempts", "25", "-o", str(out)])
    assert code == 0
    solver = get_solver("z3")
    result = solver.solve_unique(Instance.loads(out.read_text()))
    assert result.unique is True
