"""Unit tests for type definitions and eviction policies."""

import pytest
import time
from dynamic_prefetching_cache.types import (
    EvictionPolicyOldest,
    EvictionPolicyLargest,
    EvictionPolicySmallest,
    CacheEntry,
    CacheMetrics,
    MOTDetection,
    MOTFrameData,
    PrefetchTask
)


class TestEvictionPolicies:
    """Test suite for eviction policies."""
    
    @pytest.mark.unit
    def test_eviction_policy_oldest(self) -> None:
        """Test oldest eviction policy."""
        policy = EvictionPolicyOldest()
        
        # Create cache entries with different timestamps
        cache_contents = {
            1: CacheEntry("data1", 1000.0),
            2: CacheEntry("data2", 2000.0),
            3: CacheEntry("data3", 1500.0),
        }
        
        victim = policy.pick_victim(cache_contents, {})
        assert victim == 1  # Oldest timestamp
    
    @pytest.mark.unit
    def test_eviction_policy_largest(self) -> None:
        """Test largest eviction policy."""
        policy = EvictionPolicyLargest()
        
        # Create cache entries with different sized data
        cache_contents = {
            1: CacheEntry("small", 1000.0),
            2: CacheEntry("a" * 1000, 2000.0),  # Largest
            3: CacheEntry("medium" * 10, 1500.0),
        }
        
        victim = policy.pick_victim(cache_contents, {})
        assert victim == 2  # Largest data
    
    @pytest.mark.unit
    def test_eviction_policy_smallest(self) -> None:
        """Test smallest eviction policy."""
        policy = EvictionPolicySmallest()
        
        # Create cache entries with different sized data
        cache_contents = {
            1: CacheEntry("x", 1000.0),  # Smallest
            2: CacheEntry("a" * 1000, 2000.0),
            3: CacheEntry("medium" * 10, 1500.0),
        }
        
        victim = policy.pick_victim(cache_contents, {})
        assert victim == 1  # Smallest data


class TestDataStructures:
    """Test suite for data structures."""
    
    @pytest.mark.unit
    def test_cache_entry_creation(self) -> None:
        """Test cache entry creation and timestamp handling."""
        # Test with explicit timestamp
        entry1 = CacheEntry("data", 1234.5)
        assert entry1.data == "data"
        assert entry1.timestamp == 1234.5
        
        # Test with zero timestamp (should auto-assign)
        before_time = time.time()
        entry2 = CacheEntry("data", 0)
        after_time = time.time()
        
        assert entry2.data == "data"
        assert before_time <= entry2.timestamp <= after_time
    
    @pytest.mark.unit
    def test_cache_metrics_initialization(self) -> None:
        """Test cache metrics initialization."""
        metrics = CacheMetrics()
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.evictions == 0
        assert metrics.prefetch_errors == 0
        
        # Test with custom values
        metrics2 = CacheMetrics(hits=5, misses=3, evictions=2, prefetch_errors=1)
        assert metrics2.hits == 5
        assert metrics2.misses == 3
        assert metrics2.evictions == 2
        assert metrics2.prefetch_errors == 1
    
    @pytest.mark.unit
    def test_prefetch_task_comparison(self) -> None:
        """Test PrefetchTask priority comparison for heap ordering."""
        task1 = PrefetchTask(priority=-0.8, key=1)  # Higher priority (more negative)
        task2 = PrefetchTask(priority=-0.5, key=2)  # Lower priority (less negative)
        task3 = PrefetchTask(priority=-0.8, key=3)  # Same priority as task1
        
        # Test comparison for heap ordering
        assert task1 < task2  # Higher priority comes first
        assert not (task2 < task1)
        assert not (task1 < task3)  # Same priority, no ordering
        assert not (task3 < task1)
    
    @pytest.mark.unit
    def test_mot_detection_creation(self) -> None:
        """Test MOT detection data structure."""
        detection = MOTDetection(
            frame=1,
            track_id=42,
            bb_left=100.0,
            bb_top=200.0,
            bb_width=50.0,
            bb_height=75.0,
            confidence=0.95,
            class_id=125,
            visibility_ratio=237
        )
        
        assert detection.frame == 1
        assert detection.track_id == 42
        assert detection.bb_left == 100.0
        assert detection.bb_top == 200.0
        assert detection.bb_width == 50.0
        assert detection.bb_height == 75.0
        assert detection.confidence == 0.95
        assert detection.class_id == 125
        assert detection.visibility_ratio == 237
    
    @pytest.mark.unit
    def test_mot_frame_data_creation(self) -> None:
        """Test MOT frame data structure."""
        detections = [
            MOTDetection(1, 42, 100.0, 200.0, 50.0, 75.0, 0.95, 125, 237),
            MOTDetection(1, 43, 150.0, 250.0, 60.0, 80.0, 0.87, 130, 242)
        ]
        
        frame_data = MOTFrameData(frame_number=1, detections=detections)
        
        assert frame_data.frame_number == 1
        assert len(frame_data.detections) == 2
        assert frame_data.detections[0].track_id == 42
        assert frame_data.detections[1].track_id == 43 