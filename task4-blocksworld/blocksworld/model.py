"""Blocks World domain model and JSON serialisation.

This module is the single formal definition of the domain. The Prolog engine,
the Z3 engine, the verifier and the renderers all agree on what a state is and
what a legal action is because they all read this contract -- but note the
deliberate omission below.

What this module does NOT contain
---------------------------------
There is **no state-transition function here**. Applying an action to a state
is implemented three separate times, on purpose:

* ``blocksworld/prolog/blocksworld.pl``  -- as Prolog clauses
* ``blocksworld/engines/z3_engine.py``   -- as SMT constraints over time steps
* ``blocksworld/verify.py``              -- as plain Python

If the transition lived here, a mistake in it would be invisible: every engine
and the verifier would make the same mistake together and agree enthusiastically.
Keeping three independent implementations means a disagreement is a real signal.
``generator.py`` has a fourth, local copy for its random-walk mode, for the same
reason. This duplication is the point, not an oversight.

Domain definition
-----------------
A *state* is a set of stacks. Each stack is a sequence of distinct blocks
ordered bottom to top, resting on the table. Every block appears in exactly one
stack exactly once.

The table is **unordered**: two states are equal when they have the same
multiset of stacks. Sliding a stack to a different spot on the table is not a
move, so distinguishing table positions would invent moves that do not exist.
``table_capacity`` bounds how many stacks may exist at once, which is what
makes a finite table meaningful (and makes some instances genuinely
unsolvable).

An *action* is ``move(block, source, destination)``:

* ``block`` must be clear (nothing on top of it)
* ``block`` must currently rest on ``source``
* ``destination`` must be clear if it is a block, or the table must have a free
  slot if it is the table
* ``destination`` must differ from ``source`` and from ``block``

Every action costs 1. Plans are strictly sequential: no two actions happen at
the same time. The optimal plan is therefore the one with fewest moves, and a
plan's length is directly comparable across engines.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

FORMAT_INSTANCE = "blocksworld-instance"
FORMAT_PLAN = "blocksworld-plan"
FORMAT_VERSION = 1

#: Reserved destination name for the table surface. No block may be called this.
TABLE = "table"

_BLOCK_NAME = re.compile(r"^[A-Za-z0-9_]{1,16}$")


class FormatError(ValueError):
    """Raised when a document or structure violates the domain schema."""


# --------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------

#: A stack, bottom block first.
Stack = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class State:
    """A set of stacks. Construct via :meth:`of` to get canonical ordering."""

    stacks: tuple[Stack, ...]

    # -- construction ------------------------------------------------------

    @staticmethod
    def of(stacks: Iterable[Iterable[str]]) -> State:
        """Build a canonical state from any iterable of stacks.

        Empty stacks are dropped -- a table slot holding nothing is not a
        stack -- and the remainder are sorted so that equal states compare
        equal regardless of how they were written down.
        """
        cleaned = tuple(tuple(s) for s in stacks if tuple(s))
        return State(tuple(sorted(cleaned)))

    # -- observations ------------------------------------------------------

    @property
    def blocks(self) -> tuple[str, ...]:
        """Every block in the state, sorted."""
        return tuple(sorted(b for stack in self.stacks for b in stack))

    @property
    def n_stacks(self) -> int:
        return len(self.stacks)

    def supports(self) -> dict[str, str]:
        """Map each block to what it rests on: a block name, or :data:`TABLE`.

        This ``on`` relation is an equivalent encoding of the stacks and is
        what the engines and the heuristic work with.
        """
        out: dict[str, str] = {}
        for stack in self.stacks:
            below = TABLE
            for block in stack:
                out[block] = below
                below = block
        return out

    def clear_blocks(self) -> frozenset[str]:
        """Blocks with nothing on top of them."""
        return frozenset(stack[-1] for stack in self.stacks)

    def stack_of(self, block: str) -> Stack:
        for stack in self.stacks:
            if block in stack:
                return stack
        raise KeyError(f"block {block!r} is not in this state")

    def height_of(self, block: str) -> int:
        """0 for a block on the table, 1 for the block above it, and so on."""
        return self.stack_of(block).index(block)

    # -- validity ----------------------------------------------------------

    def validate(self, *, expected_blocks: Iterable[str] | None = None,
                 table_capacity: int | None = None) -> None:
        """Raise :class:`FormatError` if this is not a physically legal state."""
        seen: set[str] = set()
        for stack in self.stacks:
            if not stack:
                raise FormatError("state contains an empty stack")
            for block in stack:
                if block == TABLE:
                    raise FormatError(f"{TABLE!r} is reserved and cannot be a block")
                if not _BLOCK_NAME.match(block):
                    raise FormatError(
                        f"block name {block!r} must match {_BLOCK_NAME.pattern}"
                    )
                if block in seen:
                    # A block in two places would mean it supports two stacks
                    # at once, or is its own ancestor.
                    raise FormatError(f"block {block!r} appears more than once")
                seen.add(block)
        if expected_blocks is not None:
            expected = set(expected_blocks)
            if seen != expected:
                missing = sorted(expected - seen)
                extra = sorted(seen - expected)
                raise FormatError(
                    "state does not cover the declared blocks"
                    + (f"; missing {missing}" if missing else "")
                    + (f"; unexpected {extra}" if extra else "")
                )
        if table_capacity is not None and self.n_stacks > table_capacity:
            raise FormatError(
                f"state uses {self.n_stacks} table slots but capacity is "
                f"{table_capacity}"
            )

    # -- serialisation -----------------------------------------------------

    def to_json(self) -> list[list[str]]:
        return [list(stack) for stack in self.stacks]

    @staticmethod
    def from_json(raw: Any) -> State:
        if not isinstance(raw, list):
            raise FormatError("a state must be a list of stacks")
        for stack in raw:
            if not isinstance(stack, list) or not all(
                isinstance(b, str) for b in stack
            ):
                raise FormatError("each stack must be a list of block names")
        return State.of(raw)

    def __str__(self) -> str:  # pragma: no cover - diagnostics only
        return " | ".join("-".join(s) for s in self.stacks) or "(empty)"


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Action:
    """``move(block, source -> destination)``. Cost 1."""

    block: str
    source: str
    destination: str

    def describe(self) -> str:
        """One line of plain English, used by ``--explain`` and the renderers."""
        if self.source == TABLE and self.destination == TABLE:
            return f"move {self.block} on the table"  # pragma: no cover - illegal
        if self.source == TABLE:
            return f"pick up {self.block} from the table and stack it on {self.destination}"
        if self.destination == TABLE:
            return f"unstack {self.block} from {self.source} and put it on the table"
        return f"unstack {self.block} from {self.source} and stack it on {self.destination}"

    def to_json(self) -> dict[str, str]:
        return {"block": self.block, "from": self.source, "to": self.destination}

    @staticmethod
    def from_json(raw: Any) -> Action:
        if not isinstance(raw, dict):
            raise FormatError("an action must be an object")
        missing = {"block", "from", "to"} - raw.keys()
        if missing:
            raise FormatError(f"action is missing keys: {sorted(missing)}")
        for key in ("block", "from", "to"):
            if not isinstance(raw[key], str):
                raise FormatError(f"action field {key!r} must be a string")
        return Action(raw["block"], raw["from"], raw["to"])

    def __str__(self) -> str:  # pragma: no cover - diagnostics only
        return f"move({self.block}, {self.source} -> {self.destination})"


# --------------------------------------------------------------------------
# Instances
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Instance:
    """A planning problem: get from ``initial`` to ``goal``."""

    id: str
    blocks: tuple[str, ...]
    initial: State
    goal: State
    table_capacity: int
    seed: int | None = None
    generator: str | None = None

    # -- derived -----------------------------------------------------------

    @property
    def n_blocks(self) -> int:
        return len(self.blocks)

    @property
    def completeness_bound(self) -> int | None:
        """A horizon beyond which failure proves unsolvability, or ``None``.

        When the table can hold every block at once, any instance is solvable
        in at most ``2n`` moves: move every block to the table (at most ``n``
        moves, since each block is moved at most once), then build the goal
        bottom-up (again at most ``n``). So if no plan of length ``2n`` exists,
        none exists at all.

        With a restricted table this argument breaks down -- the dismantling
        phase may not have anywhere to put things -- so no sound bound is
        offered and exhausting a search limit proves nothing.
        """
        if self.table_capacity >= self.n_blocks:
            return 2 * self.n_blocks
        return None

    def heuristic(self, state: State) -> int:
        """Admissible lower bound on moves remaining from ``state``.

        Counts blocks resting on something other than what the goal requires.
        A single move changes the support of exactly one block -- the one being
        moved -- so it can reduce this count by at most one. The count is
        therefore never greater than the true remaining distance, which is what
        admissibility requires.
        """
        goal_supports = self.goal.supports()
        return sum(
            1
            for block, support in state.supports().items()
            if goal_supports.get(block) != support
        )

    # -- validation --------------------------------------------------------

    def validate(self) -> None:
        if self.n_blocks == 0:
            raise FormatError("an instance must declare at least one block")
        if len(set(self.blocks)) != self.n_blocks:
            raise FormatError("block names must be unique")
        if self.table_capacity < 1:
            raise FormatError("table_capacity must be at least 1")
        self.initial.validate(
            expected_blocks=self.blocks, table_capacity=self.table_capacity
        )
        self.goal.validate(
            expected_blocks=self.blocks, table_capacity=self.table_capacity
        )

    def structurally_unsolvable(self) -> str | None:
        """A reason this instance admits no plan, found without searching.

        Returns ``None`` when no cheap proof is available -- which is not a
        claim that the instance is solvable.
        """
        if set(self.initial.blocks) != set(self.goal.blocks):
            return "initial and goal states describe different sets of blocks"
        if self.goal.n_stacks > self.table_capacity:
            return (
                f"goal needs {self.goal.n_stacks} table slots "
                f"but capacity is {self.table_capacity}"
            )
        return None

    # -- serialisation -----------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "format": FORMAT_INSTANCE,
            "version": FORMAT_VERSION,
            "id": self.id,
            "blocks": list(self.blocks),
            "initial": self.initial.to_json(),
            "goal": self.goal.to_json(),
            "table_capacity": self.table_capacity,
        }
        if self.seed is not None:
            doc["seed"] = self.seed
        if self.generator is not None:
            doc["generator"] = self.generator
        return doc

    def dumps(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_json(), indent=indent)

    @staticmethod
    def from_json(raw: Any) -> Instance:
        if not isinstance(raw, dict):
            raise FormatError("instance document must be a JSON object")
        if raw.get("format") != FORMAT_INSTANCE:
            raise FormatError(
                f"expected format {FORMAT_INSTANCE!r}, got {raw.get('format')!r}"
            )
        if raw.get("version") != FORMAT_VERSION:
            raise FormatError(f"unsupported instance version {raw.get('version')!r}")
        for key in ("id", "blocks", "initial", "goal", "table_capacity"):
            if key not in raw:
                raise FormatError(f"instance is missing required key {key!r}")
        if not isinstance(raw["blocks"], list) or not all(
            isinstance(b, str) for b in raw["blocks"]
        ):
            raise FormatError("instance.blocks must be a list of strings")
        capacity = raw["table_capacity"]
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise FormatError("instance.table_capacity must be an int")
        inst = Instance(
            id=str(raw["id"]),
            blocks=tuple(raw["blocks"]),
            initial=State.from_json(raw["initial"]),
            goal=State.from_json(raw["goal"]),
            table_capacity=capacity,
            seed=raw.get("seed"),
            generator=raw.get("generator"),
        )
        inst.validate()
        return inst

    @staticmethod
    def loads(text: str) -> Instance:
        return Instance.from_json(json.loads(text))


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Plan:
    """An ordered action sequence, plus how the engine arrived at it.

    ``status`` is one of:

    ``sat``
        ``actions`` is a plan reaching the goal.
    ``unsat``
        No plan exists. Engines only report this when they can justify it.
    ``limit``
        The engine reached its depth or horizon limit without an answer. This
        is *not* a proof of unsolvability and is kept distinct from it.
    ``unknown``
        The engine timed out or failed for another reason.
    """

    instance_id: str
    status: str
    actions: tuple[Action, ...] = ()
    engine: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.actions)

    @property
    def sat(self) -> bool:
        return self.status == "sat"

    def explain(self) -> list[str]:
        """Numbered plain-English narration of the plan."""
        if not self.sat:
            return [f"no plan ({self.status})"]
        if not self.actions:
            return ["the goal already holds in the initial state; no moves needed"]
        return [
            f"{i}. {action.describe()}"
            for i, action in enumerate(self.actions, start=1)
        ]

    def to_json(self) -> dict[str, Any]:
        return {
            "format": FORMAT_PLAN,
            "version": FORMAT_VERSION,
            "instance_id": self.instance_id,
            "engine": self.engine,
            "status": self.status,
            "length": self.length,
            "actions": [a.to_json() for a in self.actions],
            "stats": self.stats,
        }

    def dumps(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_json(), indent=indent)

    @staticmethod
    def from_json(raw: Any) -> Plan:
        if not isinstance(raw, dict):
            raise FormatError("plan document must be a JSON object")
        if raw.get("format") != FORMAT_PLAN:
            raise FormatError(
                f"expected format {FORMAT_PLAN!r}, got {raw.get('format')!r}"
            )
        if raw.get("version") != FORMAT_VERSION:
            raise FormatError(f"unsupported plan version {raw.get('version')!r}")
        actions_raw = raw.get("actions", [])
        if not isinstance(actions_raw, list):
            raise FormatError("plan.actions must be a list")
        plan = Plan(
            instance_id=str(raw.get("instance_id", "")),
            status=str(raw.get("status", "unknown")),
            actions=tuple(Action.from_json(a) for a in actions_raw),
            engine=raw.get("engine"),
            stats=raw.get("stats") or {},
        )
        declared = raw.get("length")
        if declared is not None and declared != plan.length:
            raise FormatError(
                f"plan declares length {declared} but carries {plan.length} actions"
            )
        return plan

    @staticmethod
    def loads(text: str) -> Plan:
        return Plan.from_json(json.loads(text))
