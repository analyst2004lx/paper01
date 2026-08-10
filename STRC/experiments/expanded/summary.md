# Expanded STRC matrix

## E1 miss

| instance | n | C1 pass | mean Cl | mean seeds |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 5 | 5/5 | 16.4 | 5.8 |
| `congested_8x4x4` | 5 | 5/5 | 49.2 | 15.2 |
| `S8x4x4_high` | 5 | 5/5 | 82.8 | 15.6 |

## E2 containment

| instance | E2a | E2b | feas |
|---|---:|---:|---:|
| `example_3x3x2` | 5/5 | 2/5 | 5/5 |
| `congested_8x4x4` | 5/5 | 1/5 | 5/5 |
| `S8x4x4_high` | 5/5 | 4/5 | 5/5 |

## E3 boundary (no expand)

| instance | miss_B | R2 win | R1 feas | R2 feas |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 5/5 | 5/5 | 0/5 | 5/5 |
| `congested_8x4x4` | 5/5 | 5/5 | 0/5 | 5/5 |
| `S8x4x4_high` | 5/5 | 5/5 | 0/5 | 5/5 |

## Scale (STRC vs R0+)

| instance | φ | STRC feas | STRC ms | R0 Cmax | speedup |
|---|---:|---:|---:|---:|---:|
| `congested_8x4x4` | 0.10 | 100% | 8.8 | 101.2 | 345× |
| `congested_8x4x4` | 0.25 | 100% | 9.0 | 106.4 | 369× |
| `congested_8x4x4` | 0.50 | 100% | 4.4 | 109.0 | 471× |
| `congested_8x4x4` | 0.75 | 100% | 6.7 | 109.8 | 310× |
| `congested_8x4x4` | 1.00 | 100% | 9.2 | 128.4 | 232× |
| `example_3x3x2` | 0.10 | 100% | 1.2 | 34.0 | 2294× |
| `example_3x3x2` | 0.25 | 100% | 1.1 | 34.6 | 2135× |
| `example_3x3x2` | 0.50 | 100% | 0.9 | 34.8 | 2192× |
| `example_3x3x2` | 0.75 | 100% | 1.2 | 35.2 | 1651× |
| `example_3x3x2` | 1.00 | 100% | 1.3 | 36.2 | 1517× |

## E5 budgets

| instance | budget | R0 Cmax | R2 Cmax | R2 ms |
|---|---:|---:|---:|---:|
| `congested_8x4x4` | 0.2 | 212.7 | 299.0 | 1.8 |
| `congested_8x4x4` | 1 | 160.7 | 299.0 | 1.8 |
| `congested_8x4x4` | 2 | 139.3 | 299.0 | 1.8 |
| `example_3x3x2` | 0.2 | 45.7 | 92.0 | 0.5 |
| `example_3x3x2` | 1 | 45.3 | 92.0 | 0.5 |
| `example_3x3x2` | 2 | 45.3 | 92.0 | 0.5 |
