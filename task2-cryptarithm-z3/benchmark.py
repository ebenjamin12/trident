#!/usr/bin/env python3
"""Benchmark the Z3 SMT backend against the brute-force fallback.

Both engines are imported from CryptarithmSolver and run on the same nine
puzzles used by the project's test suite. The script reports wall-clock time
for each engine and checks that the two agree on whether a solution exists.

Usage:  python3 benchmark.py
"""
import contextlib
import io
import sys
import time

# Importing the solver prints its dictionary banner; suppress it so the
# benchmark table is the only output.
with contextlib.redirect_stdout(io.StringIO()):
    from CryptarithmSolver import solve_z3, solve_brute_force

PUZZLES = [
    ("SEND+MORE=MONEY",    "SEND",  "MORE",  "MONEY"),
    ("TWO+TWO=FOUR",       "TWO",   "TWO",   "FOUR"),
    ("CROSS+ROADS=DANGER", "CROSS", "ROADS", "DANGER"),
    ("A+B=C",              "A",     "B",     "C"),
    ("AA+B=AC",            "AA",    "B",     "AC"),
    ("ABCD+EFGH=IJKL",     "ABCD",  "EFGH",  "IJKL"),
    ("ONE+ONE=MANY",       "ONE",   "ONE",   "MANY"),
    ("SIX+TEN=SIX",        "SIX",   "TEN",   "SIX"),
    ("ART+ART=CART",       "ART",   "ART",   "CART"),
]


def timed(fn, *args, reps=3):
    """Return (best wall-clock seconds, result)."""
    best, result = float("inf"), None
    for _ in range(reps):
        start = time.perf_counter()
        result = fn(*args)
        best = min(best, time.perf_counter() - start)
    return best, result


def main():
    # Warm up: the first Z3 call pays one-off initialisation cost.
    solve_z3("SEND", "MORE", "MONEY")

    print(f"{'Puzzle':<20} {'Letters':>7} {'Z3':>10} {'Brute':>12} {'Speedup':>9}  Result")
    print("-" * 76)

    total_z3 = total_bf = 0.0
    all_agree = True

    for name, w1, w2, w3 in PUZZLES:
        letters = len(set(w1 + w2 + w3))
        t_z3, r_z3 = timed(solve_z3, w1, w2, w3)
        t_bf, r_bf = timed(solve_brute_force, w1, w2, w3, reps=1)

        agree = (r_z3 is None) == (r_bf is None)
        all_agree &= agree
        total_z3 += t_z3
        total_bf += t_bf

        speedup = t_bf / t_z3 if t_z3 > 0 else 0.0
        status = "solved" if r_z3 else "no solution"
        flag = "" if agree else "  <-- ENGINES DISAGREE"
        print(f"{name:<20} {letters:>7} {t_z3*1000:>9.2f}ms {t_bf*1000:>11.2f}ms "
              f"{speedup:>8.1f}x  {status}{flag}")

    print("-" * 76)
    ratio = total_bf / total_z3 if total_z3 > 0 else 0.0
    print(f"{'TOTAL':<20} {'':>7} {total_z3*1000:>9.2f}ms {total_bf*1000:>11.2f}ms {ratio:>8.1f}x")
    print(f"\nAll engines agree: {all_agree}")
    print(f"Python {sys.version.split()[0]}")

    try:
        import z3
        print(f"Z3 {z3.get_version_string()}")
    except ImportError:
        print("Z3 not installed - brute-force fallback only")

    return 0 if all_agree else 1


if __name__ == "__main__":
    sys.exit(main())
