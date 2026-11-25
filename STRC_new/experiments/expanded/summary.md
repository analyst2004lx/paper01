# Expanded STRC matrix

## E1 miss

| instance | n | C1 pass | mean Cl | mean seeds |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10 | 10/10 | 16.1 | 5.7 |
| `congested_8x4x4` | 10 | 10/10 | 57.7 | 18.7 |
| `S8x4x4_high` | 10 | 10/10 | 93.9 | 14.8 |
| `S8x4x4_funnel` | 10 | 10/10 | 92.1 | 15.2 |
| `S8x4x4_mid` | 10 | 10/10 | 91.5 | 14.3 |

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
| `congested_8x4x4` | 0.10 | 100% | 6.2 | 129.1 | 380× |
| `congested_8x4x4` | 0.25 | 100% | 6.6 | 142.7 | 334× |
| `congested_8x4x4` | 0.50 | 100% | 6.8 | 156.6 | 314× |
| `congested_8x4x4` | 0.75 | 100% | 7.6 | 159.7 | 285× |
| `congested_8x4x4` | 1.00 | 100% | 8.1 | 172.4 | 269× |
| `example_3x3x2` | 0.10 | 100% | 1.1 | 45.5 | 2088× |
| `example_3x3x2` | 0.25 | 100% | 1.6 | 47.7 | 1369× |
| `example_3x3x2` | 0.50 | 100% | 1.6 | 48.9 | 1364× |
| `example_3x3x2` | 0.75 | 100% | 1.9 | 50.7 | 1106× |
| `example_3x3x2` | 1.00 | 100% | 1.7 | 52.3 | 1279× |

## E5 budgets

| instance | budget | R0 Cmax | R2 Cmax | R2 ms |
|---|---:|---:|---:|---:|
| `congested_8x4x4` | 0.2 | 201.7 | 220.3 | 6.6 |
| `congested_8x4x4` | 1 | 179.0 | 220.3 | 6.6 |
| `congested_8x4x4` | 2 | 177.0 | 220.3 | 6.6 |
| `example_3x3x2` | 0.2 | 61.0 | 78.3 | 1.8 |
| `example_3x3x2` | 1 | 60.3 | 78.3 | 1.8 |
| `example_3x3x2` | 2 | 60.3 | 78.3 | 1.8 |

## E6 disturbance type x boundary

| type | class | n | R1 empty | mean T_impact | mean |R1| | mean |Cl| | mean Cl/alive | R2 covers R1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `corridor_block` | B | 50 | 50/50 | 0.0 | 0.0 | 70.3 | 0.905 | 50/50 |
  repair `corridor_block`: R2 feas 50/50
| `corridor_slowdown` | B | 50 | 50/50 | 0.0 | 0.0 | 68.4 | 0.879 | 50/50 |
  repair `corridor_slowdown`: R2 feas 50/50
| `agv_breakdown` | A | 50 | 0/50 | 6.9 | 34.9 | 58.0 | 0.773 | 50/50 |
  repair `agv_breakdown`: R2 feas 50/50
| `ra_failure` | A | 50 | 0/50 | 12.1 | 45.8 | 69.4 | 0.906 | 50/50 |
  repair `ra_failure`: R2 feas 50/50
