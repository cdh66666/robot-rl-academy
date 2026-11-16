// Compact educational DQN: 4-32-32-2 neural Q-network, experience replay,
// epsilon-greedy exploration, Double-DQN target, Huber loss and Adam.
import { normalize } from './core.mjs';

class Network {
  constructor(random) {
    this.shapes = [[4, 32], [32, 32], [32, 2]];
    this.params = [];
    for (const [input, output] of this.shapes) {
      const w = new Float64Array(input * output);
      const scale = Math.sqrt(6 / (input + output));
      for (let i = 0; i < w.length; i++) w[i] = (random() * 2 - 1) * scale;
      this.params.push(w, new Float64Array(output));
    }
    this.m = this.params.map(p => new Float64Array(p.length));
    this.v = this.params.map(p => new Float64Array(p.length));
    this.t = 0;
  }
  copyFrom(other) { this.params.forEach((p, i) => p.set(other.params[i])); }
  forward(state) {
    let activations = [normalize(state)], pre = [];
    for (let k = 0; k < 3; k++) {
      const [n, m] = this.shapes[k], a = activations[k], w = this.params[2*k], b = this.params[2*k+1];
      const z = new Float64Array(m), next = new Float64Array(m);
      for (let j = 0; j < m; j++) {
        let v = b[j];
        for (let i = 0; i < n; i++) v += a[i] * w[i*m+j];
        z[j] = v; next[j] = k < 2 ? Math.max(0, v) : v;
      }
      pre.push(z); activations.push(next);
    }
    return {activations, pre, output: activations[3]};
  }
  action(s) { const out = this.forward(s).output; return out[1] > out[0] ? 1 : 0; }
  learn(batch, target, gamma, lr) {
    const grads = this.params.map(p => new Float64Array(p.length));
    for (const item of batch) {
      const onlineNext = this.forward(item.next).output;
      const best = onlineNext[1] > onlineNext[0] ? 1 : 0;
      const nextQ = target.forward(item.next).output[best];
      // A time-limit truncation is not a physical termination: bootstrap it.
      const goal = item.reward + (item.terminal ? 0 : gamma * nextQ);
      const result = this.forward(item.state);
      const diff = result.output[item.action] - goal;
      let delta = new Float64Array(2);
      delta[item.action] = Math.max(-1, Math.min(1, diff)) / batch.length;
      for (let k = 2; k >= 0; k--) {
        const [n, m] = this.shapes[k], a = result.activations[k], w = this.params[2*k];
        const previous = new Float64Array(n);
        for (let j = 0; j < m; j++) {
          grads[2*k+1][j] += delta[j];
          for (let i = 0; i < n; i++) {
            grads[2*k][i*m+j] += a[i] * delta[j];
            previous[i] += w[i*m+j] * delta[j];
          }
        }
        if (k > 0) for (let i = 0; i < n; i++) previous[i] *= result.pre[k-1][i] > 0 ? 1 : 0;
        delta = previous;
      }
    }
    this.t++;
    const corr1 = 1 - Math.pow(0.9, this.t), corr2 = 1 - Math.pow(0.999, this.t);
    for (let p = 0; p < this.params.length; p++) {
      for (let i = 0; i < this.params[p].length; i++) {
        const g = Math.max(-1, Math.min(1, grads[p][i]));
        this.m[p][i] = 0.9*this.m[p][i] + 0.1*g;
        this.v[p][i] = 0.999*this.v[p][i] + 0.001*g*g;
        this.params[p][i] -= lr * (this.m[p][i]/corr1) / (Math.sqrt(this.v[p][i]/corr2) + 1e-8);
      }
    }
  }
  export() { return this.params.map(a => Array.from(a)); }
  import(arrays) { this.params.forEach((a, i) => a.set(arrays[i])); }
}

export class DQN {
  constructor(random, options = {}) {
    this.random = random;
    this.online = new Network(random);
    this.target = new Network(random);
    this.target.copyFrom(this.online);
    this.buffer = new Array(30000);
    this.count = 0; this.cursor = 0; this.updates = 0; this.steps = 0;
    this.gamma = options.gamma ?? 0.99;
    this.lr = options.lr ?? 0.0005;
  }
  epsilon() { return Math.max(0.04, 1 - this.steps / 25000); }
  action(state, explore = true) {
    if (explore && this.random() < this.epsilon()) return this.random() < 0.5 ? 0 : 1;
    return this.online.action(state);
  }
  observe(state, action, reward, next, terminal) {
    this.buffer[this.cursor] = {state, action, reward, next, terminal};
    this.cursor = (this.cursor + 1) % this.buffer.length;
    this.count = Math.min(this.count + 1, this.buffer.length);
    this.steps++;
    if (this.count >= 1000 && this.steps % 4 === 0) {
      const batch = Array.from({length: 32}, () => this.buffer[Math.floor(this.random()*this.count)]);
      this.online.learn(batch, this.target, this.gamma, this.lr);
      if (++this.updates % 250 === 0) this.target.copyFrom(this.online);
    }
  }
  export() { return this.online.export(); }
}
