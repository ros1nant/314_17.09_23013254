
# TASK 1: AMDAHL'S LAW

## Q1.1
The inflection point is p* = 4 workers. Execution time improves until 4 workers (0.8673s), but degrades at 8 workers (0.9505s). This is caused by multiprocessing overhead, resource contention, and CPU scheduling. The system reports 20 logical cores, but the exact physical core topology is not verified.

## Q1.2
T(1) = 2.1583s, T(4) = 0.8673s.

S(4) = 2.1583 / 0.8673 = 2.48865

2.48865 = 1 / [(1-P) + P/4]

1/2.48865 = 1 - 0.75P

P = (1 - 0.40182) / 0.75

P = 0.79757 = 79.76%

## Q1.3
S_max = 1 / (1-P)

S_max = 1 / (1 - 0.79757)

S_max = 4.94x

Even with 128 cores, the theoretical speedup is limited to approximately 4.94x because of the serial fraction of the workload.

# TASK 2: FALSE SHARING

## Q2.1
A 64-bit pointer occupies 8 bytes. A 64-byte cache line contains 64/8 = 8 references. A stride of 16 means 16 × 8 = 128 bytes between references, which is greater than 64 bytes. Therefore, the references are separated by at least two cache-line widths in a contiguous reference array. Python lists store references to objects, so actual cache behavior is more complex.

## Q2.2
When Core 0 writes to index 0, it obtains exclusive ownership of the cache line, changing it to Modified (M). When Core 1 writes to index 1 on the same line, it requests ownership and invalidates Core 0's copy. Core 0 transitions to Invalid (I), and Core 1 can modify the line. Repeated writes cause cache-line ownership transfers and coherence traffic.

## Q2.3
1. C++11 alignas(64) aligns data to a cache-line boundary and, with appropriate padding, helps prevent false sharing.
2. Java @Contended adds VM-managed padding around fields or classes to reduce false sharing.

# TASK 3: SYNCHRONIZATION

## Q3.1
My UnsafeCounter returned 2,000,000, so no corruption was observed in the provided runs. In a native implementation, an increment consists of LOAD, ADD, and STORE. Overlapping operations can cause lost updates when two threads read the same value. CPython's GIL affects this experiment, so the result does not prove general thread safety.

LockedCounter took 0.2709s, while UnsafeCounter took 0.0966s. The measured contention multiplier was 2.80x.

## Q3.2
A lockless Map-Reduce design uses thread-local accumulation buffers. Each thread writes only to its own result slot, and the main thread sums the results after all threads finish.

The final result is deterministically 2,000,000. The lockless execution time and verified speedup were not measured in the provided terminal log.

Speedup = Locked Time / Lockless Time

The assignment requires at least 2.0x speedup, which must be verified experimentally.

## Q3.3
Thread-local accumulation eliminates shared mutable state and avoids lock acquisition for every increment. This reduces serialization, contention, and synchronization overhead. A final reduction combines the partial results after the threads finish. This approach can scale better than repeatedly optimizing a shared lock.

# TASK 4: ROOFLINE ANALYSIS

## Q4.1
The compute-bound workload remained approximately stable:
1 worker = 1.3217s
2 workers = 1.2037s
4 workers = 1.3366s

The memory-bound workload degraded:
1 worker = 1.0726s
2 workers = 1.1318s
4 workers = 1.8487s

The memory workload likely experiences memory-bandwidth contention and increased memory subsystem pressure. Additional workers do not necessarily improve performance when the memory system is saturated.

## Q4.2
The exact laptop CPU and RAM specifications were not included in the terminal log, so the theoretical peak memory bandwidth cannot be verified.

Bandwidth formula:

Bandwidth = Transfer Rate × Bus Width / 8

For DDR4-3200 dual-channel memory:

Bandwidth = 3200 × 64 × 2 / 8 = 51.2 GB/s

This is only an example. Shared memory bandwidth limits scalability when multiple cores compete for the same memory resources.

## Q4.3
If the embedding pipeline is memory-bandwidth saturated, adding more CPU OpenMP threads may not improve performance and can increase contention. CUDA may offer higher memory bandwidth and parallelism, but the actual benefit depends on GPU bandwidth, data transfers, and memory access patterns. I would profile the workload first and choose the architecture based on the measured bottleneck.
