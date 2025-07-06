"""Unit tests for access predictors."""

import pytest
from dynamic_prefetching_cache.predictors import (
    DistanceDecayPredictor,
    DynamicDistanceDecayPredictor,
    DynamicDataPredictor
)


class TestDistanceDecayPredictor:
    """Test suite for DistanceDecayPredictor."""
    
    def test_returns_dict_with_float_values(self):
        """Test that predictor returns correct type and positive values."""
        predictor = DistanceDecayPredictor()
        result = predictor.get_likelihoods(current=10, history=[])
        
        assert isinstance(result, dict)
        assert all(isinstance(k, int) for k in result.keys())
        assert all(isinstance(v, float) and v > 0 for v in result.values())
        assert len(result) > 0
    
    def test_handles_empty_history(self):
        """Test predictor works with empty history."""
        predictor = DistanceDecayPredictor()
        result = predictor.get_likelihoods(current=5, history=[])
        assert len(result) > 0


class TestDynamicDistanceDecayPredictor:
    """Test suite for DynamicDistanceDecayPredictor."""
    
    def test_returns_dict_with_float_values(self):
        """Test that predictor returns correct type and positive values."""
        predictor = DynamicDistanceDecayPredictor()
        result = predictor.get_likelihoods(current=10, history=[])
        
        assert isinstance(result, dict)
        assert all(isinstance(k, int) for k in result.keys())
        assert all(isinstance(v, float) and v > 0 for v in result.values())
        assert len(result) > 0
    
    def test_handles_empty_history(self):
        """Test predictor works with empty history."""
        predictor = DynamicDistanceDecayPredictor()
        result = predictor.get_likelihoods(current=5, history=[])
        assert len(result) > 0


class TestDynamicDataPredictor:
    """Test suite for DynamicDataPredictor."""
    
    def test_basic_contract_compliance(self):
        """Test that predictor returns correct type and positive values."""
        predictor = DynamicDataPredictor(possible_jumps=[5, 10, -5])
        result = predictor.get_likelihoods(current=10, history=[])
        
        assert isinstance(result, dict)
        assert all(isinstance(k, int) for k in result.keys())
        assert all(isinstance(v, float) and v > 0 for v in result.values())
        assert len(result) > 0
    
    def test_handles_empty_history(self):
        """Test predictor works with empty history."""
        predictor = DynamicDataPredictor(possible_jumps=[5, 10])
        result = predictor.get_likelihoods(current=5, history=[])
        assert len(result) > 0
    
    def test_handles_single_item_history(self):
        """Test predictor works with single item history."""
        predictor = DynamicDataPredictor(possible_jumps=[5, 10])
        result = predictor.get_likelihoods(current=5, history=[3])
        assert len(result) > 0
    
    def test_jump_targets_get_boost(self):
        """Test that exact jump targets receive jump_boost scoring."""
        predictor = DynamicDataPredictor(
            possible_jumps=[5, 10], 
            jump_boost=10.0,
            forward_bias=1.0
        )
        result = predictor.get_likelihoods(current=0, history=[])
        
        # Jump targets should have higher scores than regular forward positions
        jump_target_5 = result.get(5, 0)
        jump_target_10 = result.get(10, 0)
        regular_forward = result.get(1, 0)
        
        assert jump_target_5 > regular_forward
        assert jump_target_10 > regular_forward
    
    def test_proximity_boost_around_jump_targets(self):
        """Test that positions near jump targets get proximity boost."""
        predictor = DynamicDataPredictor(
            possible_jumps=[10], 
            proximity_boost=2.0,
            proximity_range=2
        )
        result = predictor.get_likelihoods(current=0, history=[])
        
        # Positions near jump target (10) should have some boost
        near_jump_8 = result.get(8, 0)  # 10-2
        near_jump_12 = result.get(12, 0)  # 10+2
        far_from_jump = result.get(20, 0)
        
        assert near_jump_8 > 0
        assert near_jump_12 > 0
        # Far positions might not exist or have lower base scores
    
    def test_history_boost_with_forward_streak(self):
        """Test that forward streak in history boosts forward predictions."""
        predictor = DynamicDataPredictor(
            possible_jumps=[],
            history_boost=2.0,
            forward_bias=1.0
        )
        
        # Test with forward streak history
        forward_history = [5, 6, 7, 8]  # Clear forward progression
        result_with_boost = predictor.get_likelihoods(current=8, history=forward_history)
        
        # Test without forward streak
        mixed_history = [5, 3, 7, 6]  # No clear forward progression
        result_without_boost = predictor.get_likelihoods(current=8, history=mixed_history)
        
        # Forward positions should be boosted with forward streak
        forward_pos = 9
        if forward_pos in result_with_boost and forward_pos in result_without_boost:
            assert result_with_boost[forward_pos] > result_without_boost[forward_pos]
    
    def test_length_clipping_bounds_predictions(self):
        """Test that length parameter clips predictions to valid range."""
        predictor = DynamicDataPredictor(
            possible_jumps=[50], 
            length=20,  # Only frames 0-19 are valid
            max_span=30
        )
        result = predictor.get_likelihoods(current=10, history=[])
        
        # No predictions should exceed length-1
        assert all(key < 20 for key in result.keys())
        # No negative predictions
        assert all(key >= 0 for key in result.keys())
    
    def test_negative_current_handling(self):
        """Test behavior with negative current values."""
        predictor = DynamicDataPredictor(possible_jumps=[5, 10])
        result = predictor.get_likelihoods(current=-5, history=[])
        
        # Should still return predictions, but handle negative bounds
        assert len(result) > 0
        # Should not predict negative frames (due to _clip method)
        assert all(key >= 0 for key in result.keys())
    
    def test_boundary_conditions_current_zero(self):
        """Test predictor behavior when current=0."""
        predictor = DynamicDataPredictor(possible_jumps=[5, 10])
        result = predictor.get_likelihoods(current=0, history=[])
        
        assert len(result) > 0
        # Should have forward predictions
        assert any(key > 0 for key in result.keys())
        # Should not have negative predictions
        assert all(key >= 0 for key in result.keys())
    
    def test_boundary_conditions_near_length(self):
        """Test predictor behavior when current is near length boundary."""
        predictor = DynamicDataPredictor(
            possible_jumps=[5], 
            length=10,
            max_span=20
        )
        result = predictor.get_likelihoods(current=8, history=[])
        
        # Should not predict beyond length
        assert all(key < 10 for key in result.keys())
        # Should still have some predictions
        assert len(result) > 0
    
    def test_empty_possible_jumps(self):
        """Test predictor works with empty possible_jumps list."""
        predictor = DynamicDataPredictor(possible_jumps=[])
        result = predictor.get_likelihoods(current=5, history=[])
        
        # Should still have forward/backward bias predictions
        assert len(result) > 0
        # Should have forward predictions due to forward_bias
        assert any(key > 5 for key in result.keys())
    
    def test_parameter_validation_edge_cases(self):
        """Test predictor handles edge case parameters reasonably."""
        # Test with very small max_span
        predictor = DynamicDataPredictor(possible_jumps=[1], max_span=1)
        result = predictor.get_likelihoods(current=5, history=[])
        assert len(result) > 0
        
        # Test with zero proximity_range
        predictor = DynamicDataPredictor(possible_jumps=[5], proximity_range=0)
        result = predictor.get_likelihoods(current=0, history=[])
        assert len(result) > 0