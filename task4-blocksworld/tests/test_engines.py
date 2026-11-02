"""Planning engines: correctness, optimality, unsolvability, agreement.

Layers of evidence, weakest to strongest:

1. Every returned plan passes independent verification.
2. Every returned plan length matches a hand-computed expectation.
3. Every returned plan length matches the independent BFS oracle in
   ``tests/reference.py``.
4. Asking the engine to beat its own answer by one move fails, so the plan is
   not merely valid but minimal.
5. The engines agree with each other.

Point 5 is deliberately last. Two engines written by the same author can share
a misreading of the domain, so agreement between them is corroboration, not
proof. Points 2 and 3 are what make this suite independent.
"""

from __future__ import annotations

import pytest
from blocksworld.engines import get_engine
from blocksworld.engines.prolog_engine import STRATEGIES
from blocksworld.generator import generate
from blocksworld.model import Instance, State
from blocksworld.verify import verify
from reference import optimal_length

ENGINES = ("prolog", "z3")


def _engine_or_skip(name: str, **kwargs):
    engine = get_engine(name, **kwargs)
    if not engine.available():
        pytest.skip(f"{name} toolchain not available in this environment")
    return engine


# --------------------------------------------------------------------------
# hand-constructed cases with independently known optima
# --------------------------------------------------------------------------

#: (label, instance, optimal length) -- every optimum here was worked out by
#: hand and then confirmed against the BFS oracle in test_reference_oracle.
KNOWN: list[tuple[str, Instance, int]] = [
    (
        "goal already holds",
        Instance("k0", ("A", "B"), State.of([["A", "B"]]), State.of([["A", "B"]]), 2),
        0,
    ),
    (
        "one move",
        Instance("k1", ("A", "B"), State.of([["A"], ["B"]]), State.of([["A", "B"]]), 2),
        1,
    ),
    (
        "invert a pair",
        Instance("k2", ("A", "B"), State.of([["A", "B"]]), State.of([["B", "A"]]), 2),
        2,
    ),
    (
        "three singles into a tower",
        Instance(
            "k3", ("A", "B", "C"),
            State.of([["A"], ["B"], ["C"]]), State.of([["A", "B", "C"]]), 3,
        ),
        2,
    ),
    (
        "sussman anomaly",
        Instance(
            "k4", ("A", "B", "C"),
            State.of([["C", "A"], ["B"]]), State.of([["A", "B", "C"]]), 3,
        ),
        3,
    ),
    (
        "invert a four-tower",
        Instance(
            "k5", tuple("ABCD"),
            State.of([["A", "B", "C", "D"]]), State.of([["D", "C", "B", "A"]]), 4,
        ),
        4,
    ),
    (
        "invert a three-tower on a two-slot table",
        Instance(
            "k6", ("A", "B", "C"),
            State.of([["A", "B", "C"]]), State.of([["C", "B", "A"]]), 2,
        ),
        3,
    ),
]

#: No plan exists: one stack is allowed, so nothing can ever be unstacked.
UNSOLVABLE = Instance(
    "u1", ("A", "B", "C"),
    State.of([["A", "B", "C"]]), State.of([["C", "B", "A"]]), 1,
)


@pytest.mark.parametrize("label,instance,expected", KNOWN, ids=[k[0] for k in KNOWN])
def test_reference_oracle_matches_hand_computed_optimum(label, instance, expected):
    """The oracle itself is checked before anything is checked against it."""
    assert optimal_length(instance) == expected


def test_reference_oracle_reports_unsolvable():
    assert optimal_length(UNSOLVABLE) is None


# --------------------------------------------------------------------------
# correctness against known optima
# --------------------------------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("label,instance,expected", KNOWN, ids=[k[0] for k in KNOWN])
def test_engine_finds_the_known_optimum(engine_name, label, instance, expected):
    engine = _engine_or_skip(engine_name)
    result = engine.plan(instance, timeout=120)
    assert result.status == "sat", f"{engine_name} returned {result.status}"
    report = verify(instance, result.plan)
    assert report.ok, report.summary
    assert result.plan.length == expected


@pytest.mark.parametrize("engine_name", ENGINES)
def test_zero_move_plan_has_no_actions(engine_name):
    engine = _engine_or_skip(engine_name)
    instance = KNOWN[0][1]
    result = engine.plan(instance, timeout=60)
    assert result.plan.actions == ()
    assert "already holds" in " ".join(result.plan.explain())


# --------------------------------------------------------------------------
# optimality: the engine cannot do better than its own answer
# --------------------------------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize(
    "label,instance,expected",
    [k for k in KNOWN if k[2] > 0],
    ids=[k[0] for k in KNOWN if k[2] > 0],
)
def test_no_shorter_plan_exists(engine_name, label, instance, expected):
    """Capping the search one move below the optimum must find nothing."""
    engine = _engine_or_skip(engine_name)
    result = engine.plan(instance, timeout=120, max_depth=expected - 1)
    assert not result.plan.sat, (
        f"{engine_name} found a {result.plan.length}-move plan when the "
        f"optimum is {expected}"
    )


# --------------------------------------------------------------------------
# unsolvable instances
# --------------------------------------------------------------------------


def test_prolog_bfs_proves_unsolvability():
    engine = _engine_or_skip("prolog", strategy="bfs")
    result = engine.plan(UNSOLVABLE, timeout=120)
    assert result.status == "unsat"
    assert result.stats.get("proof") == "state-space-exhausted"


@pytest.mark.parametrize("engine_name", ENGINES)
def test_bounded_search_reports_limit_not_unsat(engine_name):
    """Without a sound bound, failure must not be dressed up as a proof.

    The restricted table removes the ``2n`` completeness argument, so neither
    the horizon sweep nor the depth-bounded search may claim unsatisfiability.
    """
    engine = _engine_or_skip(engine_name)
    result = engine.plan(UNSOLVABLE, timeout=120)
    assert result.status == "limit"
    assert UNSOLVABLE.completeness_bound is None


@pytest.mark.parametrize("engine_name", ENGINES)
def test_structurally_unsolvable_is_detected_without_search(engine_name):
    """Mismatched block sets need no search to rule out."""
    engine = _engine_or_skip(engine_name)
    bad = Instance(
        "mismatch", ("A", "B"),
        State.of([["A"], ["B"]]), State.of([["A"], ["B"]]), 2,
    )
    # Hand-build a goal referencing a block the initial state lacks by going
    # around validate(), which would otherwise reject the instance.
    object.__setattr__(bad, "goal", State.of([["A"]]))
    result = engine.plan(bad, timeout=30)
    assert result.status == "unsat"
    assert result.stats.get("proof") == "structural"


@pytest.mark.parametrize("engine_name", ENGINES)
def test_goal_needing_more_slots_than_the_table_has(engine_name):
    engine = _engine_or_skip(engine_name)
    instance = Instance(
        "tight", ("A", "B"), State.of([["A", "B"]]), State.of([["A", "B"]]), 1
    )
    object.__setattr__(instance, "goal", State.of([["A"], ["B"]]))
    result = engine.plan(instance, timeout=30)
    assert result.status == "unsat"


# --------------------------------------------------------------------------
# Prolog strategies must agree with each other
# --------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize(
    "label,instance,expected",
    KNOWN[:5],
    ids=[k[0] for k in KNOWN[:5]],
)
def test_every_prolog_strategy_is_optimal(strategy, label, instance, expected):
    """IDA* must not beat or lose to unguided iterative deepening.

    If the heuristic were inadmissible, IDA* would prune an optimal branch and
    return something longer than iddfs. This is the test that would catch it.
    """
    engine = _engine_or_skip("prolog", strategy=strategy)
    result = engine.plan(instance, timeout=120)
    assert result.status == "sat"
    assert result.plan.length == expected
    assert verify(instance, result.plan).ok


# --------------------------------------------------------------------------
# agreement with the oracle on generated instances
# --------------------------------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_generated_instances_match_the_oracle(engine_name, seed):
    engine = _engine_or_skip(engine_name)
    problem = generate(4, seed=seed)
    expected = optimal_length(problem.instance)
    result = engine.plan(problem.instance, timeout=120)
    if expected is None:
        assert not result.plan.sat
        return
    assert result.status == "sat"
    assert verify(problem.instance, result.plan).ok
    assert result.plan.length == expected


def test_walk_mode_optimum_never_exceeds_the_walk_length():
    """A goal built with K random moves cannot need more than K to reach."""
    problem = generate(5, seed=7, walk=6)
    expected = optimal_length(problem.instance)
    assert expected is not None
    assert expected <= problem.walk_length


# --------------------------------------------------------------------------
# cross-engine agreement (corroboration, not proof)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_engines_agree_on_plan_length(seed):
    prolog = _engine_or_skip("prolog")
    z3 = _engine_or_skip("z3")
    problem = generate(5, seed=seed)
    a = prolog.plan(problem.instance, timeout=120)
    b = z3.plan(problem.instance, timeout=120)
    assert a.status == b.status
    if a.status == "sat":
        assert a.plan.length == b.plan.length
        assert verify(problem.instance, a.plan).ok
        assert verify(problem.instance, b.plan).ok


def test_engines_report_versions():
    for name in ENGINES:
        engine = _engine_or_skip(name)
        assert engine.version()
