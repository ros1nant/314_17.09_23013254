
import random
import time
import threading
import multiprocessing as mp


# ============================================================
# CONFIGURATION
# ============================================================

PART1_ITERATIONS = 50_000_000
PART3_ITERATIONS = 100_000_000

THREADS_PART1 = 4
THREADS_PART2 = 4

# Shared variable for Part 1 and Part 2
total_hits = 0

# Lock for Part 2
hits_lock = threading.Lock()


# ============================================================
# HELPER FUNCTION
# ============================================================

def generate_point(random_generator):
    """Generate a random point in a 1x1 square."""
    x = random_generator.random()
    y = random_generator.random()

    return x * x + y * y <= 1.0


# ============================================================
# PART 1: THE PHANTOM BUG
# ============================================================

def unsafe_worker(iterations):
    """
    Worker using a shared variable without synchronization.

    Note:
    CPython's GIL can reduce the visibility of this data race.
    This is not guaranteed to behave like Java's totalHits++.
    """
    global total_hits

    rng = random.Random()

    for _ in range(iterations):
        if generate_point(rng):
            total_hits += 1


def run_part1():
    global total_hits

    print("\n" + "=" * 60)
    print("PART 1: THE PHANTOM BUG")
    print("=" * 60)

    iterations_per_thread = PART1_ITERATIONS // THREADS_PART1

    for run in range(1, 6):
        total_hits = 0
        workers = []

        start = time.perf_counter()

        for _ in range(THREADS_PART1):
            worker = threading.Thread(
                target=unsafe_worker,
                args=(iterations_per_thread,)
            )
            workers.append(worker)
            worker.start()

        for worker in workers:
            worker.join()

        end = time.perf_counter()

        total_iterations = iterations_per_thread * THREADS_PART1
        pi = 4.0 * total_hits / total_iterations
        runtime = end - start

        print(
            f"Run {run}: "
            f"Pi = {pi:.6f}, "
            f"Hits = {total_hits}, "
            f"Time = {runtime:.4f} s"
        )


# ============================================================
# PART 2: THE SYNCHRONIZATION TRAP
# ============================================================

def synchronized_worker(iterations):
    """Worker using a lock for every shared increment."""
    global total_hits

    rng = random.Random()

    for _ in range(iterations):
        if generate_point(rng):
            with hits_lock:
                total_hits += 1


def run_single_thread(iterations):
    """Plain single-threaded baseline."""
    rng = random.Random()
    hits = 0

    start = time.perf_counter()

    for _ in range(iterations):
        if generate_point(rng):
            hits += 1

    end = time.perf_counter()

    pi = 4.0 * hits / iterations
    runtime = end - start

    return pi, runtime


def run_synchronized():
    global total_hits

    print("\n" + "=" * 60)
    print("PART 2: THE SYNCHRONIZATION TRAP")
    print("=" * 60)

    # Single-threaded baseline
    single_pi, single_time = run_single_thread(PART1_ITERATIONS)

    print(
        f"Single-threaded: "
        f"Pi = {single_pi:.6f}, "
        f"Time = {single_time:.4f} s"
    )

    # Synchronized multithreading
    total_hits = 0
    workers = []

    iterations_per_thread = PART1_ITERATIONS // THREADS_PART2

    start = time.perf_counter()

    for _ in range(THREADS_PART2):
        worker = threading.Thread(
            target=synchronized_worker,
            args=(iterations_per_thread,)
        )
        workers.append(worker)
        worker.start()

    for worker in workers:
        worker.join()

    end = time.perf_counter()

    total_iterations = iterations_per_thread * THREADS_PART2
    pi = 4.0 * total_hits / total_iterations
    synchronized_time = end - start

    multiplier = synchronized_time / single_time

    print(
        f"Synchronized ({THREADS_PART2} threads): "
        f"Pi = {pi:.6f}, "
        f"Time = {synchronized_time:.4f} s"
    )

    print(f"Slowdown multiplier: {multiplier:.2f}x")


# ============================================================
# PART 3: OPENMP-STYLE REDUCTION
# ============================================================

def reduction_worker(iterations, result_queue):
    """
    Each process has its own local counter.
    Only the final partial sum is returned.
    """
    rng = random.Random()
    local_hits = 0

    for _ in range(iterations):
        if generate_point(rng):
            local_hits += 1

    result_queue.put(local_hits)


def run_reduction(processes, iterations):
    """Run Monte Carlo using local counters and reduction."""
    result_queue = mp.Queue()
    workers = []

    iterations_per_process = iterations // processes
    remaining = iterations % processes

    start = time.perf_counter()

    for i in range(processes):
        process_iterations = iterations_per_process

        if i == processes - 1:
            process_iterations += remaining

        process = mp.Process(
            target=reduction_worker,
            args=(process_iterations, result_queue)
        )

        workers.append(process)
        process.start()

    total_hits = 0

    for _ in range(processes):
        total_hits += result_queue.get()

    for process in workers:
        process.join()

    end = time.perf_counter()

    runtime = end - start
    pi = 4.0 * total_hits / iterations

    return pi, runtime


def run_part3():
    print("\n" + "=" * 60)
    print("PART 3: OPENMP-STYLE REDUCTION")
    print("=" * 60)

    process_counts = [1, 2, 4, 8, 16, 32]

    results = []

    print(
        f"{'Threads':<10}"
        f"{'Runtime (ms)':<18}"
        f"{'Speedup':<15}"
        f"{'Efficiency':<15}"
        f"{'Pi':<15}"
    )

    print("-" * 73)

    baseline_time = None

    for processes in process_counts:
        pi, runtime = run_reduction(
            processes,
            PART3_ITERATIONS
        )

        runtime_ms = runtime * 1000

        if baseline_time is None:
            baseline_time = runtime

        speedup = baseline_time / runtime
        efficiency = (speedup / processes) * 100

        results.append(
            (
                processes,
                runtime_ms,
                speedup,
                efficiency,
                pi
            )
        )

        print(
            f"{processes:<10}"
            f"{runtime_ms:<18.2f}"
            f"{speedup:<15.2f}x"
            f"{efficiency:<15.2f}%"
            f"{pi:<15.6f}"
        )

    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("Monte Carlo Pi Approximation")
    print(f"Part 1 and Part 2 iterations: {PART1_ITERATIONS:,}")
    print(f"Part 3 iterations: {PART3_ITERATIONS:,}")
    print(f"CPU cores reported by Python: {mp.cpu_count()}")

    run_part1()
    run_synchronized()
    run_part3()

    print("\nAll experiments completed.")