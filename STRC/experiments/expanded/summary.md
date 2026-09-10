# Expanded STRC matrix

## E1 miss

| instance | n | C1 pass | mean Cl | mean seeds |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10 | 10/10 | 16.9 | 5.6 |
| `congested_8x4x4` | 10 | 10/10 | 48.4 | 15.0 |
| `S8x4x4_high` | 10 | 10/10 | 88.3 | 15.5 |
| `S8x4x4_funnel` | 10 | 10/10 | 85.4 | 15.5 |
| `S8x4x4_mid` | 10 | 10/10 | 82.8 | 15.0 |

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

## E6 disturbance type x boundary

| type | class | n | R1 empty | mean T_impact | mean |R1| | mean |Cl| | mean Cl/alive | R2 covers R1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `corridor_block` | B | 50 | 50/50 | 0.0 | 0.0 | 64.4 | 0.921 | 50/50 |
  repair `corridor_block`: R2 feas 50/50
| `corridor_slowdown` | B | 50 | 50/50 | 0.0 | 0.0 | 64.4 | 0.921 | 50/50 |
  repair `corridor_slowdown`: R2 feas 37/50
| `agv_breakdown` | A | 50 | 0/50 | 6.7 | 31.1 | 60.6 | 0.851 | 50/50 |
| `ra_failure` | A | 50 | 0/50 | 12.3 | 42.8 | 65.9 | 0.938 | 50/50 |
