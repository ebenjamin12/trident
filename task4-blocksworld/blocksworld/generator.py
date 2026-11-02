"""Reproducible Blocks World instance generation.

Two modes, because "harder" means two different things in this domain:

``partition`` (default)
    Initial and goal are independent random partitions of the blocks into
    stacks. Difficulty is driven by block count and how many stacks each state
    uses. The true optimal distance is unknown up front.

``walk``
    The goal is produced by taking ``--walk K`` random legal moves from the
    initial state. The optimal distance is then **at most** K -- and usually
    less, since a random walk doubles back. This is the mode to use when a
    controlled, known upper bound on plan length matters.

Both modes are fully determined by their seed.

A note on the duplicated move logic
-----------------------------------
``walk`` mode needs to apply actions, and it does so with its own private
``_step`` function rather than importing the verifier's. The verifier must stay
an independent check on everything else in the system, including the
generator: if the generator and the verifier shared a transition function, a
bug in it would produce instances the verifier would happily bless. Three
engines plus the verifier plus this make five independent implementations of
the same semantics, which is deliberate.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .model import TABLE, Action, Instance, State

#: Block names A, B, C, ... then A1, B1, ... once the alphabet runs out.
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True, slots=True)
class GeneratedProblem:
    """An instance plus, when known, an upper bound on its optimal length."""

    instance: Instance
    #: Number of moves used to build the goal in ``walk`` mode; ``None`` for
    #: ``partition`` mode. The optimum is at most this.
    walk_length: int | None = None


def block_names(n: int) -> tuple[str, ...]:
    """Deterministic block names for ``n`` blocks."""
    if n < 1:
        raise ValueError("need at least one block")
    names = []
    for i in range(n):
        letter = _ALPHABET[i % 26]
        suffix = i // 26
        names.append(letter if suffix == 0 else f"{letter}{suffix}")
    return tuple(names)


def _random_partition(
    rng: random.Random, blocks: list[str], max_stacks: int
) -> State:
    """Shuffle the blocks and cut them into between 1 and ``max_stacks`` stacks."""
    shuffled = list(blocks)
    rng.shuffle(shuffled)
    n_stacks = rng.randint(1, max(1, min(max_stacks, len(shuffled))))

    # Choose n_stacks-1 distinct cut points to split the sequence.
    cuts = sorted(rng.sample(range(1, len(shuffled)), n_stacks - 1)) if n_stacks > 1 else []
    stacks: list[list[str]] = []
    previous = 0
    for cut in [*cuts, len(shuffled)]:
        stacks.append(shuffled[previous:cut])
        previous = cut
    return State.of(stacks)


def _legal_moves(state: State, table_capacity: int) -> list[Action]:
    """Every action legal in ``state`` (generator-local; see module docstring)."""
    supports = state.supports()
    clear = sorted(state.clear_blocks())
    occupied = state.n_stacks
    moves: list[Action] = []
    for block in clear:
        source = supports[block]
        # Moving onto the table starts a new stack, so it needs a free slot.
        # A block already on the table has nowhere new to go, and that case is
        # excluded by requiring source != TABLE.
        if source != TABLE and occupied < table_capacity:
            moves.append(Action(block, source, TABLE))
        for destination in clear:
            if destination == block or destination == source:
                continue
            moves.append(Action(block, source, destination))
    return moves


def _step(state: State, action: Action) -> State:
    """Apply an action assumed legal (generator-local; see module docstring)."""
    stacks = [list(s) for s in state.stacks]
    for stack in stacks:
        if stack and stack[-1] == action.block:
            stack.pop()
            break
    if action.destination == TABLE:
        stacks.append([action.block])
    else:
        for stack in stacks:
            if stack and stack[-1] == action.destination:
                stack.append(action.block)
                break
    return State.of(stacks)


def generate(
    n_blocks: int = 5,
    *,
    seed: int = 0,
    table_capacity: int | None = None,
    max_stacks: int | None = None,
    walk: int | None = None,
) -> GeneratedProblem:
    """Generate one instance.

    ``table_capacity`` defaults to ``n_blocks`` (an unrestricted table, where
    every instance is solvable). ``max_stacks`` bounds how many stacks the
    random states use, and defaults to the capacity.

    With ``walk=K`` the goal is reached by K random legal moves from the
    initial state, giving an optimal length of at most K.
    """
    if n_blocks < 1:
        raise ValueError("n_blocks must be at least 1")
    capacity = n_blocks if table_capacity is None else table_capacity
    if capacity < 1:
        raise ValueError("table_capacity must be at least 1")
    if walk is not None and walk < 0:
        raise ValueError("walk length must not be negative")

    spread = capacity if max_stacks is None else max_stacks
    if spread < 1:
        raise ValueError("max_stacks must be at least 1")
    spread = min(spread, capacity)

    rng = random.Random(seed)
    blocks = list(block_names(n_blocks))

    initial = _random_partition(rng, blocks, spread)

    if walk is None:
        goal = _random_partition(rng, blocks, spread)
        mode = "partition"
        walk_length: int | None = None
    else:
        state = initial
        taken = 0
        for _ in range(walk):
            options = _legal_moves(state, capacity)
            if not options:
                break
            state = _step(state, rng.choice(options))
            taken += 1
        goal = state
        mode = f"walk{walk}"
        walk_length = taken

    # The id must distinguish every instance this function can produce,
    # otherwise two different problems collide in a benchmark record and look
    # like one engine disagreeing with itself. max_stacks changes the instance
    # without changing block count or capacity, so it belongs in the name.
    spread_tag = f"-ms{spread}" if spread != capacity else ""

    instance = Instance(
        id=f"bw-{n_blocks}b-c{capacity}{spread_tag}-{mode}-seed{seed}",
        blocks=tuple(blocks),
        initial=initial,
        goal=goal,
        table_capacity=capacity,
        seed=seed,
        generator=mode,
    )
    instance.validate()
    return GeneratedProblem(instance, walk_length)
