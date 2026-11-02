## Blocks World benchmark results

Every engine saw identical instances from seeds 1, 2, 3, 3 repetition(s) each, timeout 90.0s, states limited to 2 stack(s). Every plan counted as a success was checked by the independent verifier.

**Fixed startup cost per call** (one-block instance, goal already satisfied): `prolog:idastar` 468 ms, `z3` 2 ms. This is measured once per run and varies by tens of milliseconds between runs, so it is context for reading the wall column rather than a quantity to subtract from it -- the `engine ms` column is the engine's own directly measured solve time and is the figure to compare.


### Suite: `distance`

| Configuration | Blocks | Optimal length | prolog:idastar wall ms | z3 wall ms | prolog:idastar engine ms | z3 engine ms | prolog:idastar effort | z3 effort | lengths agree | all verified |
|---|---|---|---|---|---|---|---|---|---|---|
| walk 2 | 6 | 1, 2 | 505 [478-545] | 44 [24-45] | 1 [1-1] | 9 [4-10] | 2 states | 3 horizons | yes | yes |
| walk 4 | 6 | 1, 3 | 547 [490-548] | 24 [22-81] | 1 [0-1] | 3 [3-19] | 1 states | 2 horizons | yes | yes |
| walk 6 | 6 | 1, 3, 5 | 506 [499-597] | 106 [22-252] | 1 [1-3] | 27 [4-82] | 3 states | 4 horizons | yes | yes |
| walk 8 | 6 | 3, 4, 5 | 492 [468-535] | 179 [79-203] | 2 [0-2] | 54 [18-58] | 5 states | 5 horizons | yes | yes |
| walk 10 | 6 | 1, 3, 6 | 490 [466-549] | 89 [24-248] | 1 [1-55] | 20 [4-82] | 3 states | 4 horizons | yes | yes |

### Environment

- **python**: 3.13.18
- **platform**: Linux-6.18.44-fc-v185-x86_64-with-glibc2.39
- **machine**: x86_64
- **timestamp_utc**: 2026-11-01T12:52:03Z
- **prolog**: SWI-Prolog via swipl-wasm 3.8.2
- **z3**: Z3 5.3.3

`wall ms` includes each engine's fixed startup cost. `engine ms` is self-reported solve time: `cputime` from Prolog's `statistics/2`, and the sum of per-horizon solve times for Z3. Search-effort columns are in each engine's own units and are **not** comparable with one another -- there is no honest conversion between states expanded and horizons attempted, so no ratio is computed.
