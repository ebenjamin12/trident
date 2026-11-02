"""Common interface shared by every TetraVex solver backend.

Every engine answers the same two questions about an instance:

``solve``
    Find one layout, or report that none exists.
``solve_unique``
    Find one layout and additionally say whether a *second, visually
    different* one exists.

Uniqueness is defined up to permutation of identical tiles: if two tiles carry
the same four edge symbols, swapping them produces the same picture and is not
counted as a distinct solution. Engines implement this by constraining
identical tiles into a fixed cell order (see ``Instance.duplicate_groups``).

Note the limitation in rotation mode: tiles that are *rotations* of one another
are not treated as identical, so a puzzle whose only extra solutions come from
that symmetry is reported as non-unique. This is documented in the README.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..model import Instance, Solution


class SolverUnavailable(RuntimeError):
    """Raised when a backend's toolchain is not installed."""


@dataclass(frozen=True, slots=True)
class SolveResult:
    """What a backend reports for one instance.

    ``status`` is one of:

    ``sat``
        A solution was found; ``solution`` holds it.
    ``unsat``
        The instance was proved to have no solution.
    ``unknown``
        The engine gave up, usually because of ``timeout``.
    """

    status: str
    solution: Solution | None = None
    unique: bool | None = None
    second_solution: Solution | None = None
    elapsed: float = 0.0
    engine: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def sat(self) -> bool:
        return self.status == "sat"


class Solver:
    """Base class for solver backends."""

    name: str = "base"

    def available(self) -> bool:
        """Whether this backend's toolchain can be used right now."""
        raise NotImplementedError

    def version(self) -> str:
        """Human-readable version string for the underlying engine."""
        raise NotImplementedError

    def solve(
        self, instance: Instance, *, timeout: float | None = None
    ) -> SolveResult:
        raise NotImplementedError

    def solve_unique(
        self, instance: Instance, *, timeout: float | None = None
    ) -> SolveResult:
        raise NotImplementedError
