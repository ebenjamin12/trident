"""Generator: reproducibility, solvability by construction, presets."""

from __future__ import annotations

import pytest
from tetravex.generator import DIFFICULTY_PRESETS, generate
from tetravex.verify import verify


@pytest.mark.parametrize("rows,cols", [(1, 1), (1, 4), (4, 1), (2, 3), (3, 3), (4, 5)])
def test_reference_layout_always_verifies(rows, cols):
    """The layout the board was cut from must satisfy every constraint."""
    puzzle = generate(rows, cols, symbols=6, seed=rows * 100 + cols)
    assert verify(puzzle.instance, puzzle.reference).ok


@pytest.mark.parametrize("rotation", [False, True])
@pytest.mark.parametrize("bordered", [False, True])
def test_reference_verifies_in_every_mode(rotation, bordered):
    puzzle = generate(
        3, 3, symbols=5, seed=77, allow_rotation=rotation, bordered=bordered
    )
    report = verify(puzzle.instance, puzzle.reference)
    assert report.ok, report.summary


def test_same_seed_is_reproducible():
    a = generate(4, 4, symbols=7, seed=1234)
    b = generate(4, 4, symbols=7, seed=1234)
    assert a.instance.dumps() == b.instance.dumps()
    assert a.reference.dumps() == b.reference.dumps()


def test_different_seeds_differ():
    a = generate(4, 4, symbols=7, seed=1)
    b = generate(4, 4, symbols=7, seed=2)
    assert a.instance.dumps() != b.instance.dumps()


def test_instance_id_encodes_parameters():
    inst = generate(3, 4, symbols=6, seed=9, allow_rotation=True, bordered=True).instance
    assert inst.id == "tv-3x4-s6-rb-seed9"


def test_symbols_bound_is_respected():
    inst = generate(4, 4, symbols=3, seed=5).instance
    for tile in inst.tiles:
        assert all(0 <= e < 3 for e in tile.edges)


def test_border_present_only_when_requested():
    assert generate(3, 3, seed=1, bordered=False).instance.border is None
    assert generate(3, 3, seed=1, bordered=True).instance.border is not None


def test_border_matches_reference_layout():
    puzzle = generate(3, 3, symbols=5, seed=31, bordered=True)
    assert verify(puzzle.instance, puzzle.reference).ok


def test_rotation_mode_scrambles_tray():
    """With rotation on, the reference needs some non-zero rotations."""
    puzzle = generate(4, 4, symbols=6, seed=8, allow_rotation=True)
    rots = {p.rot for row in puzzle.reference.grid for p in row}
    assert rots != {0}


def test_no_rotation_mode_uses_only_zero():
    puzzle = generate(4, 4, symbols=6, seed=8, allow_rotation=False)
    assert {p.rot for row in puzzle.reference.grid for p in row} == {0}


def test_tile_ids_are_renumbered_after_shuffle():
    inst = generate(3, 3, symbols=8, seed=4).instance
    assert sorted(t.id for t in inst.tiles) == list(range(9))


@pytest.mark.parametrize("name", sorted(DIFFICULTY_PRESETS))
def test_difficulty_presets_produce_valid_puzzles(name):
    puzzle = generate(3, 3, seed=21, difficulty=name)
    assert puzzle.instance.difficulty == name
    assert verify(puzzle.instance, puzzle.reference).ok


def test_difficulty_preset_overrides_symbols():
    inst = generate(3, 3, symbols=99, seed=1, difficulty="hard").instance
    assert inst.symbols == DIFFICULTY_PRESETS["hard"]["symbols"]


def test_unknown_difficulty_rejected():
    with pytest.raises(ValueError, match="unknown difficulty"):
        generate(3, 3, difficulty="impossible")


@pytest.mark.parametrize("rows,cols", [(0, 3), (3, 0), (-1, 2)])
def test_bad_dimensions_rejected(rows, cols):
    with pytest.raises(ValueError, match="must both be >= 1"):
        generate(rows, cols)


def test_zero_symbols_rejected():
    with pytest.raises(ValueError, match="symbols must be >= 1"):
        generate(2, 2, symbols=0)
