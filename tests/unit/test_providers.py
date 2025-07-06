"""Unit tests for data providers."""

import pytest
import tempfile
import os
from pathlib import Path
from typing import List, Dict

from dynamic_prefetching_cache.providers import MOTDataProvider
from dynamic_prefetching_cache.types import MOTDetection, MOTFrameData


class TestMOTDataProvider:
    """Test suite for MOTDataProvider."""
    
    def test_load_valid_frame(self, temp_mot_file: str) -> None:
        """Test loading a valid frame returns correct data."""
        provider = MOTDataProvider(temp_mot_file, cache_size=10)
        
        frame_data = provider.load(1)
        
        assert frame_data.frame_number == 1
        assert len(frame_data.detections) == 2
        
        # Check first detection
        detection = frame_data.detections[0]
        assert detection.frame == 1
        assert detection.track_id == 1
        assert detection.bb_left == 100
        assert detection.bb_top == 200
        assert detection.bb_width == 50
        assert detection.bb_height == 75
        assert detection.confidence == 0.9
        assert detection.x == 125
        assert detection.y == 237
        assert detection.z == 0
    
    def test_load_nonexistent_frame(self, temp_mot_file: str) -> None:
        """Test loading a non-existent frame returns empty data."""
        provider = MOTDataProvider(temp_mot_file, cache_size=10)
        
        frame_data = provider.load(999)
        
        assert frame_data.frame_number == 999
        assert len(frame_data.detections) == 0
    
    def test_load_batch_mixed_frames(self, temp_mot_file: str) -> None:
        """Test batch loading with mix of existing and non-existing frames."""
        provider = MOTDataProvider(temp_mot_file, cache_size=10)
        
        batch_data = provider.load_batch([1, 2, 999, 3])
        
        assert len(batch_data) == 4
        assert batch_data[1].frame_number == 1
        assert len(batch_data[1].detections) == 2
        assert batch_data[2].frame_number == 2
        assert len(batch_data[2].detections) == 2
        assert batch_data[999].frame_number == 999
        assert len(batch_data[999].detections) == 0
        assert batch_data[3].frame_number == 3
        assert len(batch_data[3].detections) == 1
    
    def test_parse_invalid_line_formats(self) -> None:
        """Test parsing various invalid line formats."""
        provider = MOTDataProvider.__new__(MOTDataProvider)  # Create without __init__
        
        # Test insufficient fields
        with pytest.raises(ValueError, match="Invalid line format"):
            provider._parse_detection_line_fast("1,2,3")
        
        # Test non-numeric values
        with pytest.raises(ValueError):
            provider._parse_detection_line_fast("abc,2,3,4,5,6,7")
        
        # Test empty string
        with pytest.raises(ValueError):
            provider._parse_detection_line_fast("")
    
    def test_empty_file_handling(self) -> None:
        """Test handling of empty files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name
        
        try:
            provider = MOTDataProvider(temp_path, cache_size=10)
            
            assert provider.get_total_frames() == 0
            assert len(provider.get_available_frames()) == 0
            
            # Loading from empty file should return empty frame
            frame_data = provider.load(1)
            assert frame_data.frame_number == 1
            assert len(frame_data.detections) == 0
            
        finally:
            os.unlink(temp_path)
    
    def test_file_with_only_invalid_lines(self) -> None:
        """Test file containing only invalid/malformed lines."""
        invalid_lines = [
            "invalid,line",
            "abc,def,ghi,jkl,mno,pqr,stu",  # Non-numeric frame number
            "",  # Empty line
            "   ",  # Whitespace only
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for line in invalid_lines:
                f.write(line + '\n')
            temp_path = f.name
        
        try:
            provider = MOTDataProvider(temp_path, cache_size=10)
            
            # Should handle gracefully - no frames indexed
            assert provider.get_total_frames() == 0
            assert len(provider.get_available_frames()) == 0
            
        finally:
            os.unlink(temp_path)
    
    def test_file_with_valid_frame_invalid_detection_data(self) -> None:
        """Test file with valid frame numbers but invalid detection data."""
        lines_with_valid_frames_invalid_data = [
            "1,2,3",  # Valid frame number but too few fields for detection
            "2,abc,def,ghi,jkl,mno,pqr",  # Valid frame number but non-numeric detection data
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for line in lines_with_valid_frames_invalid_data:
                f.write(line + '\n')
            temp_path = f.name
        
        try:
            provider = MOTDataProvider(temp_path, cache_size=10)
            
            # Frames should be indexed (valid frame numbers)
            assert provider.get_total_frames() == 2
            assert 1 in provider.get_available_frames()
            assert 2 in provider.get_available_frames()
            
            # But loading should return empty detections due to invalid data
            frame_data_1 = provider.load(1)
            assert frame_data_1.frame_number == 1
            assert len(frame_data_1.detections) == 0
            
            frame_data_2 = provider.load(2)
            assert frame_data_2.frame_number == 2
            assert len(frame_data_2.detections) == 0
            
        finally:
            os.unlink(temp_path)
    
    def test_cache_lru_behavior(self, temp_mot_file: str) -> None:
        """Test LRU cache eviction behavior."""
        provider = MOTDataProvider(temp_mot_file, cache_size=2)
        
        # Load frames to fill cache
        provider.load(1)
        provider.load(2)
        
        stats = provider.get_stats()
        assert stats['cache_size'] == 2
        assert stats['cache_misses'] == 2
        assert stats['cache_hits'] == 0
        
        # Access frame 1 again (should be cache hit)
        provider.load(1)
        stats = provider.get_stats()
        assert stats['cache_hits'] == 1
        
        # Load frame 3 (should evict frame 2, the least recently used)
        provider.load(3)
        stats = provider.get_stats()
        assert stats['cache_size'] == 2
        assert stats['cache_misses'] == 3
        
        # Access frame 2 again (should be cache miss since it was evicted)
        provider.load(2)
        stats = provider.get_stats()
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 4
    
    def test_index_building_with_duplicate_frames(self) -> None:
        """Test index building when same frame appears multiple times."""
        data_lines = [
            "1,1,100,200,50,75,0.9,125,237,0",
            "1,2,200,300,60,80,0.8,230,340,0",
            "1,3,300,400,70,90,0.7,335,445,0",  # Same frame, different detection
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for line in data_lines:
                f.write(line + '\n')
            temp_path = f.name
        
        try:
            provider = MOTDataProvider(temp_path, cache_size=10)
            
            assert provider.get_total_frames() == 1  # Only one unique frame
            assert 1 in provider.get_available_frames()
            
            # Loading frame 1 should return all 3 detections
            frame_data = provider.load(1)
            assert frame_data.frame_number == 1
            assert len(frame_data.detections) == 3
            
            # Verify all detections are present
            track_ids = [det.track_id for det in frame_data.detections]
            assert sorted(track_ids) == [1, 2, 3]
            
        finally:
            os.unlink(temp_path)
    
    def test_file_seeking_accuracy(self) -> None:
        """Test that file seeking reads correct data from correct positions."""
        # Create a file with known byte positions
        data_lines = [
            "1,1,100,200,50,75,0.9,125,237,0",  # Frame 1
            "5,1,500,600,50,75,0.9,525,637,0",  # Frame 5 (skip frames 2-4)
            "10,1,1000,1100,50,75,0.9,1025,1137,0",  # Frame 10
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for line in data_lines:
                f.write(line + '\n')
            temp_path = f.name
        
        try:
            provider = MOTDataProvider(temp_path, cache_size=10)
            
            # Test loading frame 5 specifically
            frame_data = provider.load(5)
            assert frame_data.frame_number == 5
            assert len(frame_data.detections) == 1
            assert frame_data.detections[0].bb_left == 500
            assert frame_data.detections[0].bb_top == 600
            
            # Test loading frame 10
            frame_data = provider.load(10)
            assert frame_data.frame_number == 10
            assert len(frame_data.detections) == 1
            assert frame_data.detections[0].bb_left == 1000
            assert frame_data.detections[0].bb_top == 1100
            
        finally:
            os.unlink(temp_path)
    
    def test_statistics_collection(self, temp_mot_file: str) -> None:
        """Test that statistics are collected correctly."""
        provider = MOTDataProvider(temp_mot_file, cache_size=2)
        
        # Initial stats
        stats = provider.get_stats()
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 0
        assert stats['cache_hit_rate'] == 0.0
        
        # Load some frames
        provider.load(1)
        provider.load(2)
        provider.load(1)  # Cache hit
        
        stats = provider.get_stats()
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 2
        assert stats['cache_hit_rate'] == 1/3
        assert stats['total_frames'] == 3
        assert 'avg_cache_hit_time' in stats
        assert 'avg_cache_miss_time' in stats
    
    def test_clear_cache_functionality(self, temp_mot_file: str) -> None:
        """Test cache clearing functionality."""
        provider = MOTDataProvider(temp_mot_file, cache_size=10)
        
        # Load frames to populate cache
        provider.load(1)
        provider.load(2)
        
        stats = provider.get_stats()
        assert stats['cache_size'] == 2
        
        # Clear cache
        provider.clear_cache()
        
        stats = provider.get_stats()
        assert stats['cache_size'] == 0
        
        # Next load should be cache miss
        provider.load(1)
        stats = provider.get_stats()
        assert stats['cache_misses'] == 3  # 2 initial + 1 after clear
    
    def test_resource_cleanup(self, temp_mot_file: str) -> None:
        """Test that resources are properly cleaned up."""
        provider = MOTDataProvider(temp_mot_file, cache_size=10)
        
        # Load some data to open file handle
        provider.load(1)
        
        # Ensure file handle is open
        assert provider._file_handle is not None
        assert not provider._file_handle.closed
        
        # Close should clean up resources
        provider.close()
        
        assert provider._file_handle.closed
        assert len(provider.frame_cache) == 0
    
    def test_batch_loading_cache_interaction(self, temp_mot_file: str) -> None:
        """Test that batch loading properly interacts with cache."""
        provider = MOTDataProvider(temp_mot_file, cache_size=10)
        
        # Pre-load frame 1 into cache
        provider.load(1)
        
        # Verify frame 1 is in cache
        stats = provider.get_stats()
        assert stats['cache_size'] == 1
        assert stats['cache_misses'] == 1
        
        # Batch load including cached frame
        batch_data = provider.load_batch([1, 2, 3])
        
        # All frames should be in result
        assert len(batch_data) == 3
        assert all(frame_num in batch_data for frame_num in [1, 2, 3])
        
        # Cache should now contain all 3 frames
        stats = provider.get_stats()
        assert stats['cache_size'] == 3
    
