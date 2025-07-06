### Generated Data Format

The script generates realistic MOT format data with:
- **Realistic movement patterns**: Objects move with consistent velocity and random noise
- **Varying confidence scores**: Confidence changes over time with realistic fluctuations
- **Proper track continuity**: Objects appear and disappear naturally
- **Boundary constraints**: Objects stay within image boundaries

Each line follows the MOT format:
```
frame,track_id,bb_left,bb_top,bb_width,bb_height,confidence,x,y,z
```

### Example

```bash
python scripts/generate_large_mot_data.py -o examples/data/large_data.txt -t 1000 -f 100000 
```

### Using Generated Data

Once generated, use the data files with the MOTDataProvider:

```python
from dynamic_prefetching_cache import MOTDataProvider

# Use your generated data
provider = MOTDataProvider('examples/data/test_data.txt')
print(f"Generated data has {provider.get_total_frames()} frames")
print(f"Available frame range: {min(provider.get_available_frames())}-{max(provider.get_available_frames())}")
```

### Data Size Guidelines

| Configuration | Approx. Size | Use Case |
|---------------|-------------|----------|
| 100 tracks, 1K frames | ~1MB | Quick testing, development |
| 500 tracks, 10K frames | ~50MB | Performance testing |
| 1000 tracks, 100K frames | ~500MB | Stress testing, large datasets |
| 2000 tracks, 200K frames | ~2GB | Maximum performance testing |
