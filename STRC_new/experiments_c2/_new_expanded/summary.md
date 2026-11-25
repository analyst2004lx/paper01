# Expanded STRC matrix

## E1 miss

| instance | n | C1 pass | mean Cl | mean seeds |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10 | 10/10 | 15.7 | 5.7 |
| `congested_8x4x4` | 10 | 10/10 | 65.0 | 21.2 |
| `S8x4x4_high` | 10 | 10/10 | 94.9 | 14.8 |
| `S8x4x4_funnel` | 10 | 10/10 | 92.3 | 15.9 |
| `S8x4x4_mid` | 10 | 10/10 | 91.6 | 14.8 |

## E2 containment

| instance | E2a | E2b | feas |
|---|---:|---:|---:|
| `example_3x3x2` | 10/10 | 10/10 | 10/10 |
| `congested_8x4x4` | 10/10 | 9/10 | 9/10 |
| `S8x4x4_high` | 10/10 | 10/10 | 10/10 |
| `S8x4x4_funnel` | 10/10 | 9/10 | 9/10 |
| `S8x4x4_mid` | 10/10 | 9/10 | 9/10 |

## E3 boundary (no expand)

| instance | miss_B | R2 win | R1 feas | R2 feas |
|---|---:|---:|---:|---:|
| `example_3x3x2` | 10/10 | 10/10 | 0/10 | 10/10 |
| `congested_8x4x4` | 10/10 | 9/10 | 0/10 | 9/10 |
| `S8x4x4_high` | 10/10 | 10/10 | 0/10 | 10/10 |
| `S8x4x4_funnel` | 10/10 | 9/10 | 0/10 | 9/10 |
| `S8x4x4_mid` | 10/10 | 9/10 | 0/10 | 9/10 |
