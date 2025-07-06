"""
Visual Demo of Dynamic Prefetch Cache

Shows a timeline representation of frames with:
- Current position indicator
- Cached frames visualization
- Navigation controls (-5, -1, +1, +5, +30 frames)
- Real-time cache statistics
"""

import sys
from pathlib import Path

# Add parent directory to Python path to find src module
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import tkinter as tk
from tkinter import ttk
import time
import logging
from typing import Optional, Set, List, Dict, Any, Callable

# Set up debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('VisualExample')

# Enable cache logging at INFO level to see cache operations
cache_logger = logging.getLogger('DynamicPrefetchingCache')
cache_logger.setLevel(logging.DEBUG)

from src.dynamic_prefetching_cache import DynamicPrefetchingCache, DynamicDataPredictor, MOTDataProvider, EvictionPolicyOldest

NAVIGATION_STEPS = [-15, -5, -1, 1, 5, 15]

class CacheVisualizerApp:
    """Main application window with cache visualization."""
    
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Dynamic Cache Visualizer")
        self.root.geometry("1200x600")
        
        # Cache setup with optimized settings
        self.provider = MOTDataProvider('examples/data/ultra_dense_data.txt', cache_size=100)
        self.predictor = DynamicDataPredictor(possible_jumps=NAVIGATION_STEPS)
        self.cache = DynamicPrefetchingCache(
            provider=self.provider,
            predictor=self.predictor,
            on_event=self.on_cache_event
        )
        
        # State
        available_frames = sorted(self.provider.get_available_frames())
        self.current_frame: Optional[int] = available_frames[0] if available_frames else None
        self.cached_frames: Set[int] = set()
        self.recent_events: List[str] = []
        self.stats: Dict[str, Any] = {}
        
        self.setup_ui()
        self.update_display()
    
    def setup_ui(self) -> None:
        """Create the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S)
        
        # Title
        title_label = ttk.Label(main_frame, text="Dynamic Cache Visualizer", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 20))
        
        # Timeline frame
        timeline_frame = ttk.LabelFrame(main_frame, text="Frame Timeline", padding="10")
        timeline_frame.grid(row=1, column=0, columnspan=4, sticky=tk.W + tk.E, pady=(0, 10))
        
        # Canvas for timeline
        self.canvas = tk.Canvas(timeline_frame, height=100, bg='white')
        self.canvas.grid(row=0, column=0, sticky=tk.W + tk.E)
        
        # Scrollbar for timeline
        scrollbar = ttk.Scrollbar(timeline_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        scrollbar.grid(row=1, column=0, sticky=tk.W + tk.E)
        self.canvas.configure(xscrollcommand=scrollbar.set)
        
        # Control buttons
        control_frame = ttk.LabelFrame(main_frame, text="Navigation", padding="10")
        control_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W + tk.E, pady=(0, 10))
        
        for i, step in enumerate(NAVIGATION_STEPS):
            def make_navigate_command(s: int) -> Callable[[], None]:
                return lambda: self.navigate(s)
            
            ttk.Button(control_frame, text=f"{'←' if step < 0 else '→'} {abs(step)}", 
                      command=make_navigate_command(step)).grid(row=0, column=i+1, padx=5)
        
        # Jump controls
        jump_frame = ttk.Frame(control_frame)
        jump_frame.grid(row=1, column=0, columnspan=5, pady=(10, 0))
        
        ttk.Label(jump_frame, text="Jump to frame:").grid(row=0, column=0, padx=5)
        self.jump_entry = ttk.Entry(jump_frame, width=10)
        self.jump_entry.grid(row=0, column=1, padx=5)
        ttk.Button(jump_frame, text="Go", 
                  command=self.jump_to_frame).grid(row=0, column=2, padx=5)
        
        # Statistics
        stats_frame = ttk.LabelFrame(main_frame, text="Cache Statistics", padding="10")
        stats_frame.grid(row=2, column=2, sticky=tk.W + tk.E + tk.N + tk.S, pady=(0, 10))
        
        # Stats text with scrollbar
        stats_text_frame = ttk.Frame(stats_frame)
        stats_text_frame.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S)
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.rowconfigure(0, weight=1)
        
        self.stats_text = tk.Text(stats_text_frame, height=8, width=30, font=('Consolas', 9), wrap=tk.WORD)
        stats_scrollbar = ttk.Scrollbar(stats_text_frame, orient=tk.VERTICAL, command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=stats_scrollbar.set)
        
        self.stats_text.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S)
        stats_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)
        stats_text_frame.columnconfigure(0, weight=1)
        stats_text_frame.rowconfigure(0, weight=1)
        
        # Prefetch visualization
        prefetch_frame = ttk.LabelFrame(main_frame, text="Prefetch Queue", padding="10")
        prefetch_frame.grid(row=2, column=3, sticky=tk.W + tk.E + tk.N + tk.S, pady=(0, 10))
        
        # Prefetch text with scrollbar
        prefetch_text_frame = ttk.Frame(prefetch_frame)
        prefetch_text_frame.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S)
        prefetch_frame.columnconfigure(0, weight=1)
        prefetch_frame.rowconfigure(0, weight=1)
        
        self.prefetch_text = tk.Text(prefetch_text_frame, height=8, width=30, font=('Consolas', 9), wrap=tk.WORD)
        prefetch_scrollbar = ttk.Scrollbar(prefetch_text_frame, orient=tk.VERTICAL, command=self.prefetch_text.yview)
        self.prefetch_text.configure(yscrollcommand=prefetch_scrollbar.set)
        
        self.prefetch_text.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S)
        prefetch_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)
        prefetch_text_frame.columnconfigure(0, weight=1)
        prefetch_text_frame.rowconfigure(0, weight=1)
        
        # Events log
        events_frame = ttk.LabelFrame(main_frame, text="Recent Events", padding="10")
        events_frame.grid(row=3, column=0, columnspan=4, sticky=tk.W + tk.E + tk.N + tk.S, pady=(0, 10))
        
        # Events text with scrollbar
        events_text_frame = ttk.Frame(events_frame)
        events_text_frame.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S)
        events_frame.columnconfigure(0, weight=1)
        events_frame.rowconfigure(0, weight=1)
        
        self.events_text = tk.Text(events_text_frame, height=6, font=('Consolas', 8), wrap=tk.WORD)
        events_scrollbar = ttk.Scrollbar(events_text_frame, orient=tk.VERTICAL, command=self.events_text.yview)
        self.events_text.configure(yscrollcommand=events_scrollbar.set)
        
        self.events_text.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S)
        events_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)
        events_text_frame.columnconfigure(0, weight=1)
        events_text_frame.rowconfigure(0, weight=1)
        
        # Configure grid weights for proper scaling
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Main frame scaling
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.columnconfigure(3, weight=1)
        main_frame.rowconfigure(1, weight=1)  # Timeline row
        main_frame.rowconfigure(2, weight=2)  # Stats/prefetch row (bigger)
        main_frame.rowconfigure(3, weight=1)  # Events row
        
        # Individual frame scaling
        timeline_frame.columnconfigure(0, weight=1)
    
    def navigate(self, delta: int) -> None:
        """Navigate by delta frames - SIMPLE cache usage."""
        try:
            available_frames = sorted(self.provider.get_available_frames())
            if not available_frames:
                return
                
            # Find current position in available frames
            try:
                if self.current_frame is not None:
                    current_idx = available_frames.index(self.current_frame)
                else:
                    current_idx = 0
            except ValueError:
                current_idx = 0
            
            # Calculate new index
            new_idx = max(0, min(current_idx + delta, len(available_frames) - 1))
            new_frame = available_frames[new_idx]
            
            if new_frame != self.current_frame:
                logger.debug(f"NAVIGATE: {self.current_frame} -> {new_frame} (delta: {delta})")
                self.current_frame = new_frame
                # LINE 1: Just get the data - cache handles everything internally
                start_time = time.time()
                frame_data = self.cache.get(self.current_frame)
                end_time = time.time()
                logger.debug(f"NAVIGATE: {self.current_frame} -> {new_frame} (time: {end_time - start_time:.6f}s)")
                self.add_event(f"Loaded frame {self.current_frame}")
                    
        except Exception as e:
            self.add_event(f"Navigation error: {e}")
    
    def jump_to_frame(self) -> None:
        """Jump to specific frame number."""
        try:
            frame_num = int(self.jump_entry.get())
            available_frames = self.provider.get_available_frames()
            
            if frame_num in available_frames:
                logger.debug(f"JUMP: {self.current_frame} -> {frame_num}")
                self.current_frame = frame_num
                # LINE 2: Just get the data - cache handles everything internally
                start_time = time.time()
                frame_data = self.cache.get(self.current_frame)
                end_time = time.time()
                logger.debug(f"JUMP: {self.current_frame} -> {frame_num} (time: {end_time - start_time:.6f}s)")
                self.add_event(f"Jumped to frame {self.current_frame}")
            else:
                self.add_event(f"Frame {frame_num} not available")
            
            self.jump_entry.delete(0, tk.END)
        except ValueError:
            pass  # Invalid input, ignore
    
    def on_cache_event(self, event_name: str, **kwargs: Any) -> None:
        """Handle cache events."""
        # LINE 3: Track what's cached for UI display
        if event_name in ['cache_load_complete', 'prefetch_success']:
            self.cached_frames.add(kwargs['key'])
        elif event_name == 'cache_evict':
            self.cached_frames.discard(kwargs['key'])
    
    def add_event(self, event_str: str) -> None:
        """Add event to recent events list with thread safety."""
        try:
            self.recent_events.append(f"{time.strftime('%H:%M:%S')} - {event_str}")
            if len(self.recent_events) > 20:
                self.recent_events.pop(0)
        except Exception as e:
            print(f"Error adding event: {e}")
    
    def update_display(self) -> None:
        """Update the visual display with error protection."""
        try:
            self.draw_timeline()
            self.update_stats()
            self.update_prefetch()
            self.update_events()
        except Exception as e:
            print(f"Error updating display: {e}")
        finally:
            # Schedule next update
            try:
                self.root.after(100, self.update_display)
            except tk.TclError:
                # UI is closing, stop updates
                pass
    
    def draw_timeline(self) -> None:
        """Draw the frame timeline showing only frames around current position."""
        try:
            self.canvas.delete("all")
            
            # Timeline parameters
            canvas_width = self.canvas.winfo_width() or 800
            canvas_height = self.canvas.winfo_height() or 100
            
            if canvas_width <= 1:  # Canvas not initialized yet
                return
            
            # Get all available frames
            all_frames = sorted(self.provider.get_available_frames())
            if not all_frames or self.current_frame is None:
                # Show a message if no frames available
                self.canvas.create_text(canvas_width//2, canvas_height//2, 
                                      text="No frames available" if not all_frames else "No current frame",
                                      fill='red', font=('Arial', 12))
                return
            
            # OPTIMIZATION: Only show frames in a reasonable window around current frame
            window_size = 200  # Show ±200 frames around current (total 400 frames max)
            
            # Find frames to display - more robust filtering
            frames_to_show = []
            current_frame = self.current_frame
            
            # Find the range of frames to show
            min_frame = current_frame - window_size
            max_frame = current_frame + window_size
            
            # Filter frames within the window
            for frame in all_frames:
                if min_frame <= frame <= max_frame:
                    frames_to_show.append(frame)
            
            if not frames_to_show:
                # Show debug info if no frames in window
                self.canvas.create_text(canvas_width//2, canvas_height//2, 
                                      text=f"No frames in window ±{window_size} around {current_frame}",
                                      fill='orange', font=('Arial', 10))
                return
            
            # Calculate frame width and total timeline width
            frame_width = max(5, min(20, canvas_width // len(frames_to_show)))  # Adaptive width
            total_width = len(frames_to_show) * frame_width
            
            # Draw frame boxes (only the visible window)
            for i, frame_num in enumerate(frames_to_show):
                x = i * frame_width
                
                # Determine color based on state
                if frame_num == self.current_frame:
                    color = 'red'  # Current frame
                    outline = 'darkred'
                elif frame_num in self.cached_frames:
                    color = 'lightgreen'  # Cached frame
                    outline = 'green'
                else:
                    color = 'lightgray'  # Not cached
                    outline = 'gray'
                
                # Draw frame rectangle
                self.canvas.create_rectangle(
                    x, 10, x + frame_width - 2, canvas_height - 10,
                    fill=color, outline=outline, width=1
                )
                
                # Draw frame number (every 10th frame or for current frame)
                if frame_num % 10 == 0 or frame_num == self.current_frame:
                    self.canvas.create_text(
                        x + frame_width/2, canvas_height - 20,
                        text=str(frame_num), font=('Arial', 8)
                    )
            
            # Set scroll region to only the visible window
            self.canvas.configure(scrollregion=(0, 0, total_width, canvas_height))
            
            # Center the current frame in the view
            if self.current_frame in frames_to_show:
                current_idx = frames_to_show.index(self.current_frame)
                current_x = current_idx * frame_width
                # Center the current frame
                center_x = current_x + frame_width / 2
                view_center = canvas_width / 2
                if total_width > canvas_width:
                    scroll_pos = max(0, min(1, (center_x - view_center) / (total_width - canvas_width)))
                    self.canvas.xview_moveto(scroll_pos)
            
            # Legend (always visible at top-left)
            legend_y = 5
            self.canvas.create_text(10, legend_y, text="Current", fill='red', anchor='w', font=('Arial', 8, 'bold'))
            self.canvas.create_text(60, legend_y, text="Cached", fill='green', anchor='w', font=('Arial', 8))
            self.canvas.create_text(110, legend_y, text="Not Cached", fill='gray', anchor='w', font=('Arial', 8))
            
            # Show window info
            self.canvas.create_text(canvas_width - 10, legend_y, 
                                  text=f"Showing ±{window_size} frames ({len(frames_to_show)} total)", 
                                  fill='blue', anchor='e', font=('Arial', 8))
            
        except Exception as e:
            print(f"Error drawing timeline: {e}")
    
    def update_stats(self) -> None:
        """Update statistics display."""
        # LINE 4: Get cache stats for display
        self.stats = self.cache.stats()
        
        stats_text = f"""Current Frame: {self.current_frame}
Cached Frames: {len(self.cached_frames)}

Cache Stats:
  Hits: {self.stats.get('hits', 0)}
  Misses: {self.stats.get('misses', 0)}
  Evictions: {self.stats.get('evictions', 0)}
  
Cache Usage:
  Keys: {self.stats.get('cache_keys', 0)}/{self.cache.max_keys_cached}
  
Prefetch:
  Active Tasks: {self.stats.get('active_prefetch_tasks', 0)}
  Errors: {self.stats.get('prefetch_errors', 0)}"""
        
        hit_rate: float = 0.0
        if self.stats.get('hits', 0) + self.stats.get('misses', 0) > 0:
            hit_rate = self.stats.get('hits', 0) / (self.stats.get('hits', 0) + self.stats.get('misses', 0)) * 100
        
        stats_text += f"\n\nHit Rate: {hit_rate:.1f}%"
        
        # Preserve scroll position
        scroll_position = self.stats_text.yview()
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats_text)
        self.stats_text.yview_moveto(scroll_position[0])
    
    def update_prefetch(self) -> None:
        """Update prefetch queue display."""
        # LINE 5: Get predictions for display
        if self.current_frame is not None:
            scores = self.predictor.get_likelihoods(self.current_frame, list(self.cache.history))
            
            # Sort by likelihood (highest first)
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            
            prefetch_text = f"Current Frame: {self.current_frame}\n"
            prefetch_text += f"History: {list(self.cache.history)[-5:]}\n\n"
            prefetch_text += "Predictions:\n"
            
            for i, (frame, likelihood) in enumerate(sorted_scores):
                status = ""
                if frame in self.cached_frames:
                    status = " ✓"
                elif frame == self.current_frame:
                    status = " ●"
                
                prefetch_text += f"{frame:4d}: {likelihood:.3f}{status}\n"
                
            prefetch_text += f"\nQueue Size: {self.stats.get('active_prefetch_tasks', 0)}"
            
        else:
            prefetch_text = "No current frame"
        
        # Preserve scroll position
        scroll_position = self.prefetch_text.yview()
        self.prefetch_text.delete(1.0, tk.END)
        self.prefetch_text.insert(1.0, prefetch_text)
        self.prefetch_text.yview_moveto(scroll_position[0])
    
    def update_events(self) -> None:
        """Update events display."""
        try:
            events_text = "\n".join(self.recent_events[-20:])  # Show last 20 events
            
            # Check if user has scrolled up manually
            scroll_position = self.events_text.yview()
            is_at_bottom = scroll_position[1] >= 0.98  # Close to bottom
            
            self.events_text.delete(1.0, tk.END)
            self.events_text.insert(1.0, events_text)
            
            # Only auto-scroll to bottom if user was already at bottom
            if is_at_bottom:
                self.events_text.see(tk.END)
            else:
                # Preserve scroll position if user scrolled up
                self.events_text.yview_moveto(scroll_position[0])
                
        except Exception as e:
            print(f"Error updating events: {e}")
    
    def run(self) -> None:
        """Start the application."""
        self.root.mainloop()


if __name__ == "__main__":
    app = CacheVisualizerApp()
    app.run()
