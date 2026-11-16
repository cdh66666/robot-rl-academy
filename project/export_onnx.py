"""Export a deterministic PPO policy and check ONNX against SB3 predictions.

The action clamp is included. The exported model is for the simulated example,
not firmware and not a driver for a physical robot.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from stable_baselines3 import PPO


class ExportPolicy(torch.nn.Module):
    def __init__(self, policy, low, high):
        super().__init__()
        self.policy = policy
        self.register_buffer("low", torch.as_tensor(low, dtype=torch.float32))
        self.register_buffer("high", torch.as_tensor(high, dtype=torch.float32))

    def forward(self, observation):
        action, _, _ = self.policy(observation, deterministic=True)
        return torch.minimum(torch.maximum(action, self.low), self.high)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=Path("runs/pendulum/ppo_pendulum.zip"))
    parser.add_argument("--out", type=Path, default=Path("runs/pendulum/policy.onnx"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    model = PPO.load(args.model, device="cpu")
    model.policy.eval()
    wrapper = ExportPolicy(model.policy, model.action_space.low, model.action_space.high).eval()
    dummy = torch.zeros((1, *model.observation_space.shape), dtype=torch.float32)
    with torch.no_grad():
        torch.onnx.export(wrapper, dummy, str(args.out), input_names=["observation"], output_names=["action"],
                          dynamic_axes={"observation": {0: "batch"}, "action": {0: "batch"}},
                          opset_version=17, dynamo=False)
    onnx.checker.check_model(onnx.load(str(args.out)))
    runtime = ort.InferenceSession(str(args.out), providers=["CPUExecutionProvider"])
    # Cover small and extreme observations, so the output-clamping contract is checked too.
    rng = np.random.default_rng(20261116)
    observations = np.concatenate([np.zeros((1,4)), rng.normal(0, 0.2, (50,4)), rng.normal(0, 20, (50,4))]).astype(np.float32)
    sb3, _ = model.predict(observations, deterministic=True)
    exported = runtime.run(None, {"observation": observations})[0]
    max_error = float(np.max(np.abs(sb3-exported)))
    if not np.allclose(sb3, exported, rtol=1e-5, atol=1e-5):
        raise RuntimeError(f"ONNX and SB3 differ, max error={max_error}")
    evidence = {"samples": len(observations), "max_absolute_error": max_error,
                "clip_inside_model": True, "observation_dtype": "float32",
                "note": "simulation policy only; hardware deployment not tested"}
    args.out.with_suffix(".verification.json").write_text(json.dumps(evidence, indent=2) + "\n",encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
