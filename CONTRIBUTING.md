# Contributing to Trident

Trident is a comparative study: the same problem solved under different
paradigms, with the comparison itself as the deliverable. That shapes what a
useful contribution looks like, so it is worth reading the two sections below
before opening a pull request.

## The rules that are not stylistic

These exist because breaking them silently invalidates the project's results.

### 1. The verifier stays independent

`task3-tetravex/tetravex/verify.py` and
`task4-blocksworld/blocksworld/verify.py` must never import a solver or
planning engine, and must never reuse an engine's transition or constraint
code. They re-derive the rules from the domain specification alone.

A test in each problem parses the verifier's AST and fails if an engine module
appears among its imports. Do not relax that test. If a verifier and an engine
shared code, a bug in the shared part would be invisible: the engine would
produce a wrong answer and the verifier would cheerfully agree.

### 2. Nothing is reported as a success until it has been verified

Every CLI `solve` path runs the independent verifier before writing output and
exits non-zero if it fails, whichever engine produced the result. Benchmarks
record `verified` per measurement. Renderers refuse to draw an unverified plan.
Keep all three.

### 3. Engines never substitute for one another

If an engine's toolchain is missing it raises `SolverUnavailable` /
`EngineUnavailable`. It does not hand the problem to the other engine. A
benchmark that quietly swapped backends would be worthless, and a user who
asked for Prolog should not silently get Z3.

The Prolog *execution path* (native `swipl` vs. the `swipl-wasm` fallback) is
different — that is the same engine reached two ways, the Prolog source is
identical in both, and the path used is recorded in `stats.mode`.

### 4. Measurements are reported, not improved

Do not round, re-run until favourable, or quote a figure the code did not
produce. Benchmarks record medians with observed ranges, and the ranges exist
precisely so that a long tail stays visible — see the 8-block Blocks World row,
where one seed cost 67× another.

Search-effort columns are in each engine's own units (states expanded vs.
horizons attempted) and are deliberately **not** converted into a ratio. There
is no honest conversion.

### 5. `limit` is not `unsat`

An engine may report `unsat` only when it can justify it. "I searched to my
ceiling and found nothing" is `limit`. Collapsing the two is the easiest way
for a planner to lie, and the distinction is tested.

### 6. The duplicated transition logic is deliberate

Blocks World implements "apply an action to a state" five times — Prolog
clauses, SMT constraints, the verifier, a generator-local copy, and the test
oracle in `tests/reference.py`. Consolidating them would be the obvious
refactor and would destroy the project's main correctness argument. Each file
says so in its docstring; please leave them separate.

## Development

### Setup

```bash
pip install -r task3-tetravex/requirements.txt
pip install -r task4-blocksworld/requirements.txt
pipx install ruff            # lint only; not a runtime dependency
```

A Prolog toolchain is needed for the Prolog engines — either `swipl` on `PATH`
(preferred), or `npm ci` inside `task3-tetravex/tetravex/prolog/` and
`task4-blocksworld/blocksworld/prolog/` for the WASM fallback.

### The dispatcher's executable bit

`trident` must stay committed with git mode `100755`. The README documents
`./trident <problem> <command>` as the entry point, so a clone carrying
`100644` instead gives every user `Permission denied` on every documented
command, while the test suites still pass — they import the packages directly
and never go through the dispatcher.

The bit is easy to lose by rebuilding the tree from an archive extracted on a
filesystem without a Unix executable bit, or with `core.fileMode=false` set.
Restore it without touching file contents:

```bash
git update-index --chmod=+x trident
```

The `lint` job checks the committed mode, so a regression fails fast with the
remedy rather than as a bare exit 126 later on.

### Before opening a pull request

```bash
ruff check .
(cd task3-tetravex   && python -m pytest tests/ -q)
(cd task4-blocksworld && python -m pytest tests/ -q)
```

Both suites must pass with no skips on a machine that has both toolchains.
Solver tests *skip* rather than fail when a toolchain is absent, so a run with
skips means your environment is incomplete, not that the code is fine.

### Adding a test

Prefer a test whose expected value was derived independently of the code under
test. The strongest tests in this repository are the ones checking engine
output against hand-computed optima and against `tests/reference.py`; the
weakest is "the two engines agree", which is why it comes last in
`test_engines.py`.

### Coursework directories

`task1-haskell-cryptography/` and `task2-cryptarithm-z3/` are submitted
academic work, preserved as-is. Known defects in them are listed under *Known
limitations* in the root README rather than fixed, because the benchmark
figures published in that README were measured against exactly this code.
Please do not "tidy" them; open an issue instead.

## Commit messages and scope

One logical change per pull request. If a change alters a published number,
re-run the relevant benchmark and update the README table in the same commit,
so documentation and measurements never drift apart.
