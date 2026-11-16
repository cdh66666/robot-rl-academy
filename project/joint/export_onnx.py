"""Export the deterministic actor and verify against SB3's actual predict()."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import onnx
import onnxruntime as ort
import torch
from stable_baselines3 import PPO


class DeterministicActor(torch.nn.Module):
    def __init__(self, policy):
        super().__init__()
        self.policy = policy

    def forward(self, obs):
        features = self.policy.extract_features(obs)
        latent = self.policy.mlp_extractor.forward_actor(features)
        # SB3 predict() clips this unsquashed Gaussian mean to the Box action space.
        return torch.clamp(self.policy.action_net(latent), -1.0, 1.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("artifacts/joint_ppo.zip"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    model = PPO.load(args.model, device="cpu")
    model.policy.set_training_mode(False)
    actor = DeterministicActor(model.policy).eval()
    path = args.output/"joint_actor.onnx"
    torch.onnx.export(actor, torch.zeros((1,4), dtype=torch.float32), str(path),
                      input_names=["observation"], output_names=["action"],
                      dynamic_axes={"observation":{0:"batch"}, "action":{0:"batch"}},
                      opset_version=17, dynamo=False)
    onnx.checker.check_model(onnx.load(path))
    options = ort.SessionOptions(); options.intra_op_num_threads = 1; options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(73913)
    observations = rng.uniform([-1.2,-1,-.84,-1], [1.2,1,.84,1], size=(100,4)).astype(np.float32)
    sb3_actions, _ = model.predict(observations, deterministic=True)
    onnx_actions = session.run(["action"], {"observation":observations})[0]
    difference = float(np.max(np.abs(sb3_actions - onnx_actions)))
    result = {"inputs":"float32 observation [batch,4]", "outputs":"float32 clipped action [batch,1]",
              "samples":len(observations), "max_abs_action_difference":difference,
              "tolerance":1e-5, "passed":bool(difference <= 1e-5),
              "warning":"This validates numerical inference only, not a hardware deployment."}
    (args.output/"onnx_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit("ONNX and SB3 outputs differ beyond tolerance")


if __name__ == "__main__":
    main()
