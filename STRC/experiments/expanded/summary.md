# Expanded STRC matrix

## E1 miss

| instance | n | C1 pass | mean Cl | mean seeds |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10 | 10/10 | 16.7 | 5.6 |
| `congested_8x4x4` | 10 | 10/10 | 48.3 | 15.0 |
| `S8x4x4_high` | 10 | 10/10 | 85.9 | 15.5 |
| `S8x4x4_funnel` | 10 | 10/10 | 82.1 | 15.5 |
| `S8x4x4_mid` | 10 | 10/10 | 80.2 | 15.0 |

## E2 containment

| instance | E2a | E2b | feas |
|---|---:|---:|---:|
| `example_3x3x2` | 10/10 | 10/10 | 10/10 |
| `congested_8x4x4` | 10/10 | 10/10 | 10/10 |
| `S8x4x4_high` | 10/10 | 10/10 | 10/10 |
| `S8x4x4_funnel` | 10/10 | 10/10 | 10/10 |
| `S8x4x4_mid` | 10/10 | 10/10 | 10/10 |

## E3 boundary (no expand)

| instance | miss_B | R2 win | R1 feas | R2 feas |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10/10 | 10/10 | 0/10 | 10/10 |
| `congested_8x4x4` | 10/10 | 10/10 | 0/10 | 10/10 |
| `S8x4x4_high` | 10/10 | 10/10 | 0/10 | 10/10 |
| `S8x4x4_funnel` | 10/10 | 10/10 | 0/10 | 10/10 |
| `S8x4x4_mid` | 10/10 | 10/10 | 0/10 | 10/10 |

## Scale (STRC vs R0+)

| instance | φ | STRC feas | STRC ms | R0 Cmax | speedup |
|---|---:|---:|---:|---:|---:|
| `congested_8x4x4` | 0.10 | 100% | 7.9 | 99.4 | 393× |
| `congested_8x4x4` | 0.25 | 100% | 9.7 | 104.0 | 377× |
| `congested_8x4x4` | 0.50 | 100% | 6.7 | 110.2 | 422× |
| `congested_8x4x4` | 0.75 | 100% | 7.9 | 116.9 | 287× |
| `congested_8x4x4` | 1.00 | 100% | 9.6 | 123.5 | 223× |
| `example_3x3x2` | 0.10 | 100% | 1.1 | 34.0 | 2538× |
| `example_3x3x2` | 0.25 | 100% | 1.1 | 34.6 | 2436× |
| `example_3x3x2` | 0.50 | 100% | 1.3 | 35.6 | 1834× |
| `example_3x3x2` | 0.75 | 100% | 1.2 | 36.4 | 1779× |
| `example_3x3x2` | 1.00 | 100% | 1.4 | 36.9 | 1455× |

## E5 budgets

| instance | budget | R0 Cmax | R2 Cmax | R2 ms |
|---|---:|---:|---:|---:|
| `congested_8x4x4` | 0.2 | 212.7 | 299.0 | 1.7 |
| `congested_8x4x4` | 1 | 160.7 | 299.0 | 1.7 |
| `congested_8x4x4` | 2 | 140.0 | 299.0 | 1.7 |
| `example_3x3x2` | 0.2 | 45.7 | 88.7 | 0.6 |
| `example_3x3x2` | 1 | 45.3 | 88.7 | 0.6 |
| `example_3x3x2` | 2 | 45.3 | 88.7 | 0.6 |

## E6 disturbance type x boundary

| type | class | n | R1 empty | mean T_impact | mean |R1| | mean |Cl| | mean Cl/alive | R2 covers R1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `corridor_block` | B | 50 | 50/50 | 0.0 | 0.0 | 62.6 | 0.901 | 50/50 |
| `corridor_slowdown` | B | 50 | 50/50 | 0.0 | 0.0 | 62.6 | 0.901 | 50/50 |
| `agv_breakdown` | A | 50 | 0/50 | 6.7 | 31.1 | 53.0 | 0.753 | 50/50 |
| `ra_failure` | A | 50 | 0/50 | 12.3 | 42.8 | 62.7 | 0.902 | 50/50 |
