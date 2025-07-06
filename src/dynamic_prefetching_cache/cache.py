"""
Dynamic Prefetched Cache Framework

A simple synchronous framework that pre-loads and serves keyed data items with minimal latency.

## Why Use This Cache?

Traditional caches are reactive - they only load data after you request it. This cache is proactive:
it predicts which keys you'll need next and loads them in the background, dramatically reducing
latency for sequential or predictable access patterns.

## Quick Start

```python
from dynamic_prefetching_cache import DynamicPrefetchingCache
from my_app import MyDataProvider, MyAccessPredictor

# Set up your data source and predictor
provider = MyDataProvider()  # Must implement DataProvider protocol
predictor = MyAccessPredictor()  # Must implement AccessPredictor protocol

# Create cache with context manager for clean resource management
with DynamicPrefetchingCache(provider, predictor, max_keys_cached=512) as cache:
    # Just use get() - everything else is automatic
    for key in stream_of_keys:
        data = cache.get(key)  # Fast! Likely already prefetched
        process(data)
        
    # Check performance
    stats = cache.stats()
    print(f"Hit rate: {stats['hits'] / (stats['hits'] + stats['misses']):.2%}")
```

## Provider Requirements

Your DataProvider must be:
- **Thread-safe**: `load()` may be called from background threads
- **Synchronous**: Return data directly, not futures/coroutines
- **Reliable**: Raise exceptions for missing/invalid keys

```python
class MyDataProvider:
    def load(self, key: int) -> Any:
        # Your data loading logic here
        return fetch_from_database(key)
```

## Predictor Interface

Your AccessPredictor generates likelihood scores for potential next keys:

```python
class MyAccessPredictor:
    def get_likelihoods(self, current_key: int, history: list[int]) -> dict[int, float]:
        # Return higher scores for more likely keys
        # Can omit keys with zero/negligible likelihood
        return {
            current_key + 1: 0.8,  # Very likely
            current_key + 2: 0.3,  # Possible
            current_key - 1: 0.1,  # Unlikely
        }
```

## Thread Safety Guarantees

- `get()` is safe from multiple threads
- Internal worker thread handles all background prefetching
- `close()` is idempotent and safe to call multiple times
- All internal state is properly synchronized

## Performance Tuning

- **Sequential access**: Use distance-based predictors (built-in)
- **Random access**: Cache effectiveness drops, mostly becomes LRU
- **Bursty access**: Tune `max_keys_cached` and `max_keys_prefetched`
- **Slow provider**: Increase prefetch concurrency, monitor `prefetch_errors`

## Event Monitoring

Register an event callback to monitor cache behavior:

```python
def on_cache_event(event_name: str, **kwargs):
    if event_name == 'prefetch_error':
        logger.warning(f"Failed to prefetch key {kwargs['key']}: {kwargs['error']}")

cache = DynamicPrefetchingCache(provider, predictor, on_event=on_cache_event)
```

See `EventCallback` protocol for complete event documentation.
"""

import time
import threading
from collections import deque
from typing import Any, Optional, Dict, List, Set, Tuple, Type, Deque
from threading import Lock
import queue
import logging
import heapq

logger = logging.getLogger('DynamicPrefetchingCache')

from .types import (
    DataProvider, 
    AccessPredictor, 
    EvictionPolicy, 
    EvictionPolicyOldest, 
    CacheEntry, 
    EventCallback,
    CacheMetrics
)



class DynamicPrefetchingCache:
    """
    Dynamic prefetched cache.
    
    Serves keyed data items with minimal latency while proactively
    prefetching keys most likely to be requested next.
    
    ## Primary API
    
    The main method you need is `get(key)` - it handles everything automatically:
    - Updates current position tracking
    - Triggers intelligent prefetching in the background
    - Returns data from cache or loads it synchronously
    
    ## Lifecycle & Telemetry
    
    Additional methods are provided for resource management and monitoring:
    - `close()` or context manager usage for clean shutdown
    - `stats()` for performance metrics and cache state
    - `on_event` callback for detailed operational events
    
    ## Thread Safety
    
    - `get()` is safe to call from multiple threads
    - Internal worker thread handles all background prefetching
    - `close()` is idempotent and thread-safe
    
    ## Usage Examples
    
    ### Basic Usage
    ```python
    with DynamicPrefetchingCache(provider, predictor, max_keys_cached=512) as cache:
        for key in stream_of_keys:
            record = cache.get(key)
            process(record)
    ```
    
    ### With Monitoring
    ```python
    def handle_events(event_name: str, **kwargs):
        if event_name == 'prefetch_error':
            logger.warning(f"Prefetch failed: {kwargs}")
    
    cache = DynamicPrefetchingCache(
        provider=my_provider,
        predictor=my_predictor,
        max_keys_cached=1000,
        max_keys_prefetched=8,
        on_event=handle_events
    )
    
    try:
        # Use the cache
        data = cache.get(42)
        
        # Check performance
        stats = cache.stats()
        hit_rate = stats['hits'] / (stats['hits'] + stats['misses'])
        logger.info(f"Cache hit rate: {hit_rate:.2%}")
        
    finally:
        cache.close()
    ```
    
    ### Performance Monitoring
    ```python
    stats = cache.stats()
    print(f"Hits: {stats['hits']}")
    print(f"Misses: {stats['misses']}")
    print(f"Hit rate: {stats['hits'] / (stats['hits'] + stats['misses']):.2%}")
    print(f"Evictions: {stats['evictions']}")
    print(f"Prefetch errors: {stats['prefetch_errors']}")
    print(f"Cache size: {stats['cache_keys']}")
    print(f"Active prefetch tasks: {stats['active_prefetch_tasks']}")
    ```
    """
    
    def __init__(self,
                 provider: DataProvider,
                 predictor: AccessPredictor,
                 max_keys_cached: int = 100,
                 eviction_policy: Type[EvictionPolicy] = EvictionPolicyOldest,
                 history_size: int = 30,
                 max_keys_prefetched: int = 20,
                 on_event: Optional[EventCallback] = None) -> None:
        """
        Initialize the Dynamic prefetched cache.
        
        Args:
            provider: Data source that can load records by key
            predictor: Access pattern predictor that generates likelihood scores
            max_keys_cached: Maximum number of items to keep in cache
            eviction_policy: Policy class for choosing which items to evict when cache is full
            history_size: Maximum number of recent key accesses to remember for prediction
            max_keys_prefetched: Maximum number of concurrent prefetch operations
            on_event: Optional callback function for cache events
        """
        self.provider = provider
        self.predictor = predictor
        self.max_keys_cached = max_keys_cached
        self.history_size = history_size
        self.max_keys_prefetched = max_keys_prefetched
        self.on_event = on_event
        
        # Set up eviction policy
        self.eviction_policy = eviction_policy()
        
        # Cache storage
        self.cache: Dict[int, CacheEntry] = {}
        self.cache_lock = Lock()
        
        # Access history
        self.history: Deque[int] = deque(maxlen=history_size)
        self.current_key: Optional[int] = None
        
        # Background worker thread
        self.shutdown_flag = threading.Event()
        self.work_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=self.max_keys_prefetched*2)
        self.queued_keys: Set[int] = set()
        self.queue_lock = Lock()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        # Metrics
        self._metrics_lock = Lock()
        self.metrics = CacheMetrics()
        
        logger.info(f"DynamicPrefetchingCache initialized: max_keys_cached={max_keys_cached}, max_keys_prefetched={max_keys_prefetched}")
    
    def get(self, key: int) -> Any:
        """
        Get data for key - the primary cache interface.
        
        This is the main method you'll use. It automatically:
        1. Updates current position to this key
        2. Triggers dynamic prefetching in background
        3. Returns the data (from cache or loads it synchronously)
        
        Thread-safe and can be called from multiple threads concurrently.
        
        Args:
            key: The key to get data for
        
        Returns:
            The data for this key
            
        Raises:
            Exception: If the provider fails to load the data
        """
        # Update position if changed
        if key != self.current_key:
            self._update_position(key)
        
        # Check cache first
        with self.cache_lock:
            try:
                entry = self.cache[key]
                with self._metrics_lock:
                    self.metrics.hits += 1
                logger.debug(f"Cache HIT for key {key}")
                return entry.data
            except KeyError:
                pass
        
        # Not in cache - load synchronously
        with self._metrics_lock:
            self.metrics.misses += 1
        
        logger.debug(f"Cache MISS for key {key} - loading synchronously")
        return self._load_and_cache_sync(key)
    
    def _update_position(self, key: int) -> None:
        """Update current position and trigger dynamic prefetching."""
        old_key = self.current_key
        self.current_key = key
        self.history.append(key)
        
        # Detect if this is a jump vs sequential step
        is_jump = old_key is None or abs(key - old_key) > 1
        if is_jump:
            logger.debug(f"Position jump: {old_key} -> {key} (rebuilding prefetch queue)")
        else:
            logger.debug(f"Position step: {old_key} -> {key}")
        
        self._update_prefetch(is_rebuild=is_jump)
    
    def _update_prefetch(self, is_rebuild: bool = False) -> None:
        """Dynamic prefetch: calculate what we need and update work queue efficiently."""
        if self.current_key is None:
            return
        
        # Calculate what we want to prefetch
        scores = self.predictor.get_likelihoods(self.current_key, list(self.history))
        desired_keys_with_scores = self._get_desired_keys_with_scores(scores)
        
        # Update work queue efficiently
        self._sync_work_queue(desired_keys_with_scores, is_rebuild)
    
    def _get_desired_keys_with_scores(self, scores: Dict[int, float]) -> List[Tuple[int, float]]:
        """Get the keys we want to prefetch with their scores, sorted by priority."""
        desired_keys: List[Tuple[int, float]] = []
        with self.cache_lock:
            # Filter out already cached keys first
            uncached_scores = {k: v for k, v in scores.items() if k not in self.cache}
            
            if not uncached_scores:
                return desired_keys
            
            # Get only the top keys we actually need for prefetching
            max_keys_cached_to_fetch = min(
                self.max_keys_prefetched,  # Max prefetch queue size
                len(uncached_scores)
            )
            
            if max_keys_cached_to_fetch <= 0:
                return desired_keys
            
            # Use heapq.nlargest for efficient top-k selection
            # This is much faster than sorting all scores
            top_items = heapq.nlargest(
                max_keys_cached_to_fetch, 
                uncached_scores.items(), 
                key=lambda x: x[1]
            )
            
            desired_keys = [(key, score) for key, score in top_items]
        
        return desired_keys
    
    def _sync_work_queue(self, desired_keys_with_scores: List[Tuple[int, float]], is_rebuild: bool = False) -> None:
        """Sync work queue: rebuild completely if is_rebuild, otherwise minimal operations."""
        desired_keys = {key for key, score in desired_keys_with_scores}
        
        with self.queue_lock:
            if is_rebuild:
                self._rebuild_queue(desired_keys_with_scores)
            else:
                self._incremental_sync(desired_keys_with_scores, desired_keys)
    
    def _rebuild_queue(self, desired_keys_with_scores: List[Tuple[int, float]]) -> None:
        """Rebuild the work queue completely. Must be called with queue_lock held."""
        # Clear everything
        while not self.work_queue.empty():
            try:
                self.work_queue.get_nowait()
                self.work_queue.task_done()
            except queue.Empty:
                break
        self.queued_keys.clear()
        
        # Add all keys in priority order (highest score first)
        added_count = 0
        for key, score in desired_keys_with_scores:
            try:
                self.work_queue.put_nowait((-score, key))
                self.queued_keys.add(key)
                added_count += 1
            except queue.Full:
                break
        
        logger.debug(f"Rebuilt prefetch queue: {added_count} keys, top priorities: {[f'{k}({s:.2f})' for k, s in desired_keys_with_scores[:3]]}")
    
    def _incremental_sync(self, desired_keys_with_scores: List[Tuple[int, float]], desired_keys: Set[int]) -> None:
        """Incrementally sync the work queue. Must be called with queue_lock held."""
        # Remove unwanted keys from tracking
        unwanted_keys = self.queued_keys - desired_keys
        if unwanted_keys:
            logger.debug(f"Removing {len(unwanted_keys)} unwanted keys from tracking")
        self.queued_keys -= unwanted_keys
        
        # Add new keys in priority order (highest score first)
        added_count = 0
        for key, score in desired_keys_with_scores:
            if key not in self.queued_keys:
                try:
                    self.work_queue.put_nowait((-score, key))
                    self.queued_keys.add(key)
                    added_count += 1
                except queue.Full:
                    break
        
        if added_count > 0:
            logger.debug(f"Added {added_count} new keys to prefetch queue")
        logger.debug(f"Total queued keys: {len(self.queued_keys)}")
    
    def _load_and_cache(self, key: int, is_prefetch: bool = False) -> Any:
        """Load data and cache it. Unified method for both sync and prefetch loading."""
        event_prefix = 'prefetch' if is_prefetch else 'cache_load'
        self._emit_event(f'{event_prefix}_start', key=key)
        
        try:
            data = self.provider.load(key)
            
            with self.cache_lock:
                entry = CacheEntry(data=data, timestamp=time.monotonic())
                self.cache[key] = entry
                self._evict_if_needed()
            
            self._emit_event(f'{event_prefix}_{"success" if is_prefetch else "complete"}', key=key)
            return data
            
        except Exception as e:
            if is_prefetch:
                with self._metrics_lock:
                    self.metrics.prefetch_errors += 1
            self._emit_event(f'{event_prefix}_error', key=key, error=str(e))
            raise
    
    def _load_and_cache_sync(self, key: int) -> Any:
        """Load data synchronously and cache it."""
        return self._load_and_cache(key, is_prefetch=False)
    
    def _worker_loop(self) -> None:
        """Single worker thread that loads data in background."""
        while not self.shutdown_flag.is_set():
            try:
                try:
                    # Use shorter timeout to check shutdown flag more frequently
                    priority_item = self.work_queue.get(timeout=0.5)
                    # Extract key from priority tuple (negative_score, key)
                    key = priority_item[1]
                    score = -priority_item[0]
                    logger.debug(f"Loading key {key} (priority score: {score:.2f})")
                except queue.Empty:
                    continue
                
                # Remove from tracking as soon as we get it
                with self.queue_lock:
                    self.queued_keys.discard(key)
                
                # Check shutdown flag before potentially blocking provider.load()
                if self.shutdown_flag.is_set():
                    # Put the item back in queue for clean shutdown
                    self.work_queue.task_done()
                    break
                
                try:
                    self._load_and_cache(key, is_prefetch=True)
                except Exception as e:
                    # Error handling and event emission is already done in _load_and_cache
                    # Just log for debugging purposes
                    logger.debug(f"Prefetch failed for key {key}: {e}")
                
                self.work_queue.task_done()
                
            except Exception as e:
                self._emit_event('worker_error', error=str(e))
    
    def _evict_if_needed(self) -> None:
        """Evict entries if over key limit. Must be called with cache_lock held."""
        if not self.cache or len(self.cache) <= self.max_keys_cached:
            return
        
        # Calculate scores once for all evictions
        scores = {}
        if self.current_key is not None:
            scores = self.predictor.get_likelihoods(self.current_key, list(self.history))
        
        # Evict multiple items using the same scores
        while self.cache and len(self.cache) > self.max_keys_cached:
            victim_key = self._pick_eviction_victim(scores)
            _ = self.cache.pop(victim_key)
            
            with self._metrics_lock:
                self.metrics.evictions += 1
            
            logger.debug(f"Evicted key {victim_key} (cache limit: {self.max_keys_cached})")
            self._emit_event('cache_evict', key=victim_key)
    
    def _pick_eviction_victim(self, scores: Dict[int, float]) -> int:
        """Pick victim: lowest likelihood first, eviction policy as tie-breaker."""
        if not scores:
            victim = self.eviction_policy.pick_victim(self.cache, {})
            return int(victim)
        
        # Find keys with minimum likelihood score
        cached_scores = {key: scores.get(key, 0.0) for key in self.cache.keys()}
        min_score = min(cached_scores.values())
        tied_keys = [key for key, score in cached_scores.items() if score == min_score]
        
        if len(tied_keys) == 1:
            return tied_keys[0]
        else:
            # Use eviction policy as tie-breaker
            tied_cache = {key: self.cache[key] for key in tied_keys}
            tied_scores = {key: scores.get(key, 0.0) for key in tied_keys}
            victim = self.eviction_policy.pick_victim(tied_cache, tied_scores)
            return int(victim)
    
    def stats(self) -> Dict[str, int]:
        """
        Get a snapshot of current cache statistics and metrics.
        
        Returns:
            Dictionary containing the following keys:
            - hits: Number of cache hits (data found in cache)
            - misses: Number of cache misses (data loaded from provider)
            - evictions: Number of items evicted due to key limits
            - prefetch_errors: Number of prefetch operations that failed
            - cache_keys: Current number of items in cache
            - active_prefetch_tasks: Number of currently running prefetch tasks        
        """
        with self._metrics_lock:
            return {
                'hits': self.metrics.hits,
                'misses': self.metrics.misses,
                'evictions': self.metrics.evictions,
                'prefetch_errors': self.metrics.prefetch_errors,
                'cache_keys': len(self.cache),
                'active_prefetch_tasks': self.work_queue.qsize()
            }
    
    def close(self) -> None:
        """Close the cache and clean up resources."""
        logger.info("Closing DynamicPrefetchingCache...")
        self.shutdown_flag.set()
        
        # Give worker thread time to finish current task and exit cleanly
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
            
            # If thread is still alive, it's likely blocked in provider.load()
            if self.worker_thread.is_alive():
                logger.warning("Worker thread did not exit cleanly - provider may be blocking indefinitely")
                logger.warning("Consider implementing timeout or cancellation in your DataProvider.load() method")
        
        logger.info("DynamicPrefetchingCache closed")
    
    def shutdown(self) -> None:
        """Shutdown the cache and clean up resources."""
        self.close()
    
    def __enter__(self) -> "DynamicPrefetchingCache":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> None:
        """Context manager exit."""
        self.close()
    
    def __del__(self) -> None:
        """Cleanup when cache is garbage collected."""
        try:
            self.close()
        except:
            pass  # Ignore errors during cleanup
    
    def _emit_event(self, event_name: str, **kwargs: Any) -> None:
        """Emit event to callback if configured."""
        if self.on_event:
            try:
                self.on_event(event_name, **kwargs)
            except Exception as e:
                logger.warning(f"Error emitting event {event_name}: {e}")
                pass
