"""Inspect a single-joint MuJoCo teaching model using known simulated inputs.

This is a numerical simulation only. It never opens a port or controls hardware.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco

from contract import MAX_REFERENCE_RATE, POLICY_PERIOD_S, Q_COMMAND_LIMIT, position_reference
from joint_env import HERE, N_SUBSTEPS, JointReachEnv


def simulate(env: JointReachEnv, requested_reference: float, cycles: int) -> dict:
    """Apply one signed teaching reference to a fresh, zero-angle simulation."""
    mujoco.mj_resetData(env.model, env.data)
    env.data.qpos[0] = 0.0
    env.data.qvel[0] = 0.0
    env.data.ctrl[0] = 0.0
    mujoco.mj_forward(env.model, env.data)
    action = requested_reference / Q_COMMAND_LIMIT
    reference = 0.0
    rows = []
    peak_force = 0.0
    maximum_reference_change = 0.0
    for i in range(cycles):
        old_reference = reference
        reference = position_reference(action, reference)
        maximum_reference_change = max(maximum_reference_change, abs(reference-old_reference))
        env.data.ctrl[0] = reference
        for _ in range(N_SUBSTEPS):
            mujoco.mj_step(env.model, env.data)
            peak_force = max(peak_force, abs(float(env.data.actuator_force[0])))
        rows.append({"cycle": i + 1, "simulated_time_s": round((i + 1) * POLICY_PERIOD_S, 6),
                     "applied_reference_rad": float(reference), "angle_rad": float(env.data.qpos[0]),
                     "velocity_rad_s": float(env.data.qvel[0]), "actuator_torque_nm": float(env.data.actuator_force[0])})
    return {"requested_reference_rad": requested_reference, "max_reference_change_rad": maximum_reference_change,
            "peak_abs_actuator_torque_nm_sampled_each_physics_step": peak_force, "first_sample": rows[0],
            "last_sample": rows[-1], "samples": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, default=HERE / "model.xml")
    parser.add_argument("--target", type=float, default=0.4, help="positive simulated reference in rad")
    parser.add_argument("--cycles", type=int, default=20, help="number of 20 ms simulation cycles")
    parser.add_argument("--output", type=Path, help="optional JSON result path")
    args = parser.parse_args()
    if not 0 < args.target <= Q_COMMAND_LIMIT or not 1 <= args.cycles <= 150:
        parser.error("--target must be in (0, 0.9] rad; --cycles must be in [1, 150]")
    env = JointReachEnv(args.xml)
    try:
        positive = simulate(env, args.target, args.cycles)
        negative = simulate(env, -args.target, args.cycles)
        result = {
            "scope": "MuJoCo simulation only; no hardware connected or commanded",
            "model": args.xml.name,
            "physics_timestep_s": float(env.model.opt.timestep),
            "physics_steps_per_control_cycle": N_SUBSTEPS,
            "policy_period_s": POLICY_PERIOD_S,
            "actuator_control_range_rad": env.model.actuator_ctrlrange[0].tolist(),
            "actuator_force_range_nm": env.model.actuator_forcerange[0].tolist(),
            "reference_change_limit_rad_per_cycle": MAX_REFERENCE_RATE * POLICY_PERIOD_S,
            "positive": positive,
            "negative": negative,
            "direction_check": {
                "positive_final_angle_is_positive": positive["last_sample"]["angle_rad"] > 0,
                "negative_final_angle_is_negative": negative["last_sample"]["angle_rad"] < 0,
            },
            "limitations": "This checks two simulated inputs only, not real geometry, calibration, safety or hardware response.",
        }
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        summary = {
            "scope": result["scope"], "model": result["model"],
            "physics_timestep_s": result["physics_timestep_s"],
            "physics_steps_per_control_cycle": result["physics_steps_per_control_cycle"],
            "policy_period_s": result["policy_period_s"],
            "actuator_control_range_rad": result["actuator_control_range_rad"],
            "actuator_force_range_nm": result["actuator_force_range_nm"],
            "reference_change_limit_rad_per_cycle": result["reference_change_limit_rad_per_cycle"],
            "positive": {k:positive[k] for k in ("requested_reference_rad", "max_reference_change_rad", "peak_abs_actuator_torque_nm_sampled_each_physics_step", "first_sample", "last_sample")},
            "negative": {k:negative[k] for k in ("requested_reference_rad", "max_reference_change_rad", "peak_abs_actuator_torque_nm_sampled_each_physics_step", "first_sample", "last_sample")},
            "direction_check": result["direction_check"], "limitations": result["limitations"],
            "detailed_log": str(args.output) if args.output else "not saved; provide --output to save all samples",
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        env.close()


if __name__ == "__main__":
    main()
