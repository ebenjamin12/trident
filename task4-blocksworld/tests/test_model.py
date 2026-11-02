"""Domain model: canonical states, validity, heuristic, schema round-trips."""

from __future__ import annotations

import json

import pytest
from blocksworld.generator import generate
from blocksworld.model import (
    TABLE,
    Action,
    FormatError,
    Instance,
    Plan,
    State,
)

# -- canonical states -------------------------------------------------------


def test_table_is_unordered():
    assert State.of([["A"], ["B"]]) == State.of([["B"], ["A"]])


def test_stack_order_is_significant():
    assert State.of([["A", "B"]]) != State.of([["B", "A"]])


def test_empty_stacks_are_dropped():
    assert State.of([["A"], [], ["B"]]) == State.of([["A"], ["B"]])


def test_supports_maps_each_block_to_what_it_rests_on():
    state = State.of([["A", "B", "C"], ["D"]])
    assert state.supports() == {"A": TABLE, "B": "A", "C": "B", "D": TABLE}


def test_clear_blocks_are_the_stack_tops():
    assert State.of([["A", "B"], ["C"]]).clear_blocks() == frozenset({"B", "C"})


def test_height_counts_from_the_table():
    state = State.of([["A", "B", "C"]])
    assert [state.height_of(b) for b in "ABC"] == [0, 1, 2]


def test_blocks_are_sorted():
    assert State.of([["C"], ["A", "B"]]).blocks == ("A", "B", "C")


def test_stack_of_raises_for_an_absent_block():
    with pytest.raises(KeyError):
        State.of([["A"]]).stack_of("Z")


# -- state validity ---------------------------------------------------------


def test_rejects_a_block_in_two_places():
    with pytest.raises(FormatError, match="more than once"):
        State.of([["A"], ["A"]]).validate()


def test_rejects_the_reserved_table_name():
    with pytest.raises(FormatError, match="reserved"):
        State.of([[TABLE]]).validate()


def test_rejects_an_illegal_block_name():
    with pytest.raises(FormatError, match="must match"):
        State.of([["a b"]]).validate()


def test_rejects_a_state_that_misses_a_declared_block():
    with pytest.raises(FormatError, match="missing"):
        State.of([["A"]]).validate(expected_blocks=["A", "B"])


def test_rejects_a_state_with_an_undeclared_block():
    with pytest.raises(FormatError, match="unexpected"):
        State.of([["A"], ["B"]]).validate(expected_blocks=["A"])


def test_rejects_exceeding_the_table_capacity():
    with pytest.raises(FormatError, match="capacity"):
        State.of([["A"], ["B"], ["C"]]).validate(table_capacity=2)


# -- instance ---------------------------------------------------------------


def test_completeness_bound_is_twice_the_block_count_on_a_free_table():
    inst = generate(6, seed=1).instance
    assert inst.table_capacity == 6
    assert inst.completeness_bound == 12


def test_no_completeness_bound_on_a_restricted_table():
    inst = generate(6, seed=1, table_capacity=3).instance
    assert inst.completeness_bound is None


def test_heuristic_is_zero_at_the_goal():
    inst = generate(5, seed=2).instance
    assert inst.heuristic(inst.goal) == 0


def test_heuristic_counts_misplaced_blocks():
    inst = Instance(
        "h", ("A", "B", "C"),
        State.of([["A"], ["B"], ["C"]]), State.of([["A", "B", "C"]]), 3,
    )
    # A already rests on the table as the goal requires; B and C do not.
    assert inst.heuristic(inst.initial) == 2


def test_heuristic_never_exceeds_the_true_distance():
    """Admissibility, checked against the independent oracle."""
    from reference import optimal_length

    for seed in range(6):
        inst = generate(4, seed=seed).instance
        true_distance = optimal_length(inst)
        if true_distance is not None:
            assert inst.heuristic(inst.initial) <= true_distance


def test_rejects_zero_capacity():
    with pytest.raises(FormatError, match="at least 1"):
        Instance("x", ("A",), State.of([["A"]]), State.of([["A"]]), 0).validate()


def test_rejects_duplicate_block_names():
    inst = Instance("x", ("A", "A"), State.of([["A"]]), State.of([["A"]]), 2)
    with pytest.raises(FormatError, match="unique"):
        inst.validate()


def test_structural_unsolvability_detects_a_block_mismatch():
    inst = Instance("x", ("A",), State.of([["A"]]), State.of([["A"]]), 2)
    object.__setattr__(inst, "goal", State.of([["B"]]))
    assert "different sets of blocks" in (inst.structurally_unsolvable() or "")


def test_structural_unsolvability_returns_none_for_a_sound_instance():
    assert generate(4, seed=3).instance.structurally_unsolvable() is None


# -- actions ----------------------------------------------------------------


def test_action_describes_unstacking():
    assert "unstack" in Action("A", "B", TABLE).describe()


def test_action_describes_picking_up():
    assert "pick up" in Action("A", TABLE, "B").describe()


def test_action_json_round_trip():
    action = Action("A", "B", TABLE)
    assert Action.from_json(action.to_json()) == action


def test_action_rejects_missing_keys():
    with pytest.raises(FormatError, match="missing keys"):
        Action.from_json({"block": "A"})


# -- serialisation ----------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_instance_json_round_trip(seed):
    original = generate(5, seed=seed).instance
    assert Instance.loads(original.dumps()) == original


def test_instance_rejects_an_unknown_format():
    doc = json.loads(generate(3, seed=1).instance.dumps())
    doc["format"] = "nope"
    with pytest.raises(FormatError, match="expected format"):
        Instance.from_json(doc)


def test_instance_rejects_an_unknown_version():
    doc = json.loads(generate(3, seed=1).instance.dumps())
    doc["version"] = 99
    with pytest.raises(FormatError, match="unsupported instance version"):
        Instance.from_json(doc)


def test_plan_json_round_trip():
    plan = Plan("x", "sat", (Action("A", TABLE, "B"),), "z3", {"nodes": 1})
    assert Plan.loads(plan.dumps()).actions == plan.actions


def test_plan_rejects_a_mismatched_declared_length():
    doc = {
        "format": "blocksworld-plan",
        "version": 1,
        "instance_id": "x",
        "status": "sat",
        "length": 5,
        "actions": [{"block": "A", "from": "table", "to": "B"}],
    }
    with pytest.raises(FormatError, match="declares length 5"):
        Plan.from_json(doc)


def test_plan_explain_narrates_each_move():
    plan = Plan("x", "sat", (Action("A", TABLE, "B"), Action("C", "D", TABLE)))
    lines = plan.explain()
    assert len(lines) == 2
    assert lines[0].startswith("1.") and lines[1].startswith("2.")


def test_plan_explain_handles_a_failed_plan():
    assert "limit" in Plan("x", "limit", ()).explain()[0]
