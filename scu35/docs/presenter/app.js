'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const chapters=$$('.chapter'), tabs=$$('.chapter-tab');
const safeStore={get(k){try{return localStorage.getItem(k)}catch{return null}},set(k,v){try{localStorage.setItem(k,v)}catch{}}};
let active=0;
function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');clearTimeout(toast.timeout);toast.timeout=setTimeout(()=>el.classList.remove('show'),2300)}
function navigate(value,options={}){
 if(value==='ipi')value='platform'; // Preserve old chapter bookmarks after consolidation.
 const idx=typeof value==='string'?chapters.findIndex(c=>c.id===value):value;
 if(idx<0||idx>=chapters.length)return;
 active=idx;
 chapters.forEach((c,i)=>{c.classList.toggle('active',i===idx);c.setAttribute('aria-hidden',String(i!==idx&&!document.body.classList.contains('all-chapters')))});
 tabs.forEach((t,i)=>{t.setAttribute('aria-selected',String(i===idx));t.tabIndex=i===idx?0:-1});
 $('#chapter-position').textContent=`${String(idx+1).padStart(2,'0')} / ${chapters.length}`;
 $('#chapter-progress').style.width=`${(idx+1)/chapters.length*100}%`;
 document.title=`${chapters[idx].dataset.title} · SCU35 presenter`;
 safeStore.set('scu35:chapter',chapters[idx].id);
 if(!options.noHash)history.replaceState(null,'','#'+chapters[idx].id);
 if(!options.noScroll)window.scrollTo({top:0,behavior:'instant'});
}
tabs.forEach((t,i)=>t.addEventListener('click',()=>navigate(i)));
$$('[data-chapter]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.chapter)));
$$('[data-next]').forEach(b=>b.addEventListener('click',()=>navigate(active+1)));
$$('[data-prev]').forEach(b=>b.addEventListener('click',()=>navigate(active-1)));
$('#chapter-search').addEventListener('input',e=>{
 const term=e.target.value.toLowerCase().trim();let count=0;
 tabs.forEach((t,i)=>{const match=!term||chapters[i].textContent.toLowerCase().includes(term);t.classList.toggle('search-hidden',!match);if(match)count++});
 $('#no-match').hidden=count!==0;
});
$('#chapter-search').addEventListener('keydown',e=>{if(e.key==='Enter'){const t=tabs.find(t=>!t.classList.contains('search-hidden'));if(t){t.click();t.focus()}}if(e.key==='Escape'){e.target.value='';e.target.dispatchEvent(new Event('input'));e.target.blur()}});
$('#audience-toggle').addEventListener('click',()=>{const on=document.body.classList.toggle('audience');$('#audience-toggle').setAttribute('aria-pressed',String(on));$('#audience-toggle').textContent=on?'Presenter view':'Audience view';safeStore.set('scu35:audience',String(on))});
$('#notes-toggle').addEventListener('click',()=>{const all=$$('details.speaker');const open=!all.every(d=>d.open);all.forEach(d=>d.open=open);$('#notes-toggle').setAttribute('aria-pressed',String(open))});
$('#font-up').addEventListener('click',()=>{const n=Math.min(25,parseFloat(getComputedStyle(document.body).fontSize)+1);document.documentElement.style.setProperty('--font',n+'px')});
$('#font-down').addEventListener('click',()=>{const n=Math.max(15,parseFloat(getComputedStyle(document.body).fontSize)-1);document.documentElement.style.setProperty('--font',n+'px')});
$('#fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch{toast('Use your browser’s fullscreen shortcut')}});
let printStates=[];
window.addEventListener('beforeprint',()=>{printStates=$$('details').map(el=>[el,el.open]);printStates.forEach(([el])=>el.open=true)});
window.addEventListener('afterprint',()=>printStates.forEach(([el,open])=>el.open=open));
$('#print-all').addEventListener('click',()=>window.print());
$$('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{
 const text=document.getElementById(button.dataset.copy).textContent;
 try{await navigator.clipboard.writeText(text)}catch{
  const area=document.createElement('textarea');area.value=text;area.style.cssText='position:fixed;left:-9999px';document.body.append(area);area.select();const ok=document.execCommand('copy');area.remove();if(!ok){toast('Select and copy the command manually');return}
 }
 const old=button.textContent;button.textContent='Copied';setTimeout(()=>button.textContent=old,1600);toast('Copied to clipboard. No command was executed.');
}));
$$('.editable-notes').forEach(el=>{const key='scu35:notes:'+el.dataset.notes;el.value=safeStore.get(key)||'';el.addEventListener('input',()=>safeStore.set(key,el.value))});
$$('.checklist input').forEach((el,i)=>{el.checked=safeStore.get('scu35:check:'+i)==='true';el.addEventListener('change',()=>{safeStore.set('scu35:check:'+i,String(el.checked));updateChecks()})});
function updateChecks(){const els=$$('.checklist input');$('#check-count').textContent=`${els.filter(e=>e.checked).length} / ${els.length} checked locally`}
updateChecks();
let elapsed=0,running=false,lastTime=0;
function timerRender(){const total=Math.floor(elapsed/1000);$('#timer').textContent=String(Math.floor(total/60)).padStart(2,'0')+':'+String(total%60).padStart(2,'0')}
$('#timer-toggle').addEventListener('click',()=>{running=!running;lastTime=performance.now();$('#timer-toggle').textContent=running?'Pause':'Start';$('#timer-toggle').setAttribute('aria-pressed',String(running))});
$('#timer-reset').addEventListener('click',()=>{elapsed=0;timerRender()});
setInterval(()=>{const now=performance.now();if(running)elapsed+=now-lastTime;lastTime=now;timerRender()},250);
$$('[data-arch]').forEach(el=>{
 const show=()=>{$('#arch-explanation').innerHTML=`<strong>${el.dataset.label}</strong><p>${el.dataset.arch}</p>`;$$('[data-arch]').forEach(e=>e.setAttribute('aria-pressed',String(e===el)))};
 el.addEventListener('click',show);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}});
});
$$('[data-puf-step]').forEach(el=>el.addEventListener('click',()=>{
 const n=Number(el.dataset.pufStep);$$('[data-puf-step]').forEach(e=>e.classList.toggle('selected',e===el));
 const data=window.PRESENTER.pufSteps[n];$('#puf-detail').innerHTML=`<h3>${data.title}</h3><p>${data.text}</p><pre class="hash-output">${data.output}</pre><p class="small">Recorded excerpt, not a live hardware action.</p>`;
}));
$$('[data-boot-variant]').forEach(el=>el.addEventListener('click',()=>{
 const data=window.PRESENTER.boot[el.dataset.bootVariant];$$('[data-boot-variant]').forEach(e=>e.classList.toggle('selected',e===el));
 $('#boot-variant-title').textContent=data.title;$('#boot-variant-detail').textContent=data.explanation;
 $('#boot-command').textContent=data.command;$('#boot-output').textContent=data.output;
 $('#boot-source').textContent=data.source;$('#boot-source').href=data.link;
}));
$$('[data-payload-tab]').forEach(el=>el.addEventListener('click',()=>{
 const name=el.dataset.payloadTab;
 $$('[data-payload-tab]').forEach(t=>t.setAttribute('aria-selected',String(t===el)));
 $$('.payload-pane').forEach(p=>p.hidden=p.dataset.payloadPane!==name);
}));
function payloadRender(){
 const size=$('#payload-size').value,algo=$('#payload-algo').value;
 const v=window.PRESENTER.payloads[size];
 $('#payload-digest').textContent=v[algo];
 $('#payload-prefix').textContent=v.prefix;
 $('#payload-caption').textContent=`${size} message bytes → 32 digest bytes. Exact hardware output from the recorded PL application capture.`;
}
$('#payload-size').addEventListener('change',payloadRender);$('#payload-algo').addEventListener('change',payloadRender);payloadRender();
let zoomTrigger=null;
$$('img[data-zoom]').forEach(el=>el.addEventListener('click',()=>{zoomTrigger=el;$('#zoom-image').src=el.src;$('#zoom-image').alt=el.alt;$('#zoom-caption').textContent=el.dataset.caption||el.alt;$('#zoom-dialog').showModal()}));
$$('img[data-zoom]').forEach(el=>el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el.click()}}));
$('#zoom-close').addEventListener('click',()=>$('#zoom-dialog').close());
$('#zoom-dialog').addEventListener('click',e=>{if(e.target===$('#zoom-dialog'))$('#zoom-dialog').close()});
$('#zoom-dialog').addEventListener('close',()=>zoomTrigger?.focus());
document.addEventListener('keydown',e=>{
 const typing=e.target.matches('input,textarea,select,[contenteditable]');if(typing||e.ctrlKey||e.metaKey||e.altKey||$('#zoom-dialog').open)return;
 if(e.key==='ArrowRight'||e.key==='PageDown'){e.preventDefault();navigate(active+1);if(e.target.classList.contains('chapter-tab'))tabs[active].focus()}
 if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();navigate(active-1);if(e.target.classList.contains('chapter-tab'))tabs[active].focus()}
 if(e.key.toLowerCase()==='a')$('#audience-toggle').click();
 if(e.key.toLowerCase()==='n')$('#notes-toggle').click();
 if(e.key.toLowerCase()==='f')$('#fullscreen').click();
 if(e.key==='/'){e.preventDefault();$('#chapter-search').focus()}
});
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1),{noHash:true}));
const first=location.hash.slice(1)||safeStore.get('scu35:chapter')||chapters[0].id;
navigate(chapters.some(c=>c.id===first)?first:0,{noScroll:true});
if(safeStore.get('scu35:audience')==='true')$('#audience-toggle').click();
window.presenter={navigate,get active(){return active},chapterCount:chapters.length};
