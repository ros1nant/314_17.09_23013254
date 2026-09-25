import threading

import numpy as np
from numba import njit

from common import save_csv, team, timed


@njit(nogil=True, cache=True)
def render_rows(image, lo, hi, limit):
    height, width = image.shape
    work = 0
    for py in range(lo, hi):
        for px in range(width):
            x0 = (px - width / 2.0) * 4.0 / width
            y0 = (py - height / 2.0) * 4.0 / height
            x, y, count = 0.0, 0.0, 0
            while x * x + y * y <= 4.0 and count < limit:
                x, y = x * x - y * y + x0, 2.0 * x * y + y0
                count += 1
            image[py, px] = count
            work += count
    return work


def render(width, height, limit, p, chunk, policy):
    image = np.empty((height, width), dtype=np.int32)
    lock = threading.Lock()
    next_row = 0

    def worker(rank):
        nonlocal next_row
        work, rows = 0, 0
        if policy == 'static':
            for lo in range(rank * chunk, height, p * chunk):
                hi = min(lo + chunk, height)
                work += render_rows(image, lo, hi, limit)
                rows += hi - lo
        else:
            while True:
                with lock:
                    lo = next_row
                    if lo >= height:
                        break
                    size = chunk if policy == 'dynamic' else max(chunk, (height - lo + p - 1) // p)
                    hi = min(lo + size, height)
                    next_row = hi
                work += render_rows(image, lo, hi, limit)
                rows += hi - lo
        return rows, work
    counts = team(p, worker)
    return image, counts


def run(out, full):
    width, height, limit = (1920, 1080, 1000) if full else (128, 96, 100)
    reference = np.empty((height, width), dtype=np.int32)
    render_rows(reference, 0, height, limit)
    rows, profiles = [], []
    for policy in ('static', 'dynamic', 'guided'):
        for p in (2, 4, 8, 16):
            for chunk in (1, 16, 64, 256):
                for trial in range(1, 4):
                    seconds, (image, counts) = timed(render, width, height, limit, p, chunk, policy)
                    assert np.array_equal(image, reference)
                    assert sum(x[0] for x in counts) == height
                    assert sum(x[1] for x in counts) == int(reference.sum())
                    work = [x[1] for x in counts]
                    imbalance = (max(work) - min(work)) / (sum(work) / p)
                    row_work = [x[0] for x in counts]
                    row_imbalance = (max(row_work) - min(row_work)) / (height / p)
                    rows.append(dict(policy=policy, threads=p, chunk=chunk, trial=trial,
                                     width=width, height=height, max_iter=limit, seconds=seconds,
                                     work_imbalance=imbalance, row_imbalance=row_imbalance))
                    for rank, (count, iterations) in enumerate(counts):
                        profiles.append(dict(policy=policy, threads=p, chunk=chunk, trial=trial,
                                             rank=rank, rows=count, escape_iterations=iterations))
    save_csv(out / 'timings.csv', rows)
    save_csv(out / 'thread_work.csv', profiles)
    np.save(out / 'mandelbrot.npy', reference)
