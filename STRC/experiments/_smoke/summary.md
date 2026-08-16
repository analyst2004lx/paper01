# Expanded STRC matrix

## E1 miss

| instance | n | C1 pass | mean Cl | mean seeds |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 2 | 2/2 | 17.5 | 6.5 |
| `congested_8x4x4` | 2 | 2/2 | 52.0 | 16.0 |
| `S8x4x4_high` | 2 | 2/2 | 77.5 | 15.5 |
| `S8x4x4_funnel` | 2 | 2/2 | 81.0 | 16.0 |
| `S8x4x4_mid` | 2 | 2/2 | 80.0 | 16.5 |

## E2 containment

| instance | E2a | E2b | feas |
|---|---:|---:|---:|
| `example_3x3x2` | 2/2 | 1/2 | 2/2 |
| `congested_8x4x4` | 2/2 | 0/2 | 2/2 |
| `S8x4x4_high` | 2/2 | 1/2 | 2/2 |
| `S8x4x4_funnel` | 2/2 | 0/2 | 2/2 |
| `S8x4x4_mid` | 2/2 | 0/2 | 2/2 |

## E3 boundary (no expand)

| instance | miss_B | R2 win | R1 feas | R2 feas |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 2/2 | 2/2 | 0/2 | 2/2 |
| `congested_8x4x4` | 2/2 | 2/2 | 0/2 | 2/2 |
| `S8x4x4_high` | 2/2 | 2/2 | 0/2 | 2/2 |
| `S8x4x4_funnel` | 2/2 | 2/2 | 0/2 | 2/2 |
| `S8x4x4_mid` | 2/2 | 2/2 | 0/2 | 2/2 |

## E6 disturbance type x boundary

| type | class | n | R1 empty | mean T_impact | mean |R1| | mean |Cl| | mean Cl/alive | R2 covers R1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `corridor_block` | B | 10 | 10/10 | 0.0 | 0.0 | 61.6 | 0.896 | 10/10 |
| `corridor_slowdown` | B | 10 | 10/10 | 0.0 | 0.0 | 61.6 | 0.896 | 10/10 |
| `agv_breakdown` | A | 10 | 0/10 | 1.0 | 31.1 | 53.9 | 0.758 | 10/10 |
| `ra_failure` | A | 10 | 0/10 | 11.6 | 40.2 | 62.0 | 0.892 | 10/10 |
