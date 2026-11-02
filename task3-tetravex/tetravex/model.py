"""Core data model and JSON serialisation for TetraVex.

This module is the contract between every other part of the package. The
generator produces :class:`Instance` values, the solvers consume them and
produce :class:`Solution` values, and the verifier and renderers consume both.
Nothing in here knows that Z3 or Prolog exist.

Edge convention
---------------
A tile's edges are always stored in the order ``(top, right, bottom, left)``,
i.e. clockwise starting from the top. Rotating a tile 90 degrees clockwise
moves the left edge to the top::

    (t, r, b, l)  --rotate 90 cw-->  (l, t, r, b)

Cells are addressed as ``(row, col)`` with ``(0, 0)`` top-left.

Border convention
-----------------
Classic TetraVex leaves the outer edges of the grid unconstrained. This model
additionally supports an optional *bordered* variant in which the outer edge
values are fixed up front; see :class:`Border`. ``border=None`` means the
classic, free-border puzzle.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

FORMAT_INSTANCE = "tetravex-instance"
FORMAT_SOLUTION = "tetravex-solution"
FORMAT_VERSION = 1

#: Edge names in canonical (clockwise-from-top) order.
EDGE_NAMES = ("top", "right", "bottom", "left")


class FormatError(ValueError):
    """Raised when a JSON document does not match the expected schema."""


# --------------------------------------------------------------------------
# Tiles
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Tile:
    """A single square tile with a symbol on each of its four edges."""

    id: int
    top: int
    right: int
    bottom: int
    left: int

    @property
    def edges(self) -> tuple[int, int, int, int]:
        return (self.top, self.right, self.bottom, self.left)

    @property
    def signature(self) -> tuple[int, int, int, int]:
        """Edge tuple ignoring the tile id.

        Two tiles with the same signature are interchangeable, which matters
        for symmetry breaking and for defining solution uniqueness.
        """
        return self.edges

    def rotated(self, k: int) -> Tile:
        """Return this tile rotated ``k`` quarter-turns clockwise."""
        t, r, b, l = self.edges
        for _ in range(k % 4):
            t, r, b, l = l, t, r, b
        return Tile(self.id, t, r, b, l)

    def to_json(self) -> dict[str, int]:
        return {"id": self.id, "top": self.top, "right": self.right,
                "bottom": self.bottom, "left": self.left}

    @staticmethod
    def from_json(raw: Any) -> Tile:
        if not isinstance(raw, dict):
            raise FormatError(f"tile must be an object, got {type(raw).__name__}")
        missing = {"id", *EDGE_NAMES} - raw.keys()
        if missing:
            raise FormatError(f"tile is missing keys: {sorted(missing)}")
        for key in ("id", *EDGE_NAMES):
            if not isinstance(raw[key], int) or isinstance(raw[key], bool):
                raise FormatError(f"tile field {key!r} must be an int")
        return Tile(raw["id"], raw["top"], raw["right"], raw["bottom"], raw["left"])


# --------------------------------------------------------------------------
# Borders
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Border:
    """Fixed symbols along the outside of the grid.

    ``top`` and ``bottom`` have one entry per column (left to right); ``left``
    and ``right`` have one entry per row (top to bottom).
    """

    top: tuple[int, ...]
    right: tuple[int, ...]
    bottom: tuple[int, ...]
    left: tuple[int, ...]

    def validate(self, rows: int, cols: int) -> None:
        for name, seq, expected in (
            ("top", self.top, cols),
            ("bottom", self.bottom, cols),
            ("left", self.left, rows),
            ("right", self.right, rows),
        ):
            if len(seq) != expected:
                raise FormatError(
                    f"border.{name} has length {len(seq)}, expected {expected}"
                )

    def to_json(self) -> dict[str, list[int]]:
        return {"top": list(self.top), "right": list(self.right),
                "bottom": list(self.bottom), "left": list(self.left)}

    @staticmethod
    def from_json(raw: Any) -> Border:
        if not isinstance(raw, dict):
            raise FormatError("border must be an object or null")
        missing = set(EDGE_NAMES) - raw.keys()
        if missing:
            raise FormatError(f"border is missing keys: {sorted(missing)}")
        out: dict[str, tuple[int, ...]] = {}
        for key in EDGE_NAMES:
            seq = raw[key]
            if not isinstance(seq, list) or not all(
                isinstance(v, int) and not isinstance(v, bool) for v in seq
            ):
                raise FormatError(f"border.{key} must be a list of ints")
            out[key] = tuple(seq)
        return Border(**out)


# --------------------------------------------------------------------------
# Instances
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Instance:
    """A TetraVex puzzle: a bag of tiles to be laid out on a rows x cols grid."""

    id: str
    rows: int
    cols: int
    symbols: int
    allow_rotation: bool
    tiles: tuple[Tile, ...]
    border: Border | None = None
    seed: int | None = None
    difficulty: str | None = None

    # -- derived -----------------------------------------------------------

    @property
    def n_cells(self) -> int:
        return self.rows * self.cols

    @property
    def rotations(self) -> tuple[int, ...]:
        """Rotations a tile is allowed to take in this instance."""
        return (0, 1, 2, 3) if self.allow_rotation else (0,)

    def cells(self) -> Iterator[tuple[int, int]]:
        for r in range(self.rows):
            for c in range(self.cols):
                yield (r, c)

    def cell_index(self, row: int, col: int) -> int:
        return row * self.cols + col

    def duplicate_groups(self) -> list[list[int]]:
        """Tile ids grouped by identical edge signature, groups of size >= 2.

        Used for symmetry breaking: permuting tiles inside such a group yields
        a visually identical board, so the solvers pin them to a fixed order.
        """
        buckets: dict[tuple[int, int, int, int], list[int]] = {}
        for tile in self.tiles:
            buckets.setdefault(tile.signature, []).append(tile.id)
        return [sorted(ids) for ids in buckets.values() if len(ids) > 1]

    # -- validation --------------------------------------------------------

    def validate(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise FormatError("rows and cols must both be >= 1")
        if self.symbols < 1:
            raise FormatError("symbols must be >= 1")
        if len(self.tiles) != self.n_cells:
            raise FormatError(
                f"instance has {len(self.tiles)} tiles but {self.n_cells} cells"
            )
        ids = [t.id for t in self.tiles]
        if sorted(ids) != list(range(self.n_cells)):
            raise FormatError(
                f"tile ids must be exactly 0..{self.n_cells - 1}, got {sorted(ids)}"
            )
        for tile in self.tiles:
            for name, value in zip(EDGE_NAMES, tile.edges, strict=True):
                if not 0 <= value < self.symbols:
                    raise FormatError(
                        f"tile {tile.id} edge {name}={value} outside 0..{self.symbols - 1}"
                    )
        if self.border is not None:
            self.border.validate(self.rows, self.cols)
            for name in EDGE_NAMES:
                for value in getattr(self.border, name):
                    if not 0 <= value < self.symbols:
                        raise FormatError(
                            f"border.{name} value {value} outside 0..{self.symbols - 1}"
                        )

    # -- serialisation -----------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "format": FORMAT_INSTANCE,
            "version": FORMAT_VERSION,
            "id": self.id,
            "rows": self.rows,
            "cols": self.cols,
            "symbols": self.symbols,
            "allow_rotation": self.allow_rotation,
            "border": self.border.to_json() if self.border else None,
            "tiles": [t.to_json() for t in self.tiles],
        }
        if self.seed is not None:
            doc["seed"] = self.seed
        if self.difficulty is not None:
            doc["difficulty"] = self.difficulty
        return doc

    def dumps(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_json(), indent=indent, sort_keys=False)

    @staticmethod
    def from_json(raw: Any) -> Instance:
        if not isinstance(raw, dict):
            raise FormatError("instance document must be a JSON object")
        if raw.get("format") != FORMAT_INSTANCE:
            raise FormatError(
                f"expected format {FORMAT_INSTANCE!r}, got {raw.get('format')!r}"
            )
        if raw.get("version") != FORMAT_VERSION:
            raise FormatError(
                f"unsupported instance version {raw.get('version')!r}"
            )
        for key in ("id", "rows", "cols", "symbols", "allow_rotation", "tiles"):
            if key not in raw:
                raise FormatError(f"instance is missing required key {key!r}")
        if not isinstance(raw["tiles"], list):
            raise FormatError("instance.tiles must be a list")
        if not isinstance(raw["allow_rotation"], bool):
            raise FormatError("instance.allow_rotation must be a bool")
        border_raw = raw.get("border")
        inst = Instance(
            id=str(raw["id"]),
            rows=int(raw["rows"]),
            cols=int(raw["cols"]),
            symbols=int(raw["symbols"]),
            allow_rotation=raw["allow_rotation"],
            tiles=tuple(Tile.from_json(t) for t in raw["tiles"]),
            border=Border.from_json(border_raw) if border_raw is not None else None,
            seed=raw.get("seed"),
            difficulty=raw.get("difficulty"),
        )
        inst.validate()
        return inst

    @staticmethod
    def loads(text: str) -> Instance:
        return Instance.from_json(json.loads(text))


# --------------------------------------------------------------------------
# Solutions
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Placement:
    """Which tile sits in a cell, and how far it has been turned."""

    tile: int
    rot: int = 0

    def to_json(self) -> dict[str, int]:
        return {"tile": self.tile, "rot": self.rot}

    @staticmethod
    def from_json(raw: Any) -> Placement:
        if not isinstance(raw, dict) or "tile" not in raw:
            raise FormatError("placement must be an object with a 'tile' key")
        tile, rot = raw["tile"], raw.get("rot", 0)
        if not isinstance(tile, int) or isinstance(tile, bool):
            raise FormatError("placement.tile must be an int")
        if not isinstance(rot, int) or isinstance(rot, bool):
            raise FormatError("placement.rot must be an int")
        return Placement(tile, rot)


@dataclass(frozen=True, slots=True)
class Solution:
    """A completed board: one :class:`Placement` per cell."""

    instance_id: str
    grid: tuple[tuple[Placement, ...], ...]
    engine: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    def placements(self) -> Iterator[tuple[int, int, Placement]]:
        for r, row in enumerate(self.grid):
            for c, placement in enumerate(row):
                yield (r, c, placement)

    def edge_grid(self, instance: Instance) -> tuple[tuple[tuple[int, ...], ...], ...]:
        """The board rendered as resolved edge tuples, ignoring tile identity.

        Two solutions that differ only by swapping identical tiles produce the
        same edge grid. This is the canonical form used to decide whether a
        second solution is genuinely different.
        """
        by_id = {t.id: t for t in instance.tiles}
        return tuple(
            tuple(by_id[p.tile].rotated(p.rot).edges for p in row)
            for row in self.grid
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "format": FORMAT_SOLUTION,
            "version": FORMAT_VERSION,
            "instance_id": self.instance_id,
            "engine": self.engine,
            "grid": [[p.to_json() for p in row] for row in self.grid],
            "stats": self.stats,
        }

    def dumps(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_json(), indent=indent, sort_keys=False)

    @staticmethod
    def from_json(raw: Any) -> Solution:
        if not isinstance(raw, dict):
            raise FormatError("solution document must be a JSON object")
        if raw.get("format") != FORMAT_SOLUTION:
            raise FormatError(
                f"expected format {FORMAT_SOLUTION!r}, got {raw.get('format')!r}"
            )
        if raw.get("version") != FORMAT_VERSION:
            raise FormatError(f"unsupported solution version {raw.get('version')!r}")
        if "grid" not in raw or not isinstance(raw["grid"], list):
            raise FormatError("solution.grid must be a list of rows")
        grid = tuple(
            tuple(Placement.from_json(cell) for cell in row) for row in raw["grid"]
        )
        widths = {len(row) for row in grid}
        if len(widths) > 1:
            raise FormatError(f"solution.grid rows have inconsistent widths: {widths}")
        return Solution(
            instance_id=str(raw.get("instance_id", "")),
            grid=grid,
            engine=raw.get("engine"),
            stats=raw.get("stats") or {},
        )

    @staticmethod
    def loads(text: str) -> Solution:
        return Solution.from_json(json.loads(text))

    @staticmethod
    def from_assignment(
        instance: Instance,
        assignment: Sequence[tuple[int, int]],
        engine: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> Solution:
        """Build a solution from a flat, row-major list of ``(tile, rot)``."""
        if len(assignment) != instance.n_cells:
            raise FormatError(
                f"assignment has {len(assignment)} entries, expected {instance.n_cells}"
            )
        grid = tuple(
            tuple(
                Placement(*assignment[r * instance.cols + c])
                for c in range(instance.cols)
            )
            for r in range(instance.rows)
        )
        return Solution(instance.id, grid, engine, dict(stats or {}))
