# Expanded STRC matrix

## E1 miss

| instance | n | C1 pass | mean Cl | mean seeds |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10 | 10/10 | 16.1 | 5.7 |
| `congested_8x4x4` | 10 | 10/10 | 67.9 | 21.2 |
| `S8x4x4_high` | 10 | 10/10 | 97.0 | 14.8 |
| `S8x4x4_funnel` | 10 | 10/10 | 96.5 | 15.9 |
| `S8x4x4_mid` | 10 | 10/10 | 94.0 | 14.8 |

## E2 containment

| instance | E2a | E2b | feas |
|---|---:|---:|---:|
| `example_3x3x2` | 10/10 | 10/10 | 10/10 |
| `congested_8x4x4` | 10/10 | 10/10 | 10/10 |
| `S8x4x4_high` | 10/10 | 10/10 | 10/10 |
| `S8x4x4_funnel` | 10/10 | 9/10 | 9/10 |
| `S8x4x4_mid` | 10/10 | 10/10 | 10/10 |

## E3 boundary (no expand)

| instance | miss_B | R2 win | R1 feas | R2 feas |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10/10 | 10/10 | 0/10 | 10/10 |
| `congested_8x4x4` | 10/10 | 10/10 | 0/10 | 10/10 |
| `S8x4x4_high` | 10/10 | 10/10 | 0/10 | 10/10 |
| `S8x4x4_funnel` | 10/10 | 9/10 | 0/10 | 9/10 |
| `S8x4x4_mid` | 10/10 | 10/10 | 0/10 | 10/10 |

## Scale (STRC vs R0+)

| instance | φ | STRC feas | STRC ms | R0 Cmax | speedup |
|---|---:|---:|---:|---:|---:|
| `congested_8x4x4` | 0.10 | 100% | 6.6 | 131.5 | 327× |
| `congested_8x4x4` | 0.25 | 100% | 7.3 | 141.4 | 303× |
| `congested_8x4x4` | 0.50 | 100% | 8.7 | 158.5 | 252× |
| `congested_8x4x4` | 0.75 | 100% | 9.1 | 170.7 | 239× |
| `congested_8x4x4` | 1.00 | 100% | 9.9 | 184.4 | 223× |
| `example_3x3x2` | 0.10 | 100% | 1.1 | 45.5 | 2121× |
| `example_3x3x2` | 0.25 | 100% | 1.7 | 47.7 | 1230× |
| `example_3x3x2` | 0.50 | 100% | 1.6 | 48.9 | 1291× |
| `example_3x3x2` | 0.75 | 100% | 1.8 | 50.7 | 1227× |
| `example_3x3x2` | 1.00 | 100% | 2.0 | 52.3 | 1056× |

## E5 budgets

| instance | budget | R0 Cmax | R2 Cmax | R2 ms |
|---|---:|---:|---:|---:|
| `congested_8x4x4` | 0.2 | 204.0 | 229.7 | 6.7 |
| `congested_8x4x4` | 1 | 185.3 | 229.7 | 6.7 |
| `congested_8x4x4` | 2 | 170.7 | 229.7 | 6.7 |
| `example_3x3x2` | 0.2 | 61.0 | 78.3 | 1.8 |
| `example_3x3x2` | 1 | 60.3 | 78.3 | 1.8 |
| `example_3x3x2` | 2 | 60.3 | 78.3 | 1.8 |

## E6 disturbance type x boundary

| type | class | n | R1 empty | mean T_impact | mean |R1| | mean |Cl| | mean Cl/alive | R2 covers R1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `corridor_block` | B | 50 | 50/50 | 0.0 | 0.0 | 74.3 | 0.904 | 50/50 |
  repair `corridor_block`: R2 feas 49/50
| `corridor_slowdown` | B | 50 | 50/50 | 0.0 | 0.0 | 71.9 | 0.875 | 50/50 |
  repair `corridor_slowdown`: R2 feas 49/50
| `agv_breakdown` | A | 50 | 0/50 | 6.7 | 35.3 | 67.9 | 0.838 | 50/50 |
  repair `agv_breakdown`: R2 feas 50/50
| `ra_failure` | A | 50 | 0/50 | 12.0 | 51.3 | 73.7 | 0.907 | 50/50 |
  repair `ra_failure`: R2 feas 48/50
