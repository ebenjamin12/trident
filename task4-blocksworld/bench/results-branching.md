## Blocks World benchmark results

Every engine saw identical instances from seeds 1, 2, 3, 3 repetition(s) each, timeout 90.0s, states limited to 2 stack(s). Every plan counted as a success was checked by the independent verifier.

**Fixed startup cost per call** (one-block instance, goal already satisfied): `prolog:idastar` 558 ms, `z3` 3 ms. This is measured once per run and varies by tens of milliseconds between runs, so it is context for reading the wall column rather than a quantity to subtract from it -- the `engine ms` column is the engine's own directly measured solve time and is the figure to compare.


### Suite: `branching`

| Configuration | Blocks | Optimal length | prolog:idastar wall ms | z3 wall ms | prolog:idastar engine ms | z3 engine ms | prolog:idastar effort | z3 effort | lengths agree | all verified |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 stacks | 6 | 10 | 670 [587-821] | 770 [642-790] | 73 [64-229] | 326 [263-337] | 228 states | 11 horizons | yes | yes |
| 2 stacks | 6 | 7, 9, 10 | 564 [545-1188] | 674 [394-751] | 50 [20-651] | 266 [148-287] | 117 states | 10 horizons | yes | yes |
| 3 stacks | 6 | 6, 8, 9 | 748 [568-1058] | 419 [305-568] | 141 [5-552] | 147 [94-241] | 362 states | 9 horizons | yes | yes |
| 6 stacks | 6 | 0, 1, 3 | 545 [530-547] | 29 [9-86] | 1 [1-2] | 4 [2-27] | 1 states | 2 horizons | yes | yes |

### Environment

- **python**: 3.13.18
- **platform**: Linux-6.18.44-fc-v185-x86_64-with-glibc2.39
- **machine**: x86_64
- **timestamp_utc**: 2026-11-01T12:54:52Z
- **prolog**: SWI-Prolog via swipl-wasm 3.8.2
- **z3**: Z3 5.3.3

`wall ms` includes each engine's fixed startup cost. `engine ms` is self-reported solve time: `cputime` from Prolog's `statistics/2`, and the sum of per-horizon solve times for Z3. Search-effort columns are in each engine's own units and are **not** comparable with one another -- there is no honest conversion between states expanded and horizons attempted, so no ratio is computed.
