"""ASCII, SVG and animated rendering for Blocks World.

Like the TetraVex renderers, nothing here imports a planning engine: every
function takes an :class:`~blocksworld.model.Instance` plus states and actions,
so the same code draws a Prolog plan and a Z3 plan identically.

Renderers never replay a plan themselves. The sequence of states comes from
:func:`blocksworld.verify.verify`, which means **only a plan that has passed
independent verification can be drawn**. A renderer that computed its own
states would be a fourth transition implementation, and a picture of an
unverified plan is worse than no picture.

Outputs
-------
``render_ascii_state``     one state as text
``render_ascii_plan``      every state in sequence, captioned with its move
``render_svg_state``       one state as a standalone SVG
``render_svg_filmstrip``   every state side by side in one SVG
``render_svg_animated``    an SMIL animation; plays in any browser, no deps
``render_gif``             an animated GIF; needs Pillow
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .model import Action, Instance, State

# --------------------------------------------------------------------------
# shared geometry
# --------------------------------------------------------------------------


def _column_order(instance: Instance, state: State) -> list[tuple[str, ...]]:
    """Stacks in a stable left-to-right order.

    The domain treats the table as unordered, so any order would be correct;
    sorting by the bottom block keeps a block in the same column from frame to
    frame wherever possible, which makes an animation far easier to follow.
    """
    return sorted(state.stacks, key=lambda s: (s[0], len(s)))


def _caption(index: int, action: Action | None) -> str:
    """Full prose caption, for ASCII output where width is not a constraint."""
    if action is None:
        return "initial state"
    return f"move {index}: {action.describe()}"


def _caption_compact(index: int, action: Action | None) -> str:
    """Short caption for fixed-width panels.

    SVG text does not wrap and a GIF frame cannot grow, so the prose form
    overflows and collides with its neighbours. This keeps the three facts
    that identify a movement -- which block, from where, to where.
    """
    if action is None:
        return "start"
    return f"{index}. {action.block}: {action.source} → {action.destination}"


#: Rough advance width per character at font-size 13, used to stop a caption
#: from overflowing its panel. Measured against DejaVu Sans; approximate by
#: design, since embedding font metrics for one label would be disproportionate.
_CHAR_W = 7.0


# --------------------------------------------------------------------------
# ASCII
# --------------------------------------------------------------------------


def render_ascii_state(
    instance: Instance, state: State, *, title: str | None = None
) -> str:
    """Draw one state as stacked boxes resting on a table rule."""
    columns = _column_order(instance, state)
    width = max((len(b) for b in instance.blocks), default=1) + 2
    tallest = max((len(s) for s in columns), default=0)

    lines: list[str] = []
    if title:
        lines.append(title)

    for level in range(tallest - 1, -1, -1):
        top: list[str] = []
        mid: list[str] = []
        for stack in columns:
            if level < len(stack):
                top.append("┌" + "─" * width + "┐")
                mid.append("│" + stack[level].center(width) + "│")
            else:
                top.append(" " * (width + 2))
                mid.append(" " * (width + 2))
        # A box's lid is only drawn when nothing sits on top of it.
        lids: list[str] = []
        for i, stack in enumerate(columns):
            if level < len(stack) and level == len(stack) - 1:
                lids.append(top[i])
            elif level < len(stack):
                lids.append("├" + "─" * width + "┤")
            else:
                lids.append(" " * (width + 2))
        lines.append(" ".join(lids))
        lines.append(" ".join(mid))

    rule_unit = "┴" + "─" * width + "┴"
    if columns:
        lines.append("─" + "─".join(rule_unit for _ in columns) + "─")
    else:  # pragma: no cover - a state always has at least one stack
        lines.append("─" * (width + 4))

    slots = f"{state.n_stacks}/{instance.table_capacity} table slots used"
    lines.append(slots.rjust(len(lines[-1])))
    return "\n".join(lines)


def render_ascii_plan(
    instance: Instance,
    states: Sequence[State],
    actions: Sequence[Action],
    *,
    show_goal: bool = True,
) -> str:
    """Draw every state in the plan, each captioned with the move that made it."""
    chunks: list[str] = []
    for i, state in enumerate(states):
        action = actions[i - 1] if i > 0 else None
        chunks.append(render_ascii_state(instance, state, title=_caption(i, action)))
    if show_goal:
        chunks.append(
            render_ascii_state(instance, instance.goal, title="goal (for reference)")
        )
    return "\n\n".join(chunks)


def render_ascii_problem(instance: Instance) -> str:
    """Initial and goal states side by side in text, for posing the problem."""
    return (
        f"{instance.id}\n"
        f"{instance.n_blocks} blocks, table capacity {instance.table_capacity}, "
        f"heuristic lower bound {instance.heuristic(instance.initial)}\n\n"
        + render_ascii_state(instance, instance.initial, title="INITIAL")
        + "\n\n"
        + render_ascii_state(instance, instance.goal, title="GOAL")
    )


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

_PALETTE = (
    "#d64545", "#e08b2e", "#e5c13a", "#5ba65b", "#3f8fbf",
    "#6b58c4", "#b85ba6", "#4aa8a0", "#8c7b5a", "#7a8794",
)
_DARK_TEXT = "#15181c"
_LIGHT_TEXT = "#ffffff"
_BG = "#f5f6f8"
_TABLE = "#3a4049"


@dataclass(frozen=True, slots=True)
class _Layout:
    block_w: float = 54.0
    block_h: float = 34.0
    gap_x: float = 14.0
    margin: float = 20.0
    caption_h: float = 24.0
    table_h: float = 8.0


def _block_colour(instance: Instance, block: str) -> str:
    return _PALETTE[instance.blocks.index(block) % len(_PALETTE)]


def _text_colour(fill: str) -> str:
    code = fill.lstrip("#")
    r, g, b = (int(code[i : i + 2], 16) for i in (0, 2, 4))
    return _DARK_TEXT if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else _LIGHT_TEXT


def _panel_size(
    instance: Instance,
    states: Sequence[State],
    layout: _Layout,
    captions: Sequence[str] = (),
) -> tuple[float, float]:
    """One panel sized to hold the widest and tallest state in the sequence.

    ``captions`` widens the panel when a label would otherwise run past its
    edge and collide with the next one.
    """
    max_stacks = max((s.n_stacks for s in states), default=1)
    max_height = max((max((len(k) for k in s.stacks), default=1) for s in states),
                     default=1)
    width = max_stacks * layout.block_w + (max_stacks - 1) * layout.gap_x
    height = max_height * layout.block_h
    if captions:
        width = max(width, max(len(c) for c in captions) * _CHAR_W)
    return (max(width, layout.block_w), max(height, layout.block_h))


def _state_body(
    instance: Instance,
    state: State,
    origin_x: float,
    baseline_y: float,
    panel_w: float,
    layout: _Layout,
) -> list[str]:
    """SVG elements for one state, drawn upward from ``baseline_y``."""
    columns = _column_order(instance, state)
    total_w = len(columns) * layout.block_w + max(len(columns) - 1, 0) * layout.gap_x
    start_x = origin_x + (panel_w - total_w) / 2

    parts = [
        f'<rect x="{origin_x:.1f}" y="{baseline_y:.1f}" width="{panel_w:.1f}" '
        f'height="{layout.table_h:.1f}" rx="2" fill="{_TABLE}" />'
    ]
    for col, stack in enumerate(columns):
        x = start_x + col * (layout.block_w + layout.gap_x)
        for level, block in enumerate(stack):
            y = baseline_y - (level + 1) * layout.block_h
            fill = _block_colour(instance, block)
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{layout.block_w:.1f}" '
                f'height="{layout.block_h:.1f}" rx="4" fill="{fill}" '
                f'stroke="{_DARK_TEXT}" stroke-width="1.5" />'
            )
            parts.append(
                f'<text x="{x + layout.block_w / 2:.1f}" '
                f'y="{y + layout.block_h / 2:.1f}" fill="{_text_colour(fill)}" '
                f'font-size="16" font-family="DejaVu Sans, Verdana, sans-serif" '
                f'font-weight="600" text-anchor="middle" '
                f'dominant-baseline="central">{_escape(block)}</text>'
            )
    return parts


def _caption_element(text: str, x: float, y: float, width: float) -> str:
    return (
        f'<text x="{x + width / 2:.1f}" y="{y:.1f}" fill="{_DARK_TEXT}" '
        f'font-size="13" font-family="DejaVu Sans, Verdana, sans-serif" '
        f'text-anchor="middle" dominant-baseline="hanging">{_escape(text)}</text>'
    )


def _svg_open(width: float, height: float) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        f'<rect width="100%" height="100%" fill="{_BG}" />',
    ]


def render_svg_state(
    instance: Instance, state: State, *, title: str | None = None
) -> str:
    """One state as a standalone SVG document."""
    layout = _Layout()
    panel_w, panel_h = _panel_size(instance, [state], layout)
    width = panel_w + 2 * layout.margin
    height = panel_h + layout.table_h + 2 * layout.margin + (
        layout.caption_h if title else 0
    )
    top = layout.margin + (layout.caption_h if title else 0)
    baseline = top + panel_h

    body = _svg_open(width, height)
    if title:
        body.append(_caption_element(title, layout.margin, layout.margin / 2, panel_w))
    body.extend(
        _state_body(instance, state, layout.margin, baseline, panel_w, layout)
    )
    body.append("</svg>")
    return "\n".join(body)


def render_svg_filmstrip(
    instance: Instance,
    states: Sequence[State],
    actions: Sequence[Action],
    *,
    columns: int | None = None,
) -> str:
    """Every state laid out in a grid, each captioned with its move."""
    layout = _Layout()
    captions = [
        _caption_compact(i, actions[i - 1] if i > 0 else None)
        for i in range(len(states))
    ]
    panel_w, panel_h = _panel_size(instance, states, layout, captions)
    per_row = columns or min(len(states), 4)
    rows = (len(states) + per_row - 1) // per_row

    cell_w = panel_w + layout.gap_x * 2
    cell_h = panel_h + layout.table_h + layout.caption_h + layout.gap_x * 2
    width = per_row * cell_w + 2 * layout.margin
    height = rows * cell_h + 2 * layout.margin

    body = _svg_open(width, height)
    for i, state in enumerate(states):
        row, col = divmod(i, per_row)
        ox = layout.margin + col * cell_w + layout.gap_x
        oy = layout.margin + row * cell_h + layout.gap_x
        body.append(_caption_element(captions[i], ox, oy, panel_w))
        baseline = oy + layout.caption_h + panel_h
        body.extend(_state_body(instance, state, ox, baseline, panel_w, layout))
    body.append("</svg>")
    return "\n".join(body)


def render_svg_animated(
    instance: Instance,
    states: Sequence[State],
    actions: Sequence[Action],
    *,
    seconds_per_step: float = 1.2,
) -> str:
    """An SMIL-animated SVG cycling through the plan.

    Each state is a group whose opacity is switched on for its slice of the
    timeline with ``calcMode="discrete"``. This needs no JavaScript and no
    external library, and plays in any browser that renders SVG animation.
    """
    layout = _Layout()
    captions = [
        _caption_compact(i, actions[i - 1] if i > 0 else None)
        for i in range(len(states))
    ]
    panel_w, panel_h = _panel_size(instance, states, layout, captions)
    width = panel_w + 2 * layout.margin
    height = panel_h + layout.table_h + 2 * layout.margin + layout.caption_h
    baseline = layout.margin + layout.caption_h + panel_h
    frames = len(states)
    duration = max(frames * seconds_per_step, 0.1)
    key_times = ";".join(f"{i / frames:.4f}" for i in range(frames))

    body = _svg_open(width, height)
    for i, state in enumerate(states):
        values = ";".join("1" if j == i else "0" for j in range(frames))
        body.append(f'<g opacity="{1 if i == 0 else 0}">')
        body.append(
            f'<animate attributeName="opacity" calcMode="discrete" '
            f'values="{values}" keyTimes="{key_times}" dur="{duration:.2f}s" '
            f'repeatCount="indefinite" />'
        )
        body.append(
            _caption_element(captions[i], layout.margin, layout.margin / 2, panel_w)
        )
        body.extend(
            _state_body(instance, state, layout.margin, baseline, panel_w, layout)
        )
        body.append("</g>")
    body.append("</svg>")
    return "\n".join(body)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------
# GIF (optional; needs Pillow)
# --------------------------------------------------------------------------


class GifUnavailable(RuntimeError):
    """Raised when Pillow is not installed."""


def gif_available() -> bool:
    try:
        import PIL  # noqa: F401, PLC0415
    except ImportError:
        return False
    return True


def render_gif(
    instance: Instance,
    states: Sequence[State],
    actions: Sequence[Action],
    path: str,
    *,
    ms_per_step: int = 1200,
    scale: int = 2,
) -> str:
    """Write an animated GIF of the plan. Returns the path written.

    Frames are drawn directly with Pillow's primitives rather than by
    rasterising the SVG, which would pull in a renderer such as cairosvg. The
    GIF path therefore has exactly one optional dependency.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise GifUnavailable(
            "animated GIF output needs Pillow; `pip install pillow`, "
            "or use --format animated-svg which has no dependencies"
        ) from exc

    layout = _Layout()
    captions = [
        _caption_compact(i, actions[i - 1] if i > 0 else None)
        for i in range(len(states))
    ]
    panel_w, panel_h = _panel_size(instance, states, layout, captions)
    width = int((panel_w + 2 * layout.margin) * scale)
    height = int(
        (panel_h + layout.table_h + 2 * layout.margin + layout.caption_h) * scale
    )

    def font(size: int):
        """Best available font at ``size``, degrading rather than failing.

        Font availability is the one genuinely platform-dependent part of GIF
        output: the DejaVu paths below exist on most Linux distributions and
        on neither macOS nor Windows. Each fallback is therefore tried in turn
        and any failure is tolerated, because a GIF with an ugly font is a far
        better outcome than a traceback.

        ``load_default(size=...)`` scales (Pillow >= 10.1); the bare
        ``load_default()`` is a fixed-size bitmap font and is the last resort,
        which is why it is tried only after the sized form.
        """
        candidates = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "DejaVuSans.ttf",  # resolved from Pillow's own font directory
        )
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:  # noqa: BLE001, S112 - any failure means "try the next"
                continue
        try:
            return ImageFont.load_default(size=size)
        except Exception:  # noqa: BLE001 - older Pillow has no size parameter
            return ImageFont.load_default()

    label_font = font(int(16 * scale))
    caption_font = font(int(13 * scale))

    frames: list[Image.Image] = []
    for i, state in enumerate(states):
        image = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(image)

        caption = captions[i]
        draw.text(
            (width / 2, layout.margin / 2 * scale),
            caption,
            fill=_DARK_TEXT,
            font=caption_font,
            anchor="ma",
        )

        baseline = (layout.margin + layout.caption_h + panel_h) * scale
        draw.rounded_rectangle(
            [
                layout.margin * scale,
                baseline,
                (layout.margin + panel_w) * scale,
                baseline + layout.table_h * scale,
            ],
            radius=2 * scale,
            fill=_TABLE,
        )

        columns = _column_order(instance, state)
        total_w = (
            len(columns) * layout.block_w
            + max(len(columns) - 1, 0) * layout.gap_x
        )
        start_x = layout.margin + (panel_w - total_w) / 2
        for col, stack in enumerate(columns):
            x = (start_x + col * (layout.block_w + layout.gap_x)) * scale
            for level, block in enumerate(stack):
                y = baseline - (level + 1) * layout.block_h * scale
                fill = _block_colour(instance, block)
                draw.rounded_rectangle(
                    [x, y, x + layout.block_w * scale, y + layout.block_h * scale],
                    radius=4 * scale,
                    fill=fill,
                    outline=_DARK_TEXT,
                    width=max(int(1.5 * scale), 1),
                )
                draw.text(
                    (
                        x + layout.block_w * scale / 2,
                        y + layout.block_h * scale / 2,
                    ),
                    block,
                    fill=_text_colour(fill),
                    font=label_font,
                    anchor="mm",
                )
        frames.append(image)

    # Hold the final state a little longer so a loop is readable.
    durations = [ms_per_step] * len(frames)
    durations[-1] = ms_per_step * 2

    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    return path
