"""Model, rotation algebra and JSON round-tripping."""

from __future__ import annotations

import json

import pytest
from tetravex.generator import generate
from tetravex.model import (
    Border,
    FormatError,
    Instance,
    Solution,
    Tile,
)

# -- rotation algebra -------------------------------------------------------


def test_rotation_identity():
    tile = Tile(0, 1, 2, 3, 4)
    assert tile.rotated(0) == tile


def test_rotation_is_order_four():
    tile = Tile(0, 1, 2, 3, 4)
    assert tile.rotated(4) == tile
    assert tile.rotated(8) == tile


def test_rotation_clockwise_moves_left_edge_to_top():
    tile = Tile(0, top=1, right=2, bottom=3, left=4)
    turned = tile.rotated(1)
    assert (turned.top, turned.right, turned.bottom, turned.left) == (4, 1, 2, 3)


def test_rotation_composes():
    tile = Tile(7, 5, 6, 7, 8)
    for a in range(4):
        for b in range(4):
            assert tile.rotated(a).rotated(b) == tile.rotated(a + b)


def test_rotation_preserves_id_and_multiset_of_edges():
    tile = Tile(3, 9, 1, 4, 1)
    for k in range(4):
        turned = tile.rotated(k)
        assert turned.id == tile.id
        assert sorted(turned.edges) == sorted(tile.edges)


# -- instance validation ----------------------------------------------------


def _tiles(n: int) -> tuple[Tile, ...]:
    return tuple(Tile(i, 0, 0, 0, 0) for i in range(n))


def test_instance_rejects_wrong_tile_count():
    inst = Instance("x", 2, 2, 4, False, _tiles(3))
    with pytest.raises(FormatError, match="3 tiles but 4 cells"):
        inst.validate()


def test_instance_rejects_non_contiguous_ids():
    tiles = (Tile(0, 0, 0, 0, 0), Tile(2, 0, 0, 0, 0),
             Tile(3, 0, 0, 0, 0), Tile(4, 0, 0, 0, 0))
    with pytest.raises(FormatError, match="tile ids must be"):
        Instance("x", 2, 2, 4, False, tiles).validate()


def test_instance_rejects_out_of_range_symbol():
    tiles = _tiles(4)[:3] + (Tile(3, 99, 0, 0, 0),)
    with pytest.raises(FormatError, match="outside 0..3"):
        Instance("x", 2, 2, 4, False, tiles).validate()


def test_instance_rejects_wrong_length_border():
    border = Border(top=(0, 0, 0), right=(0, 0), bottom=(0, 0), left=(0, 0))
    with pytest.raises(FormatError, match="border.top has length 3"):
        Instance("x", 2, 2, 4, False, _tiles(4), border=border).validate()


def test_rotations_property_respects_flag():
    assert Instance("x", 1, 1, 2, False, _tiles(1)).rotations == (0,)
    assert Instance("x", 1, 1, 2, True, _tiles(1)).rotations == (0, 1, 2, 3)


def test_duplicate_groups_finds_identical_tiles():
    tiles = (
        Tile(0, 1, 1, 1, 1),
        Tile(1, 2, 2, 2, 2),
        Tile(2, 1, 1, 1, 1),
        Tile(3, 1, 1, 1, 1),
    )
    inst = Instance("x", 2, 2, 3, False, tiles)
    assert inst.duplicate_groups() == [[0, 2, 3]]


def test_duplicate_groups_empty_when_all_distinct():
    puzzle = generate(3, 3, symbols=10, seed=1)
    groups = puzzle.instance.duplicate_groups()
    assert all(len(g) >= 2 for g in groups)


# -- serialisation ----------------------------------------------------------


@pytest.mark.parametrize("rotation", [False, True])
@pytest.mark.parametrize("bordered", [False, True])
def test_instance_json_round_trip(rotation, bordered):
    original = generate(
        3, 4, symbols=5, seed=12, allow_rotation=rotation, bordered=bordered
    ).instance
    assert Instance.loads(original.dumps()) == original


def test_solution_json_round_trip():
    puzzle = generate(2, 3, symbols=4, seed=2)
    assert Solution.loads(puzzle.reference.dumps()).grid == puzzle.reference.grid


def test_instance_rejects_unknown_format():
    doc = json.loads(generate(2, 2, seed=1).instance.dumps())
    doc["format"] = "something-else"
    with pytest.raises(FormatError, match="expected format"):
        Instance.from_json(doc)


def test_instance_rejects_unknown_version():
    doc = json.loads(generate(2, 2, seed=1).instance.dumps())
    doc["version"] = 99
    with pytest.raises(FormatError, match="unsupported instance version"):
        Instance.from_json(doc)


def test_solution_rejects_ragged_grid():
    doc = {
        "format": "tetravex-solution",
        "version": 1,
        "instance_id": "x",
        "grid": [[{"tile": 0, "rot": 0}], [{"tile": 1, "rot": 0}, {"tile": 2, "rot": 0}]],
    }
    with pytest.raises(FormatError, match="inconsistent widths"):
        Solution.from_json(doc)


def test_from_assignment_rejects_wrong_length():
    inst = generate(2, 2, seed=1).instance
    with pytest.raises(FormatError, match="expected 4"):
        Solution.from_assignment(inst, [(0, 0), (1, 0)])


def test_edge_grid_ignores_tile_identity():
    """Two solutions swapping identical tiles share one edge grid."""
    tiles = (
        Tile(0, 1, 1, 1, 1),
        Tile(1, 1, 1, 1, 1),
        Tile(2, 1, 1, 1, 1),
        Tile(3, 1, 1, 1, 1),
    )
    inst = Instance("x", 2, 2, 2, False, tiles)
    a = Solution.from_assignment(inst, [(0, 0), (1, 0), (2, 0), (3, 0)])
    b = Solution.from_assignment(inst, [(1, 0), (0, 0), (3, 0), (2, 0)])
    assert a.grid != b.grid
    assert a.edge_grid(inst) == b.edge_grid(inst)
