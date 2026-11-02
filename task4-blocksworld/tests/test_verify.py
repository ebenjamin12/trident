"""The independent verifier must reject every class of invalid plan.

Each test takes a known-good plan and breaks exactly one rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from blocksworld.model import TABLE, Action, Instance, Plan, State
from blocksworld.verify import IllegalAction, apply_action, verify, verify_optimal
from reference import optimal_plan

SUSSMAN = Instance(
    "sus", ("A", "B", "C"),
    State.of([["C", "A"], ["B"]]), State.of([["A", "B", "C"]]), 3,
)
SUSSMAN_PLAN = Plan(
    "sus", "sat",
    (
        Action("A", "C", TABLE),
        Action("B", TABLE, "A"),
        Action("C", TABLE, "B"),
    ),
)


# -- independence -----------------------------------------------------------


def test_verifier_imports_no_engine():
    """Structural check: the verifier must not depend on what it checks."""
    source = (
        Path(__file__).resolve().parent.parent / "blocksworld" / "verify.py"
    ).read_text()
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(
        "engine" in name or "z3" in name or "prolog" in name for name in imported
    ), imported


# -- happy path -------------------------------------------------------------


def test_accepts_a_correct_plan():
    report = verify(SUSSMAN, SUSSMAN_PLAN)
    assert report.ok, report.summary
    assert report.final_state == SUSSMAN.goal
    assert len(report.states) == 4  # initial plus one per move


def test_states_are_recorded_in_order():
    report = verify(SUSSMAN, SUSSMAN_PLAN)
    assert report.states[0] == SUSSMAN.initial
    assert report.states[-1] == SUSSMAN.goal


def test_accepts_an_empty_plan_when_the_goal_already_holds():
    instance = Instance(
        "same", ("A",), State.of([["A"]]), State.of([["A"]]), 1
    )
    assert verify(instance, Plan("same", "sat", ())).ok


# -- one broken rule per test ----------------------------------------------


def test_rejects_moving_a_block_that_is_not_clear():
    # C has A on top of it in the initial state.
    bad = Plan("sus", "sat", (Action("C", TABLE, "B"),))
    report = verify(SUSSMAN, bad)
    assert not report.ok
    assert any(v.kind == "action" and "not clear" in v.detail for v in report.violations)


def test_rejects_a_wrong_source():
    bad = Plan("sus", "sat", (Action("A", TABLE, "B"),))  # A is on C, not the table
    report = verify(SUSSMAN, bad)
    assert any("rests on" in v.detail for v in report.violations)


def test_rejects_an_occupied_destination():
    bad = Plan("sus", "sat", (Action("A", "C", "X"),))
    report = verify(SUSSMAN, bad)
    assert any("unknown destination" in v.detail for v in report.violations)


def test_rejects_stacking_onto_a_covered_block():
    bad = Plan("sus", "sat", (Action("B", TABLE, "C"),))  # C carries A
    report = verify(SUSSMAN, bad)
    assert any("not clear" in v.detail for v in report.violations)


def test_rejects_a_self_move():
    bad = Plan("sus", "sat", (Action("A", "C", "A"),))
    report = verify(SUSSMAN, bad)
    assert any("on itself" in v.detail for v in report.violations)


def test_rejects_a_null_move():
    bad = Plan("sus", "sat", (Action("B", TABLE, TABLE),))
    report = verify(SUSSMAN, bad)
    assert any("not a move" in v.detail for v in report.violations)


def test_rejects_an_unknown_block():
    bad = Plan("sus", "sat", (Action("Z", TABLE, "B"),))
    report = verify(SUSSMAN, bad)
    assert any("unknown block" in v.detail for v in report.violations)


def test_rejects_a_plan_that_stops_short_of_the_goal():
    bad = Plan("sus", "sat", (Action("A", "C", TABLE),))
    report = verify(SUSSMAN, bad)
    assert not report.ok
    assert any(v.kind == "goal" for v in report.violations)


def test_rejects_a_cyclic_plan_that_returns_to_the_start():
    """Legal moves that undo each other never reach the goal."""
    cyclic = Plan(
        "sus", "sat",
        (Action("A", "C", TABLE), Action("A", TABLE, "C")),
    )
    report = verify(SUSSMAN, cyclic)
    assert not report.ok
    assert any(v.kind == "goal" for v in report.violations)


def test_rejects_a_plan_with_redundant_moves_that_misses_the_goal():
    redundant = Plan(
        "sus", "sat",
        (
            Action("A", "C", TABLE),
            Action("B", TABLE, "A"),
            Action("B", "A", TABLE),
        ),
    )
    assert not verify(SUSSMAN, redundant).ok


def test_rejects_a_plan_for_a_different_instance():
    bad = Plan("some-other", "sat", SUSSMAN_PLAN.actions)
    report = verify(SUSSMAN, bad)
    assert any(v.kind == "identity" for v in report.violations)


def test_rejects_a_non_sat_plan():
    report = verify(SUSSMAN, Plan("sus", "limit", ()))
    assert not report.ok
    assert any(v.kind == "status" for v in report.violations)


def test_rejects_a_malformed_instance():
    broken = Instance(
        "bad", ("A", "B"), State.of([["A"]]), State.of([["A"]]), 2
    )
    report = verify(broken, Plan("bad", "sat", ()))
    assert any(v.kind == "instance" for v in report.violations)


def test_violation_carries_the_step_index():
    bad = Plan(
        "sus", "sat",
        (Action("A", "C", TABLE), Action("C", TABLE, "A"), Action("B", TABLE, "Z")),
    )
    report = verify(SUSSMAN, bad)
    steps = [v.step for v in report.violations if v.step is not None]
    assert steps and steps[0] == 3


# -- table capacity ---------------------------------------------------------


def test_rejects_a_move_that_overflows_the_table():
    instance = Instance(
        "cap", ("A", "B", "C"),
        State.of([["A", "B"], ["C"]]), State.of([["A", "B"], ["C"]]), 2,
    )
    bad = Plan("cap", "sat", (Action("B", "A", TABLE),))
    report = verify(instance, bad)
    assert any("table is full" in v.detail for v in report.violations)


def test_allows_a_move_that_vacates_and_reoccupies_at_full_capacity():
    """Moving the only block of a stack onto another frees its slot first."""
    instance = Instance(
        "swap", ("A", "B"),
        State.of([["A"], ["B"]]), State.of([["A", "B"]]), 2,
    )
    assert verify(instance, Plan("swap", "sat", (Action("B", TABLE, "A"),))).ok


# -- apply_action directly --------------------------------------------------


def test_apply_action_raises_on_an_illegal_move():
    with pytest.raises(IllegalAction):
        apply_action(SUSSMAN.initial, Action("C", TABLE, "B"), table_capacity=3)


def test_apply_action_produces_a_canonical_state():
    after = apply_action(SUSSMAN.initial, Action("A", "C", TABLE), table_capacity=3)
    assert after == State.of([["A"], ["B"], ["C"]])


# -- optimality checking ----------------------------------------------------


def test_verify_optimal_accepts_the_shortest_plan():
    report = verify_optimal(SUSSMAN, SUSSMAN_PLAN, known_optimum=3)
    assert report.ok


def test_verify_optimal_rejects_a_valid_but_longer_plan():
    longer = optimal_plan(SUSSMAN)
    assert longer is not None
    padded = Plan(
        "sus", "sat",
        (Action("A", "C", TABLE), Action("A", TABLE, "C"), *longer),
    )
    assert verify(SUSSMAN, padded).ok, "the padded plan should still be legal"
    report = verify_optimal(SUSSMAN, padded, known_optimum=3)
    assert not report.ok
    assert any(v.kind == "optimality" for v in report.violations)
