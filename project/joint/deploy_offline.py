"""Pure offline inference/adapter example. No serial, bus, hardware or motor commands."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import onnxruntime as ort
from contract import Q_COMMAND_LIMIT, Q_FAIL_LIMIT, POLICY_PERIOD_S, observation, position_reference


class OfflineJointPolicy:
    """Demonstrates policy I/O only. Thresholds are teaching-model assumptions."""
    def __init__(self, model_path: str | Path):
        options = ort.SessionOptions(); options.intra_op_num_threads = 1; options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), sess_options=options,
                                            providers=["CPUExecutionProvider"])
        self.previous_action = None

    def reset(self, current_angle_rad: float):
        # Initial reference equals the observed angle, as in training; sends no command.
        if not np.isfinite(current_angle_rad) or abs(current_angle_rad) > Q_COMMAND_LIMIT:
            raise ValueError("initial angle outside the teaching model's command range")
        self.previous_action = current_angle_rad / Q_COMMAND_LIMIT

    def infer(self, *, angle_rad: float, velocity_rad_s: float,
              target_rad: float, sample_age_s: float) -> dict:
        values = np.asarray([angle_rad, velocity_rad_s, target_rad, sample_age_s], dtype=float)
        if self.previous_action is None:
            raise ValueError("reset with an initial measured angle before inference")
        if not np.all(np.isfinite(values)):
            raise ValueError("invalid observation or timestamp")
        if not 0.0 <= sample_age_s <= 2 * POLICY_PERIOD_S:
            raise ValueError("stale sample: no new reference produced")
        if abs(angle_rad) > Q_FAIL_LIMIT or abs(velocity_rad_s) > 12 or abs(target_rad) > .75:
            raise ValueError("outside the teaching model's tested operating envelope")
        features = observation(angle_rad, velocity_rad_s, target_rad, self.previous_action)
        prediction = self.session.run(["action"], {"observation":features.reshape(1,4)})[0]
        action = float(prediction[0,0])
        if not np.isfinite(action):
            raise ValueError("invalid policy output")
        action = float(np.clip(action, -1.0, 1.0))
        reference = position_reference(action, self.previous_action * Q_COMMAND_LIMIT)
        self.previous_action = reference / Q_COMMAND_LIMIT
        return {"observation":features.tolist(), "action_normalized":action,
                "position_reference_rad":reference, "control_period_s":POLICY_PERIOD_S,
                "executed_on_hardware":False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("artifacts/joint_actor.onnx"))
    args = parser.parse_args()
    policy = OfflineJointPolicy(args.model)
    # These inputs are invented for demonstration and do not come from a device.
    policy.reset(current_angle_rad=0.10)
    result = policy.infer(angle_rad=0.10, velocity_rad_s=0.0, target_rad=0.50, sample_age_s=0.0)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
