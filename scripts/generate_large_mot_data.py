#!/usr/bin/env python3
"""
Script to generate large MOT (Multi-Object Tracking) format test data.

This script creates realistic MOT data files for testing the dynamic prefetching cache
system with large datasets. It generates tracks with realistic movement patterns,
varying confidence scores, and proper track continuity.
"""

import random
import math
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass


@dataclass
class Track:
    """Represents a single object track with movement parameters."""
    track_id: int
    start_frame: int
    end_frame: int
    start_x: float
    start_y: float
    velocity_x: float
    velocity_y: float
    width: float
    height: float
    base_confidence: float
    
    def get_position(self, frame: int) -> Tuple[float, float]:
        """Calculate position at given frame."""
        if frame < self.start_frame or frame > self.end_frame:
            raise ValueError(f"Frame {frame} outside track range")
        
        frame_offset = frame - self.start_frame
        
        # Add some noise to movement
        noise_x = random.uniform(-2.0, 2.0)
        noise_y = random.uniform(-2.0, 2.0)
        
        x = self.start_x + (self.velocity_x * frame_offset) + noise_x
        y = self.start_y + (self.velocity_y * frame_offset) + noise_y
        
        return x, y
    
    def get_confidence(self, frame: int) -> float:
        """Calculate confidence at given frame with some variation."""
        base = self.base_confidence
        
        # Add frame-based variation
        frame_variation = 0.1 * math.sin(frame * 0.1)
        
        # Add random noise
        noise = random.uniform(-0.05, 0.05)
        
        confidence = base + frame_variation + noise
        return max(0.1, min(1.0, confidence))  # Clamp to valid range


class MOTDataGenerator:
    """Generates realistic MOT format data."""
    
    def __init__(self, 
                 image_width: int = 1920,
                 image_height: int = 1080,
                 min_track_length: int = 10,
                 max_track_length: int = 200):
        self.image_width = image_width
        self.image_height = image_height
        self.min_track_length = min_track_length
        self.max_track_length = max_track_length
        
    def generate_track(self, track_id: int, start_frame: int, max_frame: int) -> Track:
        """Generate a single track with realistic parameters."""
        
        # Random track length
        track_length = random.randint(self.min_track_length, self.max_track_length)
        end_frame = min(start_frame + track_length, max_frame)
        
        # Random starting position (avoid edges)
        margin = 100
        start_x = random.uniform(margin, self.image_width - margin)
        start_y = random.uniform(margin, self.image_height - margin)
        
        # Random velocity (pixels per frame)
        velocity_x = random.uniform(-5.0, 5.0)
        velocity_y = random.uniform(-5.0, 5.0)
        
        # Random object size
        width = random.uniform(50, 200)
        height = random.uniform(50, 200)
        
        # Random base confidence
        base_confidence = random.uniform(0.4, 0.95)
        
        return Track(
            track_id=track_id,
            start_frame=start_frame,
            end_frame=end_frame,
            start_x=start_x,
            start_y=start_y,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            width=width,
            height=height,
            base_confidence=base_confidence
        )
    
    def generate_tracks(self, num_tracks: int, num_frames: int) -> List[Track]:
        """Generate multiple tracks with overlapping lifespans."""
        tracks = []
        
        for track_id in range(1, num_tracks + 1):
            # Random start frame (allow tracks to start throughout the sequence)
            start_frame = random.randint(1, max(1, num_frames - self.min_track_length))
            
            track = self.generate_track(track_id, start_frame, num_frames)
            tracks.append(track)
        
        return tracks
    
    def generate_mot_data(self, tracks: List[Track], num_frames: int) -> List[str]:
        """Generate MOT format lines for all tracks."""
        lines = []
        
        for frame in range(1, num_frames + 1):
            frame_detections = []
            
            for track in tracks:
                if track.start_frame <= frame <= track.end_frame:
                    try:
                        x, y = track.get_position(frame)
                        confidence = track.get_confidence(frame)
                        
                        # Ensure bounding box stays within image bounds
                        bb_left = max(0, x - track.width / 2)
                        bb_top = max(0, y - track.height / 2)
                        bb_width = min(track.width, self.image_width - bb_left)
                        bb_height = min(track.height, self.image_height - bb_top)
                        
                        # Skip if bounding box is too small or outside image
                        if bb_width < 10 or bb_height < 10:
                            continue
                        
                        # MOT format: frame,track_id,bb_left,bb_top,bb_width,bb_height,confidence,x,y,z
                        line = f"{frame},{track.track_id},{bb_left:.1f},{bb_top:.1f},{bb_width:.1f},{bb_height:.1f},{confidence:.5f},{x:.1f},{y:.1f},0.0"
                        frame_detections.append(line)
                        
                    except ValueError:
                        continue
            
            lines.extend(frame_detections)
        
        return lines
    
    def generate_file(self, 
                     output_path: Path,
                     num_tracks: int,
                     num_frames: int,
                     progress_callback: Optional[Callable[[int, int, int], None]] = None) -> Dict[str, int]:
        """Generate MOT data file with progress tracking."""
        
        print(f"Generating {num_tracks} tracks across {num_frames} frames...")
        
        # Generate tracks
        tracks = self.generate_tracks(num_tracks, num_frames)
        
        print(f"Generated {len(tracks)} tracks")
        print(f"Writing to {output_path}...")
        
        # Generate and write data
        with open(output_path, 'w') as f:
            lines_written = 0
            
            for frame in range(1, num_frames + 1):
                frame_lines = []
                
                for track in tracks:
                    if track.start_frame <= frame <= track.end_frame:
                        try:
                            x, y = track.get_position(frame)
                            confidence = track.get_confidence(frame)
                            
                            bb_left = max(0, x - track.width / 2)
                            bb_top = max(0, y - track.height / 2)
                            bb_width = min(track.width, self.image_width - bb_left)
                            bb_height = min(track.height, self.image_height - bb_top)
                            
                            if bb_width >= 10 and bb_height >= 10:
                                line = f"{frame},{track.track_id},{bb_left:.1f},{bb_top:.1f},{bb_width:.1f},{bb_height:.1f},{confidence:.5f},{x:.1f},{y:.1f},0.0\n"
                                frame_lines.append(line)
                                
                        except ValueError:
                            continue
                
                # Write frame data
                f.writelines(frame_lines)
                lines_written += len(frame_lines)
                
                # Progress callback
                if progress_callback and frame % 1000 == 0:
                    progress_callback(frame, num_frames, lines_written)
        
        return {
            'total_lines': lines_written,
            'total_frames': num_frames,
            'total_tracks': len(tracks)
        }


def progress_printer(current_frame: int, total_frames: int, lines_written: int) -> None:
    """Simple progress printer."""
    percent = (current_frame / total_frames) * 100
    print(f"Progress: {current_frame}/{total_frames} frames ({percent:.1f}%) - {lines_written} lines written")


def main() -> None:
    """Main script entry point."""
    parser = argparse.ArgumentParser(description='Generate large MOT format test data')
    
    parser.add_argument('--output', '-o', type=str, required=True,
                       help='Output file path')
    parser.add_argument('--tracks', '-t', type=int, default=100,
                       help='Number of tracks to generate (default: 100)')
    parser.add_argument('--frames', '-f', type=int, default=10000,
                       help='Number of frames to generate (default: 10000)')
    parser.add_argument('--width', type=int, default=1920,
                       help='Image width in pixels (default: 1920)')
    parser.add_argument('--height', type=int, default=1080,
                       help='Image height in pixels (default: 1080)')
    parser.add_argument('--min-track-length', type=int, default=10,
                       help='Minimum track length in frames (default: 10)')
    parser.add_argument('--max-track-length', type=int, default=200,
                       help='Maximum track length in frames (default: 200)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducible generation (default: 42)')
    
    args = parser.parse_args()
    
    # Set random seed for reproducibility
    random.seed(args.seed)
    
    # Create output directory if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize generator
    generator = MOTDataGenerator(
        image_width=args.width,
        image_height=args.height,
        min_track_length=args.min_track_length,
        max_track_length=args.max_track_length
    )
    
    # Generate data
    print(f"Starting MOT data generation...")
    print(f"Configuration:")
    print(f"  - Output: {output_path}")
    print(f"  - Tracks: {args.tracks}")
    print(f"  - Frames: {args.frames}")
    print(f"  - Image size: {args.width}x{args.height}")
    print(f"  - Track length: {args.min_track_length}-{args.max_track_length} frames")
    print(f"  - Random seed: {args.seed}")
    print()
    
    stats = generator.generate_file(
        output_path=output_path,
        num_tracks=args.tracks,
        num_frames=args.frames,
        progress_callback=progress_printer
    )
    
    print(f"\nGeneration complete!")
    print(f"Statistics:")
    print(f"  - Total lines written: {stats['total_lines']:,}")
    print(f"  - Total frames: {stats['total_frames']:,}")
    print(f"  - Total tracks: {stats['total_tracks']:,}")
    print(f"  - Average detections per frame: {stats['total_lines'] / stats['total_frames']:.1f}")
    
    # File size info
    file_size = output_path.stat().st_size
    print(f"  - File size: {file_size:,} bytes ({file_size / (1024*1024):.1f} MB)")


if __name__ == '__main__':
    main() 