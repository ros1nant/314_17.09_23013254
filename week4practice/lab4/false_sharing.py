import numpy as np
from numba import njit

from common import aligned_counters, memory_load, memory_store, save_csv, team, timed


@njit(nogil=True)
def shared_counter(counters, index, iterations):
    for _ in range(iterations):
        memory_store(counters, index, memory_load(counters, index) + 1)


@njit(nogil=True, cache=True)
def local_counter(counters, index, iterations):
    count = 0
    for _ in range(iterations):
        count += 1
    counters[index] = count  # LLVM may replace the entire local loop with iterations.


def benchmark(p, stride, iterations, local=False):
    counters = aligned_counters(p, stride)
    kernel = local_counter if local else shared_counter
    seconds, _ = timed(team, p, lambda rank: kernel(counters, rank * stride, iterations))
    assert np.all(counters[::stride] == iterations)
    return seconds, counters.ctypes.data % 64


def run(out, full):
    iterations = 100_000_000 if full else 100_000
    benchmark(2, 1, 10)
    benchmark(2, 8, 10, True)
    # Save evidence that memory operations survived compilation.
    llvm = shared_counter.inspect_llvm(shared_counter.signatures[0])
    assert 'load atomic' in llvm and 'store atomic' in llvm
    (out / 'memory_kernel.ll').write_text(llvm, encoding='utf-8')
    (out / 'memory_kernel.asm').write_text(
        shared_counter.inspect_asm(shared_counter.signatures[0]), encoding='utf-8')
    rows = []
    for p in (1, 2, 4, 8, 16):
        for trial in range(1, 4):
            variants = [('unpadded', 1, False), ('padded', 8, False), ('local', 8, True)]
            if trial % 2 == 0:
                variants.reverse()
            for variant, stride, local in variants:
                seconds, alignment = benchmark(p, stride, iterations, local)
                rows.append(dict(variant=variant, threads=p, trial=trial,
                                 iterations_per_thread=iterations, stride_bytes=stride * 8,
                                 base_mod_64=alignment, seconds=seconds))
    save_csv(out / 'timings.csv', rows)
