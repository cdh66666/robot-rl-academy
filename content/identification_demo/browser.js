(() => {
  "use strict";
  const canvas = document.querySelector("#graph"), ctx = canvas.getContext("2d");
  const button = document.querySelector("#fit"), status = document.querySelector("#fit-status");
  const dataStatus = document.querySelector("#data-status");
  const split = 600, dt = .02;
  let commands = [], measured = [], prediction = null;

  function draw() {
    // Draw in CSS pixels, then scale for high-density displays so labels stay
    // legible on phones instead of shrinking with a fixed 1160px bitmap.
    const w = canvas.clientWidth || 800, h = Math.max(240, Math.round(w * 470 / 1160));
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.style.height = `${h}px`;
    canvas.width = Math.round(w * ratio); canvas.height = Math.round(h * ratio);
    ctx.setTransform(ratio,0,0,ratio,0,0);
    const L=45,R=w-14,T=18,B=h-38;
    const x=i=>L+(R-L)*i/1000, y=v=>B-(v+.42)/.84*(B-T);
    ctx.clearRect(0,0,w,h);ctx.fillStyle="#f9fcfa";ctx.fillRect(0,0,w,h);
    ctx.fillStyle="#e9f4ee";ctx.fillRect(x(split),T,R-x(split),B-T);
    ctx.strokeStyle="#dce9e5";ctx.lineWidth=1;ctx.fillStyle="#69837f";ctx.font="12px sans-serif";
    for(let i=0;i<=10;i++){const px=x(i*100);ctx.beginPath();ctx.moveTo(px,T);ctx.lineTo(px,B);ctx.stroke();ctx.fillText(String(i*2),px-7,B+26);}
    for(const value of [-.4,-.2,0,.2,.4]){const py=y(value);ctx.beginPath();ctx.moveTo(L,py);ctx.lineTo(R,py);ctx.stroke();ctx.fillText(value.toFixed(1),8,py+5);}
    ctx.strokeStyle="#9bbcb1";ctx.setLineDash([7,6]);ctx.beginPath();ctx.moveTo(x(split),T);ctx.lineTo(x(split),B);ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle="#66817b";ctx.font="12px 'Microsoft YaHei', sans-serif";ctx.fillText("拟合段",L+10,T+20);ctx.fillText("留出验证段",x(split)+8,T+20);
    const line=(values,color,width,dash=[])=>{if(!values.length)return;ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();values.forEach((v,i)=>i?ctx.lineTo(x(i),y(v)):ctx.moveTo(x(i),y(v)));ctx.stroke();ctx.setLineDash([]);};
    line(commands,"#e89463",2,[8,5]);line(measured,"#8da09e",1.4);if(prediction)line(prediction,"#058488",3);
  }
  async function load() {
    try {
      const response=await fetch("output/synthetic_servo_response.csv");
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const lines=(await response.text()).trim().split(/\r?\n/);
      if(lines.shift()!=="data_kind,time_s,command_target_rad,position_measured_rad")throw new Error("数据列不匹配");
      const rows=lines.map(line=>line.split(","));
      if(rows.length!==1001 || rows.some((r,i)=>r[0]!=="synthetic" || !Number.isFinite(Number(r[2])) || !Number.isFinite(Number(r[3])) || Math.abs(Number(r[1])-i*dt)>1e-7)) throw new Error("数据无效或采样间隔不正确");
      commands=rows.map(r=>Number(r[2]));measured=rows.map(r=>Number(r[3]));
      dataStatus.textContent="已载入 1001 个合成样本";button.disabled=false;status.textContent="点击按钮，自己算一次结果。";draw();
    } catch(error){dataStatus.textContent="数据加载失败";status.textContent="请通过课程网址或本地启动器打开，而不是直接双击文件。";console.error(error);}
  }
  button.addEventListener("click",()=>{
    button.disabled=true;status.textContent="正在用拟合段搜索参数…";
    const worker=new Worker("browser-worker.js");
    worker.onmessage=({data})=>{
      worker.terminate();button.disabled=false;
      if(data.error){status.textContent=`拟合失败：${data.error}`;return;}
      prediction=data.prediction;draw();
      document.querySelector("#tau").textContent=`${data.tau.toFixed(3)} s`;
      document.querySelector("#delay").textContent=`${data.delay.toFixed(3)} s`;
      document.querySelector("#rmse").textContent=`${data.heldoutRmse.toFixed(6)} rad`;
      document.querySelector("#results").hidden=false;
      status.textContent=`拟合完成；拟合段 RMSE ${data.trainRmse.toFixed(6)} rad。参数选择未使用留出段测量。`;
    };
    worker.onerror=()=>{worker.terminate();button.disabled=false;status.textContent="计算未能完成，请刷新后重试。";};
    worker.postMessage({commands,measured,dt,split});
  });
  window.addEventListener("resize", draw);
  draw();load();
})();
