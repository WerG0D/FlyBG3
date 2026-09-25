"""Feature extraction is deliberately incapable of accepting observations."""
from __future__ import annotations

from .model import FEATURE_NAMES, NeuralFeatures


class NeuralFeatureExtractor:
    def extract(self, neural_activity: dict[str, object]) -> NeuralFeatures:
        rates = neural_activity["rates_hz"]
        if not isinstance(rates, dict):
            raise TypeError("expected rates_hz from MaleCNS")
        return NeuralFeatures(tuple(float(rates[name]) for name in FEATURE_NAMES))
