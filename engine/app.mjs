const $ = id => document.getElementById(id);
const elements = ['start','pause','reset','random-mode','trained-mode','force','test','export'];
const lab = window.__rlLab = {ready:false, status:null, test:null, error:null};
let worker, previousBestAt = -1, currentMode = 'random';

function clearResults(message = '独立测试只衡量这个模拟任务，分数不等于机器人能在真实世界运行。') {
  $('random-result').textContent = '—'; $('trained-result').textContent = '—';
  $('test-note').textContent = message; lab.test = null;
}
function setReady() {
  lab.ready = true;
  for (const id of elements) $(id).disabled = false;
  $('pause').disabled = true;
  $('load-status').textContent = 'MuJoCo 4.0.1 已就绪。先看随机动作，再点“开始训练”。';
}
function refreshStatus(s) {
  lab.status = s;
  $('episodes').textContent = s.episodes.toLocaleString();
  $('epsilon').textContent = Math.round(s.epsilon*100) + '%';
  $('recent').textContent = s.recent == null ? '—' : s.recent.toFixed(1);
  $('best').textContent = Number.isFinite(s.bestValidation) ? s.bestValidation.toFixed(1) : '—';
  $('progress-bar').style.width = Math.min(100, s.steps / 500) + '%';
  $('progress-text').textContent = s.steps.toLocaleString() + ' / 50,000 次决策';
  $('train-state').textContent = s.running ? '训练中' : s.ended ? '训练完成' : s.steps ? '已暂停' : '等待训练';
  $('start').textContent = s.ended ? '训练完成' : s.steps ? '继续训练' : '开始训练';
  $('start').disabled = !lab.ready || s.running || s.ended;
  $('pause').disabled = !lab.ready || !s.running;
  $('seed').disabled = s.running; $('penalty').disabled = s.running;
  if (previousBestAt >= 0 && previousBestAt !== s.bestAt && lab.test) {
    clearResults('检查点已更新，请重新运行独立测试。');
  }
  previousBestAt = s.bestAt;
  $('network-result-label').textContent = s.bestAt ? '最佳策略平均' : '未训练网络平均';
  $('play-label').textContent = currentMode==='random' ? '随机动作' : s.bestAt ? '最佳策略' : '未训练网络';
  drawChart(s.curve || []);
}
function drawWorld(frame) {
  const canvas = $('world'), ctx = canvas.getContext('2d'), w=canvas.width,h=canvas.height;
  ctx.clearRect(0,0,w,h);
  const gradient=ctx.createLinearGradient(0,0,0,h); gradient.addColorStop(0,'#111f2c'); gradient.addColorStop(1,'#0a121c');
  ctx.fillStyle=gradient; ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='rgba(134,177,186,.08)'; ctx.lineWidth=1;
  for(let x=30;x<w;x+=45){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}
  for(let y=30;y<h;y+=45){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke()}
  const y=286, x=450 + frame.state[0]*135, theta=frame.state[2], px=x+Math.sin(theta)*160, py=y-13-Math.cos(theta)*160;
  ctx.strokeStyle='#38505d';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(85,y+22);ctx.lineTo(815,y+22);ctx.stroke();
  for(const dx of [-2.4,0,2.4]){const xx=450+dx*135;ctx.strokeStyle=dx===0?'#59757e':'#a06b60';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(xx,y+15);ctx.lineTo(xx,y+29);ctx.stroke();ctx.fillStyle='#7c929d';ctx.font='14px sans-serif';ctx.textAlign='center';ctx.fillText(dx+' m',xx,y+49)}
  ctx.save();ctx.shadowColor='rgba(88,224,182,.45)';ctx.shadowBlur=15;ctx.strokeStyle='#7decc8';ctx.lineWidth=13;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x,y-13);ctx.lineTo(px,py);ctx.stroke();ctx.restore();
  ctx.fillStyle='#ebfff8';ctx.beginPath();ctx.arc(px,py,9,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#4f7d83';ctx.beginPath();ctx.roundRect(x-38,y-26,76,35,7);ctx.fill();ctx.strokeStyle='#a6ded3';ctx.lineWidth=2;ctx.stroke();
  for(const q of [-24,24]){ctx.fillStyle='#b4cfd0';ctx.beginPath();ctx.arc(x+q,y+13,7,0,Math.PI*2);ctx.fill()}
  ctx.fillStyle='#ffbd7e';ctx.font='bold 29px sans-serif';ctx.textAlign='center';ctx.fillText(frame.action ? '→' : '←', x, y+3);
  $('pos').textContent = frame.state[0].toFixed(2);
  $('velocity').textContent = frame.state[1].toFixed(2);
  $('angle').textContent = (frame.state[2]*180/Math.PI).toFixed(1);
  $('angular-velocity').textContent = (frame.state[3]*180/Math.PI).toFixed(1);
  $('action').textContent = frame.action ? '右推' : '左推';
  $('frame-step').textContent = frame.frameStep;
  $('frame-result').hidden = !frame.failed && !frame.truncated;
  $('frame-result').textContent = frame.failed ? '倾角超限 / 出界 · 即将重试' : frame.truncated ? '达到 500 步 · 本回合结束' : '';
}
function drawChart(curve) {
  const canvas=$('chart'),ctx=canvas.getContext('2d'), w=canvas.width,h=canvas.height;
  ctx.clearRect(0,0,w,h);const left=55,right=w-20,top=15,bottom=h-28;
  ctx.font='15px sans-serif';ctx.textAlign='right';
  for(let value=0;value<=500;value+=100){let y=bottom-(bottom-top)*value/500;ctx.strokeStyle='#263847';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillStyle='#7d94a4';ctx.fillText(String(value),left-10,y+5)}
  if(!curve.length)return;
  ctx.strokeStyle='#58e0b6';ctx.lineWidth=3;ctx.beginPath();
  curve.forEach((point,i)=>{const x=left+(right-left)*point.steps/50000,y=bottom-(bottom-top)*point.score/500;if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y)});ctx.stroke();
  curve.forEach(point=>{const x=left+(right-left)*point.steps/50000,y=bottom-(bottom-top)*point.score/500;ctx.fillStyle='#aaffdf';ctx.beginPath();ctx.arc(x,y,4,0,2*Math.PI);ctx.fill()});
}
function init() {
  if (location.protocol === 'file:') {
    $('load-status').className='notice error';
    $('load-status').textContent='这个训练实验需要通过网站或本地 HTTP 服务打开；直接双击 HTML 无法加载浏览器模块。请返回课程入口启动。';
    lab.error='file protocol is unsupported'; return;
  }
  try {
    worker = new Worker(new URL('./worker.mjs', import.meta.url), {type:'module'});
    worker.onerror = event => {
      lab.error=event.message; $('load-status').className='notice error';
      $('load-status').textContent='训练引擎加载失败：'+event.message+'。请刷新后重试，或检查 WASM 文件是否随网站一起发布。';
    };
    worker.onmessage = ({data:m}) => {
      if(m.type==='ready'){setReady();if(lab.status)refreshStatus(lab.status)}
      else if(m.type==='status'){refreshStatus(m)}
      else if(m.type==='frame'){drawWorld(m)}
      else if(m.type==='reset'){
        previousBestAt=-1;currentMode='random';clearResults();$('force').value=10;$('force-value').textContent='10';$('seed').value=m.seed;
        $('penalty-label').textContent=m.penalty===0?'0 分':'−5 分';
        $('random-mode').classList.add('active');$('trained-mode').classList.remove('active');$('play-label').textContent='随机动作';
      } else if(m.type==='testResult'){
        lab.test=m;$('random-result').textContent=m.random.mean.toFixed(1);$('trained-result').textContent=m.trained.mean.toFixed(1);
        $('test-note').textContent=`测试推力 ${m.force} N；最佳策略来自 ${m.bestAt.toLocaleString()} 次决策的检查点。20 回合成绩范围：${m.trained.min}–${m.trained.max} 步。仅为模拟结果。`;
      } else if(m.type==='exportResult'){
        const blob=new Blob([JSON.stringify(m.payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
        a.href=url;a.download='mujoco-cartpole-dqn-experiment.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      } else if(m.type==='error'){
        lab.error=m.message;$('load-status').className='notice error';$('load-status').textContent='训练出错：'+m.message;for(const id of elements)$(id).disabled=true;
      }
    };
    worker.postMessage({type:'init',seed:Number($('seed').value),penalty:Number($('penalty').value)});
  } catch(error) {$('load-status').className='notice error';$('load-status').textContent='浏览器无法启动训练：'+error;lab.error=String(error)}
}
$('start').onclick=()=>worker.postMessage({type:'start'});
$('pause').onclick=()=>worker.postMessage({type:'pause'});
$('reset').onclick=()=>worker.postMessage({type:'reset',seed:Number($('seed').value),penalty:Number($('penalty').value)});
for(const [id,mode] of [['random-mode','random'],['trained-mode','trained']]){
  $(id).onclick=()=>{currentMode=mode;worker.postMessage({type:'mode',mode});$('random-mode').classList.toggle('active',mode==='random');$('trained-mode').classList.toggle('active',mode==='trained');$('play-label').textContent=mode==='random'?'随机动作':lab.status?.bestAt?'最佳策略':'未训练网络'};
}
$('force').oninput=e=>{$('force-value').textContent=e.target.value;worker.postMessage({type:'force',force:Number(e.target.value)});clearResults('推力已改变，请重新运行独立测试。')};
$('test').onclick=()=>{$('test-note').textContent='正在运行 20 回合独立测试…';worker.postMessage({type:'test'})};
$('export').onclick=()=>worker.postMessage({type:'export'});
drawChart([]);init();
