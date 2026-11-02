## Blocks World benchmark results

Every engine saw identical instances from seeds 1, 2, 3, 3 repetition(s) each, timeout 90.0s, states limited to 2 stack(s). Every plan counted as a success was checked by the independent verifier.

**Fixed startup cost per call** (one-block instance, goal already satisfied): `prolog:idastar` 572 ms, `z3` 2 ms. This is measured once per run and varies by tens of milliseconds between runs, so it is context for reading the wall column rather than a quantity to subtract from it -- the `engine ms` column is the engine's own directly measured solve time and is the figure to compare.


### Suite: `blocks`

| Configuration | Blocks | Optimal length | prolog:idastar wall ms | z3 wall ms | prolog:idastar engine ms | z3 engine ms | prolog:idastar effort | z3 effort | lengths agree | all verified |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 blocks | 3 | 2, 3 | 510 [488-513] | 34 [28-70] | 1 [1-1] | 11 [9-20] | 5 states | 4 horizons | yes | yes |
| 4 blocks | 4 | 4, 5 | 477 [474-517] | 99 [73-115] | 2 [2-2] | 32 [23-36] | 8 states | 5 horizons | yes | yes |
| 5 blocks | 5 | 6, 7, 8 | 569 [509-603] | 337 [217-396] | 8 [2-16] | 115 [76-150] | 28 states | 8 horizons | yes | yes |
| 6 blocks | 6 | 7, 9, 10 | 657 [573-1141] | 544 [450-805] | 64 [15-559] | 229 [185-306] | 117 states | 10 horizons | yes | yes |
| 7 blocks | 7 | 8, 9 | 618 [553-833] | 746 [614-952] | 45 [17-253] | 273 [252-418] | 95 states | 10 horizons | yes | yes |
| 8 blocks | 8 | 9, 10, 12 | 670 [584-2727] | 1337 [1051-1894] | 52 [33-2223] | 710 [499-894] | 75 states | 11 horizons | yes | yes |

### Environment

- **python**: 3.13.18
- **platform**: Linux-6.18.44-fc-v185-x86_64-with-glibc2.39
- **machine**: x86_64
- **timestamp_utc**: 2026-11-01T13:07:27Z
- **prolog**: SWI-Prolog via swipl-wasm 3.8.2
- **z3**: Z3 5.3.3

`wall ms` includes each engine's fixed startup cost. `engine ms` is self-reported solve time: `cputime` from Prolog's `statistics/2`, and the sum of per-horizon solve times for Z3. Search-effort columns are in each engine's own units and are **not** comparable with one another -- there is no honest conversion between states expanded and horizons attempted, so no ratio is computed.
