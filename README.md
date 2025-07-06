# Dynamic Prefetching Cache for Python

A Python library for memory-efficient file reading through speculative precaching. Instead of loading entire datasets into memory, this framework uses a user defined predictive function to anticipate data access patterns and proactively read and cache the most likely needed next items.

## Use Cases

This library is designed for scenarios where you need to process large files or datasets sequentially or with predictable access patterns, but cannot or do not want to load everything into memory at once.

**Primary use case**: Video frame analysis and MOT (Multiple Object Tracking) data processing, where users typically navigate through frames sequentially but may jump to specific positions. The library includes optimized providers and predictors for this scenario.

**Other applications**: Any situation where you can predict future data access patterns - time series analysis, log file processing, document processing pipelines, or any sequential data where memory usage needs to be controlled. The library is designed to be flexible and can be used in a wide range of scenarios.

## How It Works

Rather than reactive caching (loading data only after it's requested), this system implements **speculative precaching**:

1. **Predict**: Uses a user defined predictive function to identify the most likely next items
2. **Prefetch**: Loads predicted data in background thread before it's needed
3. **Serve**: Returns cached data when requested (if prediction was correct) or loads synchronously as fallback
4. **Manage**: Automatically evicts old data to maintain memory limits

## Quick Start

```python
from dynamic_prefetching_cache.predictors import DynamicDataPredictor
from dynamic_prefetching_cache.providers import MOTDataProvider
from dynamic_prefetching_cache.cache import DynamicPrefetchingCache

provider = MOTDataProvider("examples/data/large_data.txt") # Note: Use generate_large_mot_data.py to generate data
predictor = DynamicDataPredictor(possible_jumps=[-5, -1, 1, 5, 15])

# Create cache with automatic resource management
with DynamicPrefetchingCache(provider, predictor, max_keys_cached=512) as cache:
    for key in range(100):
        data = cache.get(key)  # Returns immediately if prefetched, else loads synchronously
        print(data)
        
    # Monitor performance
    stats = cache.stats()
    print(f"Hit rate: {stats['hits'] / (stats['hits'] + stats['misses']):.2%}")
```

## Core Protocols

### DataProvider Protocol
Implement this interface to connect your data source:

```python
class MyDataProvider:
    def load(self, key: int) -> Any:
        """Load data for the given key. Must be thread-safe."""
        # May be reading line(s) from a file or database
        # May be parsing a line from a text file
        # See src/dynamic_prefetching_cache/providers.py for an example
        return fetch_from_file_or_database(key)
    
    def get_available_frames(self) -> set[int]:
        """Return set of valid keys."""
        return {1, 2, 3, 4, 5}
    
    def get_total_frames(self) -> int:
        """Return total number of available keys."""
        return 5
    
    def get_stats(self) -> dict:
        """Return provider statistics."""
        return {"status": "ok"}
```

### AccessPredictor Protocol
Implement this interface to define prediction logic:

```python
class MyAccessPredictor:
    def get_likelihoods(self, current_key: int, history: list[int]) -> dict[int, float]:
        """Return likelihood scores for potential next keys."""
        return {
            current_key + 1: 0.8,  # High likelihood
            current_key + 2: 0.3,  # Medium likelihood
            current_key - 1: 0.1,  # Low likelihood
        }
```

## Built-in Components

### Access Predictors

The library includes several ready-to-use predictors:

- **`DistanceDecayPredictor`**: Simple distance-based prediction with configurable decay rates
- **`DynamicDistanceDecayPredictor`**: Forward-biased predictor optimized for media playback
- **`DynamicDataPredictor`**: Advanced predictor with jump detection and history analysis

```python
from dynamic_prefetching_cache.predictors import DynamicDataPredictor

# Optimized for video/media navigation patterns
predictor = DynamicDataPredictor(
    possible_jumps=[-15, -5, -1, 1, 5, 15, 30],  # Common seek distances
    forward_bias=2.0,     # Favor forward progression
    jump_boost=5.0,       # Boost exact jump targets
    proximity_boost=2.0   # Boost areas near jump targets
)
```

### MOT Data Provider

High-performance provider for MOT (Multiple Object Tracking) data files:

```python
from dynamic_prefetching_cache.providers import MOTDataProvider

# Optimized for MOT format files with built-in indexing and caching
provider = MOTDataProvider('data/tracking_results.txt', cache_size=100)

# Includes comprehensive statistics
stats = provider.get_stats()
print(f"Provider cache hit rate: {stats['cache_hit_rate']:.2%}")
```

## Configuration

```python
cache = DynamicPrefetchingCache(
    provider=my_provider,
    predictor=my_predictor,
    max_keys_cached=1000,                   # Maximum items in cache
    max_keys_prefetched=8,                  # Max concurrent prefetch tasks
    history_size=30,                        # Access history for prediction
    eviction_policy=EvictionPolicyOldest,   # Cache eviction strategy
    on_event=my_event_handler               # Optional event monitoring
)
```

## Event Monitoring

Monitor cache operations for debugging and optimization:

```python
def handle_cache_events(event_name: str, **kwargs):
    if event_name == 'prefetch_error':
        logger.warning(f"Prefetch failed for key {kwargs['key']}: {kwargs['error']}")
    elif event_name == 'cache_evict':
        logger.debug(f"Evicted key {kwargs['key']} from cache")

cache = DynamicPrefetchingCache(provider, predictor, on_event=handle_cache_events)
```

Available events: `cache_load_start/complete/error`, `prefetch_start/success/error`, `cache_evict`, `worker_error`

## Performance Monitoring

```python
stats = cache.stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hits'] / (stats['hits'] + stats['misses']):.2%}")
print(f"Active prefetch tasks: {stats['active_prefetch_tasks']}")
```

## Thread Safety

- `get()` method is thread-safe for concurrent access
- Background worker thread handles all prefetching operations
- `close()` method ensures clean resource cleanup
- All internal state is properly synchronized

## Examples

### Basic Usage Example

```python
from dynamic_prefetching_cache.cache import DynamicPrefetchingCache
from dynamic_prefetching_cache.predictors import DynamicDataPredictor
from dynamic_prefetching_cache.providers import MOTDataProvider

# Set up for video frame analysis
provider = MOTDataProvider('examples/data/example_data.txt')
predictor = DynamicDataPredictor(possible_jumps=[-5, -1, 1, 5, 15])

with DynamicPrefetchingCache(provider, predictor, max_keys_cached=200) as cache:
    for frame_id in range(100):
        detections = cache.get(frame_id)
        print(f"Frame {frame_id}: {len(detections.detections)} objects detected")
```

### Visual Interactive Demo

```bash
python examples/visable_example.py
```

### Performance Profiling

```bash
python examples/profile_example.py
```

## Installation

```bash
# Install from PyPI (when published)
pip install dynamic-prefetching-cache

# Or install from source
git clone <repository-url>
cd dynamic-prefetching-cache
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"

# Install with example dependencies (for GUI demo)
pip install -e ".[examples]"
```

## Getting Started

1. **Implement DataProvider** - Connect to your data source
2. **Choose or implement AccessPredictor** - Define prediction logic for your use case
3. **Configure cache parameters** - Set memory limits and prefetch behavior
4. **Use `cache.get(key)`** - The system handles prefetching automatically

The library abstracts away the complexity of memory management, concurrent prefetching, and prediction logic, allowing you to focus on your core data processing tasks.

## Generating Test Data

The repository includes a script to generate realistic MOT (Multiple Object Tracking) format test data for testing and development. This eliminates the need to download or upload large data files.

```bash
# Generate small test file (100 tracks, 1000 frames, ~1MB)
python scripts/generate_large_mot_data.py -o examples/data/test_data.txt -t 100 -f 1000

# Generate medium test file (500 tracks, 10000 frames, ~50MB)
python scripts/generate_large_mot_data.py -o examples/data/medium_data.txt -t 500 -f 10000

# Generate large test file (1000 tracks, 100000 frames, ~500MB)
python scripts/generate_large_mot_data.py -o examples/data/large_data.txt -t 1000 -f 100000

# Custom data generation with full options
python scripts/generate_large_mot_data.py \
    --output examples/data/custom_data.txt \
    --tracks 200 \                    # Number of object tracks
    --frames 5000 \                   # Number of frames
    --width 1920 \                    # Image width (pixels)
    --height 1080 \                   # Image height (pixels)
    --min-track-length 10 \           # Minimum track duration
    --max-track-length 200 \          # Maximum track duration
    --seed 42                         # Random seed for reproducibility
```
