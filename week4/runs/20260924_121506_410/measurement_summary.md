# Measured worksheet tables

Student: **Ainabek Aisultan**. Student ID: **230103254**.

Git URL: [https://github.com/ros1nant](https://github.com/ros1nant).

The original run used the last-four-digit input `3254`; raw logs preserve that value.
The full ID has the same final four digits and therefore the same workload.

N: **13,254,000**. Maximum steps: **688**. Checksum: **96515714**. Hits > 100: **10,684,763**.

All configurations returned matching maxima, checksums, and hit counts. Run 1 is discarded; each average uses runs 2 and 3 only.

Sequential baseline T_seq = **1.986500025 s**.

S_emp(2) = 1.986500025 / 1.488999963 = **1.334117**.

p = 2 * (1 - 1/S_emp(2)) = **0.500881003** (50.0881%).

## Table 1: OpenMP scaling

| k | Run 1 (discard) | Run 2 (s) | Run 3 (s) | Avg T_k (s) | S_emp | S_theo | Delta |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2.803000 | 2.814000 | 2.800000 | 2.807000 | 0.707695 | 1.000000 | 0.292305 |
| 2 | 1.482000 | 1.491000 | 1.487000 | 1.489000 | 1.334117 | 1.334117 | 0.000000 |
| 4 | 0.791000 | 0.796000 | 0.773000 | 0.784500 | 2.532186 | 1.601693 | -0.930493 |
| 8 | 0.443000 | 0.414000 | 0.446000 | 0.430000 | 4.619768 | 1.780217 | -2.839551 |
| 14 | 0.296000 | 0.280000 | 0.288000 | 0.284000 | 6.994717 | 1.869522 | -5.125196 |
| 16 | 0.267000 | 0.267000 | 0.260000 | 0.263500 | 7.538900 | 1.885284 | -5.653616 |
| 20 | 0.226000 | 0.241000 | 0.259000 | 0.250000 | 7.946000 | 1.907803 | -6.038197 |

S_emp(k) = T_seq / T_k; the OpenMP k=1 run is distinct from T_seq.

## Table 2: False sharing

| Variant | Threads | Avg time (s) | Throughput (iterations/s) |
|---|---:|---:|---:|
| naive | 14 | 0.330500 | 40102873.64 |
| reduction | 14 | 0.283000 | 46833923.50 |

Naive / reduction time ratio = **1.167845x**. A ratio above 1 means the naive version is slower.

The naive counters use volatile writes to preserve repeated memory accesses under -O2. The reduction also removes those memory accesses, so the ratio is not an isolated measurement of cache-coherence cost.

## Table 3: Scheduling

| Schedule | Threads | Run 1 (discard) | Run 2 (s) | Run 3 (s) | Avg time (s) |
|---|---:|---:|---:|---:|---:|
| static | 20 | 0.235000 | 0.233000 | 0.221000 | 0.227000 |
| static_1000 | 20 | 0.241000 | 0.229000 | 0.251000 | 0.240000 |
| dynamic_100 | 20 | 0.202000 | 0.197000 | 0.200000 | 0.198500 |
| dynamic_10000 | 20 | 0.199000 | 0.200000 | 0.199000 | 0.199500 |
| guided | 20 | 0.216000 | 0.196000 | 0.211000 | 0.203500 |

thread_profiles.csv contains separate diagnostic passes showing iterations, Collatz work and active loop time per thread. They are not benchmark repetitions and do not directly measure CPU utilization or hardware invalidations.

Q1-Q4 must be written using these measurements and hw_info.txt. A slowdown alone does not prove which hardware event caused it.
