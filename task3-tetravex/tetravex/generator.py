"""Reproducible TetraVex instance generation.

Construction
------------
The assessment brief suggests building a solved instance and then shuffling
the pieces, which is what happens here. A board is cut out of a grid of edge
symbols rather than by assembling tiles:

* For an ``R x C`` board there are ``(R+1) x C`` horizontal edges and
  ``R x (C+1)`` vertical edges.
* Every edge is drawn uniformly from ``0..symbols-1``.
* Tile ``(r, c)`` then reads its four symbols off that grid.

Adjacent tiles therefore share an edge *by construction*, so the instance is
solvable before anything has been searched. The reference layout is returned
alongside the instance so tests can confirm it.

This module depends on nothing but :mod:`tetravex.model` and the standard
library; in particular it never calls a solver. Filtering instances for a
unique solution is a separate, opt-in step performed by the CLI.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .model import Border, Instance, Placement, Solution, Tile

#: Named presets. ``symbols`` dominates difficulty: with few distinct symbols
#: many tiles become interchangeable and the search space grows, while a large
#: symbol alphabet makes most placements immediately contradictory. ``border``
#: pins the outside of the grid, removing a large amount of freedom.
#:
#: These are *design intent*, not measured claims -- see ``bench/`` for the
#: actual solve times each preset produces.
DIFFICULTY_PRESETS: dict[str, dict[str, object]] = {
    "easy": {"symbols": 10, "border": True},
    "medium": {"symbols": 6, "border": False},
    "hard": {"symbols": 4, "border": False},
    "extreme": {"symbols": 3, "border": False},
}


@dataclass(frozen=True, slots=True)
class GeneratedPuzzle:
    """An instance plus the layout it was cut from."""

    instance: Instance
    reference: Solution


def _instance_id(
    rows: int, cols: int, symbols: int, seed: int, rotation: bool, bordered: bool
) -> str:
    flags = f"{'r' if rotation else 'n'}{'b' if bordered else 'f'}"
    return f"tv-{rows}x{cols}-s{symbols}-{flags}-seed{seed}"


def generate(
    rows: int = 3,
    cols: int = 3,
    *,
    symbols: int = 10,
    seed: int = 0,
    allow_rotation: bool = False,
    bordered: bool = False,
    difficulty: str | None = None,
) -> GeneratedPuzzle:
    """Generate one solvable instance.

    The same ``seed`` with the same parameters always yields the same puzzle.

    If ``difficulty`` names a preset it overrides ``symbols`` and ``bordered``.
    """
    if difficulty is not None:
        if difficulty not in DIFFICULTY_PRESETS:
            raise ValueError(
                f"unknown difficulty {difficulty!r}; "
                f"choose from {sorted(DIFFICULTY_PRESETS)}"
            )
        preset = DIFFICULTY_PRESETS[difficulty]
        symbols = int(preset["symbols"])
        bordered = bool(preset["border"])
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must both be >= 1")
    if symbols < 1:
        raise ValueError("symbols must be >= 1")

    rng = random.Random(seed)

    # horizontal[r][c] is the symbol on the boundary above tile (r, c);
    # there are rows+1 of them. vertical[r][c] is the symbol to the left of
    # tile (r, c); there are cols+1 per row.
    horizontal = [[rng.randrange(symbols) for _ in range(cols)] for _ in range(rows + 1)]
    vertical = [[rng.randrange(symbols) for _ in range(cols + 1)] for _ in range(rows)]

    solved: list[list[Tile]] = []
    next_id = 0
    for r in range(rows):
        row: list[Tile] = []
        for c in range(cols):
            row.append(
                Tile(
                    id=next_id,
                    top=horizontal[r][c],
                    right=vertical[r][c + 1],
                    bottom=horizontal[r + 1][c],
                    left=vertical[r][c],
                )
            )
            next_id += 1
        solved.append(row)

    border = None
    if bordered:
        border = Border(
            top=tuple(horizontal[0]),
            bottom=tuple(horizontal[rows]),
            left=tuple(vertical[r][0] for r in range(rows)),
            right=tuple(vertical[r][cols] for r in range(rows)),
        )

    # Shuffle the tiles into the tray and renumber, so the tile ids in the
    # published instance carry no hint about where they belong.
    flat = [tile for row in solved for tile in row]
    order = list(range(len(flat)))
    rng.shuffle(order)

    tiles: list[Tile] = []
    old_to_new: dict[int, int] = {}
    for new_id, old_index in enumerate(order):
        old = flat[old_index]
        old_to_new[old.id] = new_id
        tiles.append(Tile(new_id, old.top, old.right, old.bottom, old.left))

    # If rotation is permitted, turn each tile in the tray by a random amount
    # so the reference layout needs a compensating rotation to undo it.
    tray_rotation: dict[int, int] = {t.id: 0 for t in tiles}
    if allow_rotation:
        rotated: list[Tile] = []
        for tile in tiles:
            k = rng.randrange(4)
            tray_rotation[tile.id] = k
            rotated.append(tile.rotated(k))
        tiles = rotated

    instance = Instance(
        id=_instance_id(rows, cols, symbols, seed, allow_rotation, bordered),
        rows=rows,
        cols=cols,
        symbols=symbols,
        allow_rotation=allow_rotation,
        tiles=tuple(tiles),
        border=border,
        seed=seed,
        difficulty=difficulty,
    )
    instance.validate()

    # Reconstruct the layout the board was cut from, expressed in the new ids
    # and with whatever rotation undoes the tray shuffle.
    grid = tuple(
        tuple(
            Placement(
                tile=old_to_new[solved[r][c].id],
                rot=(-tray_rotation[old_to_new[solved[r][c].id]]) % 4,
            )
            for c in range(cols)
        )
        for r in range(rows)
    )
    reference = Solution(instance.id, grid, engine="generator")
    return GeneratedPuzzle(instance, reference)
