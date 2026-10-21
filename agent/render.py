"""Static web page (single index.html, no server needed) + JSON + audit CSV."""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="PhD Radar">
<meta name="theme-color" content="#1f5f8b">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f5f1;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e3e1da;--acc:#1f5f8b;--acc2:#7a3e9d;--ok:#2f7d4f;--warn:#b26a00;--bad:#b3362b;--chip:#efede7}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1e1b;--ink:#ecebe6;--mute:#9a988f;--line:#32312c;--acc:#6fb0dc;--acc2:#c39ae0;--ok:#6fcf97;--warn:#e0a94f;--bad:#ef8a7f;--chip:#2a2926}}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding-bottom:env(safe-area-inset-bottom)}
.wrap{max-width:980px;margin:auto;padding:0 16px}
header{padding:20px 0 6px}h1{margin:0;font-size:24px;letter-spacing:-.01em}
.sub{color:var(--mute);font-size:13px}.sub a{color:var(--acc)}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:8px 0 10px}
.tabs{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}.tabs::-webkit-scrollbar{display:none}
button,select,input{font:inherit;color:var(--ink)}
.tab,.pill,select,input{min-height:44px;border:1px solid var(--line);background:var(--card);border-radius:999px;padding:0 16px;cursor:pointer}
.tab{white-space:nowrap;display:inline-flex;align-items:center;gap:7px}.tab b{font-weight:600;color:var(--mute);font-size:13px}
.tab.on,.pill.on{background:var(--acc);border-color:var(--acc);color:#fff}.tab.on b{color:#fff;opacity:.85}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}.filters input{flex:1 1 200px;border-radius:12px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;background:var(--card)}
.seg button{min-height:42px;padding:0 15px;border:0;background:transparent;cursor:pointer}.seg button.on{background:var(--acc);color:#fff}
@media (max-width:700px){.top{position:static}}
#more{display:none}#more.open{display:contents}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:12px 0}
.card.new{border-left:5px solid var(--ok)}.card.soon{border-left:5px solid var(--warn)}
.t{font-size:17px;font-weight:650;line-height:1.3}.t a{color:var(--ink);text-decoration:none}.t a:active,.t a:hover{color:var(--acc)}
.meta{color:var(--mute);font-size:14px;margin-top:3px;display:flex;flex-wrap:wrap;gap:2px 12px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.chip{background:var(--chip);border-radius:999px;padding:2px 10px;font-size:12.5px}
.chip.s{background:color-mix(in srgb,var(--acc) 16%,transparent);color:var(--acc)}.chip.z{background:color-mix(in srgb,var(--acc2) 16%,transparent);color:var(--acc2)}
.chip.new{background:color-mix(in srgb,var(--ok) 18%,transparent);color:var(--ok)}.chip.dl{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}
.why{font-size:12.5px;color:var(--mute);margin-top:7px}
.acts{display:flex;gap:8px;margin-top:11px}.acts button{flex:1;min-height:44px;border:1px solid var(--line);background:transparent;border-radius:10px;cursor:pointer;font-size:14.5px}
.acts button.on{background:var(--chip);border-color:var(--mute);font-weight:600}.acts .open{flex:1.3;text-align:center;display:flex;align-items:center;justify-content:center;border:1px solid var(--acc);color:var(--acc);border-radius:10px;text-decoration:none;font-size:14.5px;min-height:44px}
.status{margin:12px 0 0;padding:10px 14px;border-radius:10px;background:var(--chip);font-size:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}.status b{font-weight:600}.status button{min-height:36px;padding:0 14px;border:1px solid var(--acc);color:var(--acc);background:transparent;border-radius:999px;cursor:pointer}
.empty{text-align:center;color:var(--mute);padding:40px 10px}
details{margin:22px 0}summary{cursor:pointer;color:var(--mute);min-height:44px;display:flex;align-items:center}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
.bad{color:var(--bad)}.good{color:var(--ok)}
.tools{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.tools button,.tools a{min-height:44px;padding:0 16px;border:1px solid var(--line);border-radius:999px;background:var(--card);cursor:pointer;display:inline-flex;align-items:center;text-decoration:none;color:var(--ink)}
</style></head><body>
<div class="wrap"><header><h1>__TITLE__</h1>
<div class="sub">Updated __UPDATED__ · __NSTRONG__ strong + __NADJ__ adjacent · __NREJ__ rejected (audit: <b>rejected.csv</b>) · PhD / predoc / RA / doctoral researcher · Europe</div></header></div>
<div class="top"><div class="wrap">
 <div class="tabs" id="tabs"></div>
 <div class="filters">
  <div class="seg" id="who"><button data-v="all" class="on">Both</button><button data-v="shayan">Shayan</button><button data-v="zahra">Zahra</button></div>
  <div class="seg" id="tier"><button data-v="strong" class="on">Strong</button><button data-v="all">+ Adjacent</button></div>
  <button class="pill" id="moreBtn">Filters ▾</button>
  <div id="more">
   <select id="type"><option value="">All types</option></select>
   <select id="region"><option value="">All Europe</option><option value="west">Western Europe only</option></select>
   <select id="sort"><option value="rank">Best match</option><option value="deadline">Deadline soonest</option><option value="new">Newest</option></select>
   <button class="pill" id="newonly">New only</button>
  </div>
  <input id="q" type="search" placeholder="Search title, topic, country…">
 </div></div></div>
<div class="wrap"><main><div id="status" class="status"></div><div id="list"></div>
<div class="tools"><button id="copy">Copy saved list</button><button id="backup">Backup my marks</button><button id="restore">Restore marks</button>__RUNLINK__</div>
<details><summary>Source health (last run)</summary><table id="health"></table></details>
<p class="sub">Your ⭐ / applied / hidden marks live in this browser only. Use Backup → Restore to move them between iPad and phone.</p></main></div>
<script>
const DATA=__DATA__, HEALTH=__HEALTH__;
const $=s=>document.querySelector(s), esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let marks={}; try{marks=JSON.parse(localStorage.getItem('radar-marks')||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem('radar-marks',JSON.stringify(marks))}catch(e){}};
const st={tab:'review',who:'all',tier:'strong',type:'',region:'',newonly:false,q:'',sort:'rank'};
try{Object.assign(st,JSON.parse(localStorage.getItem('radar-filters')||'{}'),{tab:'review',q:'',newonly:false})}catch(e){}
const TABS=[['review','To review'],['saved','⭐ Saved'],['applied','✓ Applied'],['hidden','Hidden']];
[...new Set(DATA.map(d=>d.ptype))].sort().forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;$('#type').append(o)});
const daysLeft=d=>d?Math.round((new Date(d)-new Date(new Date().toDateString()))/864e5):null;
const markOf=d=>marks[d.url]||'';
function visible(d){
  return (st.tier==='all'||d.tier==='strong')&&(st.who==='all'||d.who.includes(st.who))&&(!st.type||d.ptype===st.type)
   &&(!st.region||d.region==='west')&&(!st.newonly||d.is_new)
   &&(!st.q||(d.title+' '+d.org+' '+d.country+' '+d.primary_field+' '+d.hits.join(' ')).toLowerCase().includes(st.q.toLowerCase()));
}
function render(){
  const inTab=d=>st.tab==='review'?!markOf(d):markOf(d)===st.tab;
  const count=t=>DATA.filter(d=>visible(d)&&(t==='review'?!markOf(d):markOf(d)===t)).length;
  $('#tabs').innerHTML=TABS.map(([k,l])=>`<button class="tab ${st.tab===k?'on':''}" data-t="${k}">${l} <b>${count(k)}</b></button>`).join('');
  const key={rank:(a,b)=>(a.tier===b.tier?0:a.tier==='strong'?-1:1)||b.score-a.score,
    deadline:(a,b)=>(a.deadline||'9999').localeCompare(b.deadline||'9999'),
    new:(a,b)=>(b.first_seen||'').localeCompare(a.first_seen||'')||b.score-a.score}[st.sort];
  const rows=DATA.filter(d=>visible(d)&&inTab(d)).sort(key);
  const active=[st.who!=='all'?(st.who==='shayan'?'Shayan':'Zahra'):'',st.tier==='strong'?'Strong only':'',st.type?st.type:'',
    st.region?'Western Europe':'',st.newonly?'New only':'',st.q?('“'+st.q+'”'):''].filter(Boolean);
  const total=DATA.filter(inTab).length;
  $('#status').innerHTML=`Showing <b>${rows.length}</b> of ${total}`+(active.length?` · filters: ${esc(active.join(', '))} <button id="reset">Show all</button>`:'');
  const rb=$('#reset'); if(rb) rb.onclick=()=>{Object.assign(st,{who:'all',tier:'all',type:'',region:'',newonly:false,q:''});$('#q').value='';$('#type').value='';$('#region').value='';render()};
  $('#list').innerHTML=rows.length?rows.map(d=>{
    const dl=daysLeft(d.deadline), soon=dl!==null&&dl>=0&&dl<=14, m=markOf(d);
    const who=d.who.map(w=>`<span class="chip ${w==='shayan'?'s':'z'}">${w==='shayan'?'Shayan':'Zahra'}</span>`).join('');
    const dtxt=d.deadline?('Deadline '+d.deadline+(dl!==null?(dl<0?' (passed)':' · '+dl+' d left'):'')):(d.rolling?'Rolling deadline':'Deadline not found');
    return `<div class="card ${d.is_new?'new':''} ${soon?'soon':''}" data-u="${esc(d.url)}"><div class="t"><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a></div>
    <div class="meta"><span>${esc(d.org||'')}</span><span>${esc(d.country||'')}${d.region==='west'?' <b class="good">· W. Europe</b>':''}</span><span>${dtxt}</span></div>
    <div class="chips">${d.is_new?'<span class="chip new">new</span>':''}${soon?'<span class="chip dl">closing soon</span>':''}<span class="chip">${esc(d.ptype)}</span>${who}
    <span class="chip">${esc(d.primary_field)}</span>${d.tier==='adjacent'?'<span class="chip">adjacent</span>':''}</div>
    <div class="why">matched: ${esc(d.hits.join(', ')||'general economics post')} · ${esc(d.sources.join(', '))}</div>
    <div class="acts"><a class="open" href="${esc(d.url)}" target="_blank" rel="noopener">Open ↗</a>
     <button data-m="saved" class="${m==='saved'?'on':''}">${m==='saved'?'⭐ Saved':'☆ Save'}</button>
     <button data-m="applied" class="${m==='applied'?'on':''}">${m==='applied'?'✓ Applied':'Applied'}</button>
     <button data-m="hidden" class="${m==='hidden'?'on':''}">${m==='hidden'?'Unhide':'Hide'}</button></div></div>`}).join('')
    :`<div class="empty">${st.tab==='review'?'Nothing here with these filters. Try “+ Adjacent”.':'Nothing in this list yet.'}</div>`;
  document.querySelectorAll('#who button').forEach(b=>b.classList.toggle('on',b.dataset.v===st.who));
  document.querySelectorAll('#tier button').forEach(b=>b.classList.toggle('on',b.dataset.v===st.tier));
  $('#newonly').classList.toggle('on',st.newonly);
  try{localStorage.setItem('radar-filters',JSON.stringify({who:st.who,tier:st.tier,type:st.type,region:st.region,sort:st.sort}))}catch(e){}
}
$('#tabs').onclick=e=>{const b=e.target.closest('[data-t]');if(b){st.tab=b.dataset.t;render()}};
$('#who').onclick=e=>{const b=e.target.closest('[data-v]');if(b){st.who=b.dataset.v;render()}};
$('#tier').onclick=e=>{const b=e.target.closest('[data-v]');if(b){st.tier=b.dataset.v;render()}};
$('#list').onclick=e=>{const b=e.target.closest('[data-m]');if(!b)return;const u=b.closest('.card').dataset.u;
  marks[u]=(marks[u]===b.dataset.m)?'':b.dataset.m; if(!marks[u])delete marks[u]; save(); render()};
$('#type').value=st.type;$('#region').value=st.region;$('#sort').value=st.sort;
$('#type').onchange=e=>{st.type=e.target.value;render()};$('#region').onchange=e=>{st.region=e.target.value;render()};
$('#sort').onchange=e=>{st.sort=e.target.value;render()};$('#q').oninput=e=>{st.q=e.target.value;render()};
$('#newonly').onclick=()=>{st.newonly=!st.newonly;render()};
$('#moreBtn').onclick=()=>{$('#more').classList.toggle('open');$('#moreBtn').textContent=$('#more').classList.contains('open')?'Filters ▴':'Filters ▾'};
$('#copy').onclick=async()=>{const t=DATA.filter(d=>markOf(d)==='saved').map(d=>`${d.title} — ${d.org||''}, ${d.country||''} — ${d.deadline||'no deadline'}\n${d.url}`).join('\n\n')||'(nothing saved)';
  try{await navigator.clipboard.writeText(t);$('#copy').textContent='Copied ✓'}catch(e){prompt('Copy:',t)}};
$('#backup').onclick=async()=>{const t=btoa(unescape(encodeURIComponent(JSON.stringify(marks))));try{await navigator.clipboard.writeText(t);$('#backup').textContent='Backup copied ✓'}catch(e){prompt('Copy this code:',t)}};
$('#restore').onclick=()=>{const t=prompt('Paste backup code:');if(!t)return;try{Object.assign(marks,JSON.parse(decodeURIComponent(escape(atob(t.trim())))));save();render()}catch(e){alert('That code was not valid.')}};
$('#health').innerHTML='<tr><th>Source</th><th>Status</th><th>Read</th><th>Note</th></tr>'+HEALTH.map(h=>`<tr><td>${esc(h.source)}${h.verified?'':' <span class="sub">(unverified)</span>'}</td><td class="${h.ok?'good':'bad'}">${h.ok?'OK':'PROBLEM'}</td><td>${h.n_items}</td><td>${esc(h.error||'')}</td></tr>`).join('');
if(st.type||st.region){$('#more').classList.add('open');$('#moreBtn').textContent='Filters ▴'}
render();
</script></body></html>
"""


def render(decisions: list[dict], health: list[dict], rejected: list[dict], title: str, today: dt.date, out_dir: Path | None = None,
           repo: str | None = None) -> Path:
    out_dir = out_dir or (ROOT / "output")
    out_dir.mkdir(parents=True, exist_ok=True)
    kept = [d for d in decisions if d["tier"] in ("strong", "adjacent")]
    payload = [{k: d.get(k) for k in ("url", "title", "org", "country", "region", "ptype", "tier", "who", "score", "hits",
                                      "primary_field", "deadline", "rolling", "first_seen", "is_new", "sources")} for d in kept]
    page = (PAGE.replace("__TITLE__", html.escape(title)).replace("__UPDATED__", today.isoformat())
            .replace("__NSTRONG__", str(sum(1 for d in kept if d["tier"] == "strong")))
            .replace("__NADJ__", str(sum(1 for d in kept if d["tier"] == "adjacent")))
            .replace("__NREJ__", str(len(rejected)))
            .replace("__RUNLINK__", (f'<a href="https://github.com/{html.escape(repo)}/actions/workflows/daily.yml" target="_blank" rel="noopener">Run update now ↗</a>' if repo else ""))
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__HEALTH__", json.dumps(health, ensure_ascii=False).replace("</", "<\\/")))
    idx = out_dir / "index.html"
    idx.write_text(page, encoding="utf-8")
    (out_dir / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out_dir / "rejected.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "organisation", "country", "source", "reason", "url"])
        for r in rejected:
            w.writerow([r["title"], r.get("org") or "", r.get("country") or "", r.get("source") or "", r["reason"], r["url"]])
    return idx
