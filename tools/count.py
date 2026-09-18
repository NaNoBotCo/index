#!/usr/bin/env python3
"""Count everything in data/assets.json from its named source and write data/counts.json.
A source that does not answer keeps its last count, marked stale with the date it was last read."""
import json, os, re, sqlite3, subprocess, sys, datetime, urllib.request, concurrent.futures as cf
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = json.load(open(os.path.join(HERE, "data", "assets.json")))
OUT = os.path.join(HERE, "data", "counts.json")
TODAY = datetime.date.today().isoformat()
prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
UA = {"User-Agent": "Mozilla/5.0 (NaNoBotCo index counter; nan@motdang.net)"}

def fetch(url, timeout=40):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode("utf-8", "replace")
def num(s): return int(str(s).replace(",", ""))

def count(spec):
    m = spec["method"]
    if m == "html_regex":
        hits = re.findall(spec["regex"], fetch(spec["url"])); return max(num(h) for h in hits)
    if m == "sitemap":
        return len(re.findall(r"<loc>", fetch(spec["url"])))
    if m == "json_key":
        return num(json.loads(fetch(spec["url"]))[spec["key"]])
    if m == "json_len":
        d = json.loads(fetch(spec["url"])); return len(d if isinstance(d, list) else d[spec.get("key", "places")])
    if m == "jsonl_lines":
        return sum(1 for ln in fetch(spec["url"]).splitlines() if ln.strip())
    if m == "hf_rows":
        d = json.loads(fetch(f"https://datasets-server.huggingface.co/size?dataset={spec['dataset']}"))
        n = d["size"]["dataset"]["num_rows"]
        if not n: raise ValueError("no row count served")
        return n
    if m == "hf_downloads":
        return num(json.loads(fetch(f"https://huggingface.co/api/datasets/{spec['dataset']}"))["downloads"])
    if m == "sqlite":
        con = sqlite3.connect(f"file:{spec['path']}?mode=ro", uri=True, timeout=10)
        try: return con.execute(spec["sql"]).fetchone()[0]
        finally: con.close()
    if m == "local_json_len":
        return sum(len(json.load(open(p))) for p in spec["paths"])
    if m == "local_json_key":
        return sum(num(json.load(open(p))[spec["key"]]) for p in spec["paths"])
    if m == "local_geojson_features":
        return sum(len(json.load(open(p))["features"]) for p in spec["paths"])
    raise ValueError("unknown method " + m)

def read(key, spec):
    old = prev.get("counts", {}).get(key, {})
    try:
        n = count(spec); return key, {"value": n, "read": TODAY, "method": spec["method"], "source": spec.get("url") or spec.get("dataset") or spec.get("path") or ", ".join(spec.get("paths", []))}
    except Exception as e:
        o = dict(old); o["stale"] = TODAY; o["error"] = str(e)[:120]
        if "value" not in o: o["value"] = None
        o.setdefault("method", spec["method"]); o.setdefault("source", spec.get("url") or spec.get("dataset") or spec.get("path") or "")
        return key, o

jobs = []
for c in ASSETS["corpora"]:
    for i, spec in enumerate(c["counts"]):
        jobs.append((f"{c['id']}#{i}", spec))
for s in ASSETS["sites"]:
    jobs.append((f"site:{s['name']}", {"method": "sitemap", "url": s["url"].rstrip("/") + "/sitemap.xml"}))
counts = {}
with cf.ThreadPoolExecutor(8) as ex:
    for key, res in ex.map(lambda j: read(*j), jobs):
        counts[key] = res

# repositories: the account's public repos, their licence, and fourteen days of traffic
repos = []
try:
    lst = json.loads(subprocess.run(["gh", "api", "users/NaNoBotCo/repos?per_page=100&type=owner"], capture_output=True, text=True, check=True).stdout)
    for r in sorted(lst, key=lambda x: x["name"].lower()):
        if r["private"] or r["archived"] or r["fork"]: continue
        row = {"name": r["name"], "url": r["html_url"], "description": r.get("description") or "", "pushed": r["pushed_at"][:10],
               "pages": f"https://nanobotco.github.io/{r['name']}/" if r.get("has_pages") else None, "license": (r.get("license") or {}).get("spdx_id")}
        try:
            t = json.loads(subprocess.run(["gh", "api", f"repos/NaNoBotCo/{r['name']}/traffic/clones"], capture_output=True, text=True, check=True).stdout)
            row["clones_14d"], row["cloners_14d"] = t.get("count", 0), t.get("uniques", 0)
            v = json.loads(subprocess.run(["gh", "api", f"repos/NaNoBotCo/{r['name']}/traffic/views"], capture_output=True, text=True, check=True).stdout)
            row["views_14d"], row["viewers_14d"] = v.get("count", 0), v.get("uniques", 0)
        except Exception as e:
            row["traffic_error"] = str(e)[:80]
        repos.append(row)
except Exception as e:
    repos = prev.get("repos", []); print("repos: kept previous list:", str(e)[:100], file=sys.stderr)

json.dump({"read": TODAY, "counts": counts, "repos": repos}, open(OUT, "w"), ensure_ascii=False, indent=1)
fresh = sum(1 for v in counts.values() if "stale" not in v); stale = len(counts) - fresh
print(f"counts: {fresh} read today, {stale} stale · repos: {len(repos)}")
for k, v in counts.items():
    if "stale" in v: print("  stale:", k, v.get("error"))
