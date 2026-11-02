"""Solver backends. Each implements the interface in :mod:`.base`."""

from .base import Solver, SolveResult, SolverUnavailable

__all__ = ["SolveResult", "Solver", "SolverUnavailable", "get_solver", "ENGINES"]

ENGINES = ("z3", "prolog")


def get_solver(name: str) -> Solver:
    """Return a backend by name. Imported lazily so a missing toolchain for
    one engine never stops the other from being used."""
    key = name.lower()
    if key == "z3":
        from .z3_solver import Z3Solver

        return Z3Solver()
    if key == "prolog":
        from .prolog_solver import PrologSolver

        return PrologSolver()
    raise ValueError(f"unknown engine {name!r}; choose from {ENGINES}")
