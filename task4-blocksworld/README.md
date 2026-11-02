# Blocks World — Prolog symbolic search vs. Z3 planning-as-SAT

The same planning problem solved two completely different ways: **SWI-Prolog**
searching the state space with an admissible heuristic, and **Z3** asserting
"there is a plan of exactly *T* steps" and incrementing *T* until the solver
finds a model.

Both read the same problem file, both guarantee optimality under the same
unit-cost model, both are checked by the same independent verifier, and both
are measured on the same instances.

```
INITIAL                          GOAL
      ┌───┐                      ┌───┐
      │ A │                      │ C │
┌───┐ ├───┤                      ├───┤
│ B │ │ C │                      │ B │
─┴───┴─┴───┴─                    ├───┤
                                 │ A │
                                ─┴───┴─
```

That is the **Sussman anomaly**, the classic case that defeats naive
subgoal-ordering planners. Both engines return the optimal three-move plan.

---

## The domain

A state is a set of stacks; each stack is a sequence of distinct blocks resting
on the table. An action is `move(block, source, destination)` costing 1:

* `block` must be clear
* `block` must currently rest on `source`
* `destination` must be clear if it is a block, or the table must have a free
  slot if it is the table
* `destination` must differ from `source` and from `block`

Two decisions worth stating explicitly:

**The table is unordered.** Two states are equal when they have the same
multiset of stacks. Sliding a stack to a different spot on the table is not a
move, so distinguishing table positions would invent actions the domain does
not have. The canonical form (stacks sorted) is what makes cycle detection and
goal testing a matter of term equality.

**`table_capacity` bounds how many stacks may exist at once.** This is what
makes a finite table meaningful, and it is the only way an instance becomes
genuinely unsolvable — with an unrestricted table every instance is solvable in
at most `2n` moves.

**Goals are complete configurations.** The final state must equal the goal
exactly, not merely satisfy a set of `on` constraints. Partial goals are a
documented limitation, not an oversight.

---

## Installation

Python 3.10+ required.

```bash
cd task4-blocksworld
pip install -r requirements.txt       # z3-solver, pillow (optional), pytest
```

For the Prolog engine, **either** install SWI-Prolog so `swipl` is on `PATH`
(preferred — faster, no extra files):

```bash
sudo apt install swi-prolog-nox     # Debian/Ubuntu
brew install swi-prolog             # macOS
```

**or** use the bundled WASM fallback:

```bash
cd blocksworld/prolog && npm ci          # swipl-wasm, needs Node 18+
```

```bash
python3 -m blocksworld engines
```

```
prolog   available   SWI-Prolog via swipl-wasm 3.8.2  [mode: wasm]
z3       available   Z3 5.3.3
```

The Prolog **source is identical** in both modes; only the invocation differs,
and `stats.mode` records which was used. If no Prolog toolchain exists the
engine raises rather than quietly handing the problem to Z3.

---

## Usage

Either `python3 -m blocksworld <cmd>`, or the repository-level front-end:

```bash
./trident blocks <cmd>        # same commands, one entry point for all problems
```

### Generate

```bash
# a reproducible 8-block problem
python3 -m blocksworld generate --blocks 8 --seed 42 -o problem.json

# tall stacks make genuinely hard instances (see Benchmarks)
python3 -m blocksworld generate --blocks 8 --seed 42 --max-stacks 2 -o problem.json

# a goal reached by 10 random moves, so the optimum is at most 10
python3 -m blocksworld generate --blocks 6 --seed 1 --walk 10 -o problem.json

# a restricted table, where instances can be unsolvable
python3 -m blocksworld generate --blocks 5 --seed 1 --capacity 2 -o problem.json
```

### Solve

```bash
python3 -m blocksworld solve problem.json --engine prolog -o plan.json
python3 -m blocksworld solve problem.json --engine z3     -o plan.json

# Prolog search strategies
python3 -m blocksworld solve problem.json --engine prolog --strategy idastar   # default
python3 -m blocksworld solve problem.json --engine prolog --strategy iddfs     # unguided
python3 -m blocksworld solve problem.json --engine prolog --strategy bfs       # proves unsat

# narrate the plan, and draw every intermediate state
python3 -m blocksworld solve problem.json --engine prolog --explain --ascii -o plan.json
```

```
1. unstack A from C and put it on the table
2. pick up B from the table and stack it on A
3. pick up C from the table and stack it on B
```

Exit codes: `0` solved or proved unsolvable, `1` gave up (`limit`/`unknown`),
`2` engine unavailable, `3` the engine produced a plan the verifier rejected.
That last one matters — **the CLI will not emit a plan that fails independent
verification**, whichever engine produced it.

### Verify

```bash
python3 -m blocksworld verify problem.json plan.json
python3 -m blocksworld verify problem.json plan.json --optimal 9
```

```
VALID - goal reached in 9 legal move(s)
```

or, on a tampered plan:

```
INVALID - 1 violation(s) across 1 category/categories: action
  [action] step 2: block 'B' is not clear; 'C' rests on it
```

### Render

```bash
python3 -m blocksworld render problem.json                                  # ascii
python3 -m blocksworld render problem.json --solution plan.json --format ascii
python3 -m blocksworld render problem.json --solution plan.json --format filmstrip   -o plan.svg
python3 -m blocksworld render problem.json --solution plan.json --format animated-svg -o plan.svg
python3 -m blocksworld render problem.json --solution plan.json --format gif          -o plan.gif
```

`animated-svg` has **no dependencies** — it is an SMIL animation that plays in
any browser. `gif` needs Pillow. Renderers refuse to draw a plan that has not
passed verification: a picture of an impossible plan is worse than no picture.

### Benchmark

```bash
python3 -m blocksworld.bench --suites blocks --blocks 3,4,5,6,7,8 \
    --seeds 1,2,3 --reps 3 --max-stacks 2
```

Suites: `blocks` (size sweep), `distance` (walk length), `branching` (stack
spread), `unsolvable`. Writes JSON and a markdown table to `bench/`.

---

## Architecture

```
task4-blocksworld/
├── blocksworld/
│   ├── model.py              domain definition, canonical states, JSON schema
│   ├── generator.py          reproducible instances; partition and walk modes
│   ├── verify.py             independent verifier; imports no engine
│   ├── render.py             ascii / svg / filmstrip / animation / gif
│   ├── cli.py                command line interface
│   ├── bench.py              measurement harness
│   ├── engines/
│   │   ├── base.py           Engine interface, PlanResult, status semantics
│   │   ├── prolog_engine.py  process driver for the symbolic planner
│   │   └── z3_engine.py      bounded-horizon SAT encoding
│   └── prolog/
│       ├── blocksworld.pl    the planner itself: iddfs, IDA*, bfs
│       ├── run_wasm.mjs      optional swipl-wasm runner
│       └── package.json      optional; only for the WASM fallback
├── tests/
│   ├── reference.py          independent BFS oracle, used only by tests
│   └── test_*.py             189 tests
├── bench/                    recorded benchmark output
└── examples/
```

Dependency direction is one-way and enforced by tests:

```
generator ─┐
           ├─> model <─┬─ engines/prolog_engine
verify ────┤           └─ engines/z3_engine
render ────┘
```

### The transition function is implemented five times, on purpose

`model.py` defines what a state and an action *are*, but contains **no
state-transition function**. Applying an action is written independently in:

| Implementation | Where | Why it is separate |
|---|---|---|
| Prolog clauses | `prolog/blocksworld.pl` | the symbolic planner |
| SMT constraints | `engines/z3_engine.py` | the SAT encoding |
| Plain Python | `verify.py` | the independent check |
| Generator-local | `generator.py` | so the generator cannot bless its own bugs |
| Test oracle | `tests/reference.py` | so neither engine is the authority |

If the transition lived in one shared place, a mistake in it would be
invisible: every engine and the verifier would make the same mistake together
and agree enthusiastically. The duplication is the point.

---

## Planning formulations

### Prolog: iterative deepening with an admissible heuristic

Three strategies, all optimal:

| Strategy | Method | Proves unsat? | Memory |
|---|---|---|---|
| `iddfs` | iterative deepening DFS | no | path-depth |
| `idastar` (default) | the same, bounded by `f = g + h` | no | path-depth |
| `bfs` | breadth-first with a closed set | **yes** | frontier + closed |

**The heuristic.** `h(S)` counts blocks resting on something other than what
the goal requires.

> *Admissibility.* A move changes the support of exactly one block — the one it
> picks up. One move therefore reduces `h` by at most 1, so `h` never exceeds
> the true remaining distance. With an admissible `h`, the first solution found
> at a given `f`-bound is optimal.

The bound starts at `h(initial)` and rises by one per round. Raising by one
rather than to the smallest `f` that exceeded the bound costs some repeated
work but keeps the optimality argument trivial: every plan shorter than the
current bound has already been fully examined.

**Cycle detection.** A branch is abandoned if it revisits a state already on
the current path. This cannot remove an optimal plan — a plan that revisits a
state contains a loop, and deleting the loop gives a strictly shorter plan to
the same goal.

**Why `bfs` exists.** It is the only strategy that can *prove* unsolvability:
when the frontier empties, every reachable state has been seen and none was the
goal. Depth-bounded search cannot distinguish "no plan" from "no plan this
short".

### Z3: bounded-horizon planning as satisfiability

Variables, for each time step `t` in `0..T`:

* `on[b][t]` — what block `b` rests on: another block's index, or `n` for the
  table
* `height[b][t]` in `0..n-1` — how far `b` sits above the table

State validity, asserted at **every** step:

| # | Constraint | Meaning |
|---|---|---|
| 1 | `on[b][t] != b` | nothing rests on itself |
| 2 | `on[b1][t] != table -> on[b1][t] != on[b2][t]` | a block supports at most one block |
| 3 | `on[b][t] == c -> height[b][t] == height[c][t] + 1` | heights are well-founded |
| 4 | `Sum(on[b][t] == table) <= capacity` | finite table |

> **Why constraint 3 is needed.** Constraints 1 and 2 alone permit a cycle: `A`
> on `B` and `B` on `A` satisfies both, yet describes nothing physical.
> Requiring each block to sit exactly one unit above its support makes a cycle
> demand `h = h + k` for `k >= 1`, which no finite integer satisfies. With
> cycles ruled out the `on` relation is a forest of chains rooted at the table —
> which is exactly a set of stacks.

Actions are two integers per step, `mover[t]` and `dest[t]`, rather than a set
of mutually exclusive booleans. **This gives action exclusivity for free**:
there is no way to express two simultaneous moves, so no at-most-one constraint
is needed. Plans are strictly sequential; no concurrency semantics are involved.

Preconditions mirror the domain one-for-one, and effects use the standard
implication pair — `mover[t] == b` forces `on[b][t+1] == dest[t]`, and
`mover[t] != b` forces `on[b][t+1] == on[b][t]`.

> *Optimality.* Every step is forced to be a real move (`dest[t]` must differ
> from the mover's current support), so a model at horizon `T` is a plan of
> exactly `T` moves, and any `T`-move plan yields a model. Horizons are tried in
> increasing order from 0, so the first satisfiable horizon **is** the minimum
> number of moves. No separate optimisation step is needed.

The per-horizon trace is recorded in the output, which makes the argument
visible rather than asserted:

```json
"per_horizon": [
  {"horizon": 0, "result": "unsat", "ms": 1.5},
  ...
  {"horizon": 8, "result": "unsat", "ms": 59.6},
  {"horizon": 9, "result": "sat",   "ms": 71.7}
]
```

### Three statuses, never conflated

| Status | Meaning |
|---|---|
| `sat` | a plan was found, and it is optimal |
| `unsat` | **proved** no plan exists |
| `limit` | hit a depth or horizon ceiling; says nothing about existence |
| `unknown` | timed out or failed |

An engine may claim `unsat` only when it can justify it: Z3 when the horizon
reached is at least the completeness bound (`2n`, valid when the table can hold
every block), Prolog `bfs` when the reachable state space is exhausted, and
either engine when a structural check rules the instance out without searching.
On a restricted table no sound bound exists, so both engines correctly report
`limit` and only `bfs` can settle the question. Collapsing `limit` into `unsat`
would turn "I gave up" into "impossible" — the easiest way for a planner to lie.

---

## Test suite

```bash
python3 -m pytest tests/ -q
```

**189 tests**, no skips.

| File | Tests | Covers |
|---|---|---|
| `test_engines.py` | 69 | known optima, optimality, unsolvability, strategy and engine agreement |
| `test_model.py` | 36 | canonical states, validity, heuristic admissibility, schema |
| `test_verify.py` | 24 | one test per class of invalid plan; AST independence check |
| `test_generator.py` | 22 | determinism, capacity handling, walk bounds |
| `test_cli.py` | 19 | every subcommand end to end, including exit codes |
| `test_render.py` | 19 | ascii geometry, SVG structure, animation frames, GIF frames and font fallback |

### Layers of evidence

The engines are **not** validated by agreeing with each other. In order of
strength:

1. Every returned plan passes independent verification.
2. Every plan length matches a **hand-computed** expectation — seven cases
   worked out on paper (0-move, 1-move, pair inversion, three-into-tower,
   Sussman anomaly, four-tower inversion, and a capacity-2 case).
3. Those hand-computed optima are themselves confirmed against
   `tests/reference.py`, an independent BFS oracle written as simply as
   possible with no regard for speed.
4. **Asking an engine to beat its own answer by one move fails** — proof the
   plan is minimal, not merely valid.
5. All three Prolog strategies return the same lengths. If the heuristic were
   inadmissible, IDA* would prune an optimal branch and come back longer than
   unguided `iddfs`; this is the test that would catch it.
6. Only then: the two engines agree with each other.

---

## Benchmark results

Measured on this machine. Both engines saw **identical instances** from
recorded seeds; every plan counted as a success was independently verified.

### Two clocks, and why both are published

`wall` is end-to-end. For Prolog it includes spawning a subprocess and, under
the WASM fallback, booting an entire SWI-Prolog runtime before a single state
is expanded — measured at roughly **500–600 ms** on a trivial instance, and
varying by tens of milliseconds between runs. That variation is why the tables
below do **not** carry a "wall minus startup" column: the subtraction is of the
same order as its own error, and on the smaller instances it goes negative.

`engine` is each engine's own directly measured solve time — `cputime` from
Prolog's `statistics/2`, and the sum of the per-horizon solve times for Z3.
That is the column to compare.

### Block-count scaling

3 seeds per size, 3 repetitions, `--max-stacks 2`, 90 s timeout, run with
nothing else on the machine. Medians, with the observed range in brackets.

| Blocks | Optimal lengths | Prolog engine | Z3 engine | Prolog wall | Z3 wall | Prolog states | Z3 horizons |
|---|---|---|---|---|---|---|---|
| 3 | 2, 3 | **1 ms** [1–1] | 11 ms [9–20] | 510 ms | 34 ms | 5 | 4 |
| 4 | 4, 5 | **2 ms** [2–2] | 32 ms [23–36] | 477 ms | 99 ms | 8 | 5 |
| 5 | 6, 7, 8 | **8 ms** [2–16] | 115 ms [76–150] | 569 ms | 337 ms | 28 | 8 |
| 6 | 7, 9, 10 | **64 ms** [15–559] | 229 ms [185–306] | 657 ms | 544 ms | 117 | 10 |
| 7 | 8, 9 | **45 ms** [17–253] | 273 ms [252–418] | 618 ms | 746 ms | 95 | 10 |
| 8 | 9, 10, 12 | **52 ms** [33–2223] | 710 ms [499–894] | 670 ms | 1337 ms | 75 | 11 |

**The engines agreed on plan length for every single instance, and every plan
passed independent verification.**

### Reading these numbers

**Z3's cost grows steeply with plan length, and that is structural.** To prove a
9-move plan optimal it must first prove horizons 0 through 8 unsatisfiable, and
each of those is a fresh constraint system whose size grows with the horizon.
The per-horizon trace shows the climb directly — 1.5 ms at horizon 0, 59.6 ms
at horizon 8, on one 7-block instance. The work is cumulative and unavoidable
in this formulation.

**Prolog's IDA\* barely notices**, staying in the tens of milliseconds across
the whole range. The heuristic is close to exact on these instances — `h` is
usually within 1–3 of the true optimum — so very few states are expanded (5 to
117). On search time it runs roughly **10× to 14× faster** than Z3 at every
size measured.

**So on this domain the symbolic searcher wins, comfortably.** That is the
reverse of the TetraVex result in `task3`, where Z3 pulled ahead from 3×3
upward. The difference is the informative part: TetraVex is a single constraint
system with no notion of sequence, exactly what SMT is built for. Blocks World
is *sequential*, and encoding "how long is the plan?" as "try every length in
turn" makes the solver pay repeatedly for something explicit search answers
once.

**Caveats.** Three seeds per size, so individual instances can be unusually
easy or hard — look at the 8-block Prolog range of 33–2223 ms, where one seed
cost sixty-seven times another, and note that the median therefore hides a very
long tail. Z3's spread is far tighter, which is its own kind of advantage. These
are short plans (≤ 12 moves); the published literature finds SAT planning
competitive at much longer horizons, and nothing here contradicts that. The
effort columns are in each engine's own units and are **not** comparable with
one another.

### Branching factor

6 blocks, varying how many stacks the random states may use. Fewer stacks means
taller towers, more blocks buried, and more forced double-handling.

| Stacks allowed | Optimal lengths | Prolog states | Z3 horizons |
|---|---|---|---|
| 1 | 10 | 228 | 11 |
| 2 | 7, 9, 10 | 117 | 10 |
| 3 | 6, 8, 9 | 362 | 9 |
| 6 | 0, 1, 3 | 1 | 2 |

The last row is why `--max-stacks 2` is the benchmark default: left
unconstrained, a random partition of 6 blocks scatters most of them into
singleton stacks that are already where the goal wants them, and the optimal
plan collapses to 0–3 moves. Those instances measure almost nothing.

### Unsolvable instances

A one-slot table: the single stack can never be dismantled, so no plan exists.

| Blocks | `prolog:bfs` | `prolog:idastar` | `z3` |
|---|---|---|---|
| 3 | **unsat**, 1 state | limit, 10 states | limit, 13 horizons |
| 4 | **unsat**, 1 state | limit, 14 states | limit, 17 horizons |
| 5 | **unsat**, 1 state | limit, 17 states | limit, 21 horizons |

Only `bfs` settles it, and it does so immediately: the initial state has no
legal successors at all, so the frontier empties after one expansion. The other
two strategies correctly report `limit` and refuse to call it a proof — which
is the behaviour being tested, not a shortcoming. Z3's cost rises with block
count (345 ms → 1709 ms wall) because it dutifully grinds through every horizon
up to its ceiling, learning nothing each time.

Raw data, including every per-horizon timing and seed, is in
`bench/results-*.json`.

---

## Known limitations

1. **Native Prolog is untested here.** All measurements used `swipl-wasm`; this
   container has no SWI-Prolog package available. The native path is
   implemented and exercised by the same tests, but no native timing is
   claimed, and most of the 477 ms startup is WASM boot rather than Prolog.
2. **Goals must be complete configurations.** Partial goals (`on(A,B)` with the
   rest unconstrained) are not supported. Both engines and the verifier would
   need a weaker goal test.
3. **No sound unsolvability bound on a restricted table.** When
   `table_capacity < n_blocks` the `2n` argument fails, so Z3 and the
   depth-bounded Prolog strategies can only report `limit`. Only `bfs` settles
   it, and only while the reachable state space fits in memory.
4. **`bfs` uses list-based closed and frontier sets**, so membership is linear.
   Fine for proving small instances unsolvable; it is not a general-purpose
   BFS.
5. **Plan lengths here are short** (≤ 12 moves). The comparison says nothing
   about horizons of 50+, where SAT planning is reported to do better.
6. **Prolog peak memory is not measured.** `global_stack_bytes` is the global
   stack in use when the search finishes, not a peak, and is reported under
   that name rather than dressed up as one.
7. **Small samples**: 3 seeds × 3 repetitions. Medians and ranges are reported;
   no confidence intervals, because quoting one from three samples would be
   noise.

## Recommended next milestone

Support **partial goals**. It is the single change that most increases what the
domain can express, it forces a genuinely different goal test in both engines
(a conjunction of `on` constraints rather than state equality), and it makes
the classic planning benchmarks expressible. It also sharpens the comparison:
partial goals usually lengthen optimal plans, which is precisely the regime
where the Z3 formulation is reported to become competitive — so it would test
the explanation offered above rather than just extending the table.

---

## References

- Kautz, H. & Selman, B. (1992). *Planning as Satisfiability.* ECAI 1992, pp. 359–363.
- Kautz, H. & Selman, B. (1996). *Pushing the Envelope: Planning, Propositional Logic, and Stochastic Search.* AAAI 1996.
- Korf, R. (1985). *Depth-First Iterative-Deepening: An Optimal Admissible Tree Search.* Artificial Intelligence 27(1), pp. 97–109.
- Sussman, G. J. (1975). *A Computer Model of Skill Acquisition.* American Elsevier.
- Gupta, N. & Nau, D. (1992). *On the Complexity of Blocks-World Planning.* Artificial Intelligence 56(2–3), pp. 223–254.
- Slaney, J. & Thiébaux, S. (2001). *Blocks World Revisited.* Artificial Intelligence 125(1–2), pp. 119–153.
- [SWI-Prolog manual](https://www.swi-prolog.org/pldoc/doc_for?object=manual) · [Z3 Python API](https://z3prover.github.io/api/html/namespacez3py.html)
