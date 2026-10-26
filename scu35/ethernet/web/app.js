'use strict';
const $=id=>document.getElementById(id);
let status=null,token='',busy=false,lastCount=-1;
const fmt=(n,d=1)=>Number(n||0).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
const hex=value=>(value||'').match(/.{1,2}/g)?.join(' ')||'—';
async function control(data){
 if(!token)return;
 try{
  const response=await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Token':token},body:JSON.stringify(data)});
  if(!response.ok)throw Error(await response.text());
  $('action-message').textContent='Applied to the next operation';await poll();
 }catch(error){$('action-message').textContent=error.message;}
}
document.querySelectorAll('[data-op]').forEach(button=>button.onclick=()=>control({op:Number(button.dataset.op)}));
document.querySelectorAll('[data-pq-case]').forEach(button=>button.onclick=()=>control({pq_case:button.dataset.pqCase}));
$('pace').onchange=event=>control({pace:event.target.value});
$('size').onchange=event=>control({size:Number(event.target.value)});
$('pause').onclick=()=>control({running:!status?.config.running});
$('checks').onclick=()=>control({check:true});
$('restore').onclick=()=>{if(confirm('Stop traffic and restore the configured recovery image?'))control({restore:true});};
$('fullscreen').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();

const descriptions={
 host:'Python prepares actual payloads, signatures and public keys. It independently verifies every reply and LMS/HSS decision.',
 hostcrypto:'Host cryptography uses AES-GCM for transport and hashlib/Python LMS/HSS as a comparison. It does not replace device verification.',
 nic:'The host NIC sends real UDP frames over the direct Ethernet cable. JTAG carries no payload traffic.',
 phy:'The external TI PHY converts the board RJ45 link to 100 Mb/s MII. It is on the board, outside the FPGA.',
 mac:'AMD AXI Ethernet Lite receives/transmits frames through its ping-pong packet RAM. It has no AXI-Stream DMA interface.',
 cpu:'MicroBlaze V parses packets, copies data, calls XilSecure, and performs the LMS/HSS signature/tree control software.',
 bram:'128 KiB local BRAM contains MicroBlaze V code, stack and networking buffers. PMC DMA cannot directly read this local address space.',
 axi:'SmartConnect provides the memory-mapped AXI path between the soft processor and peripheral registers.',
 timer:'AXI Timer measures the on-device operation interval at nominal 100 MHz. Upload and host RTT are separate measurements.',
 bridge:'PMC Bridge exposes PMC register and RAM windows to the PL MicroBlaze V AXI master.',
 ram:'PMC shared RAM stores DMA-accessible input/output, SHA state and the uploaded 4608-byte aligned signature/message/key workspace.',
 dma:'The hardened PMC DMA moves bytes between shared RAM and cryptographic streams. This is not an Ethernet AXI DMA core.',
 sss:'Secure Stream Switch connects PMC DMA to AES or SHA. Software selects these routes through the AMD drivers.',
 aes:'Hardened AES-GCM authenticates/decrypts encrypted requests and encrypts/authenticates replies using a public diagnostic key.',
 sha:'Hardened SHA3/SHAKE hashes payloads. LMS/HSS verification repeatedly invokes SHAKE while MicroBlaze V handles signature/tree logic.',
 plm:'PLM and configuration blocks participate in loading the device. They are not executing the runtime LMS/HSS verification loop.',
 trng:'TRNG is used during initialization to create a response nonce prefix. It is not invoked for every displayed operation.',
 puf:'PUF is not used by this Ethernet firmware. PUF registration and key regeneration are separate notebook demonstrations.',
 efuse:'eFUSE storage is not used for this runtime public-key/AES demo. No fuse programming or provisioning is performed.',
 debug:'UART reports initialization; MDM supports JTAG debug. Neither carries the measured Ethernet payload stream.',
 clock:'Clocking Wizard and Processor System Reset provide the fabric clock and reset. These support every runtime operation.'
};
document.querySelectorAll('[data-block]').forEach(block=>{
 const explain=()=>{$('block-explainer').textContent=descriptions[block.dataset.block];};
 block.onclick=explain;block.onkeydown=event=>{if(event.key==='Enter'||event.key===' ')explain();};
});
['dma','sss','aes','sha'].forEach(name=>$('block-'+name).classList.add('engine'));

function path(s){
 const op=s.config.op,pq=op>=7;
 document.querySelector('.system-panel').classList.toggle('running',s.phase==='live'&&s.config.running);
 let blocks=['host','nic','phy','mac','cpu','bram','axi','timer','clock'];
 let edges=['wire','mii','macbus','cpuaxi','cpuram','timerbus'];
 if(op!==3){blocks.push('hostcrypto','bridge','ram','dma','sss','aes');edges.push('hostsoftware','hostnetwork','bridgebus','bridgepmc','ramdma','dmasss','sssaes');}
 if(op>=5){blocks.push('sha');edges.push('ssssha','digestread');}
 document.querySelectorAll('.block').forEach(node=>node.classList.toggle('active',blocks.includes(node.dataset.block)));
 document.querySelectorAll('.route').forEach(node=>node.classList.toggle('active',edges.includes(node.id.replace('edge-',''))));
 $('path-mode').textContent=s.modes[op];
 const steps=op===3?['Host sends plaintext UDP','PHY + Ethernet Lite receive','MicroBlaze copies the payload','Crypto engines bypassed','Host checks the echoed bytes']:
 pq?['Host sends five AES-GCM chunks','CPU stages signature, message + key','MicroBlaze runs AMD LMS/HSS control','PMC DMA + SHAKE compute hashes','AES-GCM reply; Python checks decision']:
 op>=5?['Host sends actual payload','Ethernet Lite → CPU → shared RAM','PMC DMA routes data to SHA3 / SHAKE','AES-GCM protects the digest reply','Host decrypts + compares exact digest']:
 op===2?['Host AES-GCM encrypts request','Device authenticates + checks replay','PMC AES decrypts payload','PMC AES encrypts authenticated echo','Host verifies tag + exact plaintext']:
 ['Host sends actual plaintext','Ethernet Lite → CPU → shared RAM','PMC DMA feeds hardened AES-GCM','Device returns ciphertext + tag','Host authenticates + recovers input'];
 $('method-steps').replaceChildren(...steps.map(text=>{const item=document.createElement('li');item.textContent=text;return item;}));
 $('path-detail').textContent=pq?'Live runtime verification: signature and public key originate on the host; public verification material is uploaded once per method/case, then reused for repeated device API measurements. The AES transport key is public diagnostic data.':
 'Highlights identify the selected operation path. Clock/reset supports all methods; PLM, JTAG/UART, TRNG, PUF and eFUSE are not in the repeated payload loop.';
 if(s.count!==lastCount){
  lastCount=s.count;document.querySelector('.system-panel').classList.add('fresh');
  setTimeout(()=>document.querySelector('.system-panel').classList.remove('fresh'),350);
 }
 $('diagram-pulse').textContent=s.latest?'Verified reply #'+s.count.toLocaleString()+' · '+new Date(s.last_received*1000).toLocaleTimeString():'Waiting for a verified response';
}

function pqProgress(rows){
 const points=rows.filter(row=>row.pq_completed!==null&&row.pq_completed!==undefined);
 if(!points.length){$('pq-progress-chart').innerHTML='<text x="30" y="60">Waiting for live verification checkpoints…</text>';return;}
 const W=780,H=285,L=60,R=20,T=25,B=45;
 const xmax=Math.max(1,...points.map(p=>p.pq_device_work_us/1000),...points.map(p=>p.pq_python_work_us/1000))*1.08;
 const ymax=Math.max(1,...points.map(p=>p.pq_completed))*1.1;
 const X=x=>L+x/xmax*(W-L-R),Y=y=>H-B-y/ymax*(H-T-B);
 let svg='<title>Live completed verifications versus cumulative measured API work</title>';
 for(let i=0;i<=4;i++){
  const y=ymax*i/4,x=xmax*i/4;
  svg+=`<path d="M${L} ${Y(y)}H${W-R}" stroke="#2b3b49"/><text x="${L-8}" y="${Y(y)+4}" text-anchor="end">${Math.round(y)}</text><text x="${X(x)}" y="${H-B+20}" text-anchor="middle">${x.toFixed(0)}</text>`;
 }
 for(const [key,color,label]of[['pq_device_work_us','#51dbed','SCU35'],['pq_python_work_us','#c5ef7b','Python']]){
  svg+=`<polyline points="${points.map(p=>`${X(p[key]/1000)},${Y(p.pq_completed)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="2.5"/>`;
  for(const p of points)svg+=`<circle cx="${X(p[key]/1000)}" cy="${Y(p.pq_completed)}" r="3" fill="${color}"><title>${label}: ${p.pq_completed} completed, ${(p[key]/1000).toFixed(2)} ms measured work</title></circle>`;
 }
 svg+='<text x="60" y="15">Completed verifications · cyan SCU35 / green Python</text><text x="390" y="280" text-anchor="middle">Cumulative measured verification work (ms); transport and gaps excluded</text>';
 $('pq-progress-chart').innerHTML=svg;
}

function render(s){
 status=s;token=s.token;
 const paused=!s.config.running,live=s.phase==='live'&&(s.age_s<3||paused),pq=s.config.op>=7;
 $('connection').textContent=live?(paused?'CONNECTED / PAUSED':'LIVE HARDWARE'):s.phase.toUpperCase();
 $('connection').className='pill'+(live?' live':'');$('live-dot').className='dot'+(live?' live':'');
 $('phase').textContent=live?(paused?'TRAFFIC PAUSED':'STREAM VERIFIED'):s.phase.toUpperCase();
 $('freshness').textContent=s.latest?`Last response ${s.age_s.toFixed(1)}s ago`:'Awaiting device';
 $('clock').textContent=new Date().toLocaleTimeString();
 $('rtt').textContent=s.latest?fmt(s.median_us):'—';$('p95').textContent=fmt(s.p95_us);
 $('device').textContent=s.latest?fmt(s.latest.device_us):'—';$('rate').textContent=fmt(s.payload_Bps*8/1e6,2);
 $('count').textContent=fmt(s.count,0);$('total').textContent=fmt(s.bytes/1e6,2);
 $('errors').textContent=s.errors?`${s.errors} session error(s)`:'No failed payload / decision comparisons';
 $('load').style.width=Math.min(100,s.payload_Bps/12500000*100)+'%';
 $('pause').textContent=paused?'Resume traffic':'Pause traffic';$('size').value=s.config.size;$('size').disabled=pq||!live;
 $('pace').value=s.config.pace;$('traffic-label').textContent=pq?'· 56-byte signed message; upload separate':s.config.pace==='throughput'?'· single flight / 64-packet batches':'· paced presentation traffic';
 document.querySelectorAll('[data-op]').forEach(button=>{button.classList.toggle('selected',Number(button.dataset.op)===s.config.op);button.disabled=!live||(Number(button.dataset.op)>=7&&!s.capabilities?.lms_hss);});
 document.body.classList.toggle('pq-view',pq);$('post-quantum').hidden=!pq;
 $('recovery').textContent=s.recovery;
 const checks=s.checks;$('valid').textContent=checks.valid_roundtrip||'WAITING';$('tamper').textContent=checks.modified_tag||'WAITING';$('replay').textContent=checks.replayed_packet||'WAITING';$('checktime').textContent=checks.time?'CHECKED '+checks.time:'SESSION EVENTS';
 if(s.latest){const p=s.latest;$('plain').textContent=hex(p.plain_hex);$('cipher').textContent=hex(p.wire_hex.slice(0,p.output_bytes*2));$('result').textContent=hex(p.result_hex);$('seq').textContent=p.sequence.toLocaleString();$('nonce').textContent=p.nonce_hex||'Plain echo';$('verified').textContent=p.op>=7?'VERIFIED SIGNATURE DECISION':p.op===3?'PAYLOAD MATCH':'VERIFIED TAG + RESULT';}
 $('events').replaceChildren(...s.events.map(event=>{const row=document.createElement('div');row.className='event';const time=document.createElement('time');time.textContent=event.time;const text=document.createElement('span');text.textContent=event.message;row.append(time,text);return row;}));
 $('restore').disabled=['restored','restoring','recovery failed'].includes(s.phase);
 $('pause').disabled=!live;$('checks').disabled=!live;
 path(s);chart(s.history);
 document.querySelectorAll('[data-pq-case]').forEach(button=>button.classList.toggle('selected',button.dataset.pqCase===s.config.pq_case));
 if(pq){
  const row=s.pq,method=s.config.op===7?'LMS-SHAKE256':'HSS-SHAKE256';
  if(row&&row.algorithm===method&&row.case===s.config.pq_case){
   $('pq-decision').textContent=row.accepted?'ACCEPT':'REJECT';$('pq-decision').className=row.accepted?'':'rejected';
   $('pq-time').textContent=fmt(row.device_verify_us);$('pq-python').textContent=fmt(row.python_verify_us);
   $('pq-description').textContent=`Live ${row.algorithm} / ${row.case}: ${row.message_bytes}-byte message, ${row.signature_bytes}-byte signature, ${row.public_key_bytes}-byte public key. Device result matches Python.`;
   $('pq-upload').textContent=`Uploaded ${row.upload.bytes} bytes in ${row.upload.packets} authenticated chunks (${row.upload.wall_ms.toFixed(2)} ms). Verify-request RTT ${row.rtt_us.toFixed(1)} us. Vendor status 0x${row.vendor_status.toString(16)}. Signature upload is reused until method/case changes.`;
   pqProgress(s.history);
   const totals=s.pq_totals;
   if(totals)$('pq-progress-totals').textContent=`${totals.count} completed · SCU35 ${(totals.device_work_us/1000).toFixed(2)} ms API work · Python ${(totals.python_work_us/1000).toFixed(2)} ms reference work. Dots are sampled completion checkpoints, not within-call progress.`;
  }else{$('pq-decision').textContent='UPLOADING';$('pq-time').textContent='—';$('pq-python').textContent='—';}
 }
}
async function poll(){if(busy)return;busy=true;try{const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw Error('Status unavailable');render(await response.json());}catch(error){$('connection').textContent='SERVER OFFLINE';$('phase').textContent=error.message;}finally{busy=false;}}
window.addEventListener('resize',()=>status&&render(status));
poll();setInterval(poll,600);

function chart(rows){const canvas=$('chart'),rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);const w=rect.width,h=rect.height,l=48,r=12,t=10,b=22;let max=Math.max(100,...rows.map(x=>Math.max(x.rtt_us,x.device_us)))*1.15;for(let i=0;i<4;i++){const y=t+(h-t-b)*i/3;c.strokeStyle='#263545';c.lineWidth=1;c.beginPath();c.moveTo(l,y);c.lineTo(w-r,y);c.stroke();c.fillStyle='#8da2b5';c.font='10px Consolas, monospace';c.fillText(Math.round(max*(1-i/3)).toLocaleString(),0,y+3);}if(rows.length<2){c.fillText('Waiting for live samples…',l+25,h/2);return;}for(const [key,color]of[['rtt_us','#51dbed'],['device_us','#c5ef7b']]){c.beginPath();rows.forEach((v,i)=>{const x=l+(w-l-r)*i/Math.max(rows.length-1,1),y=t+(h-t-b)*(1-v[key]/max);i?c.lineTo(x,y):c.moveTo(x,y);});c.strokeStyle=color;c.lineWidth=2;c.stroke();}c.fillStyle='#8da2b5';c.fillText(new Date(rows[0].time*1000).toLocaleTimeString(),l,h-2);c.fillText('NOW',w-35,h-2);const values=rows.slice(-30).map(x=>x.rtt_us),hi=Math.max(...values,1),lo=Math.min(...values);$('spark').setAttribute('d',values.map((v,i)=>`${i?'L':'M'}${i*200/Math.max(values.length-1,1)} ${32-(v-lo)/Math.max(hi-lo,1)*28}`).join(''));}
