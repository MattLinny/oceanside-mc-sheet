#!/usr/bin/env python3
"""Fetch the current (or next) Sunday plan from the Planning Center API and write input.json for build_page.py.

Needs env PCO_APP_ID and PCO_SECRET (a Planning Center personal access token).
"""
import base64, datetime as dt, json, os, sys, urllib.request
from zoneinfo import ZoneInfo

SERVICE_TYPE = "1224591"  # Sunday Service (8:30 & 10:30)
BASE = "https://api.planningcenteronline.com/services/v2"
AUTH = "Basic " + base64.b64encode(f'{os.environ["PCO_APP_ID"]}:{os.environ["PCO_SECRET"]}'.encode()).decode()

def get(url):
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "User-Agent": "oceanside-mc-sheet"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def get_all(url):
    data, included = [], []
    while url:
        page = get(url)
        data += page.get("data", []); included += page.get("included", [])
        url = (page.get("links") or {}).get("next")
    return data, included

def pick_plan():
    today = dt.datetime.now(ZoneInfo("America/Vancouver")).date().isoformat()
    st = f"{BASE}/service_types/{SERVICE_TYPE}/plans?per_page=1"
    past = get(st + "&filter=past&order=-sort_date")["data"]
    future = get(st + "&filter=future&order=sort_date")["data"]
    for p in past + future:
        if (p["attributes"].get("sort_date") or "")[:10] == today:
            return p
    return future[0] if future else None

def main(out):
    plan = pick_plan()
    if not plan:
        sys.exit("No plan found")
    a, pid = plan["attributes"], plan["id"]
    root = f"{BASE}/service_types/{SERVICE_TYPE}/plans/{pid}"
    items, inc = get_all(root + "/items?per_page=100&include=song,arrangement,item_notes")
    idx = {(x["type"], x["id"]): x["attributes"] for x in inc}
    def rel(it, name):
        d = ((it.get("relationships") or {}).get(name) or {}).get("data")
        return d if d else None
    out_items = []
    for it in items:
        at = it["attributes"]
        row = {"item_type": at.get("item_type"), "title": at.get("title"), "description": at.get("description"),
               "key_name": at.get("key_name"), "notes": []}
        s, ar = rel(it, "song"), rel(it, "arrangement")
        if s: row["song"] = {k: idx.get(("Song", s["id"]), {}).get(k) for k in ("author", "ccli_number", "copyright")}
        if ar: row["arrangement"] = {k: idx.get(("Arrangement", ar["id"]), {}).get(k) for k in ("name", "bpm", "meter")}
        for n in rel(it, "item_notes") or []:
            na = idx.get(("ItemNote", n["id"]), {})
            row["notes"].append({"category_name": na.get("category_name"), "content": na.get("content")})
        out_items.append(row)
    members, inc = get_all(root + "/team_members?per_page=100&include=team")
    teams = {x["id"]: x["attributes"].get("name") for x in inc if x["type"] == "Team"}
    people = []
    for m in members:
        ma = m["attributes"]
        if ma.get("status") == "D":
            continue
        t = rel(m, "team")
        people.append({"name": ma.get("name"), "team": teams.get(t["id"]) if t else None,
                       "position": ma.get("team_position_name"),
                       "status": "confirmed" if ma.get("status") == "C" else "unconfirmed"})
    data = {"options": {"show_roster": True},
            "plan": {"dates": a.get("dates"), "service_type": "Sunday Service (8:30 & 10:30)",
                     "url": f"https://services.planningcenteronline.com/plans/{pid}",
                     "theme": a.get("title") or a.get("series_title")},
            "times": [], "items": out_items, "people": people}
    json.dump(data, open(out, "w"), indent=1)
    print(f"{a.get('dates')}: {len(out_items)} items, {len(people)} people")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "input.json")
