"""Shared pytest fixtures and configuration for dynamic_prefetching_cache tests."""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Iterator, Tuple

from dynamic_prefetching_cache.types import DataProvider, AccessPredictor, MOTDetection, MOTFrameData


class MockDataProvider(DataProvider):
    """Simple mock data provider for testing."""
    
    def __init__(self, data: Optional[Dict[int, Any]] = None) -> None:
        self.data = data or {i: f"data_{i}" for i in range(10)}
        self.load_calls: List[int] = []
        
    def load(self, key: int) -> Any:
        self.load_calls.append(key)
        if key not in self.data:
            raise KeyError(f"Key {key} not found")
        return self.data[key]
    
    def get_available_frames(self) -> Set[int]:
        return set(self.data.keys())
    
    def get_total_frames(self) -> int:
        return len(self.data)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_frames": len(self.data),
            "load_calls": len(self.load_calls)
        }


class MockAccessPredictor(AccessPredictor):
    """Simple mock access predictor for testing."""
    
    def __init__(self, predictions: Optional[Dict[int, Dict[int, float]]] = None) -> None:
        self.predictions = predictions or {}
        self.call_history: List[Tuple[int, List[int]]] = []
        
    def get_likelihoods(self, current: int, history: List[int]) -> Dict[int, float]:
        self.call_history.append((current, list(history)))
        return self.predictions.get(current, {current + 1: 0.8, current + 2: 0.4})


@pytest.fixture
def mock_provider() -> MockDataProvider:
    """Fixture providing a mock data provider."""
    return MockDataProvider()


@pytest.fixture
def mock_predictor() -> MockAccessPredictor:
    """Fixture providing a mock access predictor."""
    return MockAccessPredictor()


@pytest.fixture
def sample_mot_data() -> List[str]:
    """Fixture providing sample MOT data for testing."""
    return [
        "1,1,100,200,50,75,0.9,125,237",
        "1,2,200,300,60,80,0.8,230,340",
        "2,1,105,205,50,75,0.85,130,242",
        "2,2,205,305,60,80,0.75,235,345",
        "3,1,110,210,50,75,0.9,135,247",
    ]


@pytest.fixture
def temp_mot_file(sample_mot_data: List[str]) -> Iterator[str]:
    """Fixture providing a temporary MOT data file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for line in sample_mot_data:
            f.write(line + '\n')
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def example_data_path() -> Path:
    """Fixture providing path to the example data file."""
    return Path(__file__).parent.parent / "examples" / "data" / "example_data.txt"


@pytest.fixture
def small_test_data() -> Dict[int, MOTFrameData]:
    """Fixture providing small test dataset for unit tests."""
    return {
        1: MOTFrameData(
            frame_number=1,
            detections=[
                MOTDetection(1, 1, 100, 200, 50, 75, 0.9, 125, 237, 0)
            ]
        ),
        2: MOTFrameData(
            frame_number=2,
            detections=[
                MOTDetection(2, 1, 105, 205, 50, 75, 0.85, 130, 242, 0),
                MOTDetection(2, 2, 205, 305, 60, 80, 0.75, 235, 345, 0)
            ]
        ),
        3: MOTFrameData(
            frame_number=3,
            detections=[
                MOTDetection(3, 1, 110, 210, 50, 75, 0.9, 135, 247, 0)
            ]
        )
    } 