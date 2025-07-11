"""
MOT DataProvider - High-Performance Implementation

Optimized implementation with:
- File position indexing (byte offsets for O(1) access)
- LRU caching for frequently accessed frames
- Batch loading capabilities
- Efficient file seeking instead of sequential reads

The mot file format is:
"<frame>,<id>,<bb_left>,<bb_top>,<bb_width>,<bb_height>,<confidence>,<class_id>,<visibility_ratio>"

The data provider is optimized for the following use cases:
- Sequential access patterns (e.g. video playback)
- Jump access patterns (e.g. seeking to a specific frame)
- Mixed access patterns (e.g. random access)
- Large datasets (e.g. < 100000 frames)
"""

import sys
import time
from typing import List, Dict, Set, Any, Optional, Tuple
from collections import OrderedDict

from .types import DataProvider, MOTDetection, MOTFrameData


class MOTDataProvider(DataProvider):
    """High-performance MOT (multiple object tracking) DataProvider with optimizations."""
    
    def __init__(self, data_file: str, cache_size: int = 100):
        self.data_file = data_file
        self.cache_size = cache_size
        self.statistics: Dict[str, float] = {}
        
        # Optimized index: frame_number -> list of (byte_offset, line_length)
        self.frame_index: Dict[int, List[Tuple[int, int]]] = {}
        
        # LRU cache for recently loaded frames
        self.frame_cache: OrderedDict[int, MOTFrameData] = OrderedDict()
        
        # Keep file handle open for efficient seeking
        self._file_handle: Optional[Any] = None
        
        self._build_optimized_index()

    def _build_optimized_index(self) -> None:
        """Build optimized index with byte offsets for O(1) file access."""
        start_time = time.time()
        
        with open(self.data_file, 'r') as f:
            byte_offset = 0
            
            for line in f:
                line_length = len(line.encode('utf-8'))
                line_content = line.strip()
                
                if line_content:
                    try:
                        # Parse only the frame number (first field)
                        frame = int(line_content.split(',')[0])
                        
                        if frame not in self.frame_index:
                            self.frame_index[frame] = []
                        
                        # Store byte offset and length for direct seeking
                        self.frame_index[frame].append((byte_offset, len(line_content)))
                        
                    except (ValueError, IndexError):
                        pass  # Skip invalid lines
                
                byte_offset += line_length
        
        self.statistics['index_build_time'] = time.time() - start_time
        self.statistics['total_frames_indexed'] = len(self.frame_index)
    
    def _get_file_handle(self) -> Any:
        """Get or create file handle for efficient seeking."""
        if self._file_handle is None or self._file_handle.closed:
            self._file_handle = open(self.data_file, 'r')
        return self._file_handle
    
    def _parse_detection_line_fast(self, line: str) -> MOTDetection:
        """Optimized parsing with reduced overhead."""
        parts = line.split(',')
        if len(parts) != 9:
            raise ValueError("Invalid line format")

        # Direct conversion without intermediate variables
        return MOTDetection(
            frame=int(parts[0]),
            track_id=int(parts[1]),
            bb_left=float(parts[2]),
            bb_top=float(parts[3]),
            bb_width=float(parts[4]),
            bb_height=float(parts[5]),
            confidence=float(parts[6]),
            class_id=int(parts[7]),
            visibility_ratio=float(parts[8])
        )
    
    def _load_frame_data_direct(self, frame_number: int) -> MOTFrameData:
        """Load frame data using direct file seeking (optimized I/O)."""
        start_time = time.time()
        
        # Get byte positions for this frame
        positions = self.frame_index.get(frame_number, [])
        if not positions:
            return MOTFrameData(frame_number=frame_number, detections=[])
        
        # Use file seeking for direct access
        file_handle = self._get_file_handle()
        detections = []
        
        for byte_offset, line_length in positions:
            file_handle.seek(byte_offset)
            line = file_handle.read(line_length).strip()
            
            if line:
                try:
                    detection = self._parse_detection_line_fast(line)
                    detections.append(detection)
                except (ValueError, IndexError):
                    continue
        
        load_time = time.time() - start_time
        self._update_statistics('direct_load_time', load_time)
        
        return MOTFrameData(frame_number=frame_number, detections=detections)
    
    def _update_cache(self, frame_number: int, frame_data: MOTFrameData) -> None:
        """Update LRU cache with new frame data."""
        # Remove if already exists (to update position)
        if frame_number in self.frame_cache:
            del self.frame_cache[frame_number]
        
        # Add to end (most recently used)
        self.frame_cache[frame_number] = frame_data
        
        # Evict oldest if cache is full
        while len(self.frame_cache) > self.cache_size:
            self.frame_cache.popitem(last=False)  # Remove oldest
    
    def _update_statistics(self, key: str, value: float) -> None:
        """Update running statistics."""
        count_key = f"{key}_count"
        avg_key = f"avg_{key}"
        
        current_count = self.statistics.get(count_key, 0)
        current_avg = self.statistics.get(avg_key, 0.0)
        
        new_count = current_count + 1
        new_avg = (current_avg * current_count + value) / new_count
        
        self.statistics[count_key] = new_count
        self.statistics[avg_key] = new_avg
    
    def load(self, frame_number: int) -> MOTFrameData:
        """Load a single frame with caching."""
        start_time = time.time()
        
        # Check cache first
        if frame_number in self.frame_cache:
            # Move to end (mark as recently used)
            frame_data = self.frame_cache.pop(frame_number)
            self.frame_cache[frame_number] = frame_data
            
            self._update_statistics('cache_hit_time', time.time() - start_time)
            self.statistics['cache_hits'] = self.statistics.get('cache_hits', 0) + 1
            return frame_data
        
        # Cache miss - load from file
        frame_data = self._load_frame_data_direct(frame_number)
        self._update_cache(frame_number, frame_data)
        
        self._update_statistics('cache_miss_time', time.time() - start_time)
        self.statistics['cache_misses'] = self.statistics.get('cache_misses', 0) + 1
        
        return frame_data
    
    def load_batch(self, frame_numbers: List[int]) -> Dict[int, MOTFrameData]:
        """Load multiple frames efficiently with batch optimization."""
        start_time = time.time()
        
        # Separate cached vs uncached frames
        cached_frames = {}
        uncached_frames = []
        
        for frame_num in frame_numbers:
            if frame_num in self.frame_cache:
                cached_frames[frame_num] = self.frame_cache[frame_num]
                # Update cache position
                self.frame_cache.move_to_end(frame_num)
            else:
                uncached_frames.append(frame_num)
        
        # Load uncached frames individually (simplified batch loading)
        for frame_num in uncached_frames:
            frame_data = self._load_frame_data_direct(frame_num)
            self._update_cache(frame_num, frame_data)
            cached_frames[frame_num] = frame_data
        
        total_time = time.time() - start_time
        self._update_statistics('batch_total_time', total_time)
        
        return cached_frames
    
    def get_total_frames(self) -> int:
        """Get total number of frames."""
        return len(self.frame_index)
    
    def get_available_frames(self) -> Set[int]:
        """Get set of available frame numbers."""
        return set(self.frame_index.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        total_lines = sum(len(positions) for positions in self.frame_index.values())
        cache_hits = self.statistics.get('cache_hits', 0)
        cache_misses = self.statistics.get('cache_misses', 0)
        total_requests = cache_hits + cache_misses
        
        stats = {
            'total_frames': len(self.frame_index),
            'total_indexed_lines': total_lines,
            'index_memory_bytes': sys.getsizeof(self.frame_index),
            'cache_size': len(self.frame_cache),
            'cache_max_size': self.cache_size,
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
            'cache_hit_rate': cache_hits / total_requests if total_requests > 0 else 0.0,
            'avg_direct_load_time': self.statistics.get('avg_direct_load_time', 0.0),
            'avg_cache_hit_time': self.statistics.get('avg_cache_hit_time', 0.0),
            'avg_cache_miss_time': self.statistics.get('avg_cache_miss_time', 0.0),
        }
        
        return stats
    
    def clear_cache(self) -> None:
        """Clear the frame cache."""
        self.frame_cache.clear()
    
    def close(self) -> None:
        """Close file handle and clean up resources."""
        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()
        self.frame_cache.clear()
    
    def __del__(self) -> None:
        """Cleanup on destruction."""
        self.close()
