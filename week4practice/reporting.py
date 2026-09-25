"""Generate derived CSV tables, 200-dpi plots, Markdown and a PDF report."""
import csv
from collections import defaultdict
import json
from pathlib import Path
import statistics
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from common import save_csv


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def means(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(float(row['seconds']))
    return {key: statistics.mean(values) for key, values in groups.items()}


def build_report(run_dir):
    meta = json.loads((run_dir / 'session.json').read_text(encoding='utf-8'))
    plots = []
    lines = ['OpenMP Paradigms - Python Practice Report',
             f'Mode: {meta["mode"]}; status: {meta["status"]}; started: {meta["started"]}',
             'Student name / ID: Ainabek Aisultan / 230103254.', '', 'I. System & Hardware Specifications',
             json.dumps(meta['hardware'], indent=2), '', 'II. Experimental Methodology',
             'Native kernels are JIT-compiled before their benchmark timers. Timings use perf_counter. '
             'Lab 1 team creation has 3 trials and CPU work has 1; Lab 2 has 5 trials; '
             'Labs 3 and 4 have 3; Labs 5 and 6 have 1 per configuration. '
             'Means retain all measured trials. Thread-based measurements include creation, barriers '
             'and joining. Numba reduction uses a warmed persistent pool. Sort input copies and '
             'correctness checks are outside timing; sort task creation and pool startup are inside. '
             'CPU utilization is system-wide, not process-only. Affinity, power and temperature are '
             'not controlled. Repeated measurements should be interpreted with their variability.',
             'Quick mode uses smaller inputs to validate the software. Full mode uses the manual sizes. '
             'A quick report is not evidence for the required full-size experiments.',
             'Python Lock timings include interpreter/GIL costs. Race and cache experiments use '
             'separate relaxed atomic loads/stores to preserve real memory accesses, but the combined '
             'read/add/write is not atomic. Custom schedulers and the sort executor emulate the '
             'patterns; they are not OpenMP scheduling or work stealing.', '', 'III. Empirical Results & Visualizations']

    def figure(name, draw):
        fig, ax = plt.subplots(figsize=(8, 5))
        draw(fig, ax)
        fig.tight_layout()
        path = run_dir / (name + '.png')
        fig.savefig(path, dpi=200)
        plots.append(path)
        plt.close(fig)

    for number in meta['completed_labs']:
        folder = run_dir / f'lab{number}'
        rows = read(folder / 'timings.csv')
        lines.extend(['', f'Lab {number}: {len(rows)} measured configurations/trials.',
                      f'Raw data: lab{number}/timings.csv'])
        grouping = {1: ['variant', 'threads'], 2: ['variant', 'threads', 'n'],
                    3: ['policy', 'threads', 'chunk'], 4: ['variant', 'threads'],
                    5: ['variant', 'cutoff'], 6: ['capacity', 'passes']}[number]
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(row[key] for key in grouping)].append(float(row['seconds']))
        table = []
        lines.append('Configuration | trials | mean seconds | sample standard deviation')
        for key, values in groups.items():
            mean = statistics.mean(values)
            deviation = statistics.stdev(values) if len(values) > 1 else None
            table.append(dict(zip(grouping, key), trials=len(values), mean_seconds=mean,
                              sample_stddev_seconds=deviation if deviation is not None else ''))
            spread = f'{deviation:.6g}' if deviation is not None else 'not estimated (one trial)'
            lines.append(f'{", ".join(key)} | {len(values)} | {mean:.6g} | {spread}')
        save_csv(folder / 'summary.csv', table)
        if number == 1:
            avg = means(rows, ['variant', 'threads'])
            def draw(fig, ax):
                for variant in ('creation_join', 'cpu_work'):
                    ps = sorted(int(k[1]) for k in avg if k[0] == variant)
                    ax.plot(ps, [avg[(variant, str(p))] for p in ps], 'o-', label=variant)
                ax.set(xlabel='OS threads', ylabel='Seconds', yscale='log', title='Fork-join and per-worker CPU workload')
                ax.legend()
            figure('lab1_teams', draw)
        elif number == 2:
            avg = means(rows, ['variant', 'threads'])
            base = avg[('reduction', '1')]
            summary = []
            for p in (1, 2, 4, 8, 16):
                seconds = avg[('reduction', str(p))]
                summary.append(dict(threads=p, mean_seconds=seconds,
                                    speedup=base / seconds, efficiency=base / seconds / p))
            save_csv(folder / 'scaling.csv', summary)
            for row in summary:
                lines.append(f'P={row["threads"]}: mean={row["mean_seconds"]:.6g}s, '
                             f'S={row["speedup"]:.4f}, E={row["efficiency"]:.4f}')
            overhead = []
            for p in (1, 2, 4, 8):
                seconds = avg[('critical_python', str(p))]
                overhead.append(dict(threads=p, critical_seconds=seconds,
                                     python_baseline_seconds=avg[('serial_python', '1')],
                                     overhead_vs_python_percent=100 * (seconds / avg[('serial_python', '1')] - 1),
                                     slowdown_vs_native=seconds / avg[('serial_native_lock_n', '1')]))
            save_csv(folder / 'critical_overhead.csv', overhead)
            for row in overhead:
                lines.append(f'Critical P={row["threads"]}: overhead vs Python serial '
                             f'{row["overhead_vs_python_percent"]:.2f}% (includes GIL, locks and team costs).')
            for p in (1, 2, 4, 8):
                subset = [r for r in rows if r['variant'] == 'race' and int(r['threads']) == p]
                lines.append(f'Race P={p}: mean absolute error='
                             f'{statistics.mean(float(r["absolute_error"]) for r in subset):.6g}; '
                             'individual Pi values are in the raw CSV.')
            def draw(fig, ax):
                ps = [r['threads'] for r in summary]
                ax.plot(ps, [r['speedup'] for r in summary], 'o-', label='Measured speedup')
                ax.plot(ps, ps, '--', label='Linear ideal')
                ax.set(xlabel='Threads', ylabel='Speedup T(1)/T(P)', title='Pi reduction strong scaling')
                ax.legend(loc='upper left')
                right = ax.twinx()
                right.plot(ps, [r['efficiency'] for r in summary], 's:', color='green', label='Efficiency')
                right.set_ylabel('Efficiency S(P)/P')
                right.legend(loc='lower right')
            figure('lab2_scaling', draw)
        elif number == 3:
            avg = means(rows, ['policy', 'threads', 'chunk'])
            for policy in ('static', 'dynamic', 'guided'):
                def draw(fig, ax, policy=policy):
                    values = [[avg[(policy, str(p), str(c))] for c in (1, 16, 64, 256)] for p in (2, 4, 8, 16)]
                    mesh = ax.imshow(values, aspect='auto')
                    ax.set(xticks=range(4), xticklabels=[1, 16, 64, 256], yticks=range(4),
                           yticklabels=[2, 4, 8, 16], xlabel='Chunk (rows)', ylabel='Threads', title=f'Mandelbrot: {policy}')
                    for y in range(4):
                        for x in range(4):
                            ax.text(x, y, f'{values[y][x]:.4f}', ha='center', color='white')
                    fig.colorbar(mesh, ax=ax, label='Mean seconds')
                figure('lab3_' + policy, draw)
            lines.append('Both row-count and escape-iteration imbalance are in timings.csv; '
                         'per-rank work is in thread_work.csv. Quick images have fewer rows than '
                         'some chunks, so those cells deliberately expose idle workers.')
            figure('lab3_mandelbrot', lambda fig, ax: ax.imshow(np.load(folder / 'mandelbrot.npy'), cmap='magma'))
        elif number == 4:
            avg = means(rows, ['variant', 'threads'])
            def draw(fig, ax):
                for variant in ('unpadded', 'padded', 'local'):
                    ps = [1, 2, 4, 8, 16]
                    ax.plot(ps, [avg[(variant, str(p))] for p in ps], 'o-', label=variant)
                ax.set(xlabel='Threads', ylabel='Mean seconds', title='Counter layout (fixed increments per thread)', yscale='log')
                ax.legend()
            figure('lab4_cache', draw)
            lines.append('The local increment loop can collapse to a single final store; '
                         'its time mainly measures team overhead. LLVM and assembly evidence '
                         'are saved for the memory kernel. A padded speedup is not guaranteed.')
        elif number == 5:
            def draw(fig, ax):
                for variant in ('sequential', 'parallel'):
                    subset = [r for r in rows if r['variant'] == variant]
                    ax.plot([int(r['cutoff']) for r in subset], [float(r['seconds']) for r in subset], 'o-', label=variant)
                ax.set(xscale='log', xlabel='Cutoff K (log scale)', ylabel='Seconds', title='Recursive merge sort cutoff sweep')
                ax.legend()
            figure('lab5_cutoff', draw)
            best = min((r for r in rows if r['variant'] == 'parallel'), key=lambda r: float(r['seconds']))
            lines.append(f'Fastest tested parallel cutoff in this run: K={best["cutoff"]}, '
                         f'{float(best["seconds"]):.6g}s. One trial does not establish a stable optimum. '
                         'Work/span values in CSV are unit-operation estimates, not measured time.')
        else:
            def draw(fig, ax):
                for capacity in (1, 4, 16):
                    subset = [r for r in rows if int(r['capacity']) == capacity]
                    ax.plot([int(r['passes']) for r in subset], [float(r['packets_per_second']) for r in subset], 'o-', label=f'Queue capacity {capacity}')
                ax.set(xlabel='Blur passes', ylabel='Packets/sec', title='Pipeline throughput')
                ax.legend()
            figure('lab6_pipeline', draw)
            for r in rows:
                lines.append(f'Capacity {r["capacity"]}, passes {r["passes"]}: '
                             f'{float(r["packets_per_second"]):.2f} packets/s; '
                             f'mean latency {float(r["mean_latency_seconds"]):.6g}s; '
                             f'largest measured service time: {r["busiest_service_stage"]}.')
            lines.append('Queue occupancy is sampled at ~1 ms and may miss peaks. '
                         'Service times exclude queue blocking. Frames originate in RAM and '
                         'output goes to a memory buffer; this run does not test disk I/O.')

    lines.extend(['', 'IV. Analytical & Discussion Responses',
                  (Path(__file__).parent / 'answers.md').read_text(encoding='utf-8'), '',
                  'V. Conclusions & Insights',
                  'Correctness is checked against numerical expectations, serial images, sorted '
                  'reference data and sequential pipeline statistics. Scaling depends on scheduling '
                  'cost, synchronization, memory placement and task size as well as core count. '
                  'Use the measured tables and plots to assess this run; theory does not guarantee '
                  'monotonic speedups or a particular optimum. Full mode is needed for the manual '
                  'workload sizes. On Windows, Linux perf counters are not applicable and were not measured.'])
    text = '\n\n'.join(lines)
    (run_dir / 'report.md').write_text(text + '\n\n' + '\n'.join(f'![{p.stem}]({p.name})' for p in plots), encoding='utf-8')
    # Text and plots in one portable PDF, using only Matplotlib (no office installation).
    wrapped = []
    for line in text.splitlines():
        wrapped.extend(textwrap.wrap(line, width=100, replace_whitespace=False) or [''])
    with PdfPages(run_dir / 'report.pdf') as pdf:
        for offset in range(0, len(wrapped), 62):
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.text(0.07, 0.95, '\n'.join(wrapped[offset:offset + 62]), va='top', fontsize=8, family='monospace')
            pdf.savefig(fig)
            plt.close(fig)
        for path in plots:
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.imshow(plt.imread(path))
            ax.axis('off')
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
