"""Shared measurement helpers. Native kernels release CPython's GIL."""
import csv
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from llvmlite import ir
from numba import types
from numba.extending import intrinsic


def team(p, worker):
    """One OS thread per rank; barrier prevents executor reuse of one thread."""
    barrier = threading.Barrier(p)

    def entry(rank):
        barrier.wait()
        return worker(rank)

    with ThreadPoolExecutor(max_workers=p) as pool:
        futures = [pool.submit(entry, rank) for rank in range(p)]
        return [f.result() for f in futures]


def timed(function, *args):
    start = time.perf_counter()
    result = function(*args)
    return time.perf_counter() - start, result


def save_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def aligned_counters(p, stride):
    # Retain the owner through NumPy's base reference; begin on a 64-byte boundary.
    owner = np.zeros(p * stride + 8, dtype=np.int64)
    offset = ((-owner.ctypes.data) % 64) // 8
    return owner[offset:offset + p * stride]


@intrinsic
def memory_load(typing_context, array, index):
    """Relaxed atomic LOAD, not an atomic read-modify-write operation.

    Forces a real memory access even in an optimized loop. All callers use
    aligned int64/float64 arrays. Float values are transferred as 64-bit bits.
    """
    if not isinstance(array, types.Array) or array.dtype not in (types.int64, types.float64):
        raise TypeError('memory_load requires a 64-bit numeric array')
    signature = array.dtype(array, index)

    def codegen(context, builder, sig, args):
        ary = context.make_array(sig.args[0])(context, builder, args[0])
        pointer = builder.gep(ary.data, [args[1]])
        pointer = builder.bitcast(pointer, ir.IntType(64).as_pointer())
        bits = builder.load_atomic(pointer, 'monotonic', 8)
        return builder.bitcast(bits, context.get_value_type(sig.return_type))

    return signature, codegen


@intrinsic
def memory_store(typing_context, array, index, value):
    if not isinstance(array, types.Array) or array.dtype not in (types.int64, types.float64):
        raise TypeError('memory_store requires a 64-bit numeric array')
    signature = types.void(array, index, value)

    def codegen(context, builder, sig, args):
        ary = context.make_array(sig.args[0])(context, builder, args[0])
        pointer = builder.gep(ary.data, [args[1]])
        pointer = builder.bitcast(pointer, ir.IntType(64).as_pointer())
        bits = builder.bitcast(args[2], ir.IntType(64))
        builder.store_atomic(bits, pointer, 'monotonic', 8)
        return context.get_dummy_value()

    return signature, codegen
