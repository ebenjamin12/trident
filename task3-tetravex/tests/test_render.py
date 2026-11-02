"""Renderers: structure, independence from solvers, determinism."""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

from tetravex.generator import generate
from tetravex.render import render_ascii, render_svg


def test_renderer_does_not_import_any_solver():
    source = (Path(__file__).resolve().parent.parent / "tetravex" / "render.py").read_text()
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not any("solver" in n or "z3" in n or "prolog" in n for n in names), names


# -- ascii ------------------------------------------------------------------


def test_ascii_solution_has_expected_line_count():
    puzzle = generate(3, 3, symbols=6, seed=1)
    lines = render_ascii(puzzle.instance, puzzle.reference).splitlines()
    # 1 top rule + 3 rows x (3 content lines) + 2 inner rules + 1 bottom rule
    assert len(lines) == 1 + 3 * 3 + 2 + 1


def test_ascii_rows_are_all_the_same_width():
    puzzle = generate(3, 4, symbols=12, seed=2)
    lines = render_ascii(puzzle.instance, puzzle.reference).splitlines()
    assert len({len(line) for line in lines}) == 1


def test_ascii_contains_every_symbol_on_the_board():
    puzzle = generate(2, 2, symbols=9, seed=3)
    text = render_ascii(puzzle.instance, puzzle.reference)
    for tile in puzzle.instance.tiles:
        for edge in tile.edges:
            assert str(edge) in text


def test_ascii_show_ids_labels_each_cell():
    puzzle = generate(2, 2, symbols=5, seed=4)
    text = render_ascii(puzzle.instance, puzzle.reference, show_ids=True)
    for tile in puzzle.instance.tiles:
        assert f"#{tile.id}" in text


def test_ascii_without_solution_draws_the_tray():
    puzzle = generate(2, 2, symbols=5, seed=5)
    text = render_ascii(puzzle.instance)
    assert "Empty grid:" in text
    assert "Tiles:" in text
    assert puzzle.instance.id in text


def test_ascii_notes_a_fixed_border():
    puzzle = generate(2, 2, symbols=5, seed=6, bordered=True)
    assert "Fixed border" in render_ascii(puzzle.instance)


def test_ascii_handles_multi_digit_symbols():
    puzzle = generate(2, 2, symbols=40, seed=7)
    lines = render_ascii(puzzle.instance, puzzle.reference).splitlines()
    assert len({len(line) for line in lines}) == 1


def test_ascii_is_deterministic():
    puzzle = generate(3, 3, symbols=6, seed=8)
    a = render_ascii(puzzle.instance, puzzle.reference)
    b = render_ascii(puzzle.instance, puzzle.reference)
    assert a == b


# -- svg --------------------------------------------------------------------


def test_svg_is_well_formed_xml():
    puzzle = generate(3, 3, symbols=6, seed=9)
    root = ET.fromstring(render_svg(puzzle.instance, puzzle.reference))
    assert root.tag.endswith("svg")


def test_svg_has_four_wedges_per_tile():
    puzzle = generate(3, 3, symbols=6, seed=10)
    root = ET.fromstring(render_svg(puzzle.instance, puzzle.reference))
    polygons = root.findall(".//{http://www.w3.org/2000/svg}polygon")
    assert len(polygons) == 9 * 4


def test_svg_labels_every_edge_value():
    puzzle = generate(2, 2, symbols=6, seed=11)
    root = ET.fromstring(render_svg(puzzle.instance, puzzle.reference))
    texts = [t.text for t in root.findall(".//{http://www.w3.org/2000/svg}text")]
    assert len(texts) == 4 * 4


def test_svg_title_is_included_and_escaped():
    puzzle = generate(2, 2, symbols=4, seed=12)
    svg = render_svg(puzzle.instance, puzzle.reference, title="a & b <c>")
    assert "a &amp; b &lt;c&gt;" in svg
    ET.fromstring(svg)


def test_svg_tray_view_labels_tile_ids():
    puzzle = generate(2, 2, symbols=4, seed=13)
    svg = render_svg(puzzle.instance)
    for tile in puzzle.instance.tiles:
        assert f"#{tile.id}" in svg


def test_svg_is_deterministic():
    puzzle = generate(3, 3, symbols=6, seed=14)
    assert render_svg(puzzle.instance, puzzle.reference) == render_svg(
        puzzle.instance, puzzle.reference
    )
