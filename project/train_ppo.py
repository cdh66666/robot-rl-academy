"""Train and independently evaluate a continuous-action MuJoCo PPO example.

This is a simulation example, not a robot driver.  It never connects to hardware.
"""
import argparse
import json
import time
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
import stable_baselines3
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env


ENV_ID = "InvertedPendulum-v5"


def evaluate(model, seeds):
    """Evaluate independent episodes. The random baseline uses identical reset seeds."""
    env = gym.make(ENV_ID)
    scores, lengths, endings = [], [], []
    for seed in seeds:
        observation, _ = env.reset(seed=int(seed))
        rng = np.random.default_rng(int(seed) + 100_000)
        total, length = 0.0, 0
        while True:
            if model is None:
                action = rng.uniform(env.action_space.low, env.action_space.high).astype(np.float32)
            else:
                action, _ = model.predict(observation, deterministic=True)
            observation, reward, terminated, truncated, _ = env.step(action)
            total += float(reward)
            length += 1
            if terminated or truncated:
                scores.append(total)
                lengths.append(length)
                endings.append("terminated" if terminated else "time_limit")
                break
    env.close()
    return {
        "mean_return": round(float(np.mean(scores)), 3),
        "min_return": round(float(np.min(scores)), 3),
        "max_return": round(float(np.max(scores)), 3),
        "mean_steps": round(float(np.mean(lengths)), 3),
        "episodes_reaching_time_limit": endings.count("time_limit"),
        "returns": scores,
        "lengths": lengths,
        "endings": endings,
    }


def main():
    parser = argparse.ArgumentParser(description="MuJoCo + PPO simulation-only learning example")
    parser.add_argument("--steps", type=int, default=60_000, help="training interaction budget")
    parser.add_argument("--episodes", type=int, default=20, help="independent evaluation episodes")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("runs/pendulum"))
    args = parser.parse_args()
    if args.steps < 1 or args.episodes < 1:
        parser.error("--steps and --episodes must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)

    # These seeds are separate from the training seed. The two agents see the
    # same initial conditions; random actions have their own reproducible RNG.
    test_seeds = list(range(100_000, 100_000 + args.episodes))
    print("Evaluating random baseline...", flush=True)
    baseline = evaluate(None, test_seeds)
    env = make_vec_env(ENV_ID, n_envs=4, seed=args.seed)
    model = PPO("MlpPolicy", env, seed=args.seed, verbose=1, device="cpu", n_steps=512,
                batch_size=128, n_epochs=10, learning_rate=3e-4)
    started = time.perf_counter()
    model.learn(total_timesteps=args.steps, progress_bar=False)
    elapsed = time.perf_counter() - started
    model_path = args.out / "ppo_pendulum.zip"
    model.save(model_path)
    env.close()

    # Reload the artifact before evaluation; this verifies the saved policy path.
    reloaded = PPO.load(model_path, device="cpu")
    print("Evaluating reloaded trained policy...", flush=True)
    trained = evaluate(reloaded, test_seeds)
    with gym.make(ENV_ID) as info_env:
        dt = float(info_env.unwrapped.dt)
    report = {
        "environment": ENV_ID,
        "scope": "simulation only; no real robot or hardware validation",
        "versions": {"gymnasium": gym.__version__, "mujoco": mujoco.__version__,
                     "stable_baselines3": stable_baselines3.__version__, "torch": torch.__version__},
        "training_seed": args.seed,
        "requested_training_steps": args.steps,
        "actual_training_steps": int(model.num_timesteps),
        "training_seconds": round(elapsed, 2),
        "evaluation_seeds": test_seeds,
        "control_interval_seconds": dt,
        "observation_order": ["cart_position_m", "pole_angle_rad", "cart_velocity_m_per_s", "pole_angular_velocity_rad_per_s"],
        "action": {"meaning": "cart force", "unit": "N", "low": -3.0, "high": 3.0},
        "random_baseline": baseline,
        "trained_policy": trained,
    }
    (args.out / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print(f"Saved model and measured evaluation to {args.out}", flush=True)


if __name__ == "__main__":
    main()
