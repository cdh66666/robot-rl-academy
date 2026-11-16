"""Verify SB3 / ONNX / position reference parity in the simulator; no hardware."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from deploy_offline import OfflineJointPolicy
from joint_env import HERE, JointReachEnv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--model", type=Path, default=None,
                        help="SB3 policy to compare; defaults to <artifacts>/joint_ppo.zip")
    parser.add_argument("--xml", type=Path, default=HERE / "model.xml")
    args = parser.parse_args()
    torch.set_num_threads(1)
    model_path = args.model if args.model is not None else args.artifacts/"joint_ppo.zip"
    model = PPO.load(model_path, device="cpu")
    adapter = OfflineJointPolicy(args.artifacts/"joint_actor.onnx")
    env = JointReachEnv(args.xml)
    max_action_diff = max_ref_diff = max_obs_diff = 0.0
    samples = 0
    for seed in range(40000, 40010):
        obs, info = env.reset(seed=seed)
        adapter.reset(info["angle_rad"])
        for _ in range(150):
            action, _ = model.predict(obs, deterministic=True)
            result = adapter.infer(angle_rad=info["angle_rad"], velocity_rad_s=info["velocity_rad_s"],
                                   target_rad=info["target_rad"], sample_age_s=0.0)
            max_obs_diff = max(max_obs_diff, float(np.max(np.abs(obs-np.asarray(result["observation"])))))
            max_action_diff = max(max_action_diff, abs(float(action[0])-result["action_normalized"]))
            obs, _, terminated, truncated, info = env.step(action)
            max_ref_diff = max(max_ref_diff, abs(info["command_rad"]-result["position_reference_rad"]))
            samples += 1
            if terminated or truncated:
                break
    reject_count = 0
    for overrides in [{"sample_age_s":.041}, {"target_rad":.8}, {"angle_rad":float("nan")}]:
        sample = {"angle_rad":0.1, "velocity_rad_s":0.0, "target_rad":0.5, "sample_age_s":0.0}
        sample.update(overrides)
        try:
            adapter.infer(**sample)
        except ValueError:
            reject_count += 1
    result = {"model_source":str(model_path), "onnx_source":str(args.artifacts/"joint_actor.onnx"),
              "simulation_episodes":10, "control_samples":samples,
              "max_observation_difference":max_obs_diff, "max_action_difference":max_action_diff,
              "max_reference_difference_rad":max_ref_diff,
              "tolerances":{"observation":1e-5, "action":1e-4, "reference_rad":1e-5},
              "rejected_invalid_samples":reject_count, "expected_rejections":3,
              "passed":bool(max_obs_diff < 1e-5 and max_action_diff < 1e-4 and max_ref_diff < 1e-5 and reject_count == 3),
              "hardware_connected":False}
    (args.artifacts/"deployment_contract_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit("Contract check failed")


if __name__ == "__main__":
    main()
