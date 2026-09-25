import queue
import threading
import time

import numpy as np
from numba import njit

from common import save_csv


@njit(nogil=True, cache=True)
def blur(frame, passes):
    current = frame.copy()
    for _ in range(passes):
        target = current.copy()  # Keep edge pixels unchanged.
        for y in range(1, frame.shape[0] - 1):
            for x in range(1, frame.shape[1] - 1):
                target[y, x] = (current[y-1, x-1] + 2*current[y-1, x] + current[y-1, x+1]
                                + 2*current[y, x-1] + 4*current[y, x] + 2*current[y, x+1]
                                + current[y+1, x-1] + 2*current[y+1, x] + current[y+1, x+1]) / 16.0
        current = target
    return current


def pipeline(frames, passes, capacity):
    q1, q2 = queue.Queue(capacity), queue.Queue(capacity)
    stop, sentinel = threading.Event(), object()
    errors, records, occupancy = [], [], []
    service = [0.0, 0.0, 0.0]

    def put(q, item):
        while not stop.is_set():
            try:
                q.put(item, timeout=0.05)
                return
            except queue.Full:
                pass

    def get(q):
        while not stop.is_set():
            try:
                return q.get(timeout=0.05)
            except queue.Empty:
                pass
        return sentinel

    def producer():
        for index, frame in enumerate(frames):
            if stop.is_set():
                return
            start = time.perf_counter()
            packet = frame.copy()
            service[0] += time.perf_counter() - start
            put(q1, (index, start, packet))
        put(q1, sentinel)

    def compute():
        while True:
            item = get(q1)
            if item is sentinel:
                put(q2, sentinel)
                return
            index, created, frame = item
            start = time.perf_counter()
            filtered = blur(frame, passes)
            service[1] += time.perf_counter() - start
            put(q2, (index, created, filtered))

    def consumer():
        while True:
            item = get(q2)
            if item is sentinel:
                return
            index, created, frame = item
            start = time.perf_counter()
            records.append(dict(packet=index, minimum=float(frame.min()), maximum=float(frame.max()),
                                mean=float(frame.mean()), checksum=float(frame.sum()),
                                latency_seconds=time.perf_counter() - created))
            service[2] += time.perf_counter() - start

    def guarded(function):
        try:
            function()
        except BaseException as error:
            errors.append(error)
            stop.set()

    def monitor():
        while not stop.wait(0.001):
            occupancy.append(dict(time_seconds=time.perf_counter() - begin,
                                  queue1=q1.qsize(), queue2=q2.qsize()))

    begin = time.perf_counter()
    watcher = threading.Thread(target=monitor)
    workers = [threading.Thread(target=guarded, args=(f,)) for f in (producer, compute, consumer)]
    watcher.start()
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join()
    finally:
        stop.set()
        for worker in workers:
            worker.join()
        watcher.join()
    elapsed = time.perf_counter() - begin
    if errors:
        raise errors[0]
    assert len(records) == len(frames)
    return elapsed, records, occupancy, service


def run(out, full):
    blur(np.zeros((8, 8)), 1)
    count, size = (48, 512) if full else (12, 64)
    frames = np.random.default_rng(42).random((count, size, size))
    rows, packets, samples = [], [], []
    for capacity in (1, 4, 16):
        for passes in (1, 4, 16):
            elapsed, results, occupancy, service = pipeline(frames, passes, capacity)
            for row in results:
                expected = blur(frames[row['packet']], passes)
                for key, value in [('minimum', expected.min()), ('maximum', expected.max()),
                                   ('mean', expected.mean()), ('checksum', expected.sum())]:
                    assert np.isclose(row[key], value)
                packets.append(dict(capacity=capacity, passes=passes, **row))
            samples.extend(dict(capacity=capacity, passes=passes, **row) for row in occupancy)
            rows.append(dict(capacity=capacity, passes=passes, packets=count, frame_size=size,
                             seconds=elapsed, packets_per_second=count / elapsed,
                             mean_latency_seconds=float(np.mean([r['latency_seconds'] for r in results])),
                             producer_service_seconds=service[0], compute_service_seconds=service[1],
                             consumer_service_seconds=service[2],
                             busiest_service_stage=('producer', 'compute', 'consumer')[int(np.argmax(service))]))
    save_csv(out / 'timings.csv', rows)
    save_csv(out / 'packets.csv', packets)
    save_csv(out / 'queue_occupancy.csv', samples)
