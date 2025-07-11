"""
Centralized type definitions for the Dynamic Prefetched Cache system.

This module contains all protocols, dataclasses, and type definitions
used throughout the codebase to reduce file count and improve organization.
"""

import time
from dataclasses import dataclass
from typing import Any, Protocol, Sequence, Dict, List, Set, Mapping, Tuple


# =============================================================================
# Protocols (Interfaces)
# =============================================================================

class DataProvider(Protocol):
    """Protocol for data source that can load records by key."""
    
    def load(self, key: int) -> Any:
        """Load data for given key. May perform blocking I/O."""
        ...

    def get_available_frames(self) -> Set[int]:
        """Get set of available frame numbers."""
        ...

    def get_total_frames(self) -> int:
        """Get total number of frames."""
        ...

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the data provider."""
        ...


class AccessPredictor(Protocol):
    """Protocol for predicting future access patterns."""
    
    def get_likelihoods(self, current: int, history: Sequence[int]) -> Dict[int, float]:
        """Return likelihood scores for keys that might be accessed next."""
        ...


class EvictionPolicy(Protocol):
    """Protocol for choosing which cache entries to evict."""
    
    def pick_victim(self, 
                   cache_contents: Mapping[int, "CacheEntry"],
                   scores: Mapping[int, float]) -> int:
        """Pick a key to evict from cache."""
        ...


class EventCallback(Protocol):
    """
    Protocol for cache event callbacks.
    
    ## Event Types
    
    ### Cache Loading Events
    - `cache_load_start`: Synchronous load started
      - `key`: Key being loaded
    - `cache_load_complete`: Synchronous load completed successfully
      - `key`: Key that was loaded
    - `cache_load_error`: Synchronous load failed
      - `key`: Key that failed to load
      - `error`: Error message string
    
    ### Prefetch Events
    - `prefetch_start`: Background prefetch started
      - `key`: Key being prefetched
    - `prefetch_success`: Background prefetch completed successfully
      - `key`: Key that was prefetched
    - `prefetch_error`: Background prefetch failed
      - `key`: Key that failed to prefetch
      - `error`: Error message string
    
    ### Cache Management Events
    - `cache_evict`: Cache entry was evicted
      - `key`: Key that was evicted
    
    ### System Events
    - `worker_error`: Worker thread encountered an error
      - `error`: Error message string
    
    ## Usage Example
    
    ```python
    def my_event_handler(event_name: str, **kwargs):
        if event_name == 'prefetch_error':
            logger.warning(f"Prefetch failed for key {kwargs['key']}: {kwargs['error']}")
        elif event_name == 'cache_evict':
            logger.debug(f"Evicted key {kwargs['key']} from cache")
    
    cache = DynamicPrefetchingCache(provider, predictor, on_event=my_event_handler)
    ```
    """
    
    def __call__(self, event_name: str, **kwargs: Any) -> None:
        """
        Handle cache events.
        
        Args:
            event_name: Name of the event (see class docstring for complete list)
            **kwargs: Event-specific data (see class docstring for details)
        """
        ...


# =============================================================================
# Cache Data Structures
# =============================================================================

@dataclass
class CacheEntry:
    """Cache entry with data and metadata."""
    data: Any
    timestamp: float
    
    def __post_init__(self) -> None:
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    prefetch_errors: int = 0


@dataclass
class PrefetchTask:
    """Priority queue entry for prefetch scheduling."""
    priority: float  # negative likelihood for min-heap
    key: int
    
    def __lt__(self, other: "PrefetchTask") -> bool:
        return self.priority < other.priority


# =============================================================================
# MOT (Multi-Object Tracking) Data Structures
# =============================================================================

@dataclass
class MOTDetection:
    """Single object detection in MOT format."""
    frame: int
    track_id: int
    bb_left: float
    bb_top: float
    bb_width: float
    bb_height: float
    confidence: float
    class_id: int
    visibility_ratio: float


@dataclass
class MOTFrameData:
    """All detections for a single frame."""
    frame_number: int
    detections: List[MOTDetection]


# =============================================================================
# Eviction Policy Implementations
# =============================================================================

class EvictionPolicyOldest:
    """Evict least recently inserted entry."""
    
    def pick_victim(self, cache_contents: Mapping[int, CacheEntry], 
                   scores: Mapping[int, float]) -> int:
        return min(cache_contents.keys(), 
                  key=lambda k: cache_contents[k].timestamp)


class EvictionPolicyLargest:
    """Evict largest entry by data size."""
    
    def pick_victim(self, cache_contents: Mapping[int, CacheEntry],
                   scores: Mapping[int, float]) -> int:
        import sys
        return max(cache_contents.keys(),
                  key=lambda k: sys.getsizeof(cache_contents[k].data))


class EvictionPolicySmallest:
    """Evict smallest entry by data size."""
    
    def pick_victim(self, cache_contents: Mapping[int, CacheEntry],
                   scores: Mapping[int, float]) -> int:
        import sys
        return min(cache_contents.keys(),
                  key=lambda k: sys.getsizeof(cache_contents[k].data))


# =============================================================================
# Type Aliases
# =============================================================================

# Common type aliases for better readability
CacheContents = Dict[int, CacheEntry]
LikelihoodScores = Dict[int, float]
FrameIndex = Dict[int, List[Tuple[int, int]]]  # frame -> [(byte_offset, line_length)]
Statistics = Dict[str, Any]
