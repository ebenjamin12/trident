"""Generator: determinism, validity, capacity handling, walk mode."""

from __future__ import annotations

import pytest
from blocksworld.generator import block_names, generate
from reference import optimal_length


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 13])
def test_generated_instances_are_valid(n):
    generate(n, seed=n).instance.validate()


def test_same_seed_is_reproducible():
    a = generate(7, seed=123)
    b = generate(7, seed=123)
    assert a.instance.dumps() == b.instance.dumps()


def test_different_seeds_differ():
    a = generate(7, seed=1).instance.dumps()
    b = generate(7, seed=2).instance.dumps()
    assert a != b


def test_walk_mode_is_reproducible():
    a = generate(6, seed=5, walk=8)
    b = generate(6, seed=5, walk=8)
    assert a.instance.dumps() == b.instance.dumps()
    assert a.walk_length == b.walk_length


def test_block_names_are_stable_and_unique():
    names = block_names(30)
    assert len(set(names)) == 30
    assert names[:3] == ("A", "B", "C")
    assert names[26] == "A1"


def test_instance_id_encodes_its_parameters():
    inst = generate(4, seed=9, table_capacity=2).instance
    assert inst.id == "bw-4b-c2-partition-seed9"


def test_walk_mode_id_records_the_walk():
    inst = generate(4, seed=9, walk=5).instance
    assert "walk5" in inst.id


def test_capacity_defaults_to_the_block_count():
    assert generate(6, seed=1).instance.table_capacity == 6


def test_states_respect_a_restricted_capacity():
    inst = generate(6, seed=4, table_capacity=2).instance
    assert inst.initial.n_stacks <= 2
    assert inst.goal.n_stacks <= 2


def test_max_stacks_limits_the_spread():
    inst = generate(8, seed=3, max_stacks=2).instance
    assert inst.initial.n_stacks <= 2
    assert inst.goal.n_stacks <= 2


def test_walk_mode_bounds_the_optimum():
    """A goal reached in K random moves needs at most K moves to reach."""
    for seed in range(4):
        problem = generate(4, seed=seed, walk=5)
        distance = optimal_length(problem.instance)
        assert distance is not None
        assert distance <= problem.walk_length


def test_walk_of_zero_leaves_the_goal_equal_to_the_initial_state():
    problem = generate(5, seed=2, walk=0)
    assert problem.instance.goal == problem.instance.initial
    assert optimal_length(problem.instance) == 0


def test_walk_reports_fewer_moves_when_the_state_dead_ends():
    """On a one-slot table nothing can move, so the walk takes zero steps."""
    problem = generate(3, seed=1, table_capacity=1, walk=5)
    assert problem.walk_length == 0


def test_rejects_zero_blocks():
    with pytest.raises(ValueError, match="at least one block"):
        block_names(0)
    with pytest.raises(ValueError, match="at least 1"):
        generate(0)


def test_rejects_a_negative_walk():
    with pytest.raises(ValueError, match="must not be negative"):
        generate(3, walk=-1)


def test_rejects_zero_capacity():
    with pytest.raises(ValueError, match="at least 1"):
        generate(3, table_capacity=0)


def test_single_block_instance_is_trivially_valid():
    problem = generate(1, seed=0)
    assert problem.instance.n_blocks == 1
    assert optimal_length(problem.instance) == 0
