# Analytical answers

Student: **Ainabek Aisultan**  
Student ID: **230103254**

These explanations accompany the executable experiments. Numerical conclusions
come from each run's generated report, not assumed benchmark outcomes.

## Lab 1

**1.1 Scheduling.** The OS scheduler selects runnable kernel threads based on
priority, CPU availability, interrupts and time slices. Cores execute independently;
wake-up times and output-lock acquisition determine print order. The barrier makes
all ranks participate but does not prescribe their order after release. Ten runs
can occasionally show the same order; nondeterminism does not require a different
permutation every time. Superscalar execution does not itself choose OS thread ranks.

**1.2 Oversubscription.** More runnable threads than execution resources can cause
preemption and context switches, saving/restoring register state and scheduler
bookkeeping. Migrating work can lose cache and TLB locality, while competing working
sets can evict one another. SMT may help hide some stalls, and sleeping threads need
not cause oversubscription costs. Lab 1's square-root workload is fixed per thread,
so total work grows with P; this is not a fixed-work strong-scaling experiment.

**1.3 Barriers.** A join waits for all workers before the caller consumes their
results. OpenMP's implicit barrier also provides the required memory synchronization.
Without the corresponding ordering, subsequent code can read unfinished data or
release storage still in use. A barrier is not a lock protecting updates inside the
region. Here rank zero is an executor worker, not the caller as in an OpenMP team.

**1.4 Thread types.** A hardware thread is an architectural execution context on a
core, with registers but often shared execution units and caches. A kernel thread
is an OS-scheduled software entity mapped onto hardware contexts. A green or virtual
thread is scheduled by a language runtime onto a smaller set of kernel threads.
Many virtual threads do not create additional CPU execution units.

## Lab 2

**2.1 Lost updates.** If two threads load accumulator A=10, compute A+2 and A+3,
and store 12 and 13, the final value is 13 instead of 15. Cache coherence can correctly
order both stores without making the whole LOAD/ADD/STORE transaction atomic. The
race kernel uses separate relaxed atomic loads and stores to prevent compiler
hoisting and undefined ordinary concurrent accesses; the overall update still loses
contributions. More contenders offer more opportunities for overlap, but error is
not guaranteed to grow monotonically with P or repeat identically between runs.

**2.2 Reduction trees.** Private sums allow most arithmetic to run independently.
A balanced combine tree has P-1 additions in total but only ceil(log2(P)) dependent
stages. A centralized lock orders P partial updates, or N updates when used per
integration step. A reduction implementation may use a different final combine
strategy; this experiment does not prove that Numba uses a binary tree. Floating
point addition is not associative, so small correct-result differences are expected.

**2.3 Amdahl.** S(P)=1/(0.05+0.95/P), so the infinite-processor limit is 20.
Earlier flattening can arise from runtime overhead, barriers, load imbalance,
shared execution resources, frequency changes and memory bandwidth, depending on
the kernel. Those are possible causes, not measurements of this particular run.
Reported strong-scaling speedup uses the one-thread reduction time as T(1).

**2.4 Atomics.** A hardware atomic read-modify-write maintains exclusive ownership
while applying an indivisible update. On common x86 cacheable aligned operands,
locked instructions usually use cache coherence rather than locking an entire
external bus. LL/SC architectures can reserve a location and retry if an intervening
write invalidates the reservation. Ordering guarantees depend on the instruction
and memory order. Separate atomic LOAD and STORE operations do not form an atomic
ADD. The Python critical variant also includes interpreter/GIL and lock overhead;
its comparison with Python serial is more comparable than with native serial, but
neither isolates hardware lock contention alone.

## Lab 3

**3.1 Small chunks.** A dynamic scheduler must claim each chunk from a shared
counter or queue. Fine chunks increase lock acquisition, ownership transfers and
dispatch frequency. Here the contested software state is the next-row counter
under a Python lock; GIL and Python/native transitions also contribute. On native
implementations the cache line containing that counter can become the hardware
coherence hotspot. A chunk of one can still win when imbalance dominates; equal
iteration counts do not guarantee equal execution time.

**3.2 Spatial imbalance.** Rows near the real axis intersect more of the Mandelbrot
interior and run many pixels up to the iteration cap. In contiguous block static
scheduling, ranks owning those middle rows often finish last. The implemented
static(chunk) assigns chunks round-robin, so straggler ranks depend on chunk size
and cannot always be called the middle ranks. thread_work.csv identifies them from
actual escape-iteration counts. The report records both row-count imbalance and
escape-work imbalance as (maximum-minimum)/mean, including idle workers.

**3.3 Guided.** Guided scheduling repeatedly chooses a chunk proportional to the
remaining work divided by the team size, subject to a minimum chunk C. The example
uses max(C, ceil(remaining/P)); its final chunk can be smaller. Chunk sizes shrink
as work is claimed. OpenMP implementations can use different permitted details;
this Python policy demonstrates the mechanism rather than reproducing a runtime.

**3.4 Choosing a schedule.** Static is a useful starting point for uniform work and
predictable locality. Dynamic suits unpredictable per-iteration costs when work per
chunk is large enough to amortize dispatch. Guided often balances irregular work
with fewer initial claims, but can retain imbalance if costly work is concentrated
in the first large chunks. Sweep chunk sizes and measure both time and work.

## Lab 4

**4.1 MESI.** A 64-byte line can contain eight 8-byte counters. Four example counters
and the rest of that line look like:

```text
byte:  0       8       16      24      32                     63
       [ C0  ][ C1  ][ C2  ][ C3  ][ unused / other values    ]

Event                           Core 0       Core 1
Neither core has line             I            I
Core 0 reads line alone           E            I
Core 1 reads same line            S            S
Core 0 writes C0                  M            I
Core 1 writes C1                  I            M
Core 0 writes C0 again            M            I
```

This is a simplified MESI trace; real processors may use MESIF/MOESI variants.
Ownership changes apply to the entire line even though different counters are
modified. Modified data can be transferred between caches; each transfer need
not write all the way back to DRAM.

**4.2 Bouncing.** Writers on different cores repeatedly request exclusive ownership
of the same line. Coherence interconnect latency, invalidations and cache-to-cache
transfers limit progress. More cores can increase that traffic enough to make the
per-worker workload slower. Placement, SMT and timing overhead can change the
observed curve, so a slowdown is not guaranteed. The experiment aligns its base to
64 bytes and separates padded counters by 64 bytes. Confirm this assumption against
the reported hardware line size. Local accumulation writes only once; the compiler
can even replace the simple local increment loop with its final count.

**4.3 True versus false sharing.** True sharing occurs when threads access the same
variable and at least one writes; correct updates can require synchronization.
False sharing occurs when independent variables occupy a common coherence block.
Padding removes the latter's accidental ownership conflict but cannot remove a
real shared-variable dependency.

**4.4 JVM padding.** HotSpot's @Contended asks the VM to isolate marked fields or
contention groups with layout padding. The current HotSpot default for
ContendedPaddingWidth is 128 bytes; it is configurable, not a universal JVM or
x86 requirement. Separation larger than one 64-byte line can also reduce effects
of adjacent-line prefetching. Padding trades memory footprint for isolation, and
ordinary user classes typically need -XX:-RestrictContended. The Python experiment
uses explicit array spacing, not this annotation. References: [OpenJDK JEP 142](https://openjdk.org/jeps/142)
and [HotSpot flag definitions](https://github.com/openjdk/jdk/blob/master/src/hotspot/share/runtime/globals.hpp).

## Lab 5

**5.1 Tiny tasks.** At K=1, a balanced decomposition has N leaves and N-1 merge
nodes: roughly 2N-1 tasks, or 9,999,999 tasks for N=5,000,000. Eager creation retains
many task objects, queue entries and stack frames, exhausting memory or spending
most time scheduling. Nested process pools make this much worse. This implementation
retains a bounded window of leaf tasks and a logarithmic merge stack in one pool.
It still submits every tiny task, so K=1 can take many minutes or longer. All cutoff
values are measured without silently substituting larger ones.

**5.2 Work stealing.** A typical work-stealing worker pushes and pops at its local
end of a deque to favor recent tasks and locality. An idle worker steals older work
from the opposite end, often obtaining a larger subtree. End names differ between
implementations; the important distinction is opposite ends and reduced contention
on local operations. Python ThreadPoolExecutor uses a shared work queue, not this
deque-per-worker algorithm. The coordinator waits for child futures before submitting
their merge; no worker waits on another worker in the same pool.

**5.3 Work and span.** With unit-size leaves and sequential merging,
W(N)=2W(N/2)+Theta(N)=Theta(N log N), while
S(N)=S(N/2)+Theta(N)=Theta(N). Thus W/S=Theta(log N), not Theta(N).
For powers of two with leaf cost 1 and merge cost N, W=N(1+log2 N),
S=2N-1 and parallelism=N(1+log2 N)/(2N-1). The CSV computes a corresponding
recurrence with sequential leaf cost m*log2(max(2,m)) at the chosen cutoff.
These are operation estimates, not measured seconds or predictions including the
Python coordinator. The root merge alone costs Theta(N). A parallel merge can
binary-search split positions in the opposite input, producing independent output
partitions, or use merge-path partitioning to shorten that serial dependency.

**5.4 Loops versus tasks.** Loop work sharing partitions a known iteration space,
typically with low per-chunk overhead. Tasks represent dependencies discovered as
the program runs and suit recursive sorting, tree traversal, graph exploration and
irregular DAGs. Their flexibility costs scheduling and dependency bookkeeping;
for regular small iterations a loop scheduler is usually simpler.

## Bonus pipeline

The producer copies frames into a bounded queue; the compute stage applies repeated
3x3 Gaussian blur; the consumer stores min, max, mean and sum. Sentinels propagate
normal shutdown. Exceptions set a cancellation event, and timed queue operations
let other stages exit rather than wait forever. Throughput is packets divided by
wall time. Packet latency begins before producer queue admission and includes queue
waiting. The slowest stage service capacity constrains steady-state throughput;
larger queues can absorb bursts but do not make that stage faster. The report lists
service times, packet latencies and sampled queue occupancy for each filter/queue
configuration. Because input/output are in memory, these data do not establish disk
I/O bottlenecks. Short quick runs can be dominated by thread startup and timing noise.

## Python runtime references

Native compute functions release the GIL using Numba's nogil option. Numba's
parallel reduction selects an available backend and records it in lab2/runtime.txt;
it is not necessarily OpenMP. See [Numba compilation options](https://numba.readthedocs.io/en/stable/user/jit.html)
and [Numba threading layers](https://numba.readthedocs.io/en/stable/user/threading-layer.html).
