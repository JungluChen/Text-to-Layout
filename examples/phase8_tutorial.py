"""Executable Phase 8 tutorial: verification, dataset, and differentiable model smoke."""
import numpy as np
from text_to_gds.scientific_verification import check_passivity
from text_to_gds.neural_surrogate import NumpySParameterPredictor

assert check_passivity(np.eye(2) * 0.5).passed
print(NumpySParameterPredictor().predict([0.0] * 16))
