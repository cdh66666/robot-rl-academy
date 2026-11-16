"""Shared observation/action contract; no simulator, training framework or I/O."""
import numpy as np

Q_COMMAND_LIMIT = 0.9       # rad, this teaching model's assumed command bound
Q_FAIL_LIMIT = 1.04         # rad, this teaching model's termination threshold
QD_SCALE = 5.0              # rad/s, speed input normalizer
POLICY_PERIOD_S = 0.02      # seconds
MAX_REFERENCE_RATE = 3.0    # rad/s, a modeled setpoint slew limit


def observation(q: float, qd: float, target: float, previous_action: float) -> np.ndarray:
    values = np.asarray([q, qd, target, previous_action], dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("observation values must be finite")
    return np.asarray([
        np.clip(q / Q_COMMAND_LIMIT, -2.0, 2.0),
        np.clip(qd / QD_SCALE, -1.0, 1.0),
        np.clip(target / Q_COMMAND_LIMIT, -1.0, 1.0),
        np.clip(previous_action, -1.0, 1.0),
    ], dtype=np.float32)


def position_reference(action: float, previous_reference_rad: float) -> float:
    """Bound the requested position and its per-cycle change."""
    if not np.isfinite(action) or not np.isfinite(previous_reference_rad):
        raise ValueError("action and previous reference must be finite")
    requested = float(np.clip(action, -1.0, 1.0) * Q_COMMAND_LIMIT)
    previous = float(np.clip(previous_reference_rad, -Q_COMMAND_LIMIT, Q_COMMAND_LIMIT))
    max_delta = MAX_REFERENCE_RATE * POLICY_PERIOD_S
    return float(np.clip(requested, previous-max_delta, previous+max_delta))
