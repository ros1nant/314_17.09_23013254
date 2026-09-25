import math
import threading

import numpy as np
from numba import njit, prange, set_num_threads, threading_layer

from common import memory_load, memory_store, save_csv, team, timed


@njit(nogil=True, cache=True)
def serial(n):
    total = 0.0
    for i in range(n):
        x = (i + 0.5) / n
        total += 4.0 / (1.0 + x * x)
    return total / n


@njit(parallel=True, cache=True)
def reduction(n):
    total = 0.0
    for i in prange(n):
        x = (i + 0.5) / n
        total += 4.0 / (1.0 + x * x)
    return total / n


@njit(nogil=True)
def race_worker(shared, lo, hi, n):
    for i in range(lo, hi):
        x = (i + 0.5) / n
        old = memory_load(shared, 0)
        memory_store(shared, 0, old + 4.0 / (1.0 + x * x))


def race(n, p):
    shared = np.zeros(1)
    team(p, lambda rank: race_worker(shared, n * rank // p, n * (rank + 1) // p, n))
    return shared[0] / n


def python_sum(n):
    total = 0.0
    for i in range(n):
        x = (i + 0.5) / n
        total += 4.0 / (1.0 + x * x)
    return total / n


def critical(n, p):
    total = [0.0]
    lock = threading.Lock()

    def worker(rank):
        for i in range(n * rank // p, n * (rank + 1) // p):
            x = (i + 0.5) / n
            term = 4.0 / (1.0 + x * x)
            with lock:
                total[0] += term
    team(p, worker)
    return total[0] / n


def run(out, full):
    n = 100_000_000 if full else 200_000
    lock_n = 1_000_000 if full else 10_000
    serial(100)
    set_num_threads(1)
    reduction(100)
    race(100, 2)
    critical(100, 2)
    rows = []

    def measure(variant, p, size, function, *args):
        for trial in range(1, 6):
            seconds, value = timed(function, *args)
            if variant != 'race' or p == 1:
                assert abs(value - math.pi) < 1e-7, (variant, value)
            rows.append(dict(variant=variant, threads=p, n=size, trial=trial,
                             seconds=seconds, pi=value, absolute_error=abs(value - math.pi)))
    measure('serial_native', 1, n, serial, n)
    for p in (1, 2, 4, 8):
        measure('race', p, n, race, n, p)
    measure('serial_python', 1, lock_n, python_sum, lock_n)
    measure('serial_native_lock_n', 1, lock_n, serial, lock_n)
    for p in (1, 2, 4, 8):
        measure('critical_python', p, lock_n, critical, lock_n, p)
    for p in (1, 2, 4, 8, 16):
        set_num_threads(p)
        reduction(100)  # Team warm-up, not a retained trial.
        measure('reduction', p, n, reduction, n)
    save_csv(out / 'timings.csv', rows)
    (out / 'runtime.txt').write_text(f'Numba threading layer: {threading_layer()}\n', encoding='utf-8')
