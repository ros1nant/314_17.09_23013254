"""Small correctness checks for boundaries, dependency ordering and cancellation."""
import numpy as np

from lab2.pi_reduction import race, serial
from lab3.scheduling import render, render_rows
from lab4.false_sharing import benchmark
from lab5.merge_sort import parallel, sequential
from lab6.pipeline import blur, pipeline


def main():
    for n in (1, 2, 7, 63, 129):
        data = np.random.default_rng(n).integers(-5, 6, n, dtype=np.int64)
        for cutoff in (1, 3, n + 1):
            for workers in (1, 3):
                result = data.copy()
                parallel(result, np.empty_like(result), cutoff, workers)
                assert np.array_equal(result, np.sort(data))
            result = data.copy()
            sequential(result, np.empty_like(result), 0, n, cutoff)
            assert np.array_equal(result, np.sort(data))
    empty = np.array([], dtype=np.int64)
    parallel(empty, np.empty_like(empty), 1, 1)
    reference = np.empty((7, 11), dtype=np.int32)
    render_rows(reference, 0, 7, 31)
    for policy in ('static', 'dynamic', 'guided'):
        for chunk in (1, 3, 256):
            image, counts = render(11, 7, 31, 4, chunk, policy)
            assert np.array_equal(image, reference)
            assert sum(r for r, w in counts) == 7
    assert abs(race(1000, 1) - serial(1000)) < 1e-12
    for stride in (1, 8):
        benchmark(4, stride, 1000)
    frame = np.zeros((5, 5))
    frame[2, 2] = 16.0
    expected = np.zeros((5, 5))
    expected[1:4, 1:4] = [[1, 2, 1], [2, 4, 2], [1, 2, 1]]
    assert np.array_equal(blur(frame, 1), expected)
    _, records, _, _ = pipeline([], 1, 1)
    assert records == []
    # Invalid input must cancel all stages instead of deadlocking on a full queue.
    try:
        pipeline([None], 1, 1)
    except AttributeError:
        pass
    else:
        raise AssertionError('Producer failure did not propagate')
    print('All edge-case checks passed.')


if __name__ == '__main__':
    main()
