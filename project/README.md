# 连续动作实战：MuJoCo + PPO

这个练习是浏览器入门实验的进阶版：用 MuJoCo 模拟倒立摆，用 PPO 训练输出连续推力的策略，做独立评估，保存模型，再导出并验证 ONNX。它**不会连接或控制真实硬件**。

浏览器实验使用的是另一套离散动作 DQN；两者任务相似，但模型、动作、观察的顺序、奖励及训练算法都不完全相同，不能互换模型或直接比较分数。

## 学完能得到什么

1. 一份真实训练出的 `ppo_pendulum.zip` 策略。
2. 一份记录训练预算、依赖版本、随机策略和独立测试结果的 `evaluation.json`。
3. 一个经过数值对照的 `policy.onnx`，以及验证记录 `policy.verification.json`。
4. 一套可迁移的方法：明确输入输出契约、比较基线、独立测试、检查导出前后是否一致。

## 1. 建立环境

本项目在 Windows、Python 3.13、MuJoCo 4.0.1、Gymnasium 1.4.0 和 Stable-Baselines3 2.9.2 上做过仿真验证。首次安装需要联网；CPU 即可运行。打开终端并进入本目录，Windows PowerShell 示例：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS/Linux 可以改用 `.venv/bin/python`；具体平台与显卡配置可能影响安装与可视化。

## 2. 训练并评估

```powershell
.\.venv\Scripts\python train_ppo.py --steps 60000 --episodes 20
```

程序先用随机动作记录基线，再在仿真里训练 PPO，保存、重新加载策略，在与训练分开的 20 个初始条件下比较。SB3 按整批采样，实际交互步数可能略超过请求预算。运行时间和成绩取决于电脑、依赖与随机性；不保证每次完全相同或一定达到特定分数。

输出位于 `runs/pendulum/`。先读 `evaluation.json` 中的 `random_baseline` 与 `trained_policy`，再看每回合的分数、步数和结束方式。这里奖励每存活一步约为 1；回合达到 1000 步会被时间截断。强行把平均分理解为现实机器人的成功率是不对的。

## 3. 观看仿真

```powershell
.\.venv\Scripts\python watch_ppo.py
```

打开 MuJoCo 窗口后观察训练后的策略。若在无图形界面的服务器或远程环境运行，窗口可能不可用，但上一步的无窗口训练和评估仍可进行。

## 4. 导出与检查

```powershell
.\.venv\Scripts\python export_onnx.py
```

脚本把确定性 PPO 策略导出为 ONNX，并在 101 组输入上比较导出结果与 Stable-Baselines3 的 `predict`；数值偏差超出容差就报错。输出动作的限幅包含在 ONNX 内。

输入是 `float32`、形状 `[批量, 4]`，顺序为：小车位置（m）、杆角度（rad）、小车速度（m/s）、杆角速度（rad/s）；输出是小车推力（N），范围 `[-3, 3]`。真实硬件需要另外建立并验证自己的接口，这个倒立摆模型不能直接用于其他机器人。

## 5. 迁移到你的机器人

先完成课程的“迁移到机器人”接口表，阅读 [真实机器人实战工作手册](../content/真实机器人实战工作手册.md)。按顺序定义任务和能真实读取的观察、选择动作及控制模式、测量电机/传感器/延迟、建立模型、训练和独立评估，再分阶段做硬件验证。换主控时保持策略的输入输出契约，并重做接口适配与验证。

ONNX 只是模型文件；并不意味着任意单片机能运行它，也不包含通信、驱动、独立保护或急停。模型导出数值一致不等于真机安全或训练效果已得到验证。

## 参考

- [Gymnasium InvertedPendulum-v5 环境](https://gymnasium.farama.org/environments/mujoco/inverted_pendulum/)
- [Stable-Baselines3 PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)
- [Stable-Baselines3 的模型导出说明](https://stable-baselines3.readthedocs.io/en/master/guide/export.html)
- [MuJoCo 文档](https://mujoco.readthedocs.io/)
