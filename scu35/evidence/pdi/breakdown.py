"""Cross-check AMD Bootgen dumps and summarize a normal SCU35 PDI."""
from pathlib import Path
from collections import Counter
import hashlib,html,json,struct
HERE=Path(__file__).resolve().parent
source=HERE.parent/'compare/compare.pdi'
p=(HERE/'normal.pdi').read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert p==source.read_bytes(),'Inspection input differs from original PDI'
offset,_,cdo_size,cdo_encoded,plm_size,plm_encoded=struct.unpack_from('<6I',p,0x1c)
def decode(at,length,total,root):
 output=bytearray();start=at;chunks=0
 while length:
  count=min(0x1fe0,length);encoded=count+(32 if length>count else 0)
  data=p[at:at+encoded]
  assert len(data)==encoded and hashlib.sha3_256(data).digest()==root,'Partition hash mismatch'
  output.extend(data[:count]);chunks+=1
  if length>count:root=data[-32:]
  length-=count;at+=encoded
 assert at-start==total
 return bytes(output),chunks
plm,plm_chunks=decode(offset,plm_size,plm_encoded,p[0x368:0x388])
cdo,cdo_chunks=decode(offset+plm_encoded,cdo_size,cdo_encoded,p[0x38c:0x3ac])
assert plm==(HERE/'plm.bin').read_bytes(),'Bootgen PLM dump differs'
assert cdo==(HERE/'pmc_cdo.bin').read_bytes(),'Bootgen CDO dump differs'
assert offset+plm_encoded+cdo_encoded==len(p),'Unaccounted image bytes'
elf_path=HERE.parent/'compare/static_files/plm.elf';elf=elf_path.read_bytes()
assert elf[:5]==b'\x7fELF\x01'
entry,phoff=struct.unpack_from('<II',elf,24);phsize,phnum=struct.unpack_from('<HH',elf,42)
loads=[]
for i in range(phnum):
 typ,at,va,pa,filesz,memsz,flags,align=struct.unpack_from('<8I',elf,phoff+i*phsize)
 if typ!=1:continue
 if filesz:assert plm[pa-entry:pa-entry+filesz]==elf[at:at+filesz],'ELF load bytes differ'
 loads.append({'address_hex':hex(pa),'file_bytes':filesz,'memory_bytes':memsz})
assert sum(x['file_bytes'] for x in loads)==len(plm)
w=struct.unpack('<%dI'%(len(cdo)//4),cdo)
assert w[0]==4 and w[1]==0x004f4443 and w[3]+5==len(w) and sum(w[:5])&0xffffffff==0xffffffff
at=5;counts=Counter();stream=bytearray();stream_commands=0
while at<len(w):
 command=w[at];at+=1;op=command&65535;n=(command>>16)&255
 assert not command>>24
 if n==255:n=w[at];at+=1
 assert at+n<=len(w)
 counts[hex(op)]+=1
 if op==0x10d:
  assert n>=3 and list(w[at:at+3])==[0,0x04070000,0x4000]
  stream.extend(struct.pack('<%dI'%(n-3),*w[at+3:at+n]));stream_commands+=1
 at+=n
assert at==len(w)
(HERE/'fpga_stream.bin').write_bytes(stream)
parts=[('PLM firmware payload',len(plm)),('FPGA configuration stream',len(stream)),
       ('CDO commands / framing',len(cdo)-len(stream)),
       ('Partition SHA3 chain bytes',plm_encoded+ cdo_encoded-len(plm)-len(cdo)),
       ('Boot headers / root hashes / padding',offset)]
assert sum(n for _,n in parts)==len(p)
report={'source':str(source.resolve()),'pdi_sha256':sha(p),'total_bytes':len(p),'part':'xcsu35p-sbvb625-2-e',
 'vendor_utility':'AMD Bootgen 2026.1, -arch spartanup -read / -dump boot_files',
 'file_layout':[{'name':'Boot headers/root hashes/padding','offset':0,'bytes':offset},
                {'name':'PLM encoded partition','offset':offset,'bytes':plm_encoded},
                {'name':'FPGA CDO encoded partition','offset':offset+plm_encoded,'bytes':cdo_encoded}],
 'breakdown':[{'name':name,'bytes':n,'KiB':n/1024,'percent':n/len(p)*100} for name,n in parts],
 'plm':{'input_elf':str(elf_path.resolve()),'elf_container_bytes':len(elf),'elf_sha256':sha(elf),
        'payload_bytes':len(plm),'encoded_bytes':plm_encoded,'chain_bytes':plm_encoded-len(plm),'chunks':plm_chunks,'loads':loads},
 'fpga':{'cdo_payload_bytes':len(cdo),'encoded_bytes':cdo_encoded,'chain_bytes':cdo_encoded-len(cdo),
         'stream_bytes':len(stream),'stream_commands':stream_commands,'other_cdo_bytes':len(cdo)-len(stream),
         'cdo_commands':dict(counts),'chunks':cdo_chunks},
 'checks':{'bootgen_dumps_match':True,'partition_sha3_chains_valid':True,'plm_elf_load_bytes_match':True,'all_bytes_accounted':True,'original_pdi_unchanged':True},
 'notes':['Normal Vivado-generated image with the supplied AMD PLM, not the custom native benchmark image.',
          'ELF file size includes metadata/debug information; only file-backed load bytes are packaged.',
          'Configuration stream includes configuration packets/framing, not only LUT/BRAM frame contents.',
          'Read-only offline inspection. No hardware programming or eFUSE access performed.',
          'Bootgen printed WARNING: dl3 detected; complete raw output is retained.']}
(HERE/'breakdown.json').write_text(json.dumps(report,indent=2)+'\n')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(12,3.1),layout='constrained')
colors=['#127d85','#3c6fc4','#ecae47','#9376b7','#949fa8'];left=0
for (name,n),color in zip(parts,colors):
 ax.barh([0],n,left=left,color=color,label=f'{name}: {n:,} B ({n/len(p)*100:.3f}%)');left+=n
ax.set(xlabel='Bytes in PDI',title=f'Normal SCU35 PDI: {len(p):,} bytes',yticks=[])
ax.set_xlim(0,len(p));ax.legend(loc='upper center',bbox_to_anchor=(.5,-.3),ncol=2,fontsize=9)
fig.savefig(HERE/'breakdown.svg');fig.savefig(HERE/'breakdown.png');plt.close(fig)
rows=''.join(f'<tr><td>{html.escape(name)}</td><td>{n:,}</td><td>{n/1024:,.3f}</td><td>{n/len(p)*100:.3f}%</td></tr>' for name,n in parts)
text=f'''<!doctype html><html><meta charset="utf-8"><title>SCU35 PDI breakdown</title><style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#18323b}}img{{width:100%}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;border-bottom:1px solid #ddd;text-align:right}}td:first-child,th:first-child{{text-align:left}}code{{overflow-wrap:anywhere}}</style><h1>Normal SCU35 PDI breakdown</h1><p>AMD Bootgen 2026.1 offline inspection. Source: <code>{html.escape(report['source'])}</code></p><img src="breakdown.svg" alt="PLM, FPGA configuration stream and packaging overhead"><table><tr><th>Component</th><th>Bytes</th><th>KiB</th><th>Image</th></tr>{rows}<tr><th>Total</th><th>{len(p):,}</th><th>{len(p)/1024:,.3f}</th><th>100%</th></tr></table><p>The source PLM ELF is {len(elf):,} bytes, but its packaged firmware payload is only {len(plm):,} bytes. ELF metadata/debug sections are not embedded wholesale.</p><p>The FPGA CDO contains {len(stream):,} configuration-stream bytes and {len(cdo)-len(stream):,} command/framing bytes. SHA3 chain verification, ELF payload matching and accounting checks passed.</p><ul>{''.join('<li>'+html.escape(s)+'</li>' for s in report['notes'])}</ul><p><a href="bootgen_read.txt">Bootgen header dump</a> · <a href="bootgen_dump.txt">Bootgen extraction log</a> · <a href="breakdown.json">JSON</a> · <a href="plm_elf_layout.txt">ELF layout</a></p><p>PDI SHA256: <code>{sha(p)}</code></p></html>'''
(HERE/'report.html').write_text(text,encoding='utf-8')
print(json.dumps({'total_bytes':len(p),'breakdown':report['breakdown'],'plm':report['plm'],'checks':report['checks']},indent=2))
