import{heading,empty,notice}from'../components/common.js';import{esc,localTime}from'../utils/format.js';import{api,store}from'../utils/api.js';import{MODEL_STATES}from'../constants.js';
const vb=st=>`<span class="badge ${st==='active'?'':'mid'}">${MODEL_STATES[st]||esc(st)}</span>`;
const ids=a=>a.length>14?a.slice(0,14).join('、')+` …共${a.length}条`:a.join('、');
const cur=()=>store.versions.find(v=>v.state==='active');
function card(v,isAdmin){
  let m=v.metrics,sp=v.samples;
  return `<article class="sheet"><div style="display:flex;justify-content:space-between"><h3>${esc(v.name)}　<small class="muted">${esc(v.algorithm)}</small></h3>${vb(v.state)}</div>
  <p class="muted">训练 ${esc(v.trained_by)} · ${localTime(v.trained_at)}　/　留出 ROC AUC <b>${m.roc_auc}</b> · 准确率 <b>${m.accuracy}</b>　/　训练 ${m.training_rows} 条（${sp.train_machines.length} 台机具）· 留出 ${m.holdout_rows} 条（${sp.holdout_machines.length} 台机具）</p>
  <p class="muted">类别分布：训练 争议 ${m.train_disputed} / 无争议 ${m.train_clear} · 留出 争议 ${m.holdout_disputed} / 无争议 ${m.holdout_clear}　/　种子 ${m.seed} · 高风险阈值 ${m.high_risk_threshold}</p>
  ${v.reviewed_by?`<p class="muted">审阅 ${esc(v.reviewed_by)} · ${localTime(v.reviewed_at)}　「${esc(v.review_note)}」</p>`:''}
  ${v.activated_by?`<p class="muted">最近启用 ${esc(v.activated_by)} · ${localTime(v.activated_at)}</p>`:''}
  <details><summary class="muted">样本、编码器与评估依据</summary><p class="code">训练机具：${esc(sp.train_machines.join('、'))}<br>留出机具：${esc(sp.holdout_machines.join('、'))}<br>训练样本：${esc(ids(sp.train_samples))}<br>留出样本：${esc(ids(sp.holdout_samples))}<br>机型编码：${esc(v.encoder['机型'].join('、'))}<br>部位编码：${esc(v.encoder['故障部位'].join('、'))}<br>划分：${esc(m.split)} · 随机种子 ${m.seed}</p></details>
  ${actions(v,isAdmin)}</article>`}
function actions(v,isAdmin){
  if(!isAdmin)return '';
  if(v.state==='candidate')return `<div class="actions"><input id="note-${v.id}" placeholder="审阅意见（至少 4 字）" style="max-width:320px"><button data-review="${v.id}">审阅通过</button></div>`;
  if(v.state==='reviewed'&&!v.activated_at)return `<div class="actions"><button data-activate="${v.id}">启用此版本</button></div>`;
  if(v.state==='reviewed'&&v.activated_at)return `<div class="actions"><button class="ghost" data-rollback="${v.id}">回退到此版本</button></div>`;
  return ''}
export function render(s,u){
  let c=cur(),canTrain=['admin','assessor'].includes(u.role),isAdmin=u.role==='admin';
  return heading('04 / MODEL VERSIONS','候选模型先审后用','按机具隔离训练集与留出集，固化样本、编码器与评估依据；主管审阅后启用，可回退，切换基于当前版本且失败保留旧版。')+`<div class="split"><section>
  <div class="plate"><h2>训练候选版本</h2><p class="muted">以当前已结案历史索赔训练候选版本；同一机具的索赔不会同时进入训练集与留出集。历史不足 40 条、涉及机具不足 2 台或争议类别单一时，将说明原因并保留在用版本。</p><div class="actions"><button id="train" ${canTrain?'':'disabled'}>训练候选版本</button></div></div>
  <div class="plate"><h2>版本档案</h2>${s.versions.length?s.versions.map(v=>card(v,isAdmin)).join(''):empty('尚无模型版本，请先训练候选版本。')}</div></section>
  <aside class="rail"><h2>当前在用版本</h2>${c?`<div class="plate ochre"><span class="muted">${esc(c.name)} · 留出集 ROC AUC</span><div class="metric">${c.metrics.roc_auc}</div><p>准确率 ${c.metrics.accuracy}<br>训练 ${c.metrics.training_rows} 条 / 留出 ${c.metrics.holdout_rows} 条<br>启用 ${esc(c.activated_by||'—')}<br>${c.activated_at?localTime(c.activated_at):''}</p></div>`:'<p class="muted">尚未启用任何版本。候选经主管审阅后可启用；启用前索赔无法送分流。</p>'}
  <p class="legend">索赔受理分流时绑定当时在用版本；排队期间启用或回退不影响在途索赔，概率与依据随索赔存档可追溯。已结案旧索赔不重新改算。<br><br>启用 / 回退需基于页面当前在用版本提交；他人已抢先切换时本次操作将被拒绝，请刷新后重试。</p></aside></div>`}
export function bind(refresh){
  let t=document.querySelector('#train');if(t)t.onclick=()=>refresh(()=>api('/model-versions/train','POST',{}),'候选版本训练完成，待主管审阅');
  document.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>{let note=document.querySelector('#note-'+b.dataset.review).value.trim();if(note.length<4){notice('请填写至少 4 字审阅意见');return}refresh(()=>api('/model-versions/'+b.dataset.review+'/review','POST',{note}),'版本已审阅通过，可启用')});
  document.querySelectorAll('[data-activate]').forEach(b=>b.onclick=()=>refresh(()=>api('/model-versions/'+b.dataset.activate+'/activate','POST',{expected_current_id:cur()?.id??null}),'版本已启用，新受理分流将绑定该版本'));
  document.querySelectorAll('[data-rollback]').forEach(b=>b.onclick=()=>refresh(()=>api('/model-versions/'+b.dataset.rollback+'/rollback','POST',{expected_current_id:cur()?.id??null}),'已回退到所选版本，在用版同步切换'));
}