// Teaching environment: MuJoCo performs every integration step; the drawing is a 2D projection.
export const MODEL_XML = `<mujoco model="cartpole_teaching">
  <compiler angle="radian"/>
  <option timestep="0.005" gravity="0 0 -9.81" integrator="RK4"/>
  <default><joint damping="0"/><geom contype="0" conaffinity="0"/></default>
  <worldbody>
    <body name="cart" pos="0 0 0.1">
      <joint name="slide" type="slide" axis="1 0 0"/>
      <geom name="cart_geom" type="box" size="0.15 0.1 0.06" mass="1"/>
      <body name="pole" pos="0 0 0.06">
        <joint name="hinge" type="hinge" axis="0 1 0"/>
        <geom name="pole_geom" type="capsule" fromto="0 0 0 0 0 1" size="0.025" mass="0.1"/>
      </body>
    </body>
  </worldbody>
  <actuator><motor name="drive" joint="slide" gear="1" ctrllimited="true" ctrlrange="-20 20"/></actuator>
</mujoco>`;

export const MAX_STEPS = 500;
export const ANGLE_LIMIT = 12 * Math.PI / 180;
export const POSITION_LIMIT = 2.4;

export function randomSource(seed) {
  // Mulberry32 mixes adjacent seeds, avoiding nearly identical initial states.
  let x = seed >>> 0 || 1;
  return () => {
    let t = x = (x + 0x6D2B79F5) >>> 0;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class CartPole {
  constructor(mj, model) {
    this.mj = mj;
    this.model = model;
    this.data = new mj.MjData(model);
    this.steps = 0;
  }
  reset(random) {
    this.mj.mj_resetData(this.model, this.data);
    for (let i = 0; i < 2; i++) {
      this.data.qpos[i] = (random() - 0.5) * 0.1;
      this.data.qvel[i] = (random() - 0.5) * 0.1;
    }
    this.mj.mj_forward(this.model, this.data);
    this.steps = 0;
    return this.observation();
  }
  observation() {
    return [this.data.qpos[0], this.data.qvel[0], this.data.qpos[1], this.data.qvel[1]];
  }
  step(action, force = 10, failurePenalty = 0) {
    this.data.ctrl[0] = action === 1 ? force : -force;
    for (let i = 0; i < 4; i++) this.mj.mj_step(this.model, this.data);
    this.steps++;
    const s = this.observation();
    const terminal = Math.abs(s[0]) > POSITION_LIMIT || Math.abs(s[2]) > ANGLE_LIMIT;
    const truncated = this.steps >= MAX_STEPS;
    return {state: s, reward: 1 + (terminal ? failurePenalty : 0), terminal, truncated};
  }
  delete() { this.data.delete(); }
}

// Exposes each physical state using roughly comparable scale for stable learning.
export function normalize(s) { return [s[0] / 2.4, s[1] / 3, s[2] / ANGLE_LIMIT, s[3] / 3]; }
