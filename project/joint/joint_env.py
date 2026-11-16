"""A small, explicit Gymnasium task using a real MuJoCo single-joint model."""
from __future__ import annotations

from pathlib import Path
import gymnasium as gym
from gymnasium import spaces
import mujoco
import numpy as np
from contract import Q_COMMAND_LIMIT, Q_FAIL_LIMIT, QD_SCALE, POLICY_PERIOD_S, observation, position_reference

HERE = Path(__file__).resolve().parent
N_SUBSTEPS = 4              # 4 * 0.005 s = 0.020 s per policy update, 50 Hz
MAX_STEPS = 150             # time limit, i.e. truncation


class JointReachEnv(gym.Env):
    """Reach and hold a target angle with an approximate position-servo plant."""

    metadata = {"render_modes": []}

    def __init__(self, xml_path: str | Path | None = None):
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(str(xml_path or HERE / "model.xml"))
        if (self.model.nq, self.model.nv, self.model.nu) != (1, 1, 1):
            raise ValueError("This task contract requires exactly one hinge and one actuator")
        if self.model.jnt_type[0] != mujoco.mjtJoint.mjJNT_HINGE or not self.model.jnt_limited[0]:
            raise ValueError("The one joint must be a limited hinge; observation units are radians")
        if self.model.jnt_range[0,0] >= -Q_FAIL_LIMIT or self.model.jnt_range[0,1] <= Q_FAIL_LIMIT:
            raise ValueError("Joint limits must enclose the simulation failure thresholds")
        if (self.model.actuator_trntype[0] != mujoco.mjtTrn.mjTRN_JOINT
                or self.model.actuator_trnid[0,0] != 0 or not np.isclose(self.model.actuator_gear[0,0],1)):
            raise ValueError("The actuator must drive the single joint with unit gear")
        if (not self.model.actuator_ctrllimited[0] or not self.model.actuator_forcelimited[0]
                or self.model.actuator_ctrlrange[0,0] > -Q_COMMAND_LIMIT
                or self.model.actuator_ctrlrange[0,1] < Q_COMMAND_LIMIT):
            raise ValueError("The actuator must limit force and accept the reference range ±0.9 rad")
        kp = self.model.actuator_gainprm[0,0]
        if (self.model.actuator_gaintype[0] != mujoco.mjtGain.mjGAIN_FIXED
                or self.model.actuator_biastype[0] != mujoco.mjtBias.mjBIAS_AFFINE
                or kp <= 0 or not np.isclose(self.model.actuator_biasprm[0,1], -kp)
                or self.model.actuator_biasprm[0,2] > 0):
            raise ValueError("This example requires a position actuator with non-negative damping")
        if not np.isclose(self.model.opt.timestep * N_SUBSTEPS, POLICY_PERIOD_S):
            raise ValueError("MJCF must retain a 20 ms policy interval unless the contract is updated")
        self.data = mujoco.MjData(self.model)
        self.observation_space = spaces.Box(
            low=np.asarray([-2, -1, -1, -1], dtype=np.float32),
            high=np.asarray([2, 1, 1, 1], dtype=np.float32), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        self.target = 0.0
        self.previous_action = 0.0
        self.count = 0

    def _observation(self) -> np.ndarray:
        return observation(float(self.data.qpos[0]), float(self.data.qvel[0]), self.target, self.previous_action)

    def reset(self, *, seed: int | None = None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[0] = self.np_random.uniform(-0.7, 0.7)
        self.data.qvel[0] = self.np_random.uniform(-0.1, 0.1)
        self.target = float(self.np_random.uniform(-0.75, 0.75))
        self.data.ctrl[0] = float(self.data.qpos[0])
        self.previous_action = float(self.data.ctrl[0] / Q_COMMAND_LIMIT)
        self.count = 0
        mujoco.mj_forward(self.model, self.data)
        return self._observation(), self._info()

    def _info(self) -> dict:
        q = float(self.data.qpos[0])
        return {"angle_rad": q, "velocity_rad_s": float(self.data.qvel[0]),
                "target_rad": self.target, "error_rad": self.target-q,
                "command_rad": float(self.data.ctrl[0]),
                "actuator_torque_nm": float(self.data.actuator_force[0])}

    def step(self, action):
        a = np.asarray(action, dtype=np.float64).reshape(-1)
        if a.shape != (1,) or not np.isfinite(a[0]):
            raise ValueError("expected one finite normalized action")
        a = float(np.clip(a[0], -1.0, 1.0))
        self.data.ctrl[0] = position_reference(a, self.previous_action * Q_COMMAND_LIMIT)
        for _ in range(N_SUBSTEPS):
            mujoco.mj_step(self.model, self.data)
        q = float(self.data.qpos[0]); qd = float(self.data.qvel[0])
        if not np.isfinite(q) or not np.isfinite(qd):
            raise RuntimeError("MuJoCo produced an invalid state")
        error = self.target - q
        reward = (-2.0 * error**2 - 0.01 * qd**2
                  - 0.005 * (a-self.previous_action)**2
                  + (0.05 if abs(error) < 0.05 else 0.0))
        self.previous_action = float(self.data.ctrl[0] / Q_COMMAND_LIMIT)
        self.count += 1
        terminated = abs(q) > Q_FAIL_LIMIT or abs(qd) > 12.0
        if terminated:
            reward -= 10.0
        truncated = self.count >= MAX_STEPS and not terminated
        return self._observation(), float(reward), bool(terminated), bool(truncated), self._info()
