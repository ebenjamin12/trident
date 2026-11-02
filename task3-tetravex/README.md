# TetraVex — Z3 vs. Prolog CLP(FD)

The same edge-matching puzzle, modelled twice: once as an SMT problem for
**Z3**, once as a finite-domain constraint problem for **SWI-Prolog**. Both
read the same instance file, both are checked by the same independent
verifier, and both are measured on the same boards.

The point is not to build two solvers. It is to hold the *problem* fixed and
vary only the paradigm, so the comparison says something about the solvers
rather than about two different ways of modelling a puzzle.

```
┌───────┬───────┬───────┐
│   3   │   2   │   5   │
│ 6   2 │ 2   3 │ 3   2 │
│   7   │   1   │   0   │
├───────┼───────┼───────┤
│   7   │   1   │   0   │
│ 6   0 │ 0   1 │ 1   2 │
│   7   │   4   │   3   │
├───────┼───────┼───────┤
│   7   │   4   │   3   │
│ 0   4 │ 4   0 │ 0   4 │
│   3   │   7   │   7   │
└───────┴───────┴───────┘
```

---

## The puzzle

A bag of square tiles, each carrying a symbol on all four sides, must fill a
rectangular grid so that **every pair of touching sides shows the same
symbol**. There is exactly one tile per cell.

Two variants are supported beyond the classic rules:

| Variant | Flag | Meaning |
|---|---|---|
| Rotation | `--rotation` | Tiles may be turned by 0/90/180/270 degrees. Classic TetraVex does not allow this. |
| Fixed border | `--border` | The outer edges of the grid are pinned to given symbols. Classic TetraVex leaves them free. |

---

## Installation

Python 3.10+ is required.

```bash
cd task3-tetravex
pip install -r requirements.txt       # z3-solver, plus pytest for the tests
```

For the Prolog engine, **either** install SWI-Prolog so that `swipl` is on
`PATH` (preferred — it is faster and needs nothing else):

```bash
# Debian/Ubuntu
sudo apt install swi-prolog-nox
# macOS
brew install swi-prolog
```

**or**, if you would rather not install it, use the bundled WASM fallback:

```bash
cd tetravex/prolog && npm ci         # pulls swipl-wasm, needs Node 18+
```

Check what the toolchain found:

```bash
python3 -m tetravex engines
```

```
z3       available   Z3 5.3.3
prolog   available   SWI-Prolog via swipl-wasm 3.8.2  [mode: wasm]
```

The Prolog **model source is identical** in both modes; only the way the goal
is invoked differs. Which path was used is recorded in every result's
`stats.mode`, so benchmark output never silently mixes the two.

---

## Usage

### Generate

```bash
# a 3x3 puzzle, reproducible from its seed
python3 -m tetravex generate --rows 3 --cols 3 --seed 42 -o puzzle.json

# with the reference layout it was cut from
python3 -m tetravex generate --rows 4 --cols 4 --seed 7 \
    -o puzzle.json --with-solution reference.json

# a named difficulty, rotation allowed, pinned border
python3 -m tetravex generate --difficulty hard --rotation --seed 3 -o puzzle.json

# keep retrying seeds until the puzzle has exactly one solution
python3 -m tetravex generate --rows 3 --cols 3 --symbols 10 --unique -o puzzle.json
```

Difficulty presets set the edge alphabet and whether the border is pinned:

| Preset | Symbols | Border | Intent |
|---|---|---|---|
| `easy` | 10 | pinned | large alphabet, heavily constrained |
| `medium` | 6 | free | the default feel |
| `hard` | 4 | free | many interchangeable tiles |
| `extreme` | 3 | free | heavy ambiguity, large search space |

These are design intent, not measured claims; `bench/` records what they
actually cost.

### Solve

```bash
python3 -m tetravex solve puzzle.json --engine z3     -o solution.json
python3 -m tetravex solve puzzle.json --engine prolog -o solution.json

# also decide whether the solution is the only one
python3 -m tetravex solve puzzle.json --engine z3 --unique -o solution.json

# print the solved board while solving
python3 -m tetravex solve puzzle.json --engine prolog --ascii -o solution.json
```

Exit codes: `0` solved or proved unsatisfiable, `1` gave up (timeout), `2`
engine unavailable, `3` the engine produced a solution the verifier rejected.
That last case is the one worth watching: the CLI refuses to emit a solution
that fails verification, whichever engine produced it.

### Verify

```bash
python3 -m tetravex verify puzzle.json solution.json
```

```
VALID - all constraints satisfied
```

or, on a tampered board:

```
INVALID - 4 violation(s) across 1 category/categories: adjacency
  [adjacency] horizontal mismatch between (0,0) and (0,1): right=2 vs left=5
  ...
```

### Render

```bash
python3 -m tetravex render puzzle.json                               # tray + empty grid
python3 -m tetravex render puzzle.json --solution solution.json      # solved board
python3 -m tetravex render puzzle.json --solution solution.json --ids # label tile ids
python3 -m tetravex render puzzle.json --solution solution.json \
    --format svg --title "4x4 solved" -o board.svg
```

The SVG draws each tile as four coloured wedges meeting at the centre, with
the symbol printed in each — the same presentation as the puzzle in the
assessment brief.

### Benchmark

```bash
python3 -m tetravex.bench --sizes 2x2,2x3,3x3,3x4,4x4 --seeds 1,2,3 --reps 3
```

Writes `bench/results.json` (full detail) and `bench/results.md` (summary
table). Fixed seeds make every run reproducible.

---

## Architecture

```
task3-tetravex/
├── tetravex/
│   ├── model.py              # Tile/Instance/Solution, rotation algebra, JSON schema
│   ├── generator.py          # reproducible generation; no solver dependency
│   ├── verify.py             # independent verifier; imports no solver
│   ├── render.py             # ASCII + SVG; imports no solver
│   ├── cli.py                # command line interface
│   ├── bench.py              # measurement harness
│   ├── solvers/
│   │   ├── base.py           # Solver interface, SolveResult
│   │   ├── z3_solver.py      # SMT encoding
│   │   └── prolog_solver.py  # process driver for the CLP(FD) model
│   └── prolog/
│       ├── tetravex.pl       # the CLP(FD) model itself
│       ├── run_wasm.mjs      # optional swipl-wasm runner
│       └── package.json      # optional; only for the WASM fallback
├── tests/                    # pytest suite
└── bench/                    # recorded benchmark output
```

The dependency direction is strict and one-way:

```
generator ─┐
           ├─> model <─┬─ solvers/z3_solver
verify ────┤           └─ solvers/prolog_solver
render ────┘
```

`verify.py` and `render.py` import `model` and nothing else. Two tests parse
their ASTs and assert that no solver module is ever imported, so the
independence cannot quietly rot.

### The shared instance format

```json
{
  "format": "tetravex-instance",
  "version": 1,
  "id": "tv-3x3-s6-nf-seed42",
  "rows": 3, "cols": 3,
  "symbols": 6,
  "allow_rotation": false,
  "border": null,
  "tiles": [{"id": 0, "top": 4, "right": 2, "bottom": 8, "left": 9}],
  "seed": 42,
  "difficulty": null
}
```

Edges are always stored clockwise from the top: `(top, right, bottom, left)`.
Rotating a tile one quarter-turn clockwise moves the left edge to the top,
`(t,r,b,l) -> (l,t,r,b)`.

Solutions use the same envelope, with a `grid` of `{"tile": id, "rot": k}`.

### Generation

Rather than assembling tiles and hoping, a board is *cut out of* a grid of
edge symbols. For an `R x C` board there are `(R+1) x C` horizontal edges and
`R x (C+1)` vertical ones; each is drawn uniformly from the alphabet, and
every tile reads its four symbols off that grid. Adjacent tiles therefore
share an edge **by construction**, so the instance is solvable before anything
has been searched. The tiles are then shuffled and renumbered so their ids
carry no hint of where they belong; under `--rotation` they are also randomly
turned.

### The two encodings

Both post the same five constraints, in the same order.

| Constraint | Z3 | Prolog CLP(FD) |
|---|---|---|
| One tile per cell, each used once | `Distinct(tile[0..n])` | `all_distinct(TileAt)` |
| Tile choice determines its edges | implication per (cell, tile, rotation) | `tuples_in/2` over the tile table |
| Horizontal match | `right[c] == left[east]` | `Right #= Left` |
| Vertical match | `bottom[c] == top[south]` | `Bottom #= Top` |
| Border | equality on the outer edge vars | equality on the outer edge vars |
| Symmetry breaking | `pos[a] < pos[b]` + channelling | `pos[a] #< pos[b]` + `element/3` |

The one deliberate asymmetry: Prolog uses `all_distinct/1`, which propagates
to domain consistency, where Z3's `Distinct` is a plain disequality handled by
its own theory solver. Both express the same constraint; forcing either into
the other's shape would make the model unnatural for that paradigm, which is
the opposite of what this comparison is for.

### Uniqueness, and what "unique" means here

Both engines answer "is there a second, genuinely different solution?":

* **Z3** solves, adds a blocking clause negating the assignment it found, and
  re-solves. `unsat` means unique.
* **Prolog** uses `findall/3` over `limit(2, solve_grid(G))` — backtracking
  stops after the second answer rather than enumerating everything.

Uniqueness is defined **up to permutation of identical tiles**. If two tiles
carry the same four symbols, swapping them yields the same picture, and
counting that as a second solution would be meaningless. Both engines
therefore pin identical tiles into increasing cell order. Without this, a
board of sixteen identical tiles would report `16!` solutions.

---

## Test suite

```bash
python3 -m pytest tests/ -q
```

122 tests across five files:

| File | Covers |
|---|---|
| `test_model.py` | rotation algebra (identity, order four, composition), schema validation, JSON round-trips, edge-grid canonicalisation |
| `test_generator.py` | reproducibility, solvability by construction in every mode, presets, bad input |
| `test_verify.py` | one test per class of invalid solution; structural check that no solver is imported |
| `test_render.py` | ASCII geometry and alignment, SVG well-formedness and wedge counts, determinism |
| `test_cli.py` | every subcommand end to end, including exit codes |
| `test_solvers.py` | both engines verified independently, unsat detection, uniqueness, cross-engine agreement |

Solver tests skip rather than fail when a toolchain is missing, so the suite
is still meaningful on a machine with only one engine installed.

---

## Benchmark results

Measured on this machine, 6 edge symbols, free border, no rotation, first
solution only. Each cell is the **median of 3 repetitions over 3 seeds**.

**Fixed startup cost per call**, measured on a 1x1 board: `z3` **2.1 ms**,
`prolog` **935.5 ms**.

| Board | Cells | z3 wall | prolog wall | prolog engine | prolog minus startup | solved | agree |
|---|---|---|---|---|---|---|---|
| 2x2 | 4 | 8.0 ms | 943.2 ms | 7.0 ms | ~8 ms | 6/6 | yes |
| 2x3 | 6 | 18.2 ms | 945.4 ms | 13.0 ms | ~10 ms | 6/6 | yes |
| 3x3 | 9 | 24.4 ms | 1009.7 ms | 34.0 ms | ~74 ms | 6/6 | yes |
| 3x4 | 12 | 46.0 ms | 1045.0 ms | 86.0 ms | ~110 ms | 6/6 | yes |
| 4x4 | 16 | 84.7 ms | 1049.6 ms | 132.0 ms | ~114 ms | 6/6 | yes |

### Reading these numbers honestly

The raw wall-clock column makes Prolog look roughly **40x slower**, and that
figure would be misleading. Almost all of it is fixed cost: this run used the
**WASM fallback**, which boots an entire SWI-Prolog runtime in a fresh
subprocess on every single call. The startup calibration isolates it, and the
two independent estimates agree closely — `prolog wall − 935 ms` tracks the
engine's own `cputime` to within a few milliseconds at every size, which is
the main evidence that the calibration is measuring the right thing.

With startup removed, the real picture is much closer:

* At **2x2 and 2x3**, Prolog's search is *faster* than Z3's (7 ms vs 8 ms,
  13 ms vs 18 ms). The SMT encoding has to be built before it can be solved,
  and on a tiny problem that construction dominates — the same effect the
  cryptarithm solver in `task2` shows on three-letter puzzles.
* From **3x3 upward**, Z3 pulls ahead and the gap widens with board size
  (34 vs 24 ms, 86 vs 46 ms, 132 vs 85 ms).

So the crossover sits at around 6–9 cells on these instances. That is a
modest, specific claim from 9 instances per size; it is not a general
statement about SMT versus CLP(FD).

**A native `swipl` would change the wall-clock column substantially** — most
of the 935 ms is WASM boot, not Prolog. This environment has no SWI-Prolog
package available, so that measurement has not been taken here and no figure
for it is quoted. Running the benchmark on a machine with `swipl` installed
will report `mode: native` and produce directly comparable wall-clock times.

Both engines agreed on satisfiability for **every** instance, and every
solution either engine produced passed independent verification.

### Scaling to the breaking point

A second run pushes the board size until both engines fail. Median of 1
repetition over 2 seeds, 6 symbols, 120 s timeout
(`bench/results-large.json`). Prolog's fixed startup was 971 ms in this run:

| Board | Cells | Z3 wall | Prolog wall | Prolog engine | Solved |
|---|---|---|---|---|---|
| 4x5 | 20 | 241 ms | 2,436 ms | 1,518 ms | 4/4 |
| 5x5 | 25 | 733 ms | 6,514 ms | 5,599 ms | 4/4 |
| 5x6 | 30 | 8,333 ms | 60,373 ms | 59,418 ms | 4/4 |
| 6x6 | 36 | timeout | timeout | — | 0/2 |

Both engines solve every board up to **5x6 (30 cells)** and **both time out at
6x6 (36 cells)** against a 120-second limit. Past 20 cells the gap stops being
a constant factor: Z3 goes 241 ms → 733 ms → 8.3 s, Prolog 1.5 s → 5.6 s →
59 s. Both are growing steeply, Z3 from a lower base, and 6x6 is out of reach
for either within two minutes.

Two caveats on this table. Only two seeds per size, so individual instances
could be unusually easy or hard. And "agree" at 6x6 only means both gave up —
it is not evidence about the answer, since neither engine produced one.

---

## Known limitations

1. **Native Prolog is untested here.** The benchmark above ran entirely
   through `swipl-wasm`. The code path for native `swipl` is implemented and
   exercised by the same tests, but no native timing has been measured in this
   environment, and none is claimed.
2. **Uniqueness ignores rotational duplicates.** Symmetry breaking groups
   tiles by exact edge signature. Under `--rotation`, two tiles that are
   rotations of one another are interchangeable in a way the ordering
   constraint does not capture, so such a puzzle can be reported as
   non-unique when the two boards look identical.
3. **Z3 exposes no per-solve CPU figure** through the Python API comparable to
   Prolog's `statistics(cputime)`, so that column is blank for Z3. Its
   wall-clock is in-process and already close to pure solve time.
4. **The sample is small.** Three seeds per size, three repetitions. Enough to
   show a crossover; not enough for a confidence interval, and no variance is
   reported because quoting one from three samples would be noise.
5. **`--unique` generation can fail to find a candidate.** With a small
   alphabet, uniquely-solvable instances are rare; the CLI gives up after
   `--max-attempts` and says so rather than looping.
6. **The generator does not control difficulty precisely.** Presets set the
   alphabet size and border, which influence difficulty but do not pin it.
   Two instances from the same preset can differ substantially in solve time.

## Next steps

* Measure against a native `swipl` to replace the WASM wall-clock figures.
* Add a hand-written backtracking solver in a third language as a control, so
  the comparison has a baseline that is neither SMT nor CLP(FD).
* Experiment with CLP(FD) labelling strategies (`ff`, `ffc`, `min`) — the
  model is fixed, so this isolates search heuristics cleanly.
* Investigate the 6x6 wall: profile whether the Z3 encoding's
  per-(cell, tile, rotation) implication count is the bottleneck, and try a
  boolean assignment-matrix encoding instead.
* Raise the seed count on the scaling table so the larger boards carry a
  variance figure rather than a single median.

---

## References

- de Moura, L. & Bjørner, N. (2008). *Z3: An Efficient SMT Solver.* TACAS 2008.
- Triska, M. (2016). *The Finite Domain Constraint Solver of SWI-Prolog.* FLOPS 2016.
- Apt, K. & Wallace, M. (2007). *Constraint Logic Programming using ECLiPSe.* Cambridge University Press.
- [SWI-Prolog `library(clpfd)` documentation](https://www.swi-prolog.org/man/clpfd.html)
- [Z3 Python API](https://z3prover.github.io/api/html/namespacez3py.html)
