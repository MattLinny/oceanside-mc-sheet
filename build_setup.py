#!/usr/bin/env python3
"""Build the stage set-up page. Usage: build_setup.py input.json gear.csv out.html"""
import csv, datetime as dt, html, json, os, sys
from zoneinfo import ZoneInfo

E = lambda s: html.escape(str(s).strip(), quote=True)
ORDER = ["Worship Leader", "Vocals", "Keys", "Acoustic Guitar", "Electric Guitar", "Bass", "Drums", "Strings"]
VOCAL = {"Worship Leader", "Vocals"}
GUITARS = {"Acoustic Guitar", "Electric Guitar", "Bass"}
WIRELESS = 6
PATCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patch.csv")
SPEAKERS = ["Preaching", "MC"]
LABEL = {"Preaching": "Preacher", "MC": "Host"}
split = lambda s: [x.strip() for x in (s or "").split(";") if x.strip()]
def initials(n):
    p = n.split()
    return (p[0][0] + p[-1][0]).upper() if len(p) > 1 else n[:2].upper()

def load_rules(path):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    return {(r.get("Who") or "").strip().lower(): {"gear": split(r.get("Gear")), "notes": split(r.get("Notes")), "remove": split(r.get("Remove"))} for r in rows if (r.get("Who") or "").strip()}

def load_tasks(path):
    rows = csv.DictReader(open(path, newline="", encoding="utf-8-sig"))
    return [r["Gear"].strip() for r in rows if (r.get("Who") or "").strip().lower() == "task" and (r.get("Gear") or "").strip()]

def gear_for(name, positions, rules):
    gear, notes = [], []
    for pos in positions:
        r = rules.get(pos.lower())
        if r:
            gear += r["gear"]; notes += r["notes"]
    low = name.lower()
    if any(p != "Vocals" for p in positions):  # a guitarist singing one week needs no pedal power
        r = rules.get(low) or rules.get(low.split()[0])
        if r:
            drop = {x.lower() for x in r["remove"]}
            gear = [g for g in gear if g.lower() not in drop] + r["gear"]
            notes += r["notes"]
    if "MC" in positions:  # the host always gets a handheld, whatever a person rule removes
        gear.insert(0, "Handheld")
    return list(dict.fromkeys(gear)), list(dict.fromkeys(notes))

def monitors(band):
    """band is in stage order, vocalists first. Mon 1-6 wireless, drums always wired on 7; bass moves to wired 8 if wireless runs out."""
    out = {n: "Mon 7 wired" for n, ps in band if "Drums" in ps}
    rest = [n for n, _ in band if n not in out]
    wired = 8
    if len(rest) > WIRELESS:
        bass = next((n for n, ps in band if n in rest and "Bass" in ps), None)
        if bass:
            out[bass] = "Mon 8 wired"
            rest.remove(bass)
            wired = 9
    for i, n in enumerate(rest):
        out[n] = f"Mon {i + 1} wireless" if i < WIRELESS else f"Mon {wired + i - WIRELESS} wired"
    return out

def stands(positions):
    out = ["iPad stand" if VOCAL & set(positions) else "Music stand"]
    if GUITARS & set(positions): out.append("Guitar stand")
    return out

def lectern(name, positions, guests):
    if "Preaching" not in positions: return []
    return ["Pulpit" if name.lower() == "mark manfredi" or name in guests else "Silver table"]

def total_key(g):
    return "Wireless monitor" if g.endswith("wireless") else "Wired monitor" if g.endswith("wired") else g

def row(name, positions, rules, extra=()):
    gear, notes = gear_for(name, positions, rules)
    gear = gear + list(extra)
    role = " + ".join(LABEL.get(p, p) for p in positions)
    chips = "".join(f'<button type="button" class="g" data-g="{E(g)}" aria-pressed="false">{E(g)}</button>' for g in gear)
    note = "".join(f'<div class="n">{E(n)}</div>' for n in notes)
    body = (f'<div class="gs">{chips}</div>' if chips else "") + note
    rid = E(name + "|" + role)
    return (f'<li class="row" data-id="{rid}"><button type="button" class="tick" role="checkbox" aria-checked="false" aria-label="Check off {E(name)}"></button>'
            f'<div class="body"><div class="head"><span class="name">{E(name)}</span><span class="role">{E(role)}</span></div>{body}</div></li>'), gear

def collect(people, wanted, team=None):
    m = {}
    for p in people:
        pos = (p.get("position") or "").strip()
        if team and team not in (p.get("team") or "").lower(): continue
        if wanted is not None and pos not in wanted: continue
        m.setdefault(p["name"].strip(), [])
        if pos not in m[p["name"].strip()]: m[p["name"].strip()].append(pos)
    return m

def build(data, rules, tasks):
    plan, people = data["plan"], data["people"]
    updated = dt.datetime.now(ZoneInfo("America/Vancouver")).strftime("%a %-I:%M%p").replace("AM", "am").replace("PM", "pm")
    band = collect(people, None, "worship")
    rank = lambda pos: ORDER.index(pos) if pos in ORDER else len(ORDER)
    for ps in band.values(): ps.sort(key=rank)
    band_rows, totals = "", {}
    ordered = sorted(band.items(), key=lambda kv: min(rank(p) for p in kv[1]))
    mons = monitors(ordered)
    for name, ps in ordered:
        h, gear = row(name, ps, rules, stands(ps) + [mons[name]])
        band_rows += h
        for g in gear:
            totals[total_key(g)] = totals.get(total_key(g), 0) + 1
    speakers = collect(people, SPEAKERS)
    guests = {p["name"].strip() for p in people if p.get("position") == "Preaching" and "elder" not in (p.get("team") or "").lower()}
    speak_rows = "".join(row(n, sorted(ps, key=SPEAKERS.index), rules, lectern(n, ps, guests))[0] for n, ps in speakers.items())
    input_rows, box = "", None
    for r in csv.DictReader(open(PATCH, newline="", encoding="utf-8-sig")):
        if r["Box"] != box:
            box = r["Box"]
            input_rows += f'<li class="ihead">{E(box)}</li>'
        input_rows += f'<li class="irow"><span class="src">{E(r["No"])}</span><span class="iwho">{E(r["Input"])}</span></li>'
    task_rows = "".join(f'<li class="row" data-id="{E("task|" + t)}"><button type="button" class="tick" role="checkbox" aria-checked="false" aria-label="Check off {E(t)}"></button><div class="body"><span class="name task">{E(t)}</span></div></li>' for t in tasks)
    prod = collect(people, None, "production")
    prod_rows = "".join(f'<li class="prow"><span class="av">{E(initials(n))}</span><span class="name">{E(n)}</span><span class="role">{E(", ".join(ps))}</span></li>' for n, ps in prod.items())
    tot = "".join(f'<li><b>{c}</b><span>{E(g)}</span></li>' for g, c in sorted(totals.items(), key=lambda x: (-x[1], x[0])))
    def sec(t, sid, cls, rows):
        if not rows: return ""
        navs.append(f'<a href="#{sid}">{t}</a>')
        return f'<section id="{sid}"><h2><button type="button" class="fold" aria-expanded="true" aria-controls="{sid}-b"><span>{t}</span><span class="prog"></span><svg class="chev" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button></h2><ul id="{sid}-b" class="card {cls}">{rows}</ul></section>'
    navs = []
    totals_s = sec("Totals", "totals", "tot", tot)
    main_s = sec("Team", "team", "rows", band_rows) + sec("Speakers", "speakers", "rows", speak_rows)
    aside_s = sec("Checklist", "checklist", "rows", task_rows) + sec("Inputs", "inputs", "ilist", input_rows) + sec("Production", "production", "prod", prod_rows)
    return (HEAD + f'''<div class="bar"><div class="bar-in"><span class="bar-name">Stage Set-Up</span><span class="side"><span class="count"></span><button type="button" class="reset" hidden>Reset</button><button type="button" class="refresh" aria-label="Refresh"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg></button></span></div><nav class="nav" aria-label="Sections"><div class="nav-in">{"".join(navs)}</div></nav></div>
<div class="page" data-plan="{E(plan["dates"])}"><header><div class="eyebrow">Updated {updated}</div><h1>{E(plan["dates"])}</h1></header>
{totals_s}<div class="cols"><main>{main_s}</main><aside>{aside_s}</aside></div></div>''' + SCRIPT)

HEAD = '''<title>Stage Set-Up</title><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&display=swap" rel="stylesheet"><style>
:root{--bg:#f2f2f5;--card:#fff;--ink:#1c1c1f;--mute:#6e6e76;--line:#e6e6ea;--chip:#eef1f6;--chipink:#2f3b52;--acc:#2f6f5e}
@media(prefers-color-scheme:dark){:root{--bg:#121214;--card:#1d1d20;--ink:#f1f1f3;--mute:#9a9aa3;--line:#2c2c31;--chip:#2a2e37;--chipink:#d5dbe8;--acc:#59b89f}}
body{background:var(--bg);color:var(--ink);font:400 16px/1.4 "Inter Tight",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}
.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.bar-in,.page{max-width:68rem;margin:auto;padding-inline:16px}.bar-in{display:flex;align-items:center;justify-content:space-between;height:52px}
.bar-name{font-weight:600}.side{display:flex;align-items:center;gap:14px;color:var(--mute);font-size:.875rem;font-variant-numeric:tabular-nums}.refresh{display:flex;width:32px;height:32px;align-items:center;justify-content:center}
header{padding:22px 0 6px}.eyebrow{color:var(--mute);font-size:.8125rem}h1{font-size:1.75rem;font-weight:600;letter-spacing:-.01em;margin:2px 0 0}
h2{font-size:.8125rem;font-weight:500;color:var(--mute);margin:22px 4px 8px}
ul{list-style:none;margin:0;padding:0}.card{background:var(--card);border-radius:14px;overflow:hidden}
.row{display:flex;gap:12px;padding:14px;border-top:1px solid var(--line);transition:opacity .25s;cursor:pointer}.row:first-child,.prow:first-child{border-top:0}.row.done{opacity:.4}
.tick{flex:none;width:24px;height:24px;border-radius:50%;border:1.5px solid #c4c4cc;margin-top:1px}.done .tick{background:var(--acc);border-color:var(--acc);box-shadow:inset 0 0 0 4px var(--card)}
.body{min-width:0;flex:1}.head{display:flex;justify-content:space-between;gap:12px;align-items:baseline}.name{font-weight:500;font-size:1.0625rem;white-space:nowrap}.role{color:var(--mute);font-size:.875rem;text-align:right}
.gs{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.g{background:var(--chip);color:var(--chipink);border-radius:8px;padding:7px 11px;font-size:.9375rem;transition:background .15s}.g[aria-pressed=true]{background:var(--acc);color:var(--card)}.g[aria-pressed=true]::before{content:"\\2713\\00a0"}.name.task{white-space:normal;display:block;margin-top:1px}.n{color:var(--mute);font-size:.9375rem;margin-top:7px}
.tot{display:grid;grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr))}.tot li{display:flex;gap:9px;align-items:baseline;padding:11px 14px}.tot b{font-weight:600;font-size:1.125rem;font-variant-numeric:tabular-nums}
.prow{display:flex;align-items:center;gap:10px;padding:10px 14px;border-top:1px solid var(--line)}.prow .name{font-size:1rem}.prow .role{margin-left:auto}.av{flex:none;width:30px;height:30px;border-radius:50%;background:var(--chip);color:var(--chipink);display:flex;align-items:center;justify-content:center;font-size:.6875rem;font-weight:500}
.page{padding-bottom:40px}
@media(min-width:56rem){.cols{display:grid;grid-template-columns:3fr 2fr;gap:24px;align-items:start}}
.nav{overflow-x:auto;scrollbar-width:none}.nav::-webkit-scrollbar{display:none}.nav-in{max-width:68rem;margin:auto;padding:0 16px 8px;display:flex;gap:6px;width:max-content;min-width:100%;box-sizing:border-box}.nav a{color:var(--ink);text-decoration:none;background:var(--card);border-radius:999px;padding:7px 13px;font-size:.875rem;font-weight:500;white-space:nowrap}
section{scroll-margin-top:104px}.fold{display:flex;align-items:center;gap:8px;width:100%;min-height:32px;color:var(--mute);font-weight:500;text-align:left}.prog{margin-left:auto;font-variant-numeric:tabular-nums}.chev{flex:none;transition:transform .15s}.fold[aria-expanded=false] .chev{transform:rotate(-90deg)}h2{margin:18px 4px 6px}
.irow{display:flex;align-items:baseline;gap:10px;padding:10px 14px;border-top:1px solid var(--line)}.irow:first-child{border-top:0}.src{font-weight:600;flex:none;width:2.5rem;font-variant-numeric:tabular-nums}.ihead{padding:12px 14px 6px;color:var(--mute);font-size:.8125rem;font-weight:500;border-top:1px solid var(--line)}.ihead:first-child{border-top:0}.ihead+.irow{border-top:0}.iwho{min-width:0}.irow .role{margin-left:auto}
</style>'''
SCRIPT = '''<script>(function(){var P=document.querySelector(".page"),K="setup:"+P.dataset.plan,S={};try{S=JSON.parse(localStorage.getItem(K))||{}}catch(e){}
var R=[].slice.call(document.querySelectorAll(".row")),C=document.querySelector(".count"),X=document.querySelector(".reset");
function chips(r){return [].slice.call(r.querySelectorAll(".g"))}
function keys(r){var c=chips(r);return c.length?c.map(function(g){return r.dataset.id+"|"+g.dataset.g}):[r.dataset.id]}
function U(){var n=0,t=0;R.forEach(function(r){var k=keys(r),d=k.filter(function(i){return S[i]}).length;n+=d;t+=k.length;var all=d===k.length;r.classList.toggle("done",all);r.querySelector(".tick").setAttribute("aria-checked",all);chips(r).forEach(function(g){g.setAttribute("aria-pressed",!!S[r.dataset.id+"|"+g.dataset.g])})});C.textContent=n+"/"+t;[].forEach.call(document.querySelectorAll("section"),function(sc){var rs=[].slice.call(sc.querySelectorAll(".row"));if(!rs.length)return;var a=0,b=0;rs.forEach(function(r){var k=keys(r);b+=k.length;a+=k.filter(function(i){return S[i]}).length});sc.querySelector(".prog").textContent=a+"/"+b});X.hidden=!n;try{localStorage.setItem(K,JSON.stringify(S))}catch(e){}}
R.forEach(function(r){r.addEventListener("click",function(e){var g=e.target.closest(".g");if(g){var i=r.dataset.id+"|"+g.dataset.g;if(S[i])delete S[i];else S[i]=1;return U()}
if(!e.target.closest(".tick")&&chips(r).length)return;var k=keys(r),all=k.every(function(i){return S[i]});k.forEach(function(i){if(all)delete S[i];else S[i]=1});U()})});
var FK=K+":fold",F={};try{F=JSON.parse(localStorage.getItem(FK))||{}}catch(e){}
var SEC=[].slice.call(document.querySelectorAll("section"));
function setF(sc,closed){var b=sc.querySelector(".fold");b.setAttribute("aria-expanded",!closed);sc.querySelector(".card").hidden=closed;if(closed)F[sc.id]=1;else delete F[sc.id];try{localStorage.setItem(FK,JSON.stringify(F))}catch(e){}}
SEC.forEach(function(sc){if(F[sc.id])setF(sc,true);sc.querySelector(".fold").addEventListener("click",function(){setF(sc,!F[sc.id])})});
[].forEach.call(document.querySelectorAll(".nav a"),function(a){a.addEventListener("click",function(){setF(document.querySelector(a.getAttribute("href")),false)})});
X.addEventListener("click",function(){S={};U()});document.querySelector(".refresh").addEventListener("click",function(){location.reload()});U()})();</script>'''

if __name__ == "__main__":
    open(sys.argv[3], "w").write(build(json.load(open(sys.argv[1])), load_rules(sys.argv[2]), load_tasks(sys.argv[2]) or load_tasks("gear.csv")))
