"""Generate a self-contained HTML comparison report from benchmark data."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _safe_json(value: Any) -> str:
    """Serialize JSON safely for an inline script element."""
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _clock_summary(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    name = value.get("name") or value.get("clock_name") or value.get("clock")
    resolution = value.get("resolution_ns")
    if resolution is None and value.get("resolution") is not None:
        try:
            resolution = float(value["resolution"]) * 1_000_000_000
        except (TypeError, ValueError):
            resolution = None
    if resolution is not None:
        try:
            ns = float(resolution)
            if ns > 0:
                ns_text = f"{ns:g}"
                suffix = f"{ns_text} ns resolution"
            else:
                suffix = None
        except (TypeError, ValueError):
            suffix = str(resolution)
    else:
        suffix = None
    summary = " · ".join(str(part) for part in (name, suffix) if part not in (None, ""))
    return summary or value


def _duration(value: Any) -> str:
    if value is None:
        return "Unavailable"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Unavailable"
    if number < 0:
        return "Unavailable"
    return f"{number:,.3f}"


def _metadata(data: dict[str, Any]) -> str:
    meta = data.get("metadata") or {}
    pairs = [
        ("Measured", meta.get("measured_utc")),
        ("Python", meta.get("python_version")),
        ("Processor", meta.get("processor")),
        ("Platform", meta.get("platform")),
        ("Backend", meta.get("backend")),
        ("Clock", _clock_summary(meta.get("clock"))),
    ]
    return "".join(
        f'<div class="meta"><span>{_e(label)}</span><strong>{_e(value if value not in (None, "") else "Unavailable")}</strong></div>'
        for label, value in pairs
    )


def write_report(data: dict, path: Path) -> None:
    """Write a single-file HTML comparison report at *path*.

    The input is retained in the report for its JSON download. Missing numeric
    measurements render as “Unavailable”; they are never coerced to zero.
    """
    rows = data.get("comparisons") or []
    features = data.get("special_features") or []
    scope_notes = data.get("scope_notes") or []
    hardware = data.get("hardware") or {}
    json_data = _safe_json(data)

    # These server-rendered values are escaped independently from the embedded
    # JSON so malformed or untrusted benchmark labels cannot inject markup.
    host = _metadata(data)
    notes = "".join(f"<li>{_e(note)}</li>" for note in scope_notes) or "<li>No scope notes supplied.</li>"
    hardware_rows = "".join(
        f'<div class="meta"><span>{_e(label)}</span><strong>{_e(hardware.get(key) if hardware.get(key) not in (None, "") else "Unavailable")}</strong></div>'
        for label, key in (("Capture source", "source"), ("Capture status", "status"), ("Build", "build_id"), ("Capture SHA-256", "capture_sha256"))
    )
    feature_html = ""
    if features:
        trs = []
        for feature in features:
            trs.append("<tr>" + "".join(
                f"<td>{_e(feature.get(k) if feature.get(k) is not None else 'Unavailable')}</td>"
                for k in ("feature", "hardware_us", "status", "python_equivalent", "note")
            ) + "</tr>")
        feature_html = f'''<section class="panel"><div class="section-head"><div><p class="eyebrow">Coverage</p><h2>Special features</h2></div></div>
          <div class="table-wrap"><table><thead><tr><th>Feature</th><th>Hardware (µs)</th><th>Status</th><th>Python equivalent</th><th>Note</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div></section>'''

    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>SCU35 and Python · Performance comparison</title>
<style>
:root{{--ink:#18252d;--muted:#61727a;--line:#dce5e7;--paper:#f4f7f6;--white:#fff;--teal:#087f75;--blue:#3974b8;--amber:#a76308;--red:#a63d37;--soft:#eaf2f0;--radius:16px}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,-apple-system,sans-serif}}
header{{background:#132a31;color:#f5faf8;padding:38px max(24px,calc((100% - 1180px)/2)) 32px}}.topline{{color:#a6c7c0;text-transform:uppercase;letter-spacing:.14em;font-size:11px;font-weight:700}}h1{{font-size:clamp(28px,4vw,42px);line-height:1.1;margin:12px 0 10px;letter-spacing:-.03em}}header p{{margin:0;color:#c5d6d2;max-width:740px}}
main{{max-width:1180px;margin:26px auto;padding:0 22px 52px}}.panel{{background:var(--white);border:1px solid var(--line);border-radius:var(--radius);padding:23px;margin:18px 0;box-shadow:0 5px 20px #183a3010}}.section-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:16px}}h2{{font-size:21px;margin:2px 0 0;letter-spacing:-.02em}}.eyebrow{{font-size:11px;color:var(--teal);font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin:0}}.lede{{color:var(--muted);margin:5px 0 0}}
.meta-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}.meta{{padding:12px 14px;background:#f6f9f8;border-radius:10px;min-width:0}}.meta span{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}}.meta strong{{display:block;font-size:13px;margin-top:4px;overflow-wrap:anywhere}}
.controls{{display:flex;align-items:center;flex-wrap:wrap;gap:10px}}label{{font-size:12px;color:var(--muted);font-weight:700}}select,button{{font:inherit;border:1px solid #cbd8d9;border-radius:9px;background:#fff;color:var(--ink);padding:9px 12px}}button{{cursor:pointer;font-weight:700}}button.primary{{background:var(--teal);color:white;border-color:var(--teal)}}button:hover{{filter:brightness(.96)}}
.chart-list{{display:grid;gap:13px}}.chart-row{{display:grid;grid-template-columns:minmax(145px,220px) 1fr;gap:16px;align-items:center}}.chart-label strong{{display:block;font-size:14px}}.chart-label small{{color:var(--muted)}}.bars{{display:grid;gap:6px}}.barline{{display:grid;grid-template-columns:60px 1fr minmax(82px,120px);gap:9px;align-items:center;font-size:12px}}.barname{{color:var(--muted)}}.track{{height:12px;background:#edf1f1;border-radius:99px;overflow:hidden}}.bar{{height:100%;min-width:2px;border-radius:99px}}.bar.py{{background:var(--blue)}}.bar.hw{{background:var(--teal)}}.bar.na{{background:#c9d2d3;width:4px!important}}.barvalue{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.ratio{{font-size:12px;color:var(--muted);margin:7px 0 0 69px}}.legend{{display:flex;gap:16px;color:var(--muted);font-size:12px;margin:0 0 14px}}.dot{{display:inline-block;width:9px;height:9px;border-radius:99px;margin-right:5px}}.dot.py{{background:var(--blue)}}.dot.hw{{background:var(--teal)}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1050px;font-size:13px}}th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #e8eeee;vertical-align:top}}th{{background:#f5f8f7;color:#53656a;font-size:10px;text-transform:uppercase;letter-spacing:.08em;white-space:nowrap;position:sticky;top:0}}td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}tr:last-child td{{border-bottom:0}}.badge{{display:inline-block;padding:3px 8px;border-radius:99px;font-weight:800;font-size:11px;white-space:nowrap}}.yes{{background:#e0f3e9;color:#176242}}.no{{background:#ffebe8;color:#963d35}}.unknown{{background:#edf0f0;color:#627176}}.scope{{max-width:240px;color:var(--muted)}}.empty{{padding:24px;text-align:center;color:var(--muted)}}.notes{{margin:10px 0 0;padding-left:20px;color:#45575d}}.notes li{{margin:5px 0}}.callout{{border-left:4px solid var(--amber);background:#fff8e9;padding:13px 16px;border-radius:0 9px 9px 0;color:#5f4a29}}footer{{color:var(--muted);text-align:center;font-size:12px;padding:6px 0 20px}}
@media(max-width:680px){{main{{padding:0 12px 32px}}.panel{{padding:16px}}.chart-row{{grid-template-columns:1fr;gap:4px}}.ratio{{margin-left:0}}.barline{{grid-template-columns:52px 1fr 82px}}header{{padding:28px 18px}}}}
@media print{{body{{background:white;font-size:11px}}header{{background:white;color:#111;padding:15px 0;border-bottom:2px solid #333}}header p,.topline{{color:#444}}main{{max-width:none;padding:0}}.panel{{box-shadow:none;break-inside:avoid;padding:12px;margin:10px 0}}.controls,button{{display:none!important}}.table-wrap{{overflow:visible}}table{{min-width:0;font-size:9px}}th,td{{padding:5px}}th{{position:static}}.chart-row{{grid-template-columns:150px 1fr}}footer{{display:none}}}}
</style></head><body>
<header><div class="topline">Benchmark report</div><h1>SCU35 and Python</h1><p>Performance and correctness comparison across the measured cases. Timing values are in microseconds; each result is tied to its recorded scope and host environment.</p></header>
<main>
<section class="panel"><div class="section-head"><div><p class="eyebrow">Run context</p><h2>Environment and capture</h2></div><button id="download" class="primary" type="button">Download source JSON</button></div>
<div class="meta-grid">{host}{hardware_rows}</div><p class="eyebrow" style="margin-top:18px">Timing boundaries</p><div class="callout">The primary SCU35 operation interval includes the soft CPU and driver/DMA path; it is not isolated engine time. For hash and AES, SCU35 operation includes initialization plus the crypto data API, matching Python hash object creation or per-call AES nonce setup inside the Python call. For LMS/HSS, SCU35 operation is verification API time; initialization is outside both sides. SHA3, SHAKE, and AES Python results use C-backed libraries. LMS/HSS Python results use pure-Python SHAKE reference CPU loops. Interpret each row using its scope.</div></section>
<section class="panel"><div class="section-head"><div><p class="eyebrow">Visual comparison</p><h2>Latency by case</h2><p class="lede">Logarithmic bar lengths make fast and slow cases visible together. Labels show the exact mean latency.</p></div></div>
<div class="legend"><span><i class="dot py"></i>Python mean</span><span><i class="dot hw"></i>SCU35 operation mean</span></div>
<div class="controls" style="margin-bottom:18px"><label for="algFilter">Algorithm</label><select id="algFilter"><option value="">All algorithms</option></select><label for="caseFilter">Case</label><select id="caseFilter"><option value="">All cases</option></select></div>
<div id="charts" class="chart-list"></div></section>
<section class="panel"><div class="section-head"><div><p class="eyebrow">Measured values</p><h2>Exact timing table</h2><p class="lede">Means, medians, ranges, full-call means, ratio basis, and correctness for each comparison row.</p></div></div>
<div class="table-wrap"><table><thead><tr><th>Algorithm</th><th>Case</th><th>Size (bytes)</th><th>Python mean (µs)</th><th>Python median (µs)</th><th>Python min (µs)</th><th>Python max (µs)</th><th>SCU35 operation mean (µs)</th><th>SCU35 API mean (µs)</th><th>SCU35 full mean (µs)</th><th>SCU35 API min (µs)</th><th>SCU35 API max (µs)</th><th>Operation / Python mean</th><th>Results</th><th>Scope</th></tr></thead><tbody id="rows"></tbody></table></div><div id="noRows" class="empty" hidden>No comparison rows match these filters.</div></section>
{feature_html}
<section class="panel"><p class="eyebrow">Interpretation</p><h2>Scope notes</h2><ul class="notes">{notes}</ul></section>
<footer>Generated as a self-contained report. No external assets or network access are required.</footer></main>
<script id="report-data" type="application/json">{json_data}</script>
<script>
(()=>{{
 const d=JSON.parse(document.getElementById('report-data').textContent), rows=d.comparisons||[];
 const alg=document.getElementById('algFilter'), cs=document.getElementById('caseFilter');
 const uniq=(key)=>[...new Set(rows.map(r=>r[key]).filter(x=>x!==null&&x!==undefined).map(String))].sort((a,b)=>a.localeCompare(b,undefined,{{numeric:true}}));
 function fill(sel,values){{for(const v of values){{const o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o)}}}}
 fill(alg,uniq('algorithm'));fill(cs,uniq('case'));
 const fmt=v=>{{if(v===null||v===undefined||v===''||!Number.isFinite(Number(v))||Number(v)<0)return 'Unavailable';return Number(v).toLocaleString(undefined,{{minimumFractionDigits:3,maximumFractionDigits:3}})}};
 const fmtBytes=v=>{{if(v===null||v===undefined||v===''||!Number.isFinite(Number(v))||Number(v)<0)return 'Unavailable';return Math.round(Number(v)).toLocaleString(undefined,{{maximumFractionDigits:0}})}};
 const esc=s=>String(s??'Unavailable');
 const selected=()=>rows.filter(r=>(!alg.value||String(r.algorithm)===alg.value)&&(!cs.value||String(r.case)===cs.value));
 function render(){{
   const picked=selected(), tbody=document.getElementById('rows'), charts=document.getElementById('charts');tbody.replaceChildren();charts.replaceChildren();
   document.getElementById('noRows').hidden=picked.length>0;
   for(const r of picked){{
     const tr=document.createElement('tr');
     const values=[r.algorithm,r.case];
     for(const x of values){{const td=document.createElement('td');td.textContent=esc(x);tr.appendChild(td)}}
     const size=document.createElement('td');size.className='num';size.textContent=fmtBytes(r.size_bytes);tr.appendChild(size);
     for(const x of [r.python_mean_us,r.python_median_us,r.python_min_us,r.python_max_us,r.scu35_operation_mean_us,r.scu35_api_mean_us,r.scu35_full_mean_us,r.scu35_min_us,r.scu35_max_us]){{const td=document.createElement('td');td.className='num';td.textContent=fmt(x);tr.appendChild(td)}}
     const ratio=document.createElement('td');ratio.className='num';const p=Number(r.python_mean_us),h=Number(r.scu35_operation_mean_us);ratio.textContent=(r.python_mean_us!=null&&r.scu35_operation_mean_us!=null&&p>0&&h>=0)?(h/p).toLocaleString(undefined,{{maximumFractionDigits:3}})+'×':'Unavailable';tr.appendChild(ratio);
     const badge=document.createElement('td'), b=document.createElement('span');b.className='badge '+(r.results_match===true?'yes':r.results_match===false?'no':'unknown');b.textContent=r.results_match===true?'Match':r.results_match===false?'Mismatch':'Unavailable';badge.appendChild(b);tr.appendChild(badge);
     const scope=document.createElement('td');scope.className='scope';const a=String(r.algorithm||'').toLowerCase();const boundary=(a.includes('lms')||a.includes('hss'))?'Verification API; initialization outside both timings.':'Initialization plus crypto data API; Python per-call setup is included.';scope.textContent=(r.scope?String(r.scope)+' · ':'')+boundary;tr.appendChild(scope);tbody.appendChild(tr);
   }}
   const nums=picked.flatMap(r=>[r.python_mean_us,r.scu35_operation_mean_us].map(Number).filter(x=>Number.isFinite(x)&&x>0));
   const lo=nums.length?Math.min(...nums):1, hi=nums.length?Math.max(...nums):10, logLo=Math.log10(lo), span=Math.max(.001,Math.log10(hi)-logLo);
   for(const r of picked){{
     const item=document.createElement('div');item.className='chart-row';const label=document.createElement('div');label.className='chart-label';
     const strong=document.createElement('strong');strong.textContent=esc(r.algorithm);const small=document.createElement('small');small.textContent=esc(r.case)+' · '+fmtBytes(r.size_bytes)+' bytes';label.append(strong,small);
     const bars=document.createElement('div');bars.className='bars';
     for(const [name,key,cls] of [['Python','python_mean_us','py'],['SCU35 operation','scu35_operation_mean_us','hw']]){{
       const line=document.createElement('div');line.className='barline';const nm=document.createElement('span');nm.className='barname';nm.textContent=name;
       const track=document.createElement('div');track.className='track';const bar=document.createElement('div');bar.className='bar '+cls;const val=Number(r[key]);
       if(r[key]===null||r[key]===undefined||!Number.isFinite(val)||val<=0)bar.classList.add('na');else bar.style.width=(8+92*(Math.log10(val)-logLo)/span)+'%';
       track.appendChild(bar);const amount=document.createElement('span');amount.className='barvalue';amount.textContent=fmt(r[key])+' µs';line.append(nm,track,amount);bars.appendChild(line);
     }}
     const ratio=document.createElement('div');ratio.className='ratio';ratio.textContent='Ratio basis: SCU35 operation / Python mean = '+(r.python_mean_us!=null&&r.scu35_operation_mean_us!=null&&Number(r.python_mean_us)>0?(Number(r.scu35_operation_mean_us)/Number(r.python_mean_us)).toLocaleString(undefined,{{maximumFractionDigits:3}})+'×':'Unavailable');
     bars.appendChild(ratio);item.append(label,bars);charts.appendChild(item);
   }}
 }}
 alg.addEventListener('change',render);cs.addEventListener('change',render);render();
 document.getElementById('download').addEventListener('click',()=>{{const blob=new Blob([JSON.stringify(d,null,2)],{{type:'application/json'}}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='comparison-data.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}});
}})();
</script></body></html>'''
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")

