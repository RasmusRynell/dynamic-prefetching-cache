"""
MOT DataProvider - High-Performance Implementation

Optimized for:
- File position indexing (byte offsets for O(1)-like direct access)
- Efficient file seeking instead of sequential reads
- Batch loading convenience


MOT line format:
"<frame>,<id>,<bb_left>,<bb_top>,<bb_width>,<bb_height>,<confidence>,<class_id>,<visibility_ratio>"
"""

import sys
import time
from typing import List, Dict, Set, Any, Optional, Tuple
from threading import Lock

from .types import DataProvider, MOTDetection, MOTFrameData


class MOTDataProvider(DataProvider):
    """High-performance MOT (multiple object tracking) DataProvider with byte-offset indexing."""

    def __init__(self, data_file: str):
        self.data_file = data_file
        self.statistics: Dict[str, float] = {}

        # Optimized index: frame_number -> list of (byte_offset, line_length)
        self.frame_index: Dict[int, List[Tuple[int, int]]] = {}

        # Keep file handle open for efficient seeking
        self._file_handle: Optional[Any] = None

        # Serialize file seek/read for thread safety
        self._io_lock: Lock = Lock()

        self._build_optimized_index()

    def _build_optimized_index(self) -> None:
        """Build optimized index with byte offsets for O(1) file access (binary-safe)."""
        start_time = time.time()

        with open(self.data_file, 'rb') as f:
            byte_offset = 0

            for line_bytes in f:
                # Raw line length in bytes (including newline if present)
                raw_len = len(line_bytes)
                # Strip newline/whitespace to get content length (bytes)
                content_bytes = line_bytes.strip()

                if content_bytes:
                    try:
                        # Parse only the frame number (first field) from bytes
                        frame = int(content_bytes.split(b',')[0])

                        if frame not in self.frame_index:
                            self.frame_index[frame] = []

                        # Store byte offset and CONTENT length for direct seeking
                        # We will read exactly this many bytes starting at byte_offset
                        self.frame_index[frame].append((byte_offset, len(content_bytes)))

                    except (ValueError, IndexError):
                        pass  # Skip invalid lines

                byte_offset += raw_len

        self.statistics['index_build_time'] = time.time() - start_time
        self.statistics['total_frames_indexed'] = len(self.frame_index)
    
    def _get_file_handle(self) -> Any:
        """Get or create file handle for efficient seeking (binary mode)."""
        if self._file_handle is None or self._file_handle.closed:
            self._file_handle = open(self.data_file, 'rb')
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
            # Serialize seek/read to avoid interleaving between threads
            with self._io_lock:
                file_handle.seek(byte_offset)
                line_bytes = file_handle.read(line_length)
            # Decode after releasing lock to minimize lock time
            try:
                line = line_bytes.decode('utf-8').strip()
            except UnicodeDecodeError:
                # Skip lines that cannot be decoded as UTF-8
                continue
            
            if line:
                try:
                    detection = self._parse_detection_line_fast(line)
                    detections.append(detection)
                except (ValueError, IndexError):
                    continue
        
        load_time = time.time() - start_time
        self._update_statistics('direct_load_time', load_time)
        
        return MOTFrameData(frame_number=frame_number, detections=detections)
    
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
        """Load a single frame by seeking directly to indexed byte positions."""
        return self._load_frame_data_direct(frame_number)
    
    def load_batch(self, frame_numbers: List[int]) -> Dict[int, MOTFrameData]:
        """Load multiple frames and return a mapping from frame number to data."""
        start_time = time.time()

        result: Dict[int, MOTFrameData] = {}
        for frame_num in frame_numbers:
            result[frame_num] = self._load_frame_data_direct(frame_num)

        total_time = time.time() - start_time
        self._update_statistics('batch_total_time', total_time)

        return result
    
    def get_total_frames(self) -> int:
        """Get total number of frames."""
        return len(self.frame_index)
    
    def get_available_frames(self) -> Set[int]:
        """Get set of available frame numbers."""
        return set(self.frame_index.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics (indexing and I/O timings)."""
        total_lines = sum(len(positions) for positions in self.frame_index.values())

        stats = {
            'total_frames': len(self.frame_index),
            'total_indexed_lines': total_lines,
            'index_memory_bytes': sys.getsizeof(self.frame_index),
            'avg_direct_load_time': self.statistics.get('avg_direct_load_time', 0.0),
            'avg_batch_total_time': self.statistics.get('avg_batch_total_time', 0.0),
            'index_build_time': self.statistics.get('index_build_time', 0.0),
        }

        return stats
    
    def close(self) -> None:
        """Close file handle and clean up resources."""
        fh = getattr(self, "_file_handle", None)
        if fh and not fh.closed:
            fh.close()
    
    def __del__(self) -> None:
        """Cleanup on destruction."""
        try:
            self.close()
        except Exception:
            # Avoid raising during interpreter shutdown or partial initialization
            pass
