"""A deliberately naive reference planner, used only by the tests.

Neither engine is allowed to be the authority on what the optimal plan length
is. Two engines agreeing proves they share assumptions, not that either is
right -- and both were written by the same hand on the same afternoon, which
is exactly the circumstance in which a shared misreading of the domain
survives.

So this is a fifth implementation of the transition semantics (after Prolog,
Z3, the verifier and the generator), written as simply as possible with no
regard for speed: breadth-first search over states with a closed set. BFS over
unit-cost edges is optimal, which makes this an oracle for small instances.

It is intentionally not importable from the package. If it ever disagrees with
an engine, at least one of them is wrong and the test says so.
"""

from __future__ import annotations

from collections import deque

from blocksworld.model import TABLE, Action, Instance, State


def successors(state: State, capacity: int) -> list[tuple[Action, State]]:
    """Every legal (action, next state) pair, derived from the rules directly."""
    supports = state.supports()
    clear = sorted(state.clear_blocks())
    out: list[tuple[Action, State]] = []

    for block in clear:
        source = supports[block]
        destinations: list[str] = []
        # Onto the table: starts a new stack, so it needs a free slot, and a
        # block already on the table has nowhere new to go.
        if source != TABLE and state.n_stacks < capacity:
            destinations.append(TABLE)
        # Onto another clear block, which must not be the one it is already on.
        for candidate in clear:
            if candidate != block and candidate != source:
                destinations.append(candidate)

        for destination in destinations:
            stacks = [list(s) for s in state.stacks]
            for stack in stacks:
                if stack and stack[-1] == block:
                    stack.pop()
                    break
            if destination == TABLE:
                stacks.append([block])
            else:
                for stack in stacks:
                    if stack and stack[-1] == destination:
                        stack.append(block)
                        break
            out.append((Action(block, source, destination), State.of(stacks)))
    return out


def optimal_length(instance: Instance, *, node_limit: int = 200_000) -> int | None:
    """Fewest moves from initial to goal, or ``None`` if unreachable.

    Raises :class:`RuntimeError` rather than guessing if the search grows past
    ``node_limit``; a test that silently gave up would be worse than one that
    fails loudly.
    """
    plan = optimal_plan(instance, node_limit=node_limit)
    return None if plan is None else len(plan)


def optimal_plan(
    instance: Instance, *, node_limit: int = 200_000
) -> list[Action] | None:
    """An optimal plan, or ``None`` when the goal is unreachable."""
    start = instance.initial
    goal = instance.goal
    if start == goal:
        return []

    seen = {start}
    queue: deque[tuple[State, list[Action]]] = deque([(start, [])])
    expanded = 0

    while queue:
        state, path = queue.popleft()
        expanded += 1
        if expanded > node_limit:
            raise RuntimeError(
                f"reference planner exceeded {node_limit} expansions; "
                f"use a smaller instance in this test"
            )
        for action, successor in successors(state, instance.table_capacity):
            if successor in seen:
                continue
            if successor == goal:
                return [*path, action]
            seen.add(successor)
            queue.append((successor, [*path, action]))
    return None
