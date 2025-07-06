#!/usr/bin/env python3
"""
Application Performance Profiler

A comprehensive profiling tool for the Dynamic Prefetched Cache system.
Provides detailed performance analysis with multiple profiling approaches.

Usage:
    python examples/profile_example.py [pattern] [--detailed]
    
    pattern: sequential, random, jumps, mixed (default: all)
    --detailed: Enable detailed function-level profiling
"""

import sys
import time
import cProfile
import pstats
import io
import argparse
import tracemalloc
from pathlib import Path
from typing import Dict, List, Generator, Optional, Tuple
from contextlib import contextmanager

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.dynamic_prefetching_cache import DynamicPrefetchingCache, DynamicDataPredictor, MOTDataProvider

NAVIGATION_STEPS = [-15, -5, -1, 1, 5, 15, 30]

class ApplicationProfiler:
    """Comprehensive application profiler."""
    
    def __init__(self, data_file: str = 'examples/data/ultra_dense_data.txt'):
        self.data_file = data_file
        self.results: Dict[str, List[float]] = {}
        
    def setup_system(self) -> tuple:
        """Set up the complete cache system."""
        provider = MOTDataProvider(self.data_file)
        predictor = DynamicDataPredictor(possible_jumps=NAVIGATION_STEPS)
        cache = DynamicPrefetchingCache(provider, predictor)
        return provider, predictor, cache
    
    @contextmanager
    def timer(self, operation_name: str) -> Generator[None, None, None]:
        """Context manager for timing operations."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start_time
            if operation_name not in self.results:
                self.results[operation_name] = []
            self.results[operation_name].append(duration)
    
    def profile_access_pattern(self, pattern_name: str, num_operations: int = 1000) -> Optional[float]:
        """Profile a specific access pattern."""
        provider, predictor, cache = self.setup_system()
        available_frames = sorted(provider.get_available_frames())
        
        if not available_frames:
            print("❌ No frames available for profiling")
            return None
        
        # Define access patterns
        patterns = {
            'sequential': lambda i: available_frames[i % len(available_frames)],
            'random': lambda i: available_frames[(i * 17) % len(available_frames)],
            'jumps': lambda i: available_frames[(i * 15) % len(available_frames)] if i % 5 == 0 else available_frames[(i-1) % len(available_frames)] + 1,
            'mixed': lambda i: available_frames[(i * 7) % len(available_frames)] if i % 3 == 0 else available_frames[i % len(available_frames)]
        }
        
        if pattern_name not in patterns:
            print(f"❌ Unknown pattern: {pattern_name}")
            return None
        
        pattern_func = patterns[pattern_name]
        
        print(f"🔍 Profiling {pattern_name} access pattern...")
        
        with self.timer(f'{pattern_name}_access'):
            for i in range(min(num_operations, len(available_frames) * 2)):
                frame = pattern_func(i)
                if frame < len(available_frames):
                    cache.get(frame)
        
        # Report results
        stats = cache.stats()
        total_requests = stats.get('hits', 0) + stats.get('misses', 0)
        hit_rate = stats.get('hits', 0) / total_requests if total_requests > 0 else 0
        
        print(f"  ✅ {pattern_name.capitalize()}: {hit_rate:.1%} hit rate, {total_requests} requests")
        
        cache.close()
        return hit_rate
    
    def profile_system_components(self) -> None:
        """Profile individual system components."""
        print("🔍 Profiling System Components...")
        
        provider, predictor, cache = self.setup_system()
        available_frames = sorted(provider.get_available_frames())[:100]  # Limit for faster profiling
        
        # Profile data provider
        with self.timer('provider_load'):
            for frame in available_frames[:50]:
                provider.load(frame)
        
        # Profile predictor
        history = available_frames[:10]
        with self.timer('predictor_likelihood'):
            for frame in available_frames[:50]:
                predictor.get_likelihoods(frame, history)
        
        # Profile cache operations
        with self.timer('cache_operations'):
            for frame in available_frames[:50]:
                cache.get(frame)
        
        cache.close()
    
    def profile_with_cprofile(self, pattern: str = 'mixed', num_operations: int = 200) -> str:
        """Profile using Python's built-in cProfile."""
        print("🔍 Running Detailed Function Analysis...")
        
        def workload() -> None:
            self.profile_access_pattern(pattern, num_operations)
        
        profiler = cProfile.Profile()
        profiler.enable()
        workload()
        profiler.disable()
        
        # Analyze results
        stats_stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stats_stream)
        stats.sort_stats('cumulative')
        stats.print_stats(15)  # Top 15 functions
        
        profile_output = stats_stream.getvalue()
        print(profile_output)
        
        return profile_output
    
    def profile_memory_usage(self, num_operations: int = 500) -> Tuple[int, int]:
        """Profile memory usage."""
        print("🔍 Profiling Memory Usage...")
        
        tracemalloc.start()
        
        # Run test workload
        self.profile_access_pattern('mixed', num_operations)
        
        # Get memory statistics
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"  📊 Memory Usage: {current / 1024 / 1024:.1f} MB current, {peak / 1024 / 1024:.1f} MB peak")
        
        return current, peak
    
    def run_comprehensive_profile(self, detailed: bool = False) -> None:
        """Run a comprehensive performance profile."""
        print("🚀 Starting Comprehensive Application Profile")
        print("=" * 50)
        
        # Test all access patterns
        patterns = ['sequential', 'random', 'jumps', 'mixed']
        hit_rates = {}
        
        for pattern in patterns:
            hit_rates[pattern] = self.profile_access_pattern(pattern, 500)
        
        # Profile system components
        self.profile_system_components()
        
        # Memory profiling
        self.profile_memory_usage(300)
        
        # Detailed profiling if requested
        if detailed:
            self.profile_with_cprofile('mixed', 200)
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 Performance Summary")
        print("=" * 50)
        
        # Access pattern results
        print("Cache Hit Rates:")
        for pattern, hit_rate in hit_rates.items():
            if hit_rate is not None:
                print(f"  {pattern.capitalize():12}: {hit_rate:.1%}")
        
        # Component timing results
        print("\nComponent Performance:")
        for operation, times in self.results.items():
            if times:
                avg_time = sum(times) / len(times)
                print(f"  {operation:20}: {avg_time*1000:.2f}ms average")
        
        print("\n✅ Profiling Complete!")

def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Profile the Dynamic Prefetched Cache application')
    parser.add_argument('pattern', nargs='?', default='all', 
                       choices=['sequential', 'random', 'jumps', 'mixed', 'all'],
                       help='Access pattern to profile (default: all)')
    parser.add_argument('--detailed', action='store_true',
                       help='Enable detailed function-level profiling')
    
    args = parser.parse_args()
    
    profiler = ApplicationProfiler()
    
    if args.pattern == 'all':
        profiler.run_comprehensive_profile(detailed=args.detailed)
    else:
        profiler.profile_access_pattern(args.pattern, 1000)
        if args.detailed:
            profiler.profile_with_cprofile(args.pattern, 200)

if __name__ == '__main__':
    main() 