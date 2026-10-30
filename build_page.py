#!/usr/bin/env python3
"""Build the Oceanside Sunday MC sheet web page (app-style, phone first) from one Planning Center plan.

Usage:  python3 build_page.py input.json out/fragment.html
Input shape: see README.md (field names mirror the Planning Center connector output).
The output is an HTML fragment (title, fonts, style, content, script) that the Artifact tool
wraps in its own skeleton when publishing.
"""
import html, json, re, sys, datetime as dt
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Vancouver")
except Exception:
    TZ = dt.timezone(dt.timedelta(hours=-7))

E = lambda s: html.escape(str(s).strip(), quote=True)

# ---------- house rules ----------
KEY_ROLES = [("Worship", "Worship Leader"), ("Elder leading", "MC"), ("Sermon", "Preaching")]
CAT_MOMENT, CAT_ANNOUNCEMENT, CAT_LEADER = "Moment", "Announcement", "Leader"
ROSTER_GROUPS = [("worship", "Worship Leader", "Worship leaders"), ("elders", None, None), ("production", None, None)]  # team text (partial, any case), position filter, heading

MOMENTS = [
 ("Presence &amp; preeminence", ["Worship team finding moments of His presence and preeminence, concentrating on His holiness"]),
 ("Prayer moments", ["Congregational: agreement &amp; intercession (with slides?)", "Leader team led: a handful of leaders step up to lead us in prayer", "Altar call: traditional, come to the front", "Amongst people: individuals stand, leaders come, then others"]),
 ("Prophecy &amp; words of knowledge", ["Received before the service and weighed", "Encouraging words or scriptures released during worship", "Prophecies which need to be weighed, released during response", "Bring words of knowledge and prayer response post service"]),
 ("Priesthood &amp; people moments", ["Congregation stand and greet (with ice-breaker?)", "Recognize someone or event in the community", "Family Service Communion Groups (long weekend)"]),
 ("Provision moments <span class='aside'>(thankfulness and generosity)</span>", ["Monthly 3min giving teaching", "Semi-monthly thanksgiving moment"]),
 ("Proclamation of the Gospel", ["Presentation of the Gospel moment (3&ndash;5min)", "Family Service Communion Groups (long weekend)"]),
 ("Personal testimony moments", ["Mid-worship testimony (2min)", "Mid-service testimony (2&ndash;5min)"]),
 ("Preaching of the Word", []),
]

def lines(text):
    if not text: return []
    return [x.strip() for x in re.split(r"<br\s*/?>|\r?\n", str(text)) if len(x.strip()) > 1]
def notes(item, cat): return [n.get("content", "") for n in item.get("notes") or [] if (n.get("category_name") or "").strip() == cat and str(n.get("content", "")).strip()]
def slug(s): return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:24]
def initials(name):
    p = str(name).split()
    if not p: return "?"
    return (p[0][0] + p[-1][0]).upper() if len(p) > 1 else p[0][:2].upper()
def avatars(names, cls=""):
    return '<span class="avs">' + "".join(f'<span class="av {cls}">{E(initials(n))}</span>' for n in names[:2]) + "</span>"

def build(data):
    plan, items, people = data["plan"], data["items"], data["people"]
    opts = data.get("options", {})
    now = dt.datetime.now(TZ)
    built = now.strftime("%-d %B %Y")
    updated = now.strftime("%a %-I:%M%p").replace("AM", "am").replace("PM", "pm")

    # --- order of service: groups of rows, each row tappable
    groups, cur, idx = [], None, 0
    for it in items:
        title = (it.get("title") or "").strip()
        if it.get("item_type") == "header":
            cur = {"title": title, "rows": []}; groups.append(cur); continue
        if cur is None: cur = {"title": "", "rows": []}; groups.append(cur)
        idx += 1
        badge = f'<span class="key">{E(it["key_name"])}</span>' if it.get("item_type") == "song" and it.get("key_name") else ""
        bpm = (it.get("arrangement") or {}).get("bpm") if it.get("item_type") == "song" else None
        chips = "".join(f'<span class="chip">{E(m)}</span>' for m in notes(it, CAT_MOMENT))
        chips = f'<span class="chips">{chips}</span>' if chips else ""
        leader = notes(it, CAT_LEADER)
        meta = ""
        if leader or bpm:
            lead = f'<span class="lead">{avatars([leader[0]], "xs")}{E(", ".join(leader))}</span>' if leader else ""
            tempo = f'<span class="bpm">{bpm} bpm</span>' if bpm else ""
            meta = f'<div class="meta">{lead}{tempo}</div>'
        detail = lines(it.get("description")) + notes(it, CAT_ANNOUNCEMENT)
        if len(detail) == 1: desc = f'<div class="desc">{E(detail[0])}</div>'
        elif detail: desc = '<ul class="dlist">' + "".join(f"<li>{E(x)}</li>" for x in detail) + "</ul>"
        else: desc = ""
        labelled = "".join(f'<div class="desc"><span class="lbl">{E(c)}</span> {E(v)}</div>' for c in dict.fromkeys((x.get("category_name") or "").strip() for x in it.get("notes") or []) if c and c not in (CAT_MOMENT, CAT_ANNOUNCEMENT, CAT_LEADER) for v in notes(it, c))
        cur["rows"].append(
            f'<li class="item" data-id="{idx}-{slug(title)}">'
            f'<button type="button" class="tick" role="checkbox" aria-checked="false" aria-label="Check off {E(title)}" aria-keyshortcuts="n"></button><div class="body"><div class="head"><span class="title">{E(title)}</span>{badge}{chips}</div>{meta}{desc}{labelled}</div></li>')
    order = ""
    for g in groups:
        cap = (f'<h3 class="cap" role="button" tabindex="0"><span>{E(g["title"])}</span><span class="cap-count"></span></h3>') if g["title"] else ""
        order += f'<section class="group">{cap}<ul class="card items">{"".join(g["rows"])}</ul></section>'

    # --- key people
    keys = ""
    for label, pos in KEY_ROLES:
        names = list(dict.fromkeys(p["name"].strip() for p in people if (p.get("position") or "").strip() == pos))
        who = E(" & ".join(names)) if names else '<span class="muted">Not scheduled</span>'
        av = avatars(names) if names else '<span class="avs"><span class="av empty">?</span></span>'
        keys += f'<li class="krow">{av}<div class="kt"><span class="klabel">{E(label)}</span><span class="kname">{who}</span></div></li>'

    # --- who's serving (same groups as the printed sheet)
    rgroups = ""
    for token, position, heading in ROSTER_GROUPS:
        found, m = "", {}
        for p in people:
            team, pos = (p.get("team") or "").strip(), (p.get("position") or "").strip()
            if token in team.lower() and (position is None or pos == position):
                found = found or team
                r = m.setdefault(p["name"].strip(), [])
                if pos and pos not in r: r.append(pos)
        if not m: continue
        rows = ""
        for name, roles in m.items():
            roles = [] if position else [r for r in roles if r != found]
            rows += f'<li class="rrow"><span class="av sm">{E(initials(name))}</span><span class="rname">{E(name)}</span>' + (f'<span class="rrole">{E(", ".join(roles))}</span>' if roles else "") + "</li>"
        rgroups += f'<section class="rgroup"><h3 class="cap">{E(heading or found)}</h3><ul class="card rlist">{rows}</ul></section>'
    roster = f'<section id="people"><h2 class="sec">Who&rsquo;s serving</h2>{rgroups}</section>' if opts.get("show_roster", True) else ""

    # --- reminders: the eight moments, always open
    moments = "".join(f'<li class="moment"><span class="mnum">{i+1}</span><div><h4>{h}</h4>' + (("<ul>" + "".join(f"<li>{b}</li>" for b in bl) + "</ul>") if bl else "") + "</div></li>" for i, (h, bl) in enumerate(MOMENTS))
    theme = f'<span class="theme">{E(plan["theme"])}</span>' if plan.get("theme") else ""

    return HEAD + f'''
<div class="appbar" role="region" aria-label="Service progress"><div class="ab-in">
  <div class="ab-idle"><span class="ab-name">Sunday MC Sheet</span></div>
  <button type="button" class="ab-next" hidden><span class="ab-label">Up next</span><span class="ab-title"></span></button>
  <div class="ab-side"><span class="ab-count" hidden></span><button type="button" class="ab-reset" hidden>Reset</button><button type="button" class="ab-refresh" aria-label="Refresh to load the latest version" title="Refresh"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg></button></div>
</div></div>
<div class="page" data-plan="{E(plan["dates"])}">
<header class="hero">
  <div class="eyebrow">{E(plan["service_type"])} <span class="updated">&middot; Updated {updated}</span></div>
  <h1>{E(plan["dates"])}</h1>
  {theme}
</header>
<section class="leading" aria-label="Leading this service"><ul class="card keys">{keys}</ul></section>
<section class="card gnotes" aria-label="My notes"><div class="gn-head"><label class="gn-label" for="gn">My notes for today</label><span class="gn-hint">Saved on this device only</span></div><textarea id="gn" class="note" rows="2" placeholder="Add notes for today&hellip;"></textarea></section>
<div class="cols">
<main class="main"><section id="order"><h2 class="sec">Order of service</h2>
<p class="hint">Tap to check an item off. Press and hold to add a note.</p>
{order}
</section></main>
<aside class="side">
{roster}
<section id="reminders"><h2 class="sec">Reminders</h2>
<div class="card panel"><p class="lede">Our gatherings exist to cultivate <b>moments</b> of:</p>
<ol class="mlist">{moments}</ol></div>
</section>
</aside>
</div>
<p class="foot">From the Planning Center plan for {E(plan["dates"])}, refreshed {built}. <a href="{E(plan["url"])}">Open the plan</a></p>
</div>
''' + SCRIPT

HEAD = '''<title>Sunday MC Sheet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&display=swap">
<style>
/* App-style layout: sticky app bar, large title, grouped white cards on a soft grey canvas, tap rows that fade when checked off. Two columns from 56rem. */
:root {
  --canvas: #F3F4F6; --card: #FFFFFF; --fg: #1B1D22; --muted: #5F6573; --line: #ECEEF1;
  --accent: #3C7BEA; --ink: #1A376B; --soft: #E8F0FD; --ring: #C5CCD8; --bar: rgba(243, 244, 246, .86);
  --shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 0 0 1px rgba(16, 24, 40, .03); --note: #FFF6D6;
  --sans: "Inter Tight", system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --canvas: #0F1115; --card: #181B21; --fg: #ECEDEF; --muted: #A0A7B4; --line: #272B33; --accent: #6FA2F2; --ink: #B5D0F8; --soft: #1F2B42; --ring: #3B424E; --bar: rgba(15, 17, 21, .86); --shadow: 0 0 0 1px rgba(255, 255, 255, .05); --note: #3A3320; color-scheme: dark; }
}
:root[data-theme="dark"] { --canvas: #0F1115; --card: #181B21; --fg: #ECEDEF; --muted: #A0A7B4; --line: #272B33; --accent: #6FA2F2; --ink: #B5D0F8; --soft: #1F2B42; --ring: #3B424E; --bar: rgba(15, 17, 21, .86); --shadow: 0 0 0 1px rgba(255, 255, 255, .05); --note: #3A3320; color-scheme: dark; }
* { box-sizing: border-box; }
:root { font-size: 15px; }
body { background: var(--canvas); color: var(--fg); font-family: var(--sans); font-size: 1rem; line-height: 1.45; -webkit-text-size-adjust: 100%; overflow-wrap: break-word; -webkit-tap-highlight-color: transparent; }
h1, h2, h3, h4, p, ul, ol { margin: 0; padding: 0; }
a { color: var(--accent); }
.muted { color: var(--muted); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* app bar */
.appbar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20; background: var(--bar); -webkit-backdrop-filter: saturate(1.4) blur(14px); backdrop-filter: saturate(1.4) blur(14px); border-bottom: 1px solid var(--line); }
.ab-in { max-width: 44rem; margin-inline: auto; padding-inline: 16px; min-height: 48px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ab-name { font-weight: 600; font-size: .95rem; }
.ab-next { all: unset; cursor: pointer; display: flex; flex-direction: column; min-width: 0; flex: 1 1 auto; padding-block: 6px; }
.ab-next[hidden], .ab-count[hidden], .ab-reset[hidden], .ab-idle[hidden] { display: none; }
.ab-label { font-size: .68rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
.ab-title { font-weight: 500; font-size: 1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ab-side { display: flex; align-items: center; gap: 4px; flex: none; }
.ab-count { font-size: .85rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.ab-refresh { all: unset; cursor: pointer; display: inline-grid; place-items: center; width: 44px; height: 44px; margin-right: -10px; color: var(--accent); border-radius: 50%; }
.ab-refresh:focus-visible { outline: 2px solid var(--accent); outline-offset: -4px; }
.ab-refresh:active { background: var(--soft); }
.ab-refresh.spinning svg { animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.updated { white-space: nowrap; }
.ab-reset { all: unset; cursor: pointer; font-size: .9rem; font-weight: 500; color: var(--accent); padding: 12px 8px; }

.page { max-width: 44rem; margin-inline: auto; padding-inline: 16px; padding-block: 8px 56px; }

/* hero */
.hero { padding-block: 14px 4px; }
.eyebrow { font-size: .78rem; font-weight: 500; color: var(--muted); }
h1 { font-size: clamp(1.7rem, 7vw, 2.2rem); font-weight: 600; letter-spacing: -.015em; line-height: 1.1; margin-top: 2px; }
.theme { display: inline-block; margin-top: 8px; padding: 3px 12px; border-radius: 999px; background: var(--soft); color: var(--ink); font-size: .82rem; font-weight: 500; }

/* cards and captions */
.card { list-style: none; background: var(--card); border-radius: 14px; box-shadow: var(--shadow); overflow: hidden; }
.sec { font-size: 1.05rem; font-weight: 600; margin: 22px 2px 2px; }
.hint { color: var(--muted); font-size: .85rem; margin: 0 2px 2px; }
.cap { display: flex; justify-content: space-between; align-items: center; min-height: 44px; padding: 14px 6px 6px; font-size: .72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.group > .cap { cursor: pointer; }
.cap-count { font-variant-numeric: tabular-nums; letter-spacing: 0; }

/* who is leading */
.leading { margin-top: 12px; }
.keys .krow { display: flex; align-items: center; gap: 12px; padding: 11px 14px; }
.keys .krow + .krow { border-top: 1px solid var(--line); }
.kt { display: flex; flex-direction: column; min-width: 0; }
.klabel { font-size: .72rem; font-weight: 500; color: var(--muted); }
.kname { font-weight: 500; font-size: 1.05rem; line-height: 1.25; }
.avs { display: inline-flex; flex: none; }
.av { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: var(--soft); color: var(--ink); font-size: .78rem; font-weight: 600; box-shadow: 0 0 0 2px var(--card); }
.av:first-child { position: relative; z-index: 1; }
.av + .av { margin-left: -6px; }
.av.sm { width: 28px; height: 28px; font-size: .68rem; }
.av.xs { width: 20px; height: 20px; font-size: .55rem; box-shadow: none; }
.av.empty { background: var(--line); color: var(--muted); }

/* order of service rows */
.group { margin-top: 2px; }
.item { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 12px; padding: 13px 14px; border-top: 1px solid var(--line); cursor: pointer; transition: opacity .35s ease, background-color .2s ease; -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; touch-action: manipulation; }
.item:first-child { border-top: 0; }
.item:active { background: var(--soft); }
.tick { -webkit-appearance: none; appearance: none; display: block; position: relative; width: 22px; height: 22px; margin: 1px 0 0; padding: 0; background: transparent; border-radius: 50%; border: 2px solid var(--ring); cursor: pointer; transition: background-color .2s ease, border-color .2s ease; }
.item.next { background: var(--soft); box-shadow: inset 3px 0 0 var(--accent); }
.item.next .tick { border-color: var(--accent); }
.item.next .chip, .item.next .key { background: var(--card); }
.item.done { opacity: .4; }
.item.done .tick { background: var(--accent); border-color: var(--accent); }
.item.done .tick::after { content: ""; position: absolute; left: 6px; top: 2px; width: 5px; height: 10px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; min-width: 0; }
.title { font-weight: 500; font-size: 1.08rem; line-height: 1.3; }
.key { display: inline-grid; place-items: center; min-width: 1.7rem; height: 1.7rem; padding: 0 .4rem; border-radius: 999px; background: var(--soft); color: var(--ink); font-size: .8rem; font-weight: 600; }
.chips { margin-left: auto; display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 4px 6px; }
.chip { padding: 2px 10px; border-radius: 999px; background: var(--soft); color: var(--ink); font-size: .76rem; font-weight: 600; white-space: nowrap; }
.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; margin-top: 3px; color: var(--muted); font-size: .84rem; }
.lead { display: inline-flex; align-items: center; gap: 6px; color: var(--fg); }
.desc { margin-top: 6px; font-size: 1rem; line-height: 1.4; }
.dlist { margin-top: 6px; padding-left: 1.15rem; font-size: 1rem; line-height: 1.4; }
.dlist li + li { margin-top: 3px; }
.dlist li::marker { color: var(--accent); }
.lbl { font-weight: 600; color: var(--muted); }

/* roster */
.rgroup { margin-top: 2px; }
.rlist .rrow { display: flex; align-items: center; gap: 10px; padding: 9px 14px; }
.rlist .rrow + .rrow { border-top: 1px solid var(--line); }
.rname { font-weight: 500; }
.rrole { margin-left: auto; color: var(--muted); font-size: .85rem; text-align: right; }

/* reminders (always open) */
.panel { padding: 16px 16px 6px; margin-top: 8px; }
.lede { font-size: 1.05rem; font-weight: 500; margin-bottom: 14px; }
.lede b { color: var(--accent); font-weight: 600; }
.mlist { list-style: none; display: grid; gap: 16px; padding-bottom: 12px; }
.moment { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 12px; }
.mnum { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--soft); color: var(--ink); font-size: .8rem; font-weight: 600; }
.moment h4 { font-size: 1rem; font-weight: 600; line-height: 1.3; padding-top: 3px; }
.moment .aside { font-weight: 400; color: var(--muted); }
.moment ul { margin-top: 4px; padding-left: 1.1rem; font-size: .95rem; color: var(--fg); }
.moment li + li { margin-top: 2px; }
.moment li::marker { color: var(--accent); }

/* my notes: typed on this device, stored only in this browser */
.gnotes { margin-top: 12px; padding: 12px 14px 14px; }
.gn-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.gn-label { font-size: .72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.gn-hint { font-size: .75rem; color: var(--muted); }
textarea.note { display: block; width: 100%; resize: none; border: 1px solid var(--line); border-radius: 10px; background: var(--card); color: var(--fg); font: inherit; font-size: 16px; line-height: 1.4; padding: 9px 11px; -webkit-user-select: text; user-select: text; }
textarea.note::placeholder { color: var(--muted); }
textarea.note:focus { outline: 2px solid var(--accent); outline-offset: 1px; border-color: transparent; }
.mynote { margin-top: 8px; cursor: auto; -webkit-user-select: text; user-select: text; }
.mn-show { display: none; cursor: pointer; padding: 8px 11px; border-radius: 10px; background: var(--note); font-size: .95rem; line-height: 1.4; white-space: pre-wrap; }
.mn-show.has { display: block; }
.mn-show::before { content: "My note"; display: block; margin-bottom: 2px; font-size: .68rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.mynote .mn-edit { display: none; }
.item.editing .mynote .mn-edit { display: block; }
.item.editing .mynote .mn-show { display: none; }
.mn-bar { display: none; justify-content: flex-end; }
.item.editing .mn-bar { display: flex; }
.mn-done { all: unset; cursor: pointer; padding: 10px 4px 2px; color: var(--accent); font-size: .9rem; font-weight: 500; }
.mn-done:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 6px; }

.foot { margin-top: 28px; padding-top: 12px; color: var(--muted); font-size: .8rem; text-align: center; }

@media (min-width: 56rem) {
  .ab-in { max-width: 64rem; padding-inline: 24px; }
  .page { max-width: 64rem; padding-inline: 24px; }
  .cols { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 0 40px; align-items: start; }
  .leading .keys { display: grid; grid-template-columns: repeat(3, 1fr); }
  .leading .krow + .krow { border-top: 0; border-left: 1px solid var(--line); }
}
@media (prefers-reduced-motion: reduce) { .item, .tick { transition: none; } .ab-refresh.spinning svg { animation: none; } }
</style>'''

SCRIPT = '''<script>
(function () {
  var page = document.querySelector(".page");
  if (!page) return;
  var items = Array.prototype.slice.call(page.querySelectorAll(".item"));
  if (!items.length) return;
  var key = "mcsheet-done:" + (page.getAttribute("data-plan") || "plan");
  var done = {};
  try { var raw = window.localStorage.getItem(key); if (raw) done = JSON.parse(raw) || {}; } catch (e) { done = {}; }
  function save() { try { window.localStorage.setItem(key, JSON.stringify(done)); } catch (e) {} }

  var bar = document.querySelector(".appbar");
  var idle = bar.querySelector(".ab-idle"), nextBtn = bar.querySelector(".ab-next"), nextTitle = bar.querySelector(".ab-title");
  var count = bar.querySelector(".ab-count"), reset = bar.querySelector(".ab-reset");
  var nextEl = null;

  function titleOf(el) { var t = el.querySelector(".title"); return t ? t.textContent : ""; }

  /* my notes: kept only in this browser, per service date */
  var nkey = "mcsheet-notes:" + (page.getAttribute("data-plan") || "plan");
  var notes = { g: "", i: {} };
  try { var nr = window.localStorage.getItem(nkey); if (nr) { var np = JSON.parse(nr); if (np) { notes.g = np.g || ""; notes.i = np.i || {}; } } } catch (e) {}
  var nTimer = null;
  function saveNotes() { clearTimeout(nTimer); nTimer = setTimeout(function () { try { window.localStorage.setItem(nkey, JSON.stringify(notes)); } catch (e) {} }, 250); }
  function grow(t) { t.style.height = "auto"; t.style.height = (t.scrollHeight + 2) + "px"; }
  var gn = document.getElementById("gn");
  if (gn) { gn.value = notes.g; grow(gn); gn.addEventListener("input", function () { notes.g = gn.value; grow(gn); saveNotes(); }); }
  items.forEach(function (el) {
    var id = el.getAttribute("data-id");
    var wrap = document.createElement("div"); wrap.className = "mynote";
    var show = document.createElement("div"); show.className = "mn-show";
    var ta = document.createElement("textarea"); ta.className = "note mn-edit"; ta.rows = 2; ta.placeholder = "Add a note\u2026";
    ta.setAttribute("aria-label", "My note for " + titleOf(el));
    var bar = document.createElement("div"); bar.className = "mn-bar";
    var fin = document.createElement("button"); fin.type = "button"; fin.className = "mn-done"; fin.textContent = "Done";
    bar.appendChild(fin);
    ta.value = notes.i[id] || ""; show.textContent = ta.value; show.classList.toggle("has", !!ta.value);
    ta.addEventListener("input", function () {
      if (ta.value) notes.i[id] = ta.value; else delete notes.i[id];
      show.textContent = ta.value; show.classList.toggle("has", !!ta.value); grow(ta); saveNotes();
    });
    wrap.addEventListener("focusout", function (e) { if (!wrap.contains(e.relatedTarget)) el.classList.remove("editing"); });
    fin.addEventListener("click", function () { el.classList.remove("editing"); });
    wrap.appendChild(show); wrap.appendChild(ta); wrap.appendChild(bar);
    el.querySelector(".body").appendChild(wrap);
  });
  function openNote(el) {
    items.forEach(function (o) { if (o !== el) o.classList.remove("editing"); });
    el.classList.add("editing");
    var ta = el.querySelector(".mn-edit");
    grow(ta); ta.focus();
    setTimeout(function () { try { ta.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (e) {} }, 250);
  }

  function paint() {
    var n = 0, next = null;
    items.forEach(function (el) {
      var d = !!done[el.getAttribute("data-id")];
      el.classList.toggle("done", d);
      el.classList.remove("next");
      var tk = el.querySelector(".tick"); if (tk) tk.setAttribute("aria-checked", d ? "true" : "false");
      if (d) n++; else if (!next) next = el;
    });
    if (n > 0 && next) next.classList.add("next");
    Array.prototype.forEach.call(page.querySelectorAll(".group"), function (g) {
      var rows = g.querySelectorAll(".item"), c = 0;
      Array.prototype.forEach.call(rows, function (r) { if (r.classList.contains("done")) c++; });
      var el = g.querySelector(".cap-count");
      if (el) el.textContent = c ? c + "/" + rows.length : "";
    });
    nextEl = next;
    var active = n > 0;
    idle.hidden = active; nextBtn.hidden = !active; count.hidden = !active; reset.hidden = !active;
    if (active) {
      nextBtn.querySelector(".ab-label").textContent = next ? "Up next" : "All done";
      nextTitle.textContent = next ? titleOf(next) : "Service complete";
      count.textContent = n + "/" + items.length;
    }
  }
  function toggle(el) {
    var id = el.getAttribute("data-id");
    if (done[id]) delete done[id]; else done[id] = 1;
    save(); paint();
  }
  function toggleGroup(g) {
    var rows = Array.prototype.slice.call(g.querySelectorAll(".item"));
    var all = rows.every(function (r) { return done[r.getAttribute("data-id")]; });
    rows.forEach(function (r) { if (all) delete done[r.getAttribute("data-id")]; else done[r.getAttribute("data-id")] = 1; });
    save(); paint();
  }
  /* gestures: tap checks off; press and hold (or right-click) opens the note */
  var lpTimer = null, lpFired = false, lpX = 0, lpY = 0, wasEditing = false;
  function clearLp() { clearTimeout(lpTimer); lpTimer = null; }
  document.addEventListener("pointerdown", function (e) {
    var ae = document.activeElement;
    wasEditing = !!(ae && ae.classList && ae.classList.contains("mn-edit") && !e.target.closest(".mynote"));
  }, true);
  page.addEventListener("pointerdown", function (e) {
    if (e.button > 0 || e.target.closest(".mynote, .gnotes")) return;
    var it = e.target.closest(".item"); if (!it) return;
    lpFired = false; lpX = e.clientX; lpY = e.clientY; clearLp();
    lpTimer = setTimeout(function () {
      lpFired = true;
      try { if (navigator.vibrate) navigator.vibrate(12); } catch (x) {}
      openNote(it);
    }, 480);
  });
  page.addEventListener("pointermove", function (e) { if (lpTimer && (Math.abs(e.clientX - lpX) > 8 || Math.abs(e.clientY - lpY) > 8)) clearLp(); });
  ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) { page.addEventListener(n, clearLp); });
  window.addEventListener("scroll", clearLp, { passive: true });
  page.addEventListener("contextmenu", function (e) {
    var it = e.target.closest(".item");
    if (it && !e.target.closest(".mynote")) { e.preventDefault(); clearLp(); lpFired = false; openNote(it); }
  });
  page.addEventListener("click", function (e) {
    if (lpFired) { lpFired = false; return; }
    if (wasEditing) { wasEditing = false; return; }
    var cap = e.target.closest(".group > .cap");
    if (cap) { toggleGroup(cap.parentNode); return; }
    var it = e.target.closest(".item"); if (!it) return;
    if (e.target.closest(".mynote")) { if (e.target.closest(".mn-show")) openNote(it); return; }
    toggle(it);
  });
  page.addEventListener("keydown", function (e) {
    if ((e.key === "n" || e.key === "N") && e.target.classList && e.target.classList.contains("tick")) { e.preventDefault(); openNote(e.target.closest(".item")); return; }
    if (e.key !== " " && e.key !== "Enter") return;
    var t = e.target;
    if (t.classList.contains("cap") && t.parentNode.classList.contains("group")) { e.preventDefault(); toggleGroup(t.parentNode); }
  });
  reset.addEventListener("click", function () { done = {}; save(); paint(); });
  var refresh = bar.querySelector(".ab-refresh");
  if (refresh) refresh.addEventListener("click", function () {
    refresh.classList.add("spinning");
    setTimeout(function () { try { window.location.reload(); } catch (e) { refresh.classList.remove("spinning"); } }, 350);
  });
  nextBtn.addEventListener("click", function () {
    if (!nextEl) return;
    var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    nextEl.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "center" });
  });
  paint();
})();
</script>'''

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    open(dst, "w").write(build(json.load(open(src))))
    print("wrote", dst)
