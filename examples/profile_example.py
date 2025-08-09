#!/usr/bin/env python3
"""
Cache vs. No-Cache Performance Demo

A clear, real example comparing baseline provider access vs
DynamicPrefetchingCache across common access patterns.

Usage:
  python examples/profile_example.py [pattern] [--ops N]
  
  pattern: sequential, random, jumps, mixed, all (default: all)
  --ops:   number of operations per scenario (default: 2000)
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List
import subprocess
from statistics import mean
from tabulate import tabulate

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.dynamic_prefetching_cache import DynamicPrefetchingCache, DynamicDataPredictor, MOTDataProvider

NAVIGATION_STEPS = [-15, -5, -1, 1, 5, 15, 30]

def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = max(0, min(len(v) - 1, int(round((p / 100.0) * (len(v) - 1)))))
    return v[k]


class ApplicationProfiler:
    """Compare baseline provider vs. cached access for selected patterns."""
    
    def __init__(self, data_file: str = 'examples/data/ultra_dense_data.txt'):
        self.data_file = data_file
        self.results: Dict[str, Dict[str, float]] = {}
        
    def setup_system(self) -> tuple:
        """Ensure data exists and construct provider/predictor/cache."""
        if not Path(self.data_file).exists():
            subprocess.run([sys.executable, str(parent_dir / 'scripts' / 'generate_large_mot_data.py'), '--output', self.data_file, '--tracks', '2000', '--frames', '5000', '--seed', '42'], check=True)
        provider = MOTDataProvider(self.data_file)
        predictor = DynamicDataPredictor(possible_jumps=NAVIGATION_STEPS)
        cache = DynamicPrefetchingCache(provider, predictor)
        return provider, predictor, cache
    
    def build_sequence(self, pattern: str, available_frames: List[int], num_ops: int) -> List[int]:
        L = len(available_frames)
        if L == 0:
            return []
        frames: List[int] = []
        prev_idx = 0
        for i in range(num_ops):
            if pattern == 'sequential':
                idx = i % L
            elif pattern == 'random':
                idx = (i * 17) % L
            elif pattern == 'jumps':
                idx = (i * 15) % L if i % 5 == 0 else (prev_idx + 1) % L
            elif pattern == 'mixed':
                idx = (i * 7) % L if i % 3 == 0 else (i % L)
            elif pattern == 'search':
                # Simulate back-and-forth scanning around current position with occasional small jumps
                # Deterministic phases to avoid randomness in benchmarks
                phase = i % 20
                if phase < 6:           # small backward scan
                    idx = max(0, prev_idx - 1)
                elif phase < 12:        # small forward scan
                    idx = min(L - 1, prev_idx + 1)
                elif phase == 12:       # small jump backward
                    idx = max(0, prev_idx - 5)
                elif phase == 13:       # small jump forward
                    idx = min(L - 1, prev_idx + 5)
                else:                   # continue forward a bit
                    idx = min(L - 1, (prev_idx + 1))
            else:
                idx = i % L
            frames.append(available_frames[idx])
            prev_idx = idx
        return frames

    def measure_baseline(self, frames: List[int], work_ms: int) -> Dict[str, float]:
        provider = MOTDataProvider(self.data_file)
        durations: List[float] = []
        t0 = time.perf_counter()
        for f in frames:
            s = time.perf_counter()
            provider.load(f)
            durations.append(time.perf_counter() - s)
            if work_ms > 0:
                time.sleep(work_ms / 1000.0)
        total = time.perf_counter() - t0
        provider.close()
        return {
            'ops': float(len(frames)),
            'time_s': total,
            'ops_per_s': len(frames) / total if total > 0 else 0.0,
            'avg_ms': mean(durations) * 1000.0 if durations else 0.0,
            'p95_ms': percentile([d * 1000.0 for d in durations], 95.0) if durations else 0.0,
        }

    def measure_cached(self, frames: List[int], work_ms: int) -> Dict[str, float]:
        provider = MOTDataProvider(self.data_file)
        predictor = DynamicDataPredictor(possible_jumps=NAVIGATION_STEPS)
        cache = DynamicPrefetchingCache(provider, predictor)
        durations: List[float] = []
        t0 = time.perf_counter()
        for f in frames:
            s = time.perf_counter()
            cache.get(f)
            durations.append(time.perf_counter() - s)
            if work_ms > 0:
                time.sleep(work_ms / 1000.0)
        total = time.perf_counter() - t0
        stats = cache.stats()
        cache.close()
        ops = len(frames)
        hits = stats.get('hits', 0)
        misses = stats.get('misses', 0)
        hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0.0
        return {
            'ops': float(ops),
            'time_s': total,
            'ops_per_s': ops / total if total > 0 else 0.0,
            'avg_ms': mean(durations) * 1000.0 if durations else 0.0,
            'p95_ms': percentile([d * 1000.0 for d in durations], 95.0) if durations else 0.0,
            'hit_rate': hit_rate,
        }

    def _print_table(self, base: Dict[str, float], cached: Dict[str, float]) -> None:
        rows = [
            [
                "baseline",
                int(base['ops']),
                f"{base['time_s']:.2f}",
                f"{base['ops_per_s']:.0f}",
                f"{base['avg_ms']:.2f}",
                f"{base['p95_ms']:.2f}",
                "-",
            ],
            [
                "cached",
                int(cached['ops']),
                f"{cached['time_s']:.2f}",
                f"{cached['ops_per_s']:.0f}",
                f"{cached['avg_ms']:.2f}",
                f"{cached['p95_ms']:.2f}",
                f"{cached.get('hit_rate', 0.0):.2%}",
            ],
        ]
        headers = ["scenario", "ops", "time(s)", "ops/s", "avg(ms)", "p95(ms)", "hit_rate"]

        speedup = (base['time_s'] / cached['time_s']) if cached['time_s'] > 0 else 0.0
        p95_impr = (base['p95_ms'] / cached['p95_ms']) if cached['p95_ms'] > 0 else 0.0

        print(tabulate(rows, headers=headers, tablefmt="github"))

        print(f"➡️  Speedup: {speedup:.2f}x, p95 latency improvement: {p95_impr:.2f}x")

    def compare(self, pattern: str, num_ops: int, work_ms: int) -> None:
        provider, predictor, cache = self.setup_system()
        available = sorted(provider.get_available_frames())
        cache.close()
        if not available:
            print('❌ No frames available for profiling')
            return
        frames = self.build_sequence(pattern, available, num_ops)

        print(f"\n🔍 Pattern: {pattern}  (ops={num_ops}, work_ms={work_ms}, frames_available={len(available)})")
        base = self.measure_baseline(frames, work_ms)
        cached = self.measure_cached(frames, work_ms)
        self._print_table(base, cached)

def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Compare baseline vs cached performance')
    parser.add_argument('pattern', nargs='?', default='all',
                        choices=['sequential', 'random', 'jumps', 'mixed', 'search', 'all'],
                        help='Access pattern to benchmark (default: all)')
    parser.add_argument('--ops', type=int, default=1000,
                        help='Number of operations to run per scenario (default: 1000)')
    parser.add_argument('--work-ms', type=int, default=5,
                        help='Simulated per-item work after each access (ms). Allows prefetch overlap (default: 5)')

    args = parser.parse_args()

    profiler = ApplicationProfiler()

    patterns = ['sequential', 'random', 'jumps', 'mixed', 'search'] if args.pattern == 'all' else [args.pattern]
    for p in patterns:
        profiler.compare(p, args.ops, args.work_ms)

if __name__ == '__main__':
    main() 