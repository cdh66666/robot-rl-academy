/* Fit only the training section, then evaluate on the held-out section. */
self.onmessage = ({data}) => {
  try {
    const {commands, measured, dt, split} = data;
    if (commands.length !== measured.length || split < 2 || split >= commands.length) throw new Error("数据长度或分段不正确");
    let bestScore = Infinity, bestTau = 0, bestDelay = 0;
    for (let delay = 0; delay <= 20; delay++) {
      for (let k = 12; k <= 120; k++) {
        const tau = k * .005, alpha = 1 - Math.exp(-dt / tau);
        let position = measured[0], sq = 0;
        for (let i = 1; i < split; i++) {
          position += alpha * (commands[Math.max(0, i - 1 - delay)] - position);
          const error = position - measured[i]; sq += error * error;
        }
        if (sq < bestScore) { bestScore = sq; bestTau = tau; bestDelay = delay; }
      }
    }
    const alpha = 1 - Math.exp(-dt / bestTau);
    const predict = (start, stop, initial) => {
      const result = [initial]; let position = initial;
      for (let i = start + 1; i < stop; i++) {
        position += alpha * (commands[Math.max(0, i - 1 - bestDelay)] - position);
        result.push(position);
      }
      return result;
    };
    const train = predict(0, split, measured[0]);
    // One held-out measurement initializes the trajectory. It did not tune the model.
    const heldout = predict(split, measured.length, measured[split]);
    let sq = 0, count = 0;
    for (let i = 1; i < heldout.length; i++) { const e = heldout[i] - measured[split+i]; sq += e*e; count++; }
    self.postMessage({tau:bestTau, delay:bestDelay*dt, trainRmse:Math.sqrt(bestScore/(split-1)),
      heldoutRmse:Math.sqrt(sq/count), prediction:[...train,...heldout]});
  } catch (error) { self.postMessage({error:String(error.message || error)}); }
};
