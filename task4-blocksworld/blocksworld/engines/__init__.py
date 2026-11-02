"""Planning engines. Each implements the interface in :mod:`.base`."""

from .base import Engine, EngineUnavailable, PlanResult

__all__ = ["Engine", "EngineUnavailable", "PlanResult", "get_engine", "ENGINES"]

ENGINES = ("prolog", "z3")


def get_engine(name: str, **kwargs) -> Engine:
    """Return a backend by name.

    Imported lazily so that a missing toolchain for one engine never prevents
    the other from being used. This never substitutes one engine for another.
    """
    key = name.lower()
    if key == "z3":
        from .z3_engine import Z3Engine

        return Z3Engine()
    if key == "prolog":
        from .prolog_engine import PrologEngine

        return PrologEngine(**kwargs)
    raise ValueError(f"unknown engine {name!r}; choose from {ENGINES}")
