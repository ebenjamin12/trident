"""Renderers: structure, independence from engines, determinism."""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from blocksworld.generator import generate
from blocksworld.model import TABLE, Action, Instance, Plan, State
from blocksworld.render import (
    gif_available,
    render_ascii_plan,
    render_ascii_problem,
    render_ascii_state,
    render_gif,
    render_svg_animated,
    render_svg_filmstrip,
    render_svg_state,
)
from blocksworld.verify import verify

SUSSMAN = Instance(
    "sus", ("A", "B", "C"),
    State.of([["C", "A"], ["B"]]), State.of([["A", "B", "C"]]), 3,
)
PLAN = Plan(
    "sus", "sat",
    (Action("A", "C", TABLE), Action("B", TABLE, "A"), Action("C", TABLE, "B")),
)
SVG_NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def states():
    report = verify(SUSSMAN, PLAN)
    assert report.ok
    return report.states


def test_renderer_imports_no_engine():
    source = (
        Path(__file__).resolve().parent.parent / "blocksworld" / "render.py"
    ).read_text()
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not any(
        "engine" in n or "z3_" in n or "prolog" in n for n in names
    ), names


# -- ascii ------------------------------------------------------------------


def test_ascii_state_names_every_block():
    text = render_ascii_state(SUSSMAN, SUSSMAN.initial)
    for block in SUSSMAN.blocks:
        assert block in text


def test_ascii_state_reports_table_usage():
    assert "2/3 table slots used" in render_ascii_state(SUSSMAN, SUSSMAN.initial)


def test_ascii_problem_shows_both_states():
    text = render_ascii_problem(SUSSMAN)
    assert "INITIAL" in text and "GOAL" in text
    assert "heuristic lower bound" in text


def test_ascii_plan_captions_every_move(states):
    text = render_ascii_plan(SUSSMAN, states, PLAN.actions)
    assert "initial state" in text
    for i in range(1, 4):
        assert f"move {i}:" in text


def test_ascii_plan_has_one_block_per_state(states):
    text = render_ascii_plan(SUSSMAN, states, PLAN.actions, show_goal=False)
    assert text.count("table slots used") == len(states)


def test_ascii_is_deterministic(states):
    a = render_ascii_plan(SUSSMAN, states, PLAN.actions)
    b = render_ascii_plan(SUSSMAN, states, PLAN.actions)
    assert a == b


def test_ascii_handles_a_single_tall_stack():
    instance = generate(6, seed=1, max_stacks=1).instance
    text = render_ascii_state(instance, instance.initial)
    assert text.count("│") >= 6


# -- svg --------------------------------------------------------------------


def test_svg_state_is_well_formed():
    root = ET.fromstring(render_svg_state(SUSSMAN, SUSSMAN.initial, title="t"))
    assert root.tag.endswith("svg")


def test_svg_state_draws_one_rect_per_block_plus_the_table():
    root = ET.fromstring(render_svg_state(SUSSMAN, SUSSMAN.initial))
    rects = root.findall(f".//{SVG_NS}rect")
    # background + table + one per block
    assert len(rects) == 2 + len(SUSSMAN.blocks)


def test_svg_filmstrip_is_well_formed_and_captioned(states):
    svg = render_svg_filmstrip(SUSSMAN, states, PLAN.actions)
    root = ET.fromstring(svg)
    texts = [t.text for t in root.findall(f".//{SVG_NS}text")]
    assert "start" in texts
    assert any(t and t.startswith("1.") for t in texts)


def test_svg_filmstrip_draws_every_state(states):
    root = ET.fromstring(render_svg_filmstrip(SUSSMAN, states, PLAN.actions))
    rects = root.findall(f".//{SVG_NS}rect")
    # background + per state (table + 3 blocks)
    assert len(rects) == 1 + len(states) * (1 + len(SUSSMAN.blocks))


def test_svg_animated_has_one_animate_per_frame(states):
    root = ET.fromstring(render_svg_animated(SUSSMAN, states, PLAN.actions))
    animates = root.findall(f".//{SVG_NS}animate")
    assert len(animates) == len(states)
    for node in animates:
        assert node.get("calcMode") == "discrete"
        assert node.get("repeatCount") == "indefinite"
        assert len(node.get("values", "").split(";")) == len(states)


def test_svg_animated_shows_exactly_one_frame_at_a_time(states):
    root = ET.fromstring(render_svg_animated(SUSSMAN, states, PLAN.actions))
    columns = [
        node.get("values", "").split(";")
        for node in root.findall(f".//{SVG_NS}animate")
    ]
    for slot in range(len(states)):
        assert sum(int(col[slot]) for col in columns) == 1


def test_svg_escapes_markup_in_captions():
    instance = Instance("x", ("A",), State.of([["A"]]), State.of([["A"]]), 1)
    svg = render_svg_state(instance, instance.initial, title="a & b <c>")
    assert "a &amp; b &lt;c&gt;" in svg
    ET.fromstring(svg)


def test_svg_is_deterministic(states):
    assert render_svg_filmstrip(SUSSMAN, states, PLAN.actions) == (
        render_svg_filmstrip(SUSSMAN, states, PLAN.actions)
    )


# -- gif --------------------------------------------------------------------


@pytest.mark.skipif(not gif_available(), reason="Pillow is not installed")
def test_gif_is_written_with_one_frame_per_state(tmp_path, states):
    from PIL import Image

    target = tmp_path / "plan.gif"
    render_gif(SUSSMAN, states, PLAN.actions, str(target))
    assert target.is_file()
    with Image.open(target) as image:
        assert image.format == "GIF"
        frames = 0
        try:
            while True:
                image.seek(frames)
                frames += 1
        except EOFError:
            pass
    assert frames == len(states)


@pytest.mark.skipif(not gif_available(), reason="Pillow is not installed")
def test_gif_survives_a_machine_with_no_font_files(tmp_path, states):
    """GIF output must degrade, not crash, where DejaVu is absent.

    The font paths tried first exist on most Linux distributions and on
    neither macOS nor Windows, so the fallback chain is the only thing keeping
    this feature cross-platform. Patching ``truetype`` to reject path
    arguments while still accepting the file-like object that
    ``load_default`` feeds it reproduces that machine faithfully.
    """
    from unittest import mock

    from PIL import ImageFont

    real_truetype = ImageFont.truetype

    def paths_unavailable(font, *args, **kwargs):
        if isinstance(font, str):
            raise OSError("no such font file")
        return real_truetype(font, *args, **kwargs)

    target = tmp_path / "fallback.gif"
    with mock.patch.object(ImageFont, "truetype", side_effect=paths_unavailable):
        render_gif(SUSSMAN, states, PLAN.actions, str(target))
    assert target.is_file() and target.stat().st_size > 0


@pytest.mark.skipif(not gif_available(), reason="Pillow is not installed")
def test_gif_survives_pillow_without_a_sized_default_font(tmp_path, states):
    """``load_default(size=...)`` needs Pillow >= 10.1; older versions must work."""
    from unittest import mock

    from PIL import ImageFont

    real_truetype = ImageFont.truetype
    real_default = ImageFont.load_default

    def paths_unavailable(font, *args, **kwargs):
        if isinstance(font, str):
            raise OSError("no such font file")
        return real_truetype(font, *args, **kwargs)

    def unsized_only(*args, **kwargs):
        if kwargs:
            raise TypeError("load_default() got an unexpected keyword argument")
        return real_default()

    target = tmp_path / "old-pillow.gif"
    with mock.patch.object(ImageFont, "truetype", side_effect=paths_unavailable), \
         mock.patch.object(ImageFont, "load_default", side_effect=unsized_only):
        render_gif(SUSSMAN, states, PLAN.actions, str(target))
    assert target.is_file() and target.stat().st_size > 0
