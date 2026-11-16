"""Train the continuous-action joint policy in simulation only."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from joint_env import HERE, JointReachEnv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timesteps", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    parser.add_argument("--xml", type=Path, default=HERE / "model.xml")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.timesteps < 1:
        parser.error("--timesteps must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    env = JointReachEnv(args.xml)
    check_env(env, warn=True)
    model = PPO("MlpPolicy", env, seed=args.seed, device="cpu", verbose=0 if args.quiet else 1,
                learning_rate=3e-4, n_steps=512, batch_size=64, n_epochs=8,
                gamma=0.99, gae_lambda=0.95,
                policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64])))
    model.learn(total_timesteps=args.timesteps, progress_bar=False)
    model.save(args.output / "joint_ppo.zip")
    (args.output / "training_config.json").write_text(json.dumps({
        "algorithm":"Stable-Baselines3 PPO", "seed":args.seed,
        "requested_timesteps":args.timesteps, "actual_timesteps":model.num_timesteps,
        "model_xml_sha256":hashlib.sha256(args.xml.read_bytes()).hexdigest(),
        "control_period_s":0.02, "obs":["q_rad/0.9", "clip(qd_rad_s/5)", "target_rad/0.9", "previous_applied_position_reference_rad/0.9"],
        "action":"clip(policy_output,-1,1) * 0.9 rad, with a +/-0.06 rad/cycle setpoint slew limit",
        "physical_validation":"none: simulation only"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved simulated policy: {args.output / 'joint_ppo.zip'}")
    env.close()


if __name__ == "__main__":
    main()
