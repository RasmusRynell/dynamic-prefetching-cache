# Test Structure

This directory contains the test suite for the dynamic prefetching cache project.

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures and test utilities
├── data/                    # Test data files
│   └── simple_mot_data.txt  # Simple MOT data for testing
├── integration/             # Integration tests
│   └── test_cache_integration.py
└── unit/                    # Unit tests
    ├── test_cache.py        # Tests for DynamicPrefetchingCache
    ├── test_predictors.py   # Tests for access predictors
    ├── test_providers.py    # Tests for data providers
    └── test_types.py        # Tests for type definitions

```

## Running Tests

### Install Dependencies

```bash
pip install -e ".[dev]"
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Types

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Exclude slow tests
pytest -m "not slow"
```

### Run with Coverage

```bash
pytest --cov=src/dynamic_prefetching_cache --cov-report=html
```

## Test Categories

- **Unit Tests**: Test individual components in isolation using mocks
- **Integration Tests**: Test components working together with real data
- **Slow Tests**: Performance tests that may take longer to run

## Test Data

- `tests/data/simple_mot_data.txt`: Small MOT dataset for quick testing
- `examples/data/example_data.txt`: Large example dataset for integration tests

## Fixtures

The `conftest.py` file provides shared fixtures:

- `mock_provider`: Mock data provider for unit tests
- `mock_predictor`: Mock access predictor for unit tests  
- `temp_mot_file`: Temporary MOT data file
- `example_data_path`: Path to example data file
- `small_test_data`: Small test dataset for unit tests 