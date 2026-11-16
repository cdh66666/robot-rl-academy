import loadMujoco from './vendor/mujoco.js';
import { MODEL_XML, CartPole, randomSource, MAX_STEPS } from './core.mjs';
import { DQN } from './dqn.mjs';

let mj, model, trainEnv, checkEnv, playEnv, agent, random, state;
let running = false, ended = false, episodes = 0, currentLength = 0, scores = [];
let seed = 123, penalty = -5, testForce = 10, playMode = 'random', playState;
let bestWeights, bestValidation = -Infinity, bestAt = 0, curve = [], baseline = null;
let lastTest = null;
let generation = 0, randomPlay = randomSource(7731), lastAction = 0, playHold = 0;
const TRAIN_LIMIT = 50000;

function mean(a) { return a.reduce((x, y) => x+y, 0) / a.length; }
function evaluate(count, baseSeed, mode, force) {
  const values = [];
  for (let i = 0; i < count; i++) {
    let s = checkEnv.reset(randomSource(baseSeed + i));
    const choose = randomSource(baseSeed * 2 + i * 101);
    let len = 0;
    for (let j = 0; j < MAX_STEPS; j++) {
      const action = mode === 'random' ? (choose() < .5 ? 0 : 1) : agent.action(s, false);
      const out = checkEnv.step(action, force);
      s = out.state; len++;
      if (out.terminal || out.truncated) break;
    }
    values.push(len);
  }
  return {mean: mean(values), min: Math.min(...values), max: Math.max(...values), values};
}
function evaluateBest(count, baseSeed, force) {
  const current = agent.export();
  agent.online.import(bestWeights);
  const result = evaluate(count, baseSeed, 'network', force);
  agent.online.import(current);
  return result;
}
function status(extra = {}) {
  postMessage({type:'status', steps:agent.steps, episodes, epsilon:agent.epsilon(),
    recent: scores.length ? mean(scores.slice(-20)) : null, running, ended,
    bestValidation, bestAt, curve, baseline, ...extra});
}
function reset(config) {
  running = false; generation++;
  seed = Number(config.seed) >>> 0 || 1;
  penalty = Number(config.penalty) === 0 ? 0 : -5;
  testForce = 10; episodes = 0; currentLength = 0; scores = []; curve = []; ended = false; lastTest = null;
  random = randomSource(seed); agent = new DQN(random);
  state = trainEnv.reset(random);
  randomPlay = randomSource(seed + 7731);
  playState = playEnv.reset(randomSource(seed + 123456));
  playMode = 'random'; lastAction = 0; playHold = 0;
  baseline = evaluate(20, 98000, 'random', 10);
  const initial = evaluate(10, 8000, 'network', 10);
  bestValidation = initial.mean; bestAt = 0; bestWeights = agent.export();
  curve.push({steps:0, score:initial.mean});
  postMessage({type:'reset', seed, penalty, testForce, baseline, initial});
  status();
}
function trainChunk(localGeneration) {
  if (!running || localGeneration !== generation) return;
  for (let i = 0; i < 500 && agent.steps < TRAIN_LIMIT; i++) {
    const action = agent.action(state);
    const out = trainEnv.step(action, 10, penalty);
    agent.observe(state, action, out.reward, out.state, out.terminal);
    state = out.state; currentLength++;
    if (out.terminal || out.truncated) {
      episodes++; scores.push(currentLength);
      if (scores.length > 100) scores.shift();
      currentLength = 0;
      state = trainEnv.reset(random);
    }
    if (agent.steps % 5000 === 0) {
      const result = evaluate(10, 8000, 'network', 10);
      curve.push({steps: agent.steps, score: result.mean});
      if (result.mean > bestValidation) {
        bestValidation = result.mean; bestAt = agent.steps; bestWeights = agent.export();
        lastTest = null;
      }
    }
  }
  if (agent.steps >= TRAIN_LIMIT) { running = false; ended = true; }
  status();
  if (running) setTimeout(() => trainChunk(localGeneration), 0);
}

onmessage = async ({data: msg}) => {
  try {
    if (msg.type === 'init') {
      mj = await loadMujoco();
      model = mj.MjModel.from_xml_string(MODEL_XML);
      trainEnv = new CartPole(mj, model); checkEnv = new CartPole(mj, model); playEnv = new CartPole(mj, model);
      reset(msg);
      postMessage({type:'ready'});
      setInterval(() => {
        if (!playState) return;
        if (playHold > 0) { if (--playHold === 0) playState = playEnv.reset(randomPlay); return; }
        if (playMode === 'random') lastAction = randomPlay() < .5 ? 0 : 1;
        else {
          const current = agent.export();
          agent.online.import(bestWeights);
          lastAction = agent.action(playState, false);
          agent.online.import(current);
        }
        const out = playEnv.step(lastAction, testForce);
        playState = out.state;
        postMessage({type:'frame', state:playState, action:lastAction, frameStep:playEnv.steps,
          failed:out.terminal, truncated:out.truncated, mode:playMode, force:testForce});
        if (out.terminal || out.truncated) playHold = 18;
      }, 20);
    } else if (msg.type === 'start' && !running && !ended) {
      running = true; status(); setTimeout(() => trainChunk(generation), 0);
    } else if (msg.type === 'pause') {
      running = false; generation++; status();
    } else if (msg.type === 'reset') {
      reset(msg);
    } else if (msg.type === 'mode') {
      playMode = msg.mode === 'trained' ? 'trained' : 'random';
      playHold = 0;
      playState = playEnv.reset(randomPlay);
    } else if (msg.type === 'force') {
      testForce = Math.max(6, Math.min(14, Number(msg.force) || 10));
      lastTest = null;
      playHold = 0;
      playState = playEnv.reset(randomPlay);
    } else if (msg.type === 'test') {
      const randomResult = evaluate(20, 98000, 'random', testForce);
      const trainedResult = evaluateBest(20, 98000, testForce);
      lastTest = {force:testForce, random:randomResult, trained:trainedResult, bestAt};
      postMessage({type:'testResult', force:testForce, random:randomResult, trained:trainedResult, bestAt});
    } else if (msg.type === 'export') {
      postMessage({type:'exportResult', payload:{kind:'educational-mujoco-cartpole-dqn',
        warning:'仅用于本课程 MuJoCo 教学倒立摆，不能直接控制真实机器人。',
        seed, trainingSteps:agent.steps, bestCheckpointSteps:bestAt, bestValidationMean:bestValidation,
        reward:'survival +1, physical terminal extra '+penalty, timeLimitSteps:500,
        trainingForceN:10, testedForceN:testForce, curve, independentTest:lastTest, weights:bestWeights}});
    }
  } catch (error) {
    running = false;
    postMessage({type:'error', message:String(error && error.stack || error)});
  }
};
