"""Common interface shared by every Blocks World planning engine.

Mirrors the structure of ``tetravex/solvers/base.py`` so the two problems read
the same way.

Every engine answers one question: *what is a shortest plan from the initial
state to the goal?* Engines must either return an optimal plan or say clearly
why they could not, and the distinction between the three failure modes
matters:

``unsat``
    Proved that no plan exists. An engine may only claim this when it can
    justify it -- for Z3 that means searching up to a horizon at least as
    large as the domain's completeness bound; for Prolog it means exhausting
    the reachable state space.
``limit``
    Hit a depth or horizon ceiling with no answer. Says nothing about whether
    a plan exists.
``unknown``
    Timed out or failed.

Collapsing ``limit`` into ``unsat`` would turn "I gave up" into "impossible",
which is the single easiest way for a planner to lie.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..model import Instance, Plan


class EngineUnavailable(RuntimeError):
    """Raised when an engine's toolchain is not installed.

    Engines raise this rather than silently handing the problem to a different
    engine: a benchmark that quietly swapped backends would be worthless.
    """


@dataclass(frozen=True, slots=True)
class PlanResult:
    """What an engine reports for one instance."""

    plan: Plan
    elapsed: float = 0.0
    engine: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return self.plan.status

    @property
    def sat(self) -> bool:
        return self.plan.sat

    @property
    def length(self) -> int | None:
        return self.plan.length if self.plan.sat else None


class Engine:
    """Base class for planning backends."""

    name: str = "base"

    def available(self) -> bool:
        """Whether this engine's toolchain can be used right now."""
        raise NotImplementedError

    def version(self) -> str:
        """Human-readable version string for the underlying toolchain."""
        raise NotImplementedError

    def plan(
        self,
        instance: Instance,
        *,
        timeout: float | None = None,
        max_depth: int | None = None,
    ) -> PlanResult:
        """Return a shortest plan, or a non-``sat`` result explaining why not.

        ``max_depth`` bounds the search (plan length for symbolic search,
        horizon for SAT planning). When omitted, engines use the instance's
        :attr:`~blocksworld.model.Instance.completeness_bound` if one exists,
        which is what lets a failure be reported as ``unsat`` rather than
        ``limit``.
        """
        raise NotImplementedError
