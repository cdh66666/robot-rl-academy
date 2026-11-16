# 从单关节 MuJoCo 到 PPO 与离线策略接口

这是一套**可运行的仿真教学样例**：自定义 MJCF 建立 1 个转动关节及一个近似位置伺服，PPO 学习针对不同目标角度给位置参考；随后做独立初值评估，导出 ONNX，并检查推理前后处理是否一致。它不连接电机，也不是针对某款机器人完成的部署。

## 先理解这个闭环

每 20 ms，策略收到四个数：关节角、关节角速度、目标角、上一次实际使用的位置参考。神经网络给出一个连续动作，经过位置限幅与变化率限制后，成为本周期的角度参考。MuJoCo 的简化位置伺服依据角度误差和速度计算受限力矩，推动关节运动。状态更新后，再用新误差给奖励。

```text
目标角 + 角度/角速度 + 上次参考 → PPO 网络 → 位置目标限幅/限速
                              ↑                    ↓
                       奖励与采样 ← MuJoCo 位置伺服和关节
```

这和实际总线舵机、无刷电机的接口之间还有型号、单位、方向、零点、通信周期和延迟等差异。`model.xml` 中的电机参数只是示例，未对任何实际电机辨识。位置执行器是一个带速度阻尼和力矩饱和的简化近似，不代表真实固件或 FOC 内环。

## 立即运行

已包含训练好的 `artifacts/joint_ppo.zip` 与 `artifacts/joint_actor.onnx`，可以先评估，再独立重训。下面以 Windows 10/11、64 位电脑和 PowerShell 为例；网页入门实验不需要安装，以下步骤只用于运行这个 Python 进阶工程。

1. 在课程网站“参考资料”下载“单关节工程”，右键 ZIP 选择“全部解压”，逐层打开解压得到的 `单关节PPO` 文件夹，直到同一窗口能看到 `train.py`、`model.xml` 和 `requirements.txt`。若下载的是完整实战代码包，则进入其中的 `robot-rl-ppo/project/joint/`。
2. 在该文件夹地址栏输入 `powershell` 后回车。在打开的窗口执行 `Get-Location` 查看当前位置，并执行 `Test-Path .\model.xml`；应返回 `True`。若为 `False`，请重新从包含 `model.xml` 的文件夹打开 PowerShell。
3. 执行 `python --version`。建议使用 **64 位 Python 3.13**，本机实际测试为 Python 3.13.12；如果没有安装，可从 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/)选择 Python 3.13 的 **Windows installer (64-bit)**，安装时勾选“Add Python to PATH”。完成后重新打开 PowerShell，再确认显示 `Python 3.13.x`。首次安装依赖需要网络；训练和评估在本地 CPU 上运行，不需要云服务或 API 密钥。
4. 在同一窗口按顺序运行下面的命令。`.venv` 是这个项目单独的依赖环境，直接调用其中的 Python 即可，不需要激活环境或修改 PowerShell 执行策略。安装结束后 `pip check` 应显示 `No broken requirements found`。

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check

# 只在仿真中检查正负参考、时间步和限幅，不覆盖随包结果
.\.venv\Scripts\python.exe inspect_model.py --output first_check\model_inspection.json

# 先复现随包模型的固定种子评估，查看零动作、未训练网络、PPO 和直接目标基线
.\.venv\Scripts\python.exe evaluate.py --output first_check

# 独立重新训练到 my_run，不覆盖随包模型
.\.venv\Scripts\python.exe train.py --seed 123 --timesteps 100000 --output my_run
.\.venv\Scripts\python.exe evaluate.py --model my_run\joint_ppo.zip --output my_run
.\.venv\Scripts\python.exe export_onnx.py --model my_run\joint_ppo.zip --output my_run
.\.venv\Scripts\python.exe check_deployment.py --artifacts my_run
.\.venv\Scripts\python.exe deploy_offline.py --model my_run\joint_actor.onnx
.\.venv\Scripts\python.exe plot_results.py --artifacts my_run
```

`train.py` 默认用 CPU，PPO 以每次 512 步的批次收集数据，所以 `--timesteps 100000` 实际可执行到 100352 步。计算耗时随电脑而变。`deploy_offline.py` 只对人为给出的数字做一次推理并打印结果，没有通信端口、驱动调用或真实输出。训练配置、策略和评估结果位于输出目录；`my_run` 是用户自己生成的新目录。

`inspect_model.py` 会从零角度分别在两个独立仿真中请求 `+0.4` 和 `−0.4 rad` 位置参考，各运行 20 个控制周期；显示模型时间步、输入和力矩范围、参考的单周期最大变化、正负方向的最终角度，并将每个控制周期的样本写入你指定的 JSON。在本机默认模型一次运行中，首周期应用参考为 ±0.06 rad，20 周期后的角度约 ±0.37256 rad；每个物理步采样到的执行器力矩绝对值峰值约 0.661 N·m，低于该模拟模型的 ±1.5 N·m 限制。你的结果可能因环境不同而略有差异；这只检查两个模拟输入，不能证明真实机器人方向、标定、力矩或安全。

本机验证环境为 Windows 64 位、Python 3.13.12、Gymnasium 1.4.0、MuJoCo 4.0.1、Stable-Baselines3 2.9.2、PyTorch 2.12.0（训练指定 CPU）、ONNX 1.21.0 和 ONNX Runtime 1.26.0。2026-11-16 已在不继承系统包的新虚拟环境里，按本包 `requirements.txt` 安装并从解压包完成训练、评估、导出及离线接口检查；这次使用了本机配置的 Python 包镜像。其他系统、网络或后续依赖供应可能产生不同结果。

## 参数与输入输出契约

| 内容 | 本样例的定义 |
|---|---|
| 关节与模型 | 单轴转动，杆长 0.32 m、质量 0.25 kg；MJCF 关节范围 ±1.05 rad |
| 物理/策略周期 | MuJoCo 5 ms 一步，4 个物理步为 20 ms，即策略 50 Hz |
| 伺服近似 | MuJoCo `position` 执行器；`kp=6`、`kv=0.25`，输出力矩限制 ±1.5 N·m |
| 输入 `observation` | float32，形状 `[1,4]`，顺序：`clip(q/0.9,-2,2)`、`clip(qdot/5,-1,1)`、`clip(target/0.9,-1,1)`、`clip(previous_reference/0.9,-1,1)`。角度 rad，角速度 rad/s。 |
| 网络输出 `action` | float32，形状 `[1,1]`，经夹紧到 `[-1,1]`；这只是网络请求值，还不是电机指令或力矩。 |
| 位置参考 | 请求值乘 0.9 rad；相对于上一周期**已应用参考**，每 20 ms 变化不超过 0.06 rad，即 3 rad/s。每回合初始化参考等于初始关节角。见 `contract.py`。 |
| 一回合 | 起始角约 ±0.7 rad，初速度约 ±0.1 rad/s，目标在 ±0.75 rad；最多 150 步即 3 s。 |
| 终止与截断 | `|q| > 1.04 rad` 或 `|qdot| > 12 rad/s` 为仿真失败终止；150 步为时间截断，不等同失败。 |
| 奖励 | `-2·角度误差² - 0.01·速度² - 0.005·(本次请求−上次参考归一化值)²`，误差小于 0.05 rad 加 0.05；失败另减 10。 |

神经网络只有一个连续输出。导出的 ONNX 已做输出的 `[-1,1]` 夹紧；**乘以 0.9 rad 和每周期 0.06 rad 的位置参考限速不在 ONNX 图中**，必须由部署端按 `contract.py` 逐周期执行。网络的第四个输入是上一周期限速后实际使用的参考除以 0.9，并非网络上次未经处理的输出。

`deploy_offline.py` 演示状态有效性、超过两个周期的陈旧样本拒绝、目标/状态超出示例范围拒绝、参考限幅与限速。阈值是本模型假设，不是任何真实机器人的安全参数。实际部署还需要按硬件建立和验证独立的电源、急停、超时、失联、力矩/电流、机械边界和恢复流程。

## 自定义模型与换主控

1. 从 `model.xml` 改单关节几何、质量、关节阻尼或执行器参数，或用 `train.py --xml 你的文件.xml` 指定新模型。本环境检查它仍是受限单旋转关节、单位传动比、受限力矩的位置执行器、兼容的角度范围和 20 ms 策略周期。改变自由度、输出含义、范围或周期时，须同步修改环境、`contract.py`、网络、评估和部署接口；不能只替换 XML。
2. 训练输出会记录训练模型 XML 的 SHA-256。默认评估拒绝与训练时 XML 不一致的模型；明确做仿真参数差异实验时，可传 `--allow-model-mismatch`，结果会标注 `same_xml_as_training: false`。修改模型后应重新训练和验证。
3. 换主控时，先确认目标平台能在规定周期运行 ONNX 或完成等价转换，保持输入顺序、单位、归一化、历史状态、夹紧和限速一致；再让 AI 按具体主控/舵机协议生成设备适配器，由人核对电机零点、方向、减速比、编码器与驱动模式。总线位置舵机和无刷 FOC 驱动的命令意义可能完全不同，不可直接套用示例位置参考。
4. 先在目标平台离线比较多组输入输出与轨迹，检查周期、延迟和失效处理；再按实际硬件逐项验证传感器及执行器。此项目未完成任何实机验证。

## 已完成的模拟评估

随包策略使用种子 123、PPO 100352 个决策步训练。以下是 **2026-11-16、同一简化模型、训练以外 20 组固定初值（种子 20000–20019）** 的结果。误差为每回合最后 50 步绝对角度误差的均值；成功要求整回合未提前失败且最后 20 步每一步误差都小于 0.05 rad。对提前失败回合，误差统计其结束前最多 50 步，并单独报告失败数。

| 控制方式 | 最后 50 步平均绝对误差 | 成功 | 提前终止 |
|---|---:|---:|---:|
| 始终给零位置 | 0.4918 rad / 28.18° | 2/20 | 0/20 |
| 未训练网络 | 0.4915 rad / 28.16° | 2/20 | 0/20 |
| PPO | 0.0091 rad / 0.52° | 20/20 | 0/20 |
| 直接将目标角作为位置参考 | 0.0286 rad / 1.64° | 20/20 | 0/20 |

这个简单问题中“直接给目标”是必须保留的强基线；强化学习并非处理这类任务的唯一方案。另用 100 个不同种子、相同模型和初值分布测试：PPO 100/100 达到上述判据、无提前终止，最后 50 步平均绝对误差 0.0075 rad。它不是对不同负载、电机、摩擦、延迟或真实机器人的泛化证明。

第一轮没有限制位置参考变化率时，一个独立种子出现速度超限并提前终止；相关原始评估保存在 `first_trial_evaluation.json`。加入限速后重新训练才得到上表。证据：`artifacts/evaluation.json`、`artifacts/trace_first_episode.csv`、`artifacts/tracking_comparison.png`、`stress_slew/evaluation.json`。

ONNX 与 SB3 对 100 组相同输入的最大动作差为 `1.79e-7`；另在 10 个仿真回合共 1500 次控制采样中，状态归一化、ONNX 动作和限速参考的数值一致性检查通过，结果见 `artifacts/onnx_verification.json` 与 `artifacts/deployment_contract_check.json`。这个检查验证软件接口一致性，不验证任何物理部署。

## 文件与资料

- `model.xml`：单关节 MJCF。`joint_env.py`：Gymnasium 训练环境、奖励与终止条件。
- `inspect_model.py`：正负已知参考的模型自检；`train.py`、`evaluate.py`：训练和基线比较。`export_onnx.py`：导出和相同输入数值比对。
- `contract.py`、`deploy_offline.py`：不依赖 MuJoCo 或训练框架的预处理、后处理和离线推理示例。
- `check_deployment.py`：仿真中的训练/部署契约一致性检查。`plot_results.py`：依据评估文件绘制结果。
- [MuJoCo 位置执行器文档](https://mujoco.readthedocs.io/en/latest/XMLreference.html#actuator-position)；[Gymnasium 环境接口](https://gymnasium.farama.org/api/env/)；[Stable-Baselines3 ONNX 导出](https://stable-baselines3.readthedocs.io/en/master/guide/export.html)。
