## Blocks World benchmark results

Every engine saw identical instances from seeds 1, 2, 2 repetition(s) each, timeout 90.0s, states limited to 2 stack(s). Every plan counted as a success was checked by the independent verifier.

**Fixed startup cost per call** (one-block instance, goal already satisfied): `prolog:bfs` 493 ms, `prolog:idastar` 465 ms, `z3` 3 ms. This is measured once per run and varies by tens of milliseconds between runs, so it is context for reading the wall column rather than a quantity to subtract from it -- the `engine ms` column is the engine's own directly measured solve time and is the figure to compare.


### Suite: `unsolvable`

| Configuration | Blocks | Optimal length | prolog:bfs wall ms | prolog:idastar wall ms | z3 wall ms | prolog:bfs engine ms | prolog:idastar engine ms | z3 engine ms | prolog:bfs effort | prolog:idastar effort | z3 effort | lengths agree | all verified |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 blocks cap 1 | 3 | no plan | 500 [469-530] | 550 [516-584] | 345 [324-366] | 0 [0-0] | 1 [0-1] | 119 [110-128] | 1 states | 10 states | 13 horizons | yes | n/a |
| 4 blocks cap 1 | 4 | no plan | 553 [528-577] | 518 [508-528] | 744 [727-761] | 0 [0-0] | 1 [1-1] | 255 [251-259] | 1 states | 14 states | 17 horizons | yes | n/a |
| 5 blocks cap 1 | 5 | no plan | 533 [501-565] | 535 [510-560] | 1709 [1664-1754] | 1 [0-1] | 1 [1-2] | 599 [585-614] | 1 states | 17 states | 21 horizons | yes | n/a |

### Environment

- **python**: 3.13.18
- **platform**: Linux-6.18.44-fc-v185-x86_64-with-glibc2.39
- **machine**: x86_64
- **timestamp_utc**: 2026-11-01T12:55:20Z
- **prolog**: SWI-Prolog via swipl-wasm 3.8.2
- **z3**: Z3 5.3.3

`wall ms` includes each engine's fixed startup cost. `engine ms` is self-reported solve time: `cputime` from Prolog's `statistics/2`, and the sum of per-horizon solve times for Z3. Search-effort columns are in each engine's own units and are **not** comparable with one another -- there is no honest conversion between states expanded and horizons attempted, so no ratio is computed.
