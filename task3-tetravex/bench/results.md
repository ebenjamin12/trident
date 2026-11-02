## Benchmark results

Each cell is the median of **3 repetition(s)** over **3 seed(s)** per board size (seeds 1, 2, 3), 6 edge symbols, first solution only, timeout 60.0s.

**Fixed startup cost per call** (measured on a 1x1 board): `z3` 2.1 ms, `prolog` 935.5 ms. Subtract this from the wall-clock column to compare search effort.

| Board | Cells | z3 wall (ms) | prolog wall (ms) | z3 engine (ms) | prolog engine (ms) | solved | agree |
|---|---|---|---|---|---|---|---|
| 2x2 | 4 | 8.0 | 943.2 | - | 7.0 | 6/6 | yes |
| 2x3 | 6 | 18.2 | 945.4 | - | 13.0 | 6/6 | yes |
| 3x3 | 9 | 24.4 | 1009.7 | - | 34.0 | 6/6 | yes |
| 3x4 | 12 | 46.0 | 1045.0 | - | 86.0 | 6/6 | yes |
| 4x4 | 16 | 84.7 | 1049.6 | - | 132.0 | 6/6 | yes |

### Environment

- **python**: 3.13.18
- **platform**: Linux-6.18.44-fc-v185-x86_64-with-glibc2.39
- **machine**: x86_64
- **processor**: x86_64
- **timestamp_utc**: 2026-11-01T03:04:17Z
- **z3**: Z3 5.3.3
- **prolog**: SWI-Prolog via swipl-wasm 3.8.2
