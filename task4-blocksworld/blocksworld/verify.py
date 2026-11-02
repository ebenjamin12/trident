"""Independent verification of Blocks World plans.

This module imports nothing from :mod:`blocksworld.engines` and does not reuse
any engine's transition code. It re-implements the domain semantics from the
specification in :mod:`blocksworld.model` and replays the plan one action at a
time, checking at every step that the action was legal and that the resulting
state is physically possible.

That independence is the whole value. Two engines agreeing proves only that
they share an assumption; a third implementation disagreeing with both is how
a shared assumption gets caught. ``tests/test_verify.py`` asserts structurally
that no engine module is imported here.

Every violation is reported, not just the first, and each carries the step
index so a long plan can be debugged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import TABLE, Action, Instance, Plan, State


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule, located at a step of the plan."""

    kind: str
    detail: str
    step: int | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        where = f"step {self.step}: " if self.step is not None else ""
        return f"[{self.kind}] {where}{self.detail}"


@dataclass(frozen=True, slots=True)
class Report:
    """Outcome of checking one plan against one instance."""

    ok: bool
    violations: tuple[Violation, ...] = field(default_factory=tuple)
    states: tuple[State, ...] = field(default_factory=tuple)
    final_state: State | None = None

    @property
    def summary(self) -> str:
        if self.ok:
            steps = max(len(self.states) - 1, 0)
            return f"VALID - goal reached in {steps} legal move(s)"
        kinds = sorted({v.kind for v in self.violations})
        return (
            f"INVALID - {len(self.violations)} violation(s) "
            f"across {len(kinds)} category/categories: {', '.join(kinds)}"
        )

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.ok


# --------------------------------------------------------------------------
# Transition semantics -- this module's own implementation
# --------------------------------------------------------------------------


class IllegalAction(ValueError):
    """Raised when an action's preconditions do not hold."""


def apply_action(state: State, action: Action, *, table_capacity: int) -> State:
    """Return the state after ``action``, or raise :class:`IllegalAction`.

    Implemented here independently of every planning engine. Preconditions are
    checked in the order they are stated in the domain definition.
    """
    supports = state.supports()
    clear = state.clear_blocks()

    if action.block == TABLE:
        raise IllegalAction("the table cannot be moved")
    if action.block not in supports:
        raise IllegalAction(f"unknown block {action.block!r}")
    if action.destination == action.block:
        raise IllegalAction(f"block {action.block!r} cannot be placed on itself")
    if action.source == action.destination:
        raise IllegalAction(
            f"source and destination are both {action.source!r}; not a move"
        )
    if action.block not in clear:
        raise IllegalAction(
            f"block {action.block!r} is not clear; "
            f"{_block_above(state, action.block)!r} rests on it"
        )
    if supports[action.block] != action.source:
        raise IllegalAction(
            f"block {action.block!r} rests on {supports[action.block]!r}, "
            f"not on {action.source!r}"
        )
    if action.destination != TABLE:
        if action.destination not in supports:
            raise IllegalAction(f"unknown destination block {action.destination!r}")
        if action.destination not in clear:
            raise IllegalAction(f"destination {action.destination!r} is not clear")

    # Effects. Removing the block from its stack may empty that stack, which
    # frees a table slot; State.of drops empty stacks for us.
    stacks = [list(s) for s in state.stacks]
    for stack in stacks:
        if stack and stack[-1] == action.block:
            stack.pop()
            break

    if action.destination == TABLE:
        # The move occupies a fresh table slot. Count slots after the removal
        # above, because vacating one stack and starting another can be legal
        # at exactly full capacity.
        occupied = sum(1 for s in stacks if s)
        if occupied + 1 > table_capacity:
            raise IllegalAction(
                f"table is full: {occupied} slot(s) in use, capacity {table_capacity}"
            )
        stacks.append([action.block])
    else:
        for stack in stacks:
            if stack and stack[-1] == action.destination:
                stack.append(action.block)
                break
        else:  # pragma: no cover - unreachable given the clear check above
            raise IllegalAction(
                f"destination {action.destination!r} is not on top of any stack"
            )

    return State.of(stacks)


def _block_above(state: State, block: str) -> str | None:
    for stack in state.stacks:
        if block in stack:
            index = stack.index(block)
            return stack[index + 1] if index + 1 < len(stack) else None
    return None


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------


def verify(instance: Instance, plan: Plan) -> Report:
    """Replay ``plan`` against ``instance`` and check every rule."""
    violations: list[Violation] = []
    add = violations.append

    # -- 1. the instance itself must be well formed ------------------------
    try:
        instance.validate()
    except Exception as exc:  # noqa: BLE001 - surfaced as a violation
        add(Violation("instance", str(exc)))
        return Report(False, tuple(violations))

    # -- 2. identity and declared length -----------------------------------
    if plan.instance_id and plan.instance_id != instance.id:
        add(
            Violation(
                "identity",
                f"plan is for instance {plan.instance_id!r}, not {instance.id!r}",
            )
        )

    # -- 3. only satisfied plans carry actions -----------------------------
    if not plan.sat:
        add(
            Violation(
                "status",
                f"plan status is {plan.status!r}; only 'sat' plans can be verified",
            )
        )
        return Report(False, tuple(violations))

    # -- 4. replay ---------------------------------------------------------
    state = instance.initial
    states: list[State] = [state]

    for index, action in enumerate(plan.actions, start=1):
        try:
            state = apply_action(
                state, action, table_capacity=instance.table_capacity
            )
        except IllegalAction as exc:
            add(Violation("action", str(exc), step=index))
            return Report(False, tuple(violations), tuple(states), state)

        # Intermediate state must remain physically legal. apply_action
        # enforces this by construction, so a failure here means the
        # transition itself is wrong -- which is exactly what we want to catch.
        try:
            state.validate(
                expected_blocks=instance.blocks,
                table_capacity=instance.table_capacity,
            )
        except Exception as exc:  # noqa: BLE001
            add(Violation("intermediate-state", str(exc), step=index))
            return Report(False, tuple(violations), tuple(states), state)

        states.append(state)

    # -- 5. the goal must hold exactly -------------------------------------
    if state != instance.goal:
        add(
            Violation(
                "goal",
                f"final state is [{state}] but the goal is [{instance.goal}]",
            )
        )

    # -- 6. the reported length must match what was delivered --------------
    declared = plan.stats.get("length")
    if declared is not None and declared != plan.length:
        add(
            Violation(
                "length",
                f"stats report length {declared} but the plan has {plan.length} actions",
            )
        )

    return Report(not violations, tuple(violations), tuple(states), state)


def verify_optimal(
    instance: Instance, plan: Plan, *, known_optimum: int
) -> Report:
    """Verify a plan and additionally require it to have optimal length.

    ``known_optimum`` must come from somewhere trustworthy -- a hand-computed
    expected value in a test, or a second engine. This is kept separate from
    :func:`verify` because plan validity and plan optimality are different
    claims and conflating them hides which one failed.
    """
    report = verify(instance, plan)
    if not report.ok:
        return report
    if plan.length != known_optimum:
        return Report(
            False,
            report.violations
            + (
                Violation(
                    "optimality",
                    f"plan has {plan.length} moves but the optimum is {known_optimum}",
                ),
            ),
            report.states,
            report.final_state,
        )
    return report
