## Benchmark results

Each cell is the median of **1 repetition(s)** over **2 seed(s)** per board size (seeds 1, 2), 6 edge symbols, first solution only, timeout 120.0s.

**Fixed startup cost per call** (measured on a 1x1 board): `z3` 2.2 ms, `prolog` 971.1 ms. Subtract this from the wall-clock column to compare search effort.

| Board | Cells | z3 wall (ms) | prolog wall (ms) | z3 engine (ms) | prolog engine (ms) | solved | agree |
|---|---|---|---|---|---|---|---|
| 4x5 | 20 | 241.4 | 2436.0 | - | 1517.5 | 4/4 | yes |
| 5x5 | 25 | 733.3 | 6514.1 | - | 5599.0 | 4/4 | yes |
| 5x6 | 30 | 8333.2 | 60372.9 | - | 59418.0 | 4/4 | yes |
| 6x6 | 36 | 120218.1 | 120109.8 | - | - | 0/2 | yes |

### Environment

- **python**: 3.13.18
- **platform**: Linux-6.18.44-fc-v185-x86_64-with-glibc2.39
- **machine**: x86_64
- **processor**: x86_64
- **timestamp_utc**: 2026-11-01T03:11:08Z
- **z3**: Z3 5.3.3
- **prolog**: SWI-Prolog via swipl-wasm 3.8.2
