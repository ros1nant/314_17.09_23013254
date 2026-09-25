# Week 4 practice - Python OpenMP paradigms

Student: **Ainabek Aisultan**  
Student ID: **230103254**

Implementations for all five labs and the bonus pipeline in
`OpenMP_Lab_Practice_Manual.pdf`. Run everything from this folder using Python;
no C compiler or Java installation is needed. Numba compiles compute functions to
native code. Existing `week4` work is independent of this folder.

## Run on your Windows laptop

Open a PowerShell terminal in `week4practice` (Python 3.10+ with compatible Numba):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --mode quick
```

Using the virtual environment's Python directly avoids PowerShell activation-policy
issues. If your current Python already has the requirements, simply run:

```powershell
python run.py --mode quick
```

After the quick run succeeds, collect the manual's full-size results:

```powershell
.\.venv\Scripts\python.exe run.py --mode full
```

Or run a single lab, e.g.:

```powershell
.\.venv\Scripts\python.exe run.py --mode full --lab 3
```

Full Lab 5 uses 5,000,000 integers even for K=1: almost ten million task submissions.
The queue is bounded to protect memory, but this configuration can take many minutes
or longer. Running labs separately lets you collect shorter experiments first.
Ctrl+C stops a run; completed CSVs remain and the session is marked interrupted.
The first run also takes time to compile the native functions.

On macOS/Linux use `python3 -m venv .venv`, then `.venv/bin/python` for these commands.

## What's included

| Folder | Tasks implemented | Full workload |
|---|---|---|
| lab1 | 10 team-order logs; P=1..64 sweep; CPU load and utilization samples | 10,000,000 square roots per worker |
| lab2 | Race, per-step lock, native serial and reduction; 5 trials; errors, speedup, efficiency | 100,000,000 integration steps; 1,000,000 for locks |
| lab3 | Static, dynamic and guided; 4x4 thread/chunk matrix; 3 trials; per-rank work and heatmaps | 1920x1080 pixels, 1,000 iterations |
| lab4 | Unpadded, 64-byte padded and local counters; P=1,2,4,8,16; 3 trials | 100,000,000 increments per worker |
| lab5 | Verified recursive task merge sort; all seven cutoff values; work/span estimates | 5,000,000 integers |
| lab6 | Bonus bounded-queue pipeline; blur workload/queue sweeps; latency, throughput, occupancy | 48 frames, 512x512 |

Quick mode retains the sweep values but reduces input sizes. It verifies execution,
not full-size performance. There is one measured trial per cutoff in Lab 5 and one
per pipeline configuration. The runner warms JIT kernels before timing and validates
results outside the measured regions. Use `python verify.py` for extra edge-case checks.

## Output and report

Each invocation creates a new `results/<timestamp>_<mode>/` directory containing:

- `session.json`: actual hardware, OS, runtime, parameters/mode and completion status.
- `lab*/timings.csv`: raw measurements; additional CSVs contain CPU samples, per-rank
  work, pipeline packet statistics and queue occupancy.
- `lab1/stdout_10_runs.txt`: ten fork-join output sequences.
- `lab2/scaling.csv`, `critical_overhead.csv`: derived metrics.
- PNG plots, `report.md`, and **`report.pdf`**: measurements plus all analytical answers.

`answers.md` contains the explanations used by the report generator. The report
identifies Ainabek Aisultan, student ID 230103254. The PDF includes hardware, methodology, results,
discussion and conclusions. To regenerate it after editing answers:

```powershell
python run.py --report-only "results\YOUR_RUN_FOLDER"
```

The submitted full run is in
[`results/20260925_090644_231163_full/`](results/20260925_090644_231163_full/).
Its session records successful completion of all six labs. Open its
[`report.pdf`](results/20260925_090644_231163_full/report.pdf) for the full report.
The source manual's submission checklist is documented here; this runner does not
commit or publish your work. Git includes source, requirements, answers, documentation,
and the completed full run's report, plots, raw data and metadata. Quick runs,
virtual environments, caches, compiler diagnostics and preview images stay local.
The Mandelbrot `.npy` file is retained so the report can be regenerated from saved data.

## Interpreting the measurements

Python threads execute the Numba `nogil` kernels concurrently. The per-step Python
lock experiment includes GIL and interpreter costs; its overhead is compared with
a Python serial baseline, and native serial timing is also available. The reduction
uses Numba's selected backend, recorded in `lab2/runtime.txt`. To explicitly request
OpenMP where installed, set `$env:NUMBA_THREADING_LAYER = "omp"` before running;
an unavailable backend will raise an error instead of being reported as OpenMP.
The runner sets Numba capacity to at least 16 before import, then sets the active
reduction thread count for each trial. The 64-thread lab uses ordinary OS threads.

The race uses separate relaxed atomic loads and stores with an unprotected ADD
between them. They preserve real memory traffic without an atomic RMW, so lost
updates remain possible. The same helper keeps the false-sharing counter loop from
being optimized away; generated LLVM and assembly are saved for inspection.
Its 64-byte layout is an explicit experiment assumption. Local accumulation may
optimize to one store and should not be interpreted as timing 100 million additions.

The custom static scheduler uses round-robin chunks, not contiguous blocks. Guided
is an illustrative policy. Merge sort uses one bounded thread executor and native
kernels, avoiding nested process pools. It models recursive dependencies but does
not implement OpenMP task stealing. Full K=1 still schedules the actual tiny tasks.

Open Task Manager > Performance > CPU > Change graph to > Logical processors during
Lab 1 for the manual's system-monitor observation. Automated samples are system-wide
and may miss very short workloads. Windows cache information comes from the OS API
and CIM; missing hardware fields should be filled from your system tools.

Lab 4's Linux-only profiler task is not applicable to Windows. On Linux with `perf`
installed and counters permitted, record a separate diagnostic run:

```bash
perf stat -e L1-dcache-load-misses,L1-dcache-store-misses -o perf_lab4.txt \
  .venv/bin/python run.py --mode full --lab 4
```

Some CPUs do not expose both events. Report that limitation rather than inventing
counts. Whole-process counters include Python/JIT work and all variants; they do
not isolate false sharing. Cache misses alone do not prove coherence traffic.

Runtime behavior is documented by [Numba](https://numba.readthedocs.io/en/stable/user/threading-layer.html).
The JVM question cites [OpenJDK JEP 142](https://openjdk.org/jeps/142) and
[HotSpot's flag definitions](https://github.com/openjdk/jdk/blob/master/src/hotspot/share/runtime/globals.hpp).
