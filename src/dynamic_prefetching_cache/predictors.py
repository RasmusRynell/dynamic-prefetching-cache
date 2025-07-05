from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Dict, List, Optional

from .types import AccessPredictor


class DistanceDecayPredictor(AccessPredictor):
    """Simple predictor based on distance decay from current position."""
    
    def __init__(self, max_span: int = 60, decay: float = 1.5):
        self.max_span = max_span
        self.decay = decay
    
    def get_likelihoods(self, current: int, history: Sequence[int]) -> dict[int, float]:
        """Return likelihood scores based on distance from current key."""
        keys = {current + d for d in range(-self.max_span, self.max_span + 1)}
        return {k: 1 / (abs(k - current) + 1) ** self.decay for k in keys}


class DynamicDistanceDecayPredictor(AccessPredictor):
    """Predicts data playback patterns with forward bias."""
    
    def __init__(self, forward_bias: float = 2.0, max_span: int = 25):
        self.forward_bias = forward_bias
        self.max_span = max_span
    
    def get_likelihoods(self, current: int, history: Sequence[int]) -> dict[int, float]:
        """Generate likelihood scores with forward playback bias."""
        scores = {}
        
        # Strong forward bias for normal playback
        for i in range(1, self.max_span + 1):
            key = current + i
            scores[key] = self.forward_bias / (i ** 0.8)
        
        # Weaker backward bias for seeks
        for i in range(1, min(self.max_span // 2, current) + 1):
            key = current - i
            scores[key] = 0.3 / (i ** 1.2)
        
        # Boost likelihood for recent history patterns
        if len(history) >= 2:
            recent_direction = history[-1] - history[-2]
            if recent_direction > 0:  # Forward movement
                for i in range(1, 10):
                    key = current + i
                    if key in scores:
                        scores[key] *= 1.5
        
        return scores
    

class DynamicDataPredictor(AccessPredictor):
    """
    Probabilistic next-frame predictor for interactive media playback.

    Scoring terms (all additive):
    • Forward bias: ∝ forward_bias / (Δf ** forward_exp)
    • Backward bias: ∝ backward_bias / (Δb ** backward_exp)
    • Exact jump target: +jump_boost
    • Jump proximity (±proximity_range): +proximity_boost / (|offset|+1)
    • Recent forward streak: multiply affected forward scores by history_boost

    Parameters
    ----------
    possible_jumps : list[int]
        Relative frame offsets available to the user.
    forward_bias : float, default 2.0
    backward_bias : float, default 0.3
    jump_boost : float, default 3.0
    proximity_boost : float, default 1.2
    history_boost : float, default 1.5
    max_span : int, default 25
        Max forward distance; backward span is max_span//2.
    forward_exp : float, default 0.8
    backward_exp : float, default 1.2
    proximity_range : int, default 3
    length : Optional[int], default None
        Total number of frames (if known).  Predictions beyond this are clipped.
    """

    def __init__(
        self,
        possible_jumps: List[int],
        *,
        forward_bias: float = 2.0,
        backward_bias: float = 0.3,
        jump_boost: float = 5.0,
        proximity_boost: float = 2.0,
        history_boost: float = 2.0,
        max_span: int = 30,
        forward_exp: float = 0.8,
        backward_exp: float = 1.2,
        proximity_range: int = 5,
        length: Optional[int] = None,
    ):
        self.possible_jumps = possible_jumps
        self.forward_bias = forward_bias
        self.backward_bias = backward_bias
        self.jump_boost = jump_boost
        self.proximity_boost = proximity_boost
        self.history_boost = history_boost
        self.max_span = max_span
        self.forward_exp = forward_exp
        self.backward_exp = backward_exp
        self.proximity_range = proximity_range
        self.length = length

    def _clip(self, frame: int) -> bool:
        """Return True if frame is within [0, length) (or always True if length=None)."""
        if frame < 0:
            return False
        return self.length is None or frame < self.length

    def get_likelihoods(self, current: int, history: Sequence[int]) -> Dict[int, float]:
        scores: Dict[int, float] = defaultdict(float)

        # Forward bias
        for d in range(1, self.max_span + 1):
            f = current + d
            if self._clip(f):
                scores[f] += self.forward_bias / (d ** self.forward_exp)

        # Backward bias
        back_span = min(self.max_span // 2, current)
        for d in range(1, back_span + 1):
            f = current - d
            scores[f] += self.backward_bias / (d ** self.backward_exp)

        # Exact jump destinations
        for j in self.possible_jumps:
            tgt = current + j
            if self._clip(tgt):
                scores[tgt] += self.jump_boost

        # Proximity to jump targets
        for j in self.possible_jumps:
            tgt = current + j
            if not self._clip(tgt):
                continue
            for off in range(-self.proximity_range, self.proximity_range + 1):
                if off == 0:
                    continue
                f = tgt + off
                if self._clip(f):
                    scores[f] += self.proximity_boost / (abs(off) + 1)

        # Recent-history forward streak boost
        if len(history) >= 3:
            if all(history[i] < history[i + 1] for i in (-3, -2)):
                for d in range(1, min(10, self.max_span) + 1):
                    f = current + d
                    if f in scores:
                        scores[f] *= self.history_boost

        return dict(scores)