"""Run from this folder: python run.py --mode quick (or --mode full)."""
import argparse
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

# Set the pool capacity BEFORE importing Numba; required sweeps include 16 workers.
os.environ.setdefault('NUMBA_NUM_THREADS', str(max(16, os.cpu_count() or 1)))
import matplotlib
import numba
import numpy as np
import psutil

LABS = {1: 'lab1.fork_join', 2: 'lab2.pi_reduction', 3: 'lab3.scheduling',
        4: 'lab4.false_sharing', 5: 'lab5.merge_sort', 6: 'lab6.pipeline'}
ROOT = Path(__file__).resolve().parent


def hardware():
    info = dict(cpu=platform.processor(), physical_cores=psutil.cpu_count(logical=False),
                logical_cpus=psutil.cpu_count(), ram_bytes=psutil.virtual_memory().total,
                os=platform.platform(), python=sys.version, numpy=np.__version__,
                numba=numba.__version__, matplotlib=matplotlib.__version__,
                numba_pool_capacity=numba.config.NUMBA_NUM_THREADS,
                timer='time.perf_counter', timer_resolution_seconds=__import__('time').get_clock_info('perf_counter').resolution,
                cache_info='Not automatically available; record L1/L2/L3 from system tools.',
                environment={key: os.environ.get(key) for key in
                             ('NUMBA_NUM_THREADS', 'NUMBA_THREADING_LAYER', 'OMP_NUM_THREADS')})
    if os.name == 'nt':
        command = ('Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,'
                   'NumberOfLogicalProcessors,L2CacheSize,L3CacheSize | ConvertTo-Json -Compress')
        result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            info['windows_processor_kib'] = json.loads(result.stdout)
        # GetLogicalProcessorInformation exposes cache descriptors, including L1.
        import ctypes as ct
        from ctypes import wintypes as wt

        class Cache(ct.Structure):
            _fields_ = [('level', ct.c_ubyte), ('associativity', ct.c_ubyte),
                        ('line_bytes', ct.c_ushort), ('size_bytes', wt.DWORD), ('type', ct.c_int)]

        class Detail(ct.Union):
            _fields_ = [('cache', Cache), ('reserved', ct.c_ulonglong * 2)]

        class Entry(ct.Structure):
            _fields_ = [('mask', ct.c_size_t), ('relationship', ct.c_int), ('detail', Detail)]

        api = ct.windll.kernel32.GetLogicalProcessorInformation
        length = wt.DWORD(0)
        api(None, ct.byref(length))
        buffer = ct.create_string_buffer(length.value)
        if api(buffer, ct.byref(length)):
            entries = ct.cast(buffer, ct.POINTER(Entry))
            caches = []
            for i in range(length.value // ct.sizeof(Entry)):
                entry = entries[i]
                if entry.relationship == 2:
                    cache = entry.detail.cache
                    caches.append(dict(level=cache.level, bytes=cache.size_bytes,
                                       line_bytes=cache.line_bytes, type=cache.type,
                                       logical_cpu_mask=entry.mask))
            info['cache_info'] = caches
            info['cache_type_key'] = {'0': 'unified', '1': 'instruction', '2': 'data', '3': 'trace'}
    elif platform.system() == 'Linux':
        result = subprocess.run(['lscpu', '--json'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            info['cache_info'] = json.loads(result.stdout)
    elif platform.system() == 'Darwin':
        result = subprocess.run(['sysctl', 'machdep.cpu.brand_string', 'hw.l1dcachesize',
                                 'hw.l1icachesize', 'hw.l2cachesize', 'hw.l3cachesize'],
                                capture_output=True, text=True, timeout=10)
        info['cache_info'] = result.stdout or info['cache_info']
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['quick', 'full'], default='quick')
    parser.add_argument('--lab', choices=['all', '1', '2', '3', '4', '5', '6'], default='all')
    parser.add_argument('--report-only', type=Path, help='Regenerate report for an existing run directory')
    args = parser.parse_args()
    from reporting import build_report
    if args.report_only:
        build_report(args.report_only.resolve())
        return
    if numba.config.NUMBA_NUM_THREADS < 16:
        parser.error('NUMBA_NUM_THREADS must be at least 16; remove that environment override or set it to 16.')
    run_dir = ROOT / 'results' / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + args.mode)
    run_dir.mkdir(parents=True)
    metadata = dict(student_name='Ainabek Aisultan', student_id='230103254',
                    mode=args.mode, requested_lab=args.lab, started=datetime.now().astimezone().isoformat(),
                    status='running', completed_labs=[], hardware=hardware())
    metadata_path = run_dir / 'session.json'
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f'Output: {run_dir}', flush=True)
    if args.mode == 'full':
        print('Full Lab 5 with K=1 submits millions of tasks and can take a long time.\n'
              'Run individual labs with --lab 1 ... --lab 6 if preferred.', flush=True)
    try:
        for number in LABS:
            if args.lab != 'all' and int(args.lab) != number:
                continue
            print(f'Running lab {number} ({args.mode})...', flush=True)
            out = run_dir / f'lab{number}'
            out.mkdir()
            importlib.import_module(LABS[number]).run(out, args.mode == 'full')
            metadata['completed_labs'].append(number)
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        metadata['status'] = 'complete'
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        build_report(run_dir)
    except BaseException as error:
        metadata['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        metadata['error'] = repr(error)
        raise
    finally:
        metadata['finished'] = datetime.now().astimezone().isoformat()
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f'Done. Open {run_dir / "report.pdf"}', flush=True)


if __name__ == '__main__':
    main()
