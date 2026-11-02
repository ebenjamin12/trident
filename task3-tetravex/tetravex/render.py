"""ASCII and SVG rendering for TetraVex boards.

Rendering is deliberately independent of the solvers: every function here
takes an :class:`~tetravex.model.Instance` and optionally a
:class:`~tetravex.model.Solution`, and nothing else. The same code therefore
draws a generated puzzle, a Z3 answer and a Prolog answer identically, which
is what makes a visual diff between engines meaningful.
"""

from __future__ import annotations

from .model import Instance, Solution, Tile

# --------------------------------------------------------------------------
# ASCII
# --------------------------------------------------------------------------

_TL, _TR, _BL, _BR = "┌", "┐", "└", "┘"
_H, _V = "─", "│"
_TT, _BT, _LT, _RT, _CR = "┬", "┴", "├", "┤", "┼"


def _cell_width(instance: Instance) -> int:
    """Inner width of one tile box, sized to the widest symbol."""
    digits = len(str(max(instance.symbols - 1, 0)))
    return 2 * digits + 5


def _tile_lines(tile: Tile | None, width: int) -> list[str]:
    if tile is None:
        return [" " * width] * 3
    top = str(tile.top).center(width)
    bottom = str(tile.bottom).center(width)
    left, right = str(tile.left), str(tile.right)
    # One space of padding at each outer edge, the rest between the two values.
    pad = max(width - len(left) - len(right) - 2, 1)
    middle = (" " + left + " " * pad + right + " ").ljust(width)[:width]
    return [top, middle, bottom]


def _rule(left: str, mid: str, right: str, width: int, cols: int) -> str:
    return left + (mid.join([_H * width] * cols)) + right


def render_ascii(
    instance: Instance, solution: Solution | None = None, *, show_ids: bool = False
) -> str:
    """Draw the board.

    With no solution, draws the empty grid alongside the tray of tiles, which
    is how the puzzle is posed. With a solution, draws the filled board.
    """
    width = _cell_width(instance)
    by_id = {t.id: t for t in instance.tiles}

    if solution is None:
        lines = [f"{instance.id}  ({instance.rows}x{instance.cols}, "
                 f"{instance.symbols} symbols, "
                 f"rotation {'allowed' if instance.allow_rotation else 'fixed'})",
                 "",
                 "Empty grid:"]
        lines.append(_rule(_TL, _TT, _TR, width, instance.cols))
        for r in range(instance.rows):
            for _ in range(3):
                lines.append(_V + _V.join([" " * width] * instance.cols) + _V)
            if r < instance.rows - 1:
                lines.append(_rule(_LT, _CR, _RT, width, instance.cols))
        lines.append(_rule(_BL, _BT, _BR, width, instance.cols))
        lines.append("")
        lines.append("Tiles:")
        lines.extend(_tray(instance, width))
        if instance.border is not None:
            lines.append("")
            lines.append(_border_note(instance))
        return "\n".join(lines)

    rows: list[str] = []
    rows.append(_rule(_TL, _TT, _TR, width, instance.cols))
    for r, row in enumerate(solution.grid):
        resolved = [by_id[p.tile].rotated(p.rot) for p in row]
        triple = [_tile_lines(t, width) for t in resolved]
        for line_no in range(3):
            rows.append(_V + _V.join(part[line_no] for part in triple) + _V)
        if show_ids:
            ids = [
                (f"#{p.tile}" + (f"r{p.rot}" if p.rot else "")).center(width)
                for p in row
            ]
            rows.append(_V + _V.join(ids) + _V)
        if r < instance.rows - 1:
            rows.append(_rule(_LT, _CR, _RT, width, instance.cols))
    rows.append(_rule(_BL, _BT, _BR, width, instance.cols))
    return "\n".join(rows)


def _tray(instance: Instance, width: int, per_line: int = 6) -> list[str]:
    """The unplaced tiles, in rows of ``per_line``."""
    out: list[str] = []
    tiles = list(instance.tiles)
    for start in range(0, len(tiles), per_line):
        chunk = tiles[start : start + per_line]
        out.append(" " + "  ".join(f"#{t.id}".center(width - 1) for t in chunk))
        out.append(_rule(_TL, _TT, _TR, width, len(chunk)))
        triple = [_tile_lines(t, width) for t in chunk]
        for line_no in range(3):
            out.append(_V + _V.join(part[line_no] for part in triple) + _V)
        out.append(_rule(_BL, _BT, _BR, width, len(chunk)))
    return out


def _border_note(instance: Instance) -> str:
    b = instance.border
    assert b is not None
    return (
        f"Fixed border -- top: {list(b.top)}  right: {list(b.right)}  bottom: {list(b.bottom)}  left: {list(b.left)}"
    )


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

#: Colours cycle when an instance uses more symbols than the palette holds.
_PALETTE = (
    "#d64545", "#e08b2e", "#e5c13a", "#5ba65b", "#3f8fbf",
    "#6b58c4", "#b85ba6", "#4aa8a0", "#8c7b5a", "#7a8794",
)
_DARK_TEXT = "#15181c"
_LIGHT_TEXT = "#ffffff"


def _colour(symbol: int) -> str:
    return _PALETTE[symbol % len(_PALETTE)]


def _text_colour(symbol: int) -> str:
    """Pick black or white text for contrast against the wedge colour."""
    hexcode = _colour(symbol).lstrip("#")
    r, g, b = (int(hexcode[i : i + 2], 16) for i in (0, 2, 4))
    # Rec. 601 luma; the 150 threshold was chosen against this palette.
    return _DARK_TEXT if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else _LIGHT_TEXT


def _tile_svg(tile: Tile, x: float, y: float, size: float) -> list[str]:
    """One tile as four triangular wedges meeting at the centre."""
    x2, y2 = x + size, y + size
    cx, cy = x + size / 2, y + size / 2
    wedges = (
        ("top", tile.top, f"{x},{y} {x2},{y} {cx},{cy}", cx, y + size * 0.22),
        ("right", tile.right, f"{x2},{y} {x2},{y2} {cx},{cy}", x2 - size * 0.22, cy),
        ("bottom", tile.bottom, f"{x2},{y2} {x},{y2} {cx},{cy}", cx, y2 - size * 0.22),
        ("left", tile.left, f"{x},{y2} {x},{y} {cx},{cy}", x + size * 0.22, cy),
    )
    parts: list[str] = []
    for _name, symbol, points, tx, ty in wedges:
        parts.append(
            f'<polygon points="{points}" fill="{_colour(symbol)}" '
            f'stroke="#ffffff" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{ty:.1f}" fill="{_text_colour(symbol)}" '
            f'font-size="{size * 0.22:.1f}" font-family="DejaVu Sans, Verdana, sans-serif" '
            f'font-weight="600" text-anchor="middle" dominant-baseline="central">'
            f"{symbol}</text>"
        )
    parts.append(
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="none" '
        f'stroke="#15181c" stroke-width="2" />'
    )
    return parts


def render_svg(
    instance: Instance,
    solution: Solution | None = None,
    *,
    size: float = 72.0,
    gap: float = 0.0,
    title: str | None = None,
) -> str:
    """Render the board as a standalone SVG document.

    With no solution, the tray of unplaced tiles is drawn instead of a filled
    board, spaced out so individual tiles are distinguishable.
    """
    by_id = {t.id: t for t in instance.tiles}
    margin = 24.0
    heading = 30.0 if title is not None else 0.0

    if solution is None:
        per_row = min(instance.cols * 2, max(instance.cols, 4))
        count = len(instance.tiles)
        n_rows = (count + per_row - 1) // per_row
        gap = gap or size * 0.18
        board_w = per_row * size + (per_row - 1) * gap
        board_h = n_rows * (size + gap + 14)
        cells = [
            (i % per_row, i // per_row, by_id[t.id], t.id)
            for i, t in enumerate(instance.tiles)
        ]
    else:
        per_row = instance.cols
        n_rows = instance.rows
        board_w = per_row * size + (per_row - 1) * gap
        board_h = n_rows * size + (n_rows - 1) * gap
        cells = [
            (c, r, by_id[p.tile].rotated(p.rot), p.tile)
            for r, c, p in solution.placements()
        ]

    width = board_w + 2 * margin
    height = board_h + 2 * margin + heading

    body: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        '<rect width="100%" height="100%" fill="#f5f6f8" />',
    ]
    if title is not None:
        body.append(
            f'<text x="{width / 2:.1f}" y="{margin + 4:.1f}" fill="#15181c" '
            f'font-size="16" font-family="DejaVu Sans, Verdana, sans-serif" '
            f'font-weight="600" text-anchor="middle" '
            f'dominant-baseline="hanging">{_escape(title)}</text>'
        )

    for col, row, tile, tile_id in cells:
        x = margin + col * (size + gap)
        y = margin + heading + row * (size + gap + (14 if solution is None else 0))
        body.extend(_tile_svg(tile, x, y, size))
        if solution is None:
            body.append(
                f'<text x="{x + size / 2:.1f}" y="{y + size + 11:.1f}" fill="#3a4049" '
                f'font-size="11" font-family="DejaVu Sans, Verdana, sans-serif" '
                f'text-anchor="middle">#{tile_id}</text>'
            )

    body.append("</svg>")
    return "\n".join(body)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
