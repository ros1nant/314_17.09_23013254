from collections import deque
from concurrent.futures import ThreadPoolExecutor
import math
import os

import numpy as np
from numba import njit

from common import save_csv, timed


@njit(nogil=True, cache=True)
def merge(data, scratch, lo, mid, hi):
    i, j = lo, mid
    for k in range(lo, hi):
        if i < mid and (j >= hi or data[i] <= data[j]):
            scratch[k] = data[i]
            i += 1
        else:
            scratch[k] = data[j]
            j += 1
    data[lo:hi] = scratch[lo:hi]


@njit(nogil=True, cache=True)
def leaf_sort(data, lo, hi):
    data[lo:hi].sort()


@njit(nogil=True, cache=True)
def sequential(data, scratch, lo, hi, cutoff):
    if hi - lo <= cutoff:
        leaf_sort(data, lo, hi)
        return
    mid = (lo + hi) // 2
    sequential(data, scratch, lo, mid, cutoff)
    sequential(data, scratch, mid, hi, cutoff)
    merge(data, scratch, lo, mid, hi)


def leaves(lo, hi, cutoff, depth=0):
    if hi - lo <= cutoff:
        yield lo, hi, depth
    else:
        mid = (lo + hi) // 2
        yield from leaves(lo, mid, cutoff, depth + 1)
        yield from leaves(mid, hi, cutoff, depth + 1)


def parallel(data, scratch, cutoff, workers):
    """A lazy recursive DAG with O(workers + log N) retained futures.

    Only the coordinator waits for dependencies. Workers never wait for other
    workers, so even K=1 cannot deadlock or create unbounded nested pools.
    This is a shared FIFO executor, not an OpenMP work-stealing implementation.
    """
    pending, stack = deque(), []
    task_count = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        def consume():
            nonlocal task_count
            lo, hi, depth, future = pending.popleft()
            future.result()
            while stack and stack[-1][2] == depth:
                left_lo, left_hi, _, left_future = stack.pop()
                assert left_hi == lo
                left_future.result()
                future.result()
                future = pool.submit(merge, data, scratch, left_lo, lo, hi)
                task_count += 1
                lo, depth = left_lo, depth - 1
            stack.append((lo, hi, depth, future))

        for lo, hi, depth in leaves(0, len(data), cutoff):
            pending.append((lo, hi, depth, pool.submit(leaf_sort, data, lo, hi)))
            task_count += 1
            if len(pending) >= 2 * workers:
                consume()
        while pending:
            consume()
        assert len(stack) == 1
        stack[0][3].result()
    return task_count


def work_span(n, cutoff):
    """Unit-operation model, not measured seconds; sequential leaves cost m log2 m."""
    if n <= cutoff:
        cost = n * math.log2(max(2, n))
        return cost, cost
    wl, sl = work_span(n // 2, cutoff)
    wr, sr = work_span(n - n // 2, cutoff)
    return wl + wr + n, max(sl, sr) + n


def run(out, full):
    n = 5_000_000 if full else 2048
    workers = min(8, os.cpu_count() or 1)
    tiny = np.array([3, 1, 2], dtype=np.int64)
    sequential(tiny.copy(), np.empty_like(tiny), 0, 3, 1)
    parallel(tiny.copy(), np.empty_like(tiny), 1, 2)
    source = np.random.default_rng(42).integers(0, 10_000_000, n, dtype=np.int64)
    expected = np.sort(source)
    rows = []
    for cutoff in (1, 10, 100, 1000, 10000, 50000, 100000):
        print(f'  Merge sort: N={n:,}, cutoff={cutoff:,}', flush=True)
        work, span = work_span(n, cutoff)
        for variant in ('sequential', 'parallel'):
            data, scratch = source.copy(), np.empty_like(source)
            if variant == 'sequential':
                seconds, _ = timed(sequential, data, scratch, 0, n, cutoff)
                tasks = 0
            else:
                seconds, tasks = timed(parallel, data, scratch, cutoff, workers)
            assert np.array_equal(data, expected), (variant, cutoff)
            rows.append(dict(variant=variant, n=n, cutoff=cutoff, threads=workers if variant == 'parallel' else 1,
                             trial=1, seconds=seconds, tasks=tasks, model_work=work,
                             model_span=span, model_parallelism=work / span))
        save_csv(out / 'timings.csv', rows)  # Preserve completed cutoffs during long full runs.
