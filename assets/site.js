/* The course and the experiment run in the browser; no tracking or account is required. */
(() => {
  "use strict";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  // The long course has new material; a completed short preview is not a
  // completed long episode. Keep robot forms, but start a separate progress log.
  const progressKey = "robot-rl-done-long-v2";
  const state = { lessons: [], videos: new Map(), done: readJson(progressKey, []), robot: readJson("robot-rl-contract", {}) };

  function readJson(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  }
  function writeJson(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* The app still works in private storage modes. */ }
  }
  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  }
  function externalUrl(value) {
    try { const u = new URL(value); return ["http:", "https:"].includes(u.protocol) ? u.href : "#"; } catch { return "#"; }
  }
  function lessonById(id) { return state.lessons.find(lesson => String(lesson.id).padStart(2,"0") === id); }
  function lessonUrl(id) { return `#lesson/${id}`; }
  function splitCheck(item) {
    if (typeof item === "object" && item !== null) return {q:item.question ?? "自测", a:item.answer ?? ""};
    const pieces = String(item).split(/答[：:]/);
    return {q:pieces[0], a:pieces.slice(1).join("答：") || "请结合本课内容回答。"};
  }
  function updateNavigation(id = "") {
    $("#lesson-nav").innerHTML = state.lessons.map(lesson => {
      const n = String(lesson.id).padStart(2,"0");
      const done = state.done.includes(n);
      return `<a class="lesson-link ${n === id ? "active" : ""}" href="${lessonUrl(n)}" ${n === id ? 'aria-current="page"' : ""}><span class="lesson-num">${esc(n)}</span><span>${esc(lesson.title)}</span><span class="lesson-check">${done ? "✓" : ""}</span></a>`;
    }).join("");
    const total = state.lessons.length || 10;
    const count = state.lessons.filter(x => state.done.includes(String(x.id).padStart(2,"0"))).length;
    $("#progress-label").textContent = `${count} / ${total}`;
    $("#progress-fill").style.width = `${Math.round(count / total * 100)}%`;
    $(".side-count").textContent = `${total} 课`;
  }
  function videoHtml(lesson) {
    const id = String(lesson.id).padStart(2,"0");
    const item = state.videos.get(id);
    if (!item || !item.file) return `<div class="video-shell"><div class="video-placeholder"><strong>本课视频正在准备</strong><span>先从下方图文和动手任务开始。</span></div></div>`;
    // Paths are authored by this course and must stay inside the video folder.
    const file = String(item.file);
    if (file.includes("..") || /^(?:[a-z]+:|\/)/i.test(file)) return "";
    const safe = path => path && !String(path).includes("..") && !/^(?:[a-z]+:|\/)/i.test(String(path));
    // The public long-course videos are release assets; keep the website itself
    // small. Only accept this repository's expected, episode-specific URL.
    let remote = "";
    try {
      const u = new URL(item.remote_file || "");
      if (u.protocol === "https:" && u.hostname === "github.com" && u.pathname === `/cdh66666/robot-rl-academy/releases/download/course-v2/${id}.mp4` && !u.search && !u.hash) remote = u.href;
    } catch { /* Older course manifests have only local files. */ }
    const local = `video/${file}`;
    const localServer = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
    const source = remote && !localServer ? remote : local;
    const fallback = remote && localServer ? ` data-remote-fallback="${esc(remote)}"` : "";
    return `<div class="video-shell"><video controls preload="metadata" playsinline src="${esc(source)}"${fallback}>你的浏览器无法播放视频。</video></div><div class="video-caption">本集可在这里直接观看。${remote ? ` <a class="text-link" href="${esc(remote)}" target="_blank" rel="noopener noreferrer">打开视频文件</a>` : ""}${safe(item.subtitle) ? ` · <a class="text-link" href="${esc(`video/${item.subtitle}`)}" download>下载字幕</a>` : ""}${safe(item.chapters) ? ` · <a class="text-link" href="${esc(`video/${item.chapters}`)}" download>下载章节时间码</a>` : ""}</div>`;
  }
  function renderLesson(id) {
    const lesson = lessonById(id);
    if (!lesson) { $("#lesson-content").innerHTML = '<div class="page-head"><div><h1>没有找到这一课</h1><p>请从左侧目录选择课程。</p></div></div>'; return; }
    const index = state.lessons.indexOf(lesson);
    const previous = state.lessons[index-1], next = state.lessons[index+1];
    const blocks = (lesson.blocks || []).map(b => `<h3>${esc(b.heading)}</h3><p>${esc(b.body)}</p>`).join("");
    const practices = (lesson.practice || []).map(x => `<li>${esc(x)}</li>`).join("");
    const checks = (lesson.check || []).map(item => {const c=splitCheck(item);return `<details><summary>${esc(c.q)}</summary><p>${esc(c.a)}</p></details>`;}).join("");
    const sources = (lesson.sources || []).map(s => `<li><a href="${esc(externalUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.label)} ↗</a></li>`).join("");
    const chapters = (lesson.chapters || []).map((chapter,i) => {
      const sec = Number(chapter.start_seconds || 0), minute = Math.floor(sec / 60), second = Math.floor(sec % 60);
      const stamp = `${String(minute).padStart(2,'0')}:${String(second).padStart(2,'0')}`;
      const transcript = String(chapter.narration || '').split(/\n+/).filter(Boolean).map(p => `<p>${esc(p)}</p>`).join('');
      const references = (chapter.source_urls || []).map((url,n) => `<a href="${esc(externalUrl(url))}" target="_blank" rel="noopener noreferrer">资料 ${n+1} ↗</a>`).join('　');
      return `<details class="chapter"><summary><span class="chapter-number">${String(i+1).padStart(2,'0')}</span><span>${esc(chapter.title)}</span><span class="chapter-time">${stamp}</span></summary><div class="chapter-content"><p><strong>跟着做：</strong>${esc(chapter.practice)}</p><p><strong>预期结果：</strong>${esc(chapter.expected)}</p><button type="button" class="small-button jump-video" data-seconds="${sec}">从 ${stamp} 开始观看</button><details class="transcript"><summary>展开本章讲解文字</summary>${transcript}</details>${references ? `<p class="chapter-references">${references}</p>` : ''}</div></details>`;
    }).join('');
    const done = state.done.includes(id);
    $("#lesson-content").innerHTML = `
      <div class="lesson-head"><div class="lesson-crumb"><a href="#start">学习路线</a> / 第 ${esc(id)} 课</div><span class="section-tag">${esc(lesson.duration || "动手学习")}</span><h1>${esc(lesson.title)}</h1><p class="why">${esc(lesson.why)}</p><div class="lesson-meta"><span class="pill">学完后动手做</span><span>看视频 · 读重点 · 做练习</span></div></div>
      <div class="lesson-body"><div class="outcome"><div><h2>这一课学什么</h2><p>${esc(lesson.objective)}</p></div><div><h2>学完能做什么</h2><p>${esc(lesson.outcome)}</p></div></div><article class="content-card lesson-video"><div class="card-label">本课视频</div>${videoHtml(lesson)}</article>
      <div class="lesson-grid"><div class="lesson-text"><article class="content-card"><div class="card-label">核心内容</div>${blocks}</article>${chapters ? `<article class="content-card"><div class="card-label">章节与跟练</div><h2>按步骤学，每一章都能动手</h2><p>展开章节查看操作、预期结果和讲解文字；也可以跳到对应视频位置。</p>${chapters}</article>` : ''}<article class="content-card"><div class="card-label">亲手试一试</div><h2>按照这几步做</h2><ol class="practice-list">${practices}</ol><div class="lesson-actions"><a class="button secondary" href="#lab">打开训练实验室</a>${id === "02" || index >= 6 ? '<a class="button secondary" href="#robot">填写机器人接口表</a>' : ""}${id === "07" ? '<a class="button secondary" href="content/identification_demo/browser.html" target="_blank">打开网页辨识实验</a>' : ""}${id === "04" ? '<a class="button secondary" href="project/guide.html" target="_blank">打开连续动作跟练</a>' : ""}${["05","09","10"].includes(id) ? '<a class="button secondary" href="project/joint/guide.html" target="_blank">打开单关节实战</a>' : ""}</div></article><article class="content-card"><div class="card-label">检查是否理解</div><h2>试着自己回答</h2>${checks}</article></div>
      <aside class="lesson-support"><article class="content-card"><div class="card-label">继续查证</div><h2>本课资料</h2><ul class="source-list">${sources}</ul></article></aside></div>
      <div class="lesson-actions"><button class="button ${done ? "secondary" : "primary"}" id="mark-done" data-id="${esc(id)}">${done ? "✓ 已标记完成" : "标记本课完成"}</button>${previous ? `<a class="button ghost" href="${lessonUrl(String(previous.id).padStart(2,"0"))}">上一课</a>` : ""}${next ? `<a class="button ghost next" href="${lessonUrl(String(next.id).padStart(2,"0"))}">下一课：${esc(next.title)} ↗</a>` : '<a class="button ghost next" href="#robot">整理你的机器人项目 ↗</a>'}</div></div>`;
    $("#mark-done")?.addEventListener("click", () => {
      state.done = done ? state.done.filter(x => x !== id) : [...new Set([...state.done,id])];
      writeJson(progressKey,state.done); renderLesson(id); updateNavigation(id);
    });
    const videoElement = $("#lesson-content video");
    videoElement?.addEventListener("error", () => {
      const fallback = videoElement.dataset.remoteFallback;
      if (fallback) { delete videoElement.dataset.remoteFallback; videoElement.src = fallback; videoElement.load(); return; }
      const caption = videoElement.closest('.video-shell')?.nextElementSibling;
      if (caption && !caption.querySelector('[role="status"]')) {
        const notice = document.createElement('span'); notice.setAttribute('role','status');
        notice.textContent = ' 视频暂时无法加载；请检查网络或尝试打开视频文件。'; caption.appendChild(notice);
      }
    });
    $$('.jump-video', $('#lesson-content')).forEach(button => button.addEventListener('click', () => {
      const video = $('#lesson-content video');
      if (!video) return;
      video.currentTime = Number(button.dataset.seconds || 0);
      video.scrollIntoView({behavior:'smooth',block:'center'});
      video.play().catch(() => {});
    }));
  }
  function route() {
    let route = location.hash.slice(1) || "start";
    const lessonMatch = route.match(/^lesson\/(\d{1,2})$/);
    let view = lessonMatch ? "lesson" : route;
    if (!["start","lesson","lab","robot","resources"].includes(view)) view = "start";
    $$(".view").forEach(el => el.classList.add("hidden"));
    $(`#view-${view}`).classList.remove("hidden");
    $$("[data-top]").forEach(el => el.classList.toggle("active", el.dataset.top === (view === "lesson" ? "start" : view)));
    const id = lessonMatch ? lessonMatch[1].padStart(2,"0") : "";
    if (view === "lesson") renderLesson(id);
    if (view === "lab" && !$("#lab-frame").src) $("#lab-frame").src = "engine/index.html";
    updateNavigation(id);
    window.scrollTo({top:0,behavior:"instant"});
  }
  function robotFields() {
    return Object.fromEntries(new FormData($("#robot-form")).entries());
  }
  function setupRobotForm() {
    const form = $("#robot-form");
    for (const [key,value] of Object.entries(state.robot || {})) if (form.elements[key]) form.elements[key].value = value;
    form.addEventListener("input", () => {state.robot=robotFields();writeJson("robot-rl-contract",state.robot);});
    form.addEventListener("submit", e => {
      e.preventDefault();
      const f = robotFields();
      const field = (name) => f[name]?.trim() || "待测／待补充";
      $("#prompt-output").value = `请作为机器人强化学习工程师，与我一起制定一个可以复现和验证的训练项目。\n\n【任务和机器人】${field("task")}\n【关节与驱动】${field("actuators")}\n【真实可获得的观察】${field("observations")}\n【可发送动作】${field("actions")}\n【主控和通信】${field("controller")}\n【限制与待测参数】${field("limits")}\n【奖励与结束条件】${field("reward_termination")}\n【重置与独立评估】${field("reset_evaluation")}\n\n请先列出关键缺失信息及其测量方法，不编造参数；逐项明确观察和动作的顺序、坐标系、单位、归一化、频率、上下限和超时处理。再给我 MuJoCo 模型、训练环境、奖励与终止条件、基线与独立评估计划，区分系统辨识与随机化。先生成仿真和离线回放代码，提供可运行测试和预期输出。部署时说明策略、接口适配、驱动闭环及独立安全层的边界；换主控时优先保持策略输入输出契约，明确哪些接口必须重写。未经具体硬件核验，不要自动连接实机或驱动电机，列出断电检查、通信只读、低风险分阶段验证及回退方法。每一步说明目的、操作和验收标准。`;
      $("#prompt-card").scrollIntoView({behavior:"smooth",block:"start"});
    });
    $("#copy-prompt").addEventListener("click", async e => {
      try { await navigator.clipboard.writeText($("#prompt-output").value); e.currentTarget.textContent="已复制"; setTimeout(()=>e.currentTarget.textContent="复制",1800); }
      catch { $("#prompt-output").focus(); $("#prompt-output").select(); e.currentTarget.textContent="请手动复制"; }
    });
    $("#save-contract").addEventListener("click", () => {
      const blob = new Blob([JSON.stringify({schema:"robot-rl-contract-v1",...robotFields()},null,2)],{type:"application/json;charset=utf-8"});
      const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="机器人接口表.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
  }
  async function init() {
    setupRobotForm();
    // The lab is same-origin. Fit its content so learners do not have to use
    // two nested scrollbars to reach the controls and the evaluation chart.
    $("#lab-frame").addEventListener("load", e => {
      try {
        const frame = e.currentTarget;
        const body = frame.contentDocument.body;
        if (!body) return;
        const fit = () => { frame.style.height = `${Math.max(780, body.scrollHeight + 8)}px`; };
        fit();
        new ResizeObserver(fit).observe(body);
      } catch { /* A standalone link remains available if framing is blocked. */ }
    });
    try {
      const response = await fetch("content/lessons.json",{cache:"no-cache"});
      if (!response.ok) throw new Error(`课程文件 HTTP ${response.status}`);
      const data = await response.json(); state.lessons = Array.isArray(data.lessons) ? data.lessons : [];
      if (!state.lessons.length) throw new Error("课程文件中没有课程");
    } catch (err) {
      $("#lesson-nav").innerHTML = `<p class="muted">课程加载失败。请使用课程网址或本地启动器打开网站。${esc(err.message)}</p>`;
      return;
    }
    try {
      const response = await fetch("video/manifest.json",{cache:"no-cache"});
      if (response.ok) { const data=await response.json(); for(const v of data.videos || []) state.videos.set(String(v.id).padStart(2,"0"),v); }
    } catch { /* Written lessons stay usable while the videos are being made. */ }
    route();
    window.addEventListener("hashchange", route);
  }
  init();
})();
