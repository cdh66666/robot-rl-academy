# 浏览器 MuJoCo 强化学习实验室

## 集成与运行

网站中以 `<iframe src="engine/index.html" title="MuJoCo 倒立摆训练实验室"></iframe>` 嵌入。建议 iframe 宽度 100%，高度不少于 1800px（容器较窄时需要更高），或提供独立页面链接。页面是响应式，可独立打开。

运行时文件：`index.html`、`lab.css`、`app.mjs`、`worker.mjs`、`core.mjs`、`dqn.mjs`、`vendor/mujoco.js`、`vendor/mujoco.wasm`、`vendor/MUJOCO-LICENSE.txt`。其中官方 WASM 约 11.2 MB。网站托管服务器应以 `application/wasm` 提供 `.wasm`、以 JavaScript MIME 提供 `.js` 和 `.mjs`，允许同源 Worker 和 WebAssembly；单线程版本无需 COOP/COEP 跨源隔离。静态网站可在首次加载这些文件之后不依赖外网与 API 密钥，未设置离线 Service Worker，所以首次打开仍需能访问网站本身。不要声称断网刷新可用。

浏览器安全限制下不能双击 `file://` 运行 ES module / Worker / WASM；需通过 HTTPS 网站或本地 HTTP 静态服务访问。访客不需要 Node、Python、npm，也不用 GPU。仓库里的 `node_modules`、测试脚本和截图不是发布运行的必需文件。

## 行为与参数

- 动力学：官方 Google DeepMind MuJoCo 4.0.1 单线程 WASM。`core.mjs` 自建教学倒立摆 MJCF，小车平移 + 杆单轴转动；所有推进由 `mj_step` 执行。画面是读取物理状态绘制的二维投影，并非 3D 渲染，也不等同 Gymnasium 官方环境的参数复刻。
- 一个动作维持 4 次 5 ms MuJoCo 物理步，即每 20 ms 决策一次；动作只有 −10 / +10 N，两种方向。初始位置、速度、角度、角速度各自按约 ±0.05 的对应单位随机采样。
- 失败：杆倾角超过 ±12° 或小车位置超过 ±2.4 m；超出阈值的那一步奖励为 +1 加上用户选择的失败额外项（默认 −5，因此净值为 −4；也可选 0）。分数始终是实际存活决策步数，不是累计奖励。500 步是时间截断，不能当作失败终止。
- 算法：4-32-32-2 网络、ReLU、Double DQN、经验回放池、固定间隔更新目标网络、ε 贪婪探索、Huber loss、Adam。在线网络选下一动作，目标网络评价；时间截断仍 bootstrap，失败终止不 bootstrap。每次训练最多 50,000 决策步；无后端。
- 每 5,000 步在 10 个固定初始条件上验证，保留最佳均值检查点；“独立测试”用另外 20 个固定初始条件评估当前最佳检查点及随机策略，显示平均与范围。它们只是这个仿真任务的有限测试，不是保证训练成功的证明。
- 推力滑块只影响播放与独立测试，不影响训练；默认训练推力为 10 N。改变种子或失败奖励后点“重新开始”生效。下载的 JSON 含曲线、权重和最近一次有效独立测试；未实现导入。若浏览器未自动保存，页面会出现手动保存链接及可复制的记录文字。策略只适用于教学模型，不能直接部署实机。

## 实测与注意事项

2026-11-16，系统 Chrome 无头浏览器，默认种子 123、奖励 −5、实际完成 50,000 决策。10 N 的 20 回合独立测试：随机动作平均 25.2 步，训练得到的最佳检查点平均 459.45 步（UI 显示到一位小数）；推力改为 6 N 时同一检查点均值 399.0 步。结果见 `qa/browser-results.json`，`qa/desktop-trained.png`、`qa/mobile-trained.png` 为界面截图。已检查暂停/恢复、种子与奖励重置、模型导出、手机横向溢出和页面错误；不同随机种子、浏览器/计算环境及配置可能产生不同结果，不代表物理机器人性能。

复测：开发环境先安装 `package.json` 中依赖，在此目录运行 `node test-browser.mjs`（测试使用本机 Chrome 和仅绑定 127.0.0.1 的临时静态服务）。最终访客不需安装这些开发依赖。

## 第三方许可

`vendor/mujoco.js` 与 `vendor/mujoco.wasm` 来自 [Google DeepMind 官方 `@mujoco/mujoco` 4.0.1](https://www.npmjs.com/package/@mujoco/mujoco)，Apache-2.0；完整许可证随附于 `vendor/MUJOCO-LICENSE.txt`。训练网络、课程页面和倒立摆 MJCF 为本项目教学代码。
