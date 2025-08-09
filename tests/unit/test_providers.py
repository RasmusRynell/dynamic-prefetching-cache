"""Unit tests for data providers."""

import pytest
import tempfile
import os
from pathlib import Path
from typing import List, Dict

from dynamic_prefetching_cache.providers import MOTDataProvider


class TestMOTDataProvider:
    """Test suite for MOTDataProvider."""
    
    def test_load_valid_frame(self, temp_mot_file: str) -> None:
        """Test loading a valid frame returns correct data."""
        provider = MOTDataProvider(temp_mot_file)
        
        frame_data = provider.load(1)
        
        assert frame_data.frame_number == 1
        assert len(frame_data.detections) == 2
        
        # Check first detection
        detection = frame_data.detections[0]
        assert detection.frame == 1, f"Frame number should be 1, but is {detection.frame}"
        assert detection.track_id == 1, f"Track ID should be 1, but is {detection.track_id}"
        assert detection.bb_left == 100, f"BB left should be 100, but is {detection.bb_left}"
        assert detection.bb_top == 200, f"BB top should be 200, but is {detection.bb_top}"
        assert detection.bb_width == 50, f"BB width should be 50, but is {detection.bb_width}"
        assert detection.bb_height == 75, f"BB height should be 75, but is {detection.bb_height}"
        assert detection.confidence == 0.9, f"Confidence should be 0.9, but is {detection.confidence}"
        assert detection.class_id == 125, f"Class ID should be 125, but is {detection.class_id}"
        assert detection.visibility_ratio == 237, f"Visibility ratio should be 237, but is {detection.visibility_ratio}"
    
    def test_load_nonexistent_frame(self, temp_mot_file: str) -> None:
        """Test loading a non-existent frame returns empty data."""
        provider = MOTDataProvider(temp_mot_file)
        
        frame_data = provider.load(999)
        
        assert frame_data.frame_number == 999
        assert len(frame_data.detections) == 0
    
    def test_load_batch_mixed_frames(self, temp_mot_file: str) -> None:
        """Test batch loading with mix of existing and non-existing frames."""
        provider = MOTDataProvider(temp_mot_file)
        
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
            provider = MOTDataProvider(temp_path)
            
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
            provider = MOTDataProvider(temp_path)
            
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
            provider = MOTDataProvider(temp_path)
            
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
    
    # Removed: internal LRU cache is no longer part of provider
    
    def test_index_building_with_duplicate_frames(self) -> None:
        """Test index building when same frame appears multiple times."""
        data_lines = [
            "1,1,100,200,50,75,0.9,125,237",
            "1,2,200,300,60,80,0.8,230,340",
            "1,3,300,400,70,90,0.7,335,445",  # Same frame, different detection
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for line in data_lines:
                f.write(line + '\n')
            temp_path = f.name
        
        try:
            provider = MOTDataProvider(temp_path)
            
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
            "1,1,100,200,50,75,0.9,125,237",  # Frame 1
            "5,1,500,600,50,75,0.9,525,637",  # Frame 5 (skip frames 2-4)
            "10,1,1000,1100,50,75,0.9,1025,1137",  # Frame 10
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for line in data_lines:
                f.write(line + '\n')
            temp_path = f.name
        
        try:
            provider = MOTDataProvider(temp_path)
            
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
        """Test that statistics about indexing and I/O are collected."""
        provider = MOTDataProvider(temp_mot_file)

        # Initial stats
        stats = provider.get_stats()
        assert stats['total_frames'] == 3
        assert 'total_indexed_lines' in stats
        assert 'index_memory_bytes' in stats
        assert 'avg_direct_load_time' in stats
        assert 'index_build_time' in stats

        # Load some frames (ensure timing fields get updated)
        provider.load(1)
        provider.load(2)
        provider.load(1)

        stats = provider.get_stats()
        assert stats['total_frames'] == 3
        assert 'avg_direct_load_time' in stats
    
    # Removed: clear_cache no longer exists in provider
    
    def test_resource_cleanup(self, temp_mot_file: str) -> None:
        """Test that resources are properly cleaned up."""
        provider = MOTDataProvider(temp_mot_file)
        
        # Load some data to open file handle
        provider.load(1)
        
        # Ensure file handle is open
        assert provider._file_handle is not None
        assert not provider._file_handle.closed
        
        # Close should clean up resources
        provider.close()
        
        assert provider._file_handle.closed
    
    def test_batch_loading_returns_all_requested_frames(self, temp_mot_file: str) -> None:
        """Test batch loading returns a mapping for requested frames and updates timing stats."""
        provider = MOTDataProvider(temp_mot_file)

        batch_data = provider.load_batch([1, 2, 3])

        assert len(batch_data) == 3
        assert all(frame_num in batch_data for frame_num in [1, 2, 3])

        stats = provider.get_stats()
        assert 'avg_batch_total_time' in stats
    
