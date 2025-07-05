# Dynamic Prefetching Cache

A reusable framework that dynamically pre-loads and serves keyed data items with minimal latency. The system uses a user supplied predictive algorithm to anticipate future data access patterns and proactively cache the most likely needed items within configurable memory constraints.

## Why Use This Cache?

Traditional caches are reactive - they only load data after you request it. This cache is **proactive**: it predicts which keys you'll need next and loads them in the background, dramatically reducing latency for sequential or predictable access patterns.

## Quick Start

```python
from dynamic_prefetching_cache import DynamicPrefetchingCache, DynamicDataPredictor
from my_app import MyDataProvider  # Your data source

# Set up your data source and predictor
provider = MyDataProvider()  # Must implement DataProvider protocol
predictor = DynamicDataPredictor(possible_jumps=[-5, -1, 1, 5, 15])

# Create cache with context manager for clean resource management
with DynamicPrefetchingCache(provider, predictor, max_keys=512) as cache:
    # Just use get() - everything else is automatic
    for key in stream_of_keys:
        data = cache.get(key)  # Fast! Likely already prefetched
        process(data)
        
    # Check performance
    stats = cache.stats()
    print(f"Hit rate: {stats['hits'] / (stats['hits'] + stats['misses']):.2%}")
```

## Core Concepts

### DataProvider Protocol
Your data source must implement the `DataProvider` protocol:

```python
class MyDataProvider:
    def load(self, key: int) -> Any:
        # Your data loading logic here - must be thread-safe
        return fetch_from_database(key)
    
    def get_available_frames(self) -> set[int]:
        # Return set of valid keys
        return {1, 2, 3, 4, 5}
    
    def get_total_frames(self) -> int:
        # Return total number of frames
        return 5
    
    def get_stats(self) -> dict:
        # Return provider statistics
        return {"status": "ok"}
```

### AccessPredictor Protocol
Your predictor generates likelihood scores for potential next keys:

```python
class MyAccessPredictor:
    def get_likelihoods(self, current_key: int, history: list[int]) -> dict[int, float]:
        # Return higher scores for more likely keys
        return {
            current_key + 1: 0.8,  # Very likely
            current_key + 2: 0.3,  # Possible
            current_key - 1: 0.1,  # Unlikely
        }
```

## Built-in Components

The library includes several ready-to-use components to get you started quickly:

### Access Predictors

- **`DistanceDecayPredictor`**: Simple distance-based prediction with configurable decay
- **`DynamicDistanceDecayPredictor`**: Forward-biased predictor for media playback
- **`DynamicDataPredictor`**: Advanced predictor with jump detection and history analysis

```python
from dynamic_prefetching_cache import DynamicDataPredictor

# For media playback with common navigation patterns
predictor = DynamicDataPredictor(
    possible_jumps=[-15, -5, -1, 1, 5, 15, 30],  # Common seek distances
    forward_bias=2.0,     # Favor forward playback
    jump_boost=5.0,       # Boost exact jump targets
    proximity_boost=2.0   # Boost areas near jump targets
)
```

### MOT Data Provider

High-performance provider for MOT (Multiple Object Tracking) data files:

```python
from dynamic_prefetching_cache import MOTDataProvider

# Optimized for MOT format files with built-in caching
provider = MOTDataProvider('data/tracking_results.txt', cache_size=100)

# Supports batch loading and comprehensive statistics
stats = provider.get_stats()
print(f"Cache hit rate: {stats['cache_hit_rate']:.2%}")
```

## Examples

### Generated Data Format

See [examples/data/README.md](examples/data/README.md) for more details.

### Basic Usage Example

```python
from dynamic_prefetching_cache import DynamicPrefetchingCache, DynamicDataPredictor, MOTDataProvider

# Set up for video frame analysis
provider = MOTDataProvider('examples/data/example_data.txt')
predictor = DynamicDataPredictor(possible_jumps=[-5, -1, 1, 5, 15])

with DynamicPrefetchingCache(provider, predictor, max_keys=200) as cache:
    for frame_id in range(100):
        detections = cache.get(frame_id)
        print(f"Frame {frame_id}: {len(detections.detections)} objects detected")
```

### Visual Interactive Demo

Run the included visual demo to see the cache in action:

```bash
python examples/visable_example.py
```

This opens a GUI showing:
- Real-time cache visualization
- Navigation controls (jump by -15, -5, -1, +1, +5, +15 frames)
- Live statistics and prefetch queue status
- Event logging for cache operations

### Performance Profiling

Analyze cache performance with different access patterns:

```bash
python examples/profile_example.py
# Or for detailed analysis:
python examples/profile_example.py --detailed
```

Profiles multiple access patterns:
- **Sequential**: Normal forward playback
- **Random**: Unpredictable access
- **Jumps**: Large forward/backward seeks
- **Mixed**: Combination of patterns

## Configuration Options

```python
cache = DynamicPrefetchingCache(
    provider=my_provider,
    predictor=my_predictor,
    max_keys=1000,                           # Maximum items in cache
    max_number_of_keys_in_cache=8,          # Max concurrent prefetch tasks
    history_size=30,                        # Access history for prediction
    eviction_policy=EvictionPolicyOldest,   # Cache eviction strategy
    on_event=my_event_handler               # Optional event monitoring
)
```

## Event Monitoring

Monitor cache operations with event callbacks:

```python
def handle_cache_events(event_name: str, **kwargs):
    if event_name == 'prefetch_error':
        logger.warning(f"Prefetch failed for key {kwargs['key']}: {kwargs['error']}")
    elif event_name == 'cache_evict':
        logger.debug(f"Evicted key {kwargs['key']} from cache")

cache = DynamicPrefetchingCache(provider, predictor, on_event=handle_cache_events)
```

Available events:
- `cache_load_start/complete/error`: Synchronous loading
- `prefetch_start/success/error`: Background prefetching
- `cache_evict`: Cache entry eviction
- `worker_error`: System errors

## Performance Monitoring

```python
stats = cache.stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hits'] / (stats['hits'] + stats['misses']):.2%}")
print(f"Active prefetch tasks: {stats['active_prefetch_tasks']}")
```

## Thread Safety

- `get()` is safe to call from multiple threads
- Internal worker thread handles all background prefetching
- `close()` is idempotent and thread-safe
- All internal state is properly synchronized


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

# Run examples
python examples/visable_example.py
python examples/profile_example.py
```

## Getting Started

1. **Implement your DataProvider** - Connect to your data source
2. **Choose a predictor** - Use built-in predictors or create custom ones
3. **Configure the cache** - Set memory limits and options
4. **Use `cache.get(key)`** - Everything else is automatic!

The system handles all the complexity of prefetching, memory management, and concurrent operations transparently.

## Generating Test Data

The repository includes a script to generate realistic MOT (Multiple Object Tracking) format test data for testing and development. This eliminates the need to download or upload large data files.

### Quick Data Generation

```bash
# Generate small test file (100 tracks, 1000 frames, ~1MB)
python scripts/generate_large_mot_data.py -o examples/data/test_data.txt -t 100 -f 1000

# Generate medium test file (500 tracks, 10000 frames, ~50MB)
python scripts/generate_large_mot_data.py -o examples/data/medium_data.txt -t 500 -f 10000

# Generate large test file (1000 tracks, 100000 frames, ~500MB)
python scripts/generate_large_mot_data.py -o examples/data/large_data.txt -t 1000 -f 100000
```

### Data Generation Options

The script supports various options for customizing the generated data:

```bash
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
