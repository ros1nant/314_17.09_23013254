import math
import threading
import time

import psutil
from numba import njit

from common import save_csv, team, timed


@njit(nogil=True, cache=True)
def cpu_work(n):
    total = 0.0
    for i in range(n):
        total += math.sqrt(i + 1.0)
    return total


def run(out, full):
    cpu_work(10)  # Compile before timing.
    with (out / 'stdout_10_runs.txt').open('w', encoding='utf-8') as log:
        for trial in range(1, 11):
            log.write(f'Run {trial}: serial caller TID={threading.get_native_id()}\n')
            lock = threading.Lock()

            def identify(rank):
                time.sleep(0.001 * (rank % 3))
                line = f'Rank {rank}/4 | native TID={threading.get_native_id()}\n'
                with lock:
                    log.write(line)
            team(4, identify)
            log.write('All workers joined; serial caller resumes.\n\n')
    rows, samples = [], []
    n = 10_000_000 if full else 100_000
    for p in (1, 2, 4, 8, 16, 32, 64):
        for trial in range(1, 4):
            seconds, _ = timed(team, p, lambda rank: threading.get_native_id())
            rows.append(dict(variant='creation_join', threads=p, trial=trial,
                             iterations_per_thread=0, seconds=seconds, checksum=0))
        stop = threading.Event()

        def monitor():
            psutil.cpu_percent(percpu=True)
            while not stop.wait(0.1):
                for core, usage in enumerate(psutil.cpu_percent(percpu=True)):
                    samples.append(dict(threads=p, time=time.perf_counter(),
                                        logical_cpu=core, utilization_percent=usage))
        watcher = threading.Thread(target=monitor)
        watcher.start()
        try:
            seconds, values = timed(team, p, lambda rank: cpu_work(n))
        finally:
            stop.set()
            watcher.join()
        assert len(values) == p and all(v == values[0] for v in values)
        rows.append(dict(variant='cpu_work', threads=p, trial=1,
                         iterations_per_thread=n, seconds=seconds, checksum=sum(values)))
    save_csv(out / 'timings.csv', rows)
    save_csv(out / 'cpu_utilization.csv', samples)
    (out / 'monitor_notes.txt').write_text(
        'CPU samples are system-wide per logical CPU, every ~100 ms. Short runs may '
        'finish before a sample. Open Task Manager > Performance > CPU > Logical '
        'processors during a full run for the manual observation. CPU workload is '
        'fixed per worker, so its total work grows with P. Rank 0 is a worker, not '
        'the original serial caller.\n', encoding='utf-8')
