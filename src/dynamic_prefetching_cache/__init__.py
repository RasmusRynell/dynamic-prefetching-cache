"""
Dynamic Prefetching Cache - A predictive caching framework

A reusable framework that intelligently pre-loads and serves keyed data items 
with minimal latency using user-supplied predictive algorithms.
"""

from .cache import DynamicPrefetchingCache
from .predictors import (
    DistanceDecayPredictor,
    DynamicDistanceDecayPredictor, 
    DynamicDataPredictor
)
from .providers import MOTDataProvider
from .types import (
    DataProvider,
    AccessPredictor,
    EvictionPolicy,
    EventCallback,
    EvictionPolicyOldest,
    EvictionPolicyLargest,
    EvictionPolicySmallest,
    MOTDetection,
    MOTFrameData
)

__version__ = "0.1.2"
__author__ = "Rasmus Rynell"
__email__ = "rynell.rasmus@gmail.com"

__all__ = [
    # Main cache class
    "DynamicPrefetchingCache",
    
    # Built-in predictors
    "DistanceDecayPredictor",
    "DynamicDistanceDecayPredictor", 
    "DynamicDataPredictor",
    
    # Built-in data provider
    "MOTDataProvider",
    
    # Protocols for custom implementations
    "DataProvider",
    "AccessPredictor", 
    "EvictionPolicy",
    "EventCallback",
    
    # Eviction policies
    "EvictionPolicyOldest",
    "EvictionPolicyLargest",
    "EvictionPolicySmallest",
    
    # Data structures
    "MOTDetection",
    "MOTFrameData",
    
    # Package metadata
    "__version__",
    "__author__",
    "__email__",
]
