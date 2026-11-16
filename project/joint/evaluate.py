"""Compare policies on the same 20 fixed, training-independent simulation seeds."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from joint_env import HERE, JointReachEnv, MAX_STEPS


def evaluate(policy_name, model, episodes, first_seed, xml):
    env = JointReachEnv(xml)
    rows = []
    records = []
    for i in range(episodes):
        seed = first_seed + i
        obs, _ = env.reset(seed=seed)
        random = np.random.default_rng(seed + 1000000)
        errors = []
        returns = 0.0
        terminated = False
        peak_torque = 0.0
        for t in range(MAX_STEPS):
            if policy_name == "zero":
                action = np.asarray([0.0], dtype=np.float32)
            elif policy_name == "random":
                action = np.asarray([random.uniform(-1, 1)], dtype=np.float32)
            elif policy_name == "target_copy":
                action = np.asarray([obs[2]], dtype=np.float32)
            else:
                action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            errors.append(abs(info["error_rad"]))
            returns += reward
            peak_torque = max(peak_torque, abs(info["actuator_torque_nm"]))
            if i == 0:
                records.append({"policy":policy_name, "seed":seed, "step":t+1,
                    "time_s":round((t+1)*.02, 4), "target_rad":info["target_rad"],
                    "angle_rad":info["angle_rad"], "velocity_rad_s":info["velocity_rad_s"],
                    "command_rad":info["command_rad"], "actuator_torque_nm":info["actuator_torque_nm"]})
            if terminated or truncated:
                break
        success = not terminated and len(errors) == MAX_STEPS and all(v < .05 for v in errors[-20:])
        rows.append({"seed":seed, "mean_error_rad":float(np.mean(errors)),
            "final_50_mean_error_rad":float(np.mean(errors[-50:])), "success":success,
            "terminated":terminated, "episode_length":len(errors),
            "episode_return":float(returns), "max_torque_nm":peak_torque})
    env.close()
    aggregate = {
        "episodes":episodes, "mean_abs_error_rad":float(np.mean([r["mean_error_rad"] for r in rows])),
        "final_50_mean_abs_error_rad":float(np.mean([r["final_50_mean_error_rad"] for r in rows])),
        "final_50_mean_abs_error_deg":float(np.degrees(np.mean([r["final_50_mean_error_rad"] for r in rows]))),
        "success_count":int(sum(r["success"] for r in rows)),
        "success_fraction":float(np.mean([r["success"] for r in rows])),
        "terminated_count":int(sum(r["terminated"] for r in rows)),
        "mean_episode_return":float(np.mean([r["episode_return"] for r in rows])),
        "max_observed_torque_nm":float(max(r["max_torque_nm"] for r in rows)),
        "per_episode":rows,
    }
    return aggregate, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("artifacts/joint_ppo.zip"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--first-seed", type=int, default=20000)
    parser.add_argument("--xml", type=Path, default=HERE / "model.xml")
    parser.add_argument("--allow-model-mismatch", action="store_true",
                        help="Allow an intentionally different XML for sim-to-sim comparison")
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    model_hash = hashlib.sha256(args.xml.read_bytes()).hexdigest()
    config_path = args.model.parent/"training_config.json"
    trained_hash = json.loads(config_path.read_text(encoding="utf-8")).get("model_xml_sha256") if config_path.exists() else None
    same_model = model_hash == trained_hash if trained_hash else False
    if not same_model and not args.allow_model_mismatch:
        parser.error("MJCF hash does not match the model training config (or config is missing); retrain, or use --allow-model-mismatch for a deliberately labeled sim-to-sim test")
    torch.set_num_threads(1)
    trained = PPO.load(args.model, device="cpu")
    # Same architecture and seed as train.py, with no learning.
    untrained = PPO("MlpPolicy", JointReachEnv(args.xml), seed=123, device="cpu", n_steps=512,
                    batch_size=64, n_epochs=8,
                    policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64])))
    results = {"description":"Simulation only; identical independent initial conditions for each policy.",
               "model_xml_sha256":model_hash, "same_xml_as_training":same_model,
               "seed_range":[args.first_seed, args.first_seed+args.episodes-1],
               "success_definition":"all last 20 steps |target-angle| < 0.05 rad and no early termination",
               "baselines":{"zero":"always commands 0 rad", "random":"uniform random action each step",
                            "target_copy":"hand-coded proportional reference equals target; no learning",
                            "untrained":"fresh neural network before PPO updates", "ppo":"trained policy"},
               "policies":{}}
    all_traces = []
    for name, model in [("zero",None),("random",None),("target_copy",None),("untrained",untrained),("ppo",trained)]:
        summary, trace = evaluate(name, model, args.episodes, args.first_seed, args.xml)
        results["policies"][name] = summary
        all_traces.extend(trace)
        print(f"{name:12} final50 MAE={summary['final_50_mean_abs_error_rad']:.4f} rad "
              f"({summary['final_50_mean_abs_error_deg']:.2f} deg), success={summary['success_count']}/{args.episodes}, "
              f"terminated={summary['terminated_count']}")
    (args.output/"evaluation.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.output/"trace_first_episode.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_traces[0].keys()))
        writer.writeheader(); writer.writerows(all_traces)
    print(f"Saved metrics and first-seed traces to {args.output}")


if __name__ == "__main__":
    main()
