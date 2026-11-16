"""Watch a saved PPO policy in the MuJoCo simulator. Does not access hardware."""
import argparse
from pathlib import Path

import gymnasium as gym
from stable_baselines3 import PPO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=Path("runs/pendulum/ppo_pendulum.zip"))
    parser.add_argument("--episodes", type=int, default=3)
    args = parser.parse_args()
    model = PPO.load(args.model, device="cpu")
    env = gym.make("InvertedPendulum-v5", render_mode="human")
    try:
        for ep in range(args.episodes):
            observation, _ = env.reset(seed=200_000 + ep)
            total = 0.0
            while True:
                action, _ = model.predict(observation, deterministic=True)
                observation, reward, terminated, truncated, _ = env.step(action)
                total += float(reward)
                if terminated or truncated:
                    print(f"episode {ep+1}: return={total:.1f}")
                    break
    finally:
        env.close()


if __name__ == "__main__":
    main()
