#!/usr/bin/env python3
"""Render docs/ from data/assets.json + data/counts.json: index.html, index.txt, assets.json,
catalog.jsonld, llms.txt, robots.txt, sitemap.xml."""
import json
import sys
import shutil, os, html, datetime
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = json.load(open(os.path.join(HERE, "data", "assets.json")))
C = json.load(open(os.path.join(HERE, "data", "counts.json")))
DOCS = os.path.join(HERE, "docs"); os.makedirs(DOCS, exist_ok=True)
HOME = A["home"]; TODAY = C.get("read", datetime.date.today().isoformat())
def fmt(n): return "—" if n is None else f"{n:,}"
def cnt(key):
    v = C["counts"].get(key, {}); return v.get("value"), v.get("stale"), v.get("source", "")

rows = []                                   # merged rows for every output
for c in A["corpora"]:
    counts = []
    for i, spec in enumerate(c["counts"]):
        v, stale, src = cnt(f"{c['id']}#{i}")
        counts.append({"label": spec["label"], "value": v, "stale": stale, "source": src, "method": spec["method"]})
    rows.append({**c, "counts": counts})
sites = []
for s in A["sites"]:
    v, stale, src = cnt(f"site:{s['name']}")
    sites.append({**s, "pages": v, "stale": stale})
repos = C.get("repos", [])
tot_records = sum(r["counts"][0]["value"] for r in rows if r["counts"] and r["counts"][0]["value"] and r["counts"][0]["label"] not in ("downloads",))
tot_downloads = sum(c["value"] or 0 for r in rows for c in r["counts"] if c["label"] == "downloads")
tot_cloners = sum(r.get("cloners_14d", 0) for r in repos); tot_clones = sum(r.get("clones_14d", 0) for r in repos)
tot_viewers = sum(r.get("viewers_14d", 0) for r in repos)
tot_pages = sum(s["pages"] or 0 for s in sites)
totals = {"corpora": len(rows), "records": tot_records, "sites": len(sites), "pages": tot_pages, "repos": len(repos),
          "clones_14d": tot_clones, "cloners_14d": tot_cloners, "viewers_14d": tot_viewers, "downloads": tot_downloads, "read": TODAY}

merged = {"title": A["title"], "one_line": A["one_line"], "byline": A["byline"], "publisher": A["publisher"], "contact": A["contact"],
          "home": HOME, "read": TODAY, "price": A["price"], "sponsor": A["sponsor"], "totals": totals, "corpora": rows, "sites": sites, "repos": repos}
json.dump(merged, open(os.path.join(DOCS, "assets.json"), "w"), ensure_ascii=False, indent=1)
# the roster every other site points at
shutil.copyfile(os.path.join(HERE, "data", "fleet.json"), os.path.join(DOCS, "fleet.json"))

# ---- JSON-LD: a DataCatalog whose parts are the corpora ----
def ds(r):
    d = {"@type": "Dataset", "name": r["name"], "description": r["what"], "url": r["where"],
         "creator": {"@type": "Person", "name": "Nan Peacock"}, "publisher": {"@type": "Organization", "name": "NaNoBotCo", "url": "https://github.com/NaNoBotCo"},
         "license": "https://creativecommons.org/licenses/by-sa/4.0/", "isAccessibleForFree": True, "dateModified": TODAY}
    if r["counts"] and r["counts"][0]["value"] is not None:
        d["size"] = f"{r['counts'][0]['value']:,} {r['counts'][0]['label']}"
    return d
ld = {"@context": "https://schema.org", "@type": "DataCatalog", "name": A["title"], "description": A["one_line"], "url": HOME,
      "creator": {"@type": "Person", "name": "Nan Peacock"}, "publisher": {"@type": "Organization", "name": "NaNoBotCo"},
      "dateModified": TODAY, "license": "https://creativecommons.org/licenses/by-sa/4.0/", "dataset": [ds(r) for r in rows]}
json.dump(ld, open(os.path.join(DOCS, "catalog.jsonld"), "w"), ensure_ascii=False, indent=1)

# ---- the text version ----
W = 78
def line(ch="-"): return ch * W
t = [A["title"].upper(), A["one_line"], f"Counted {TODAY} · {A['byline']} · {A['contact']}", line("="), "",
     "TOTALS",
     f"  corpora {totals['corpora']} · records {fmt(tot_records)} · sites {totals['sites']} · pages {fmt(tot_pages)} · repositories {totals['repos']}",
     f"  fourteen days: {fmt(tot_clones)} clones by {fmt(tot_cloners)} machines · {fmt(tot_viewers)} human viewers · dataset downloads {fmt(tot_downloads)}",
     "", "PRICE", f"  attribution: {A['price']['attribution']}", f"  commercial: {A['price']['commercial']} · {A['contact']}", "",
     "CORPORA", line()]
for r in rows:
    cs = " · ".join(f"{fmt(c['value'])} {c['label']}" + (f" (last read {c['stale']})" if c["stale"] and c["value"] is not None else "") for c in r["counts"]) or "count: not yet measured"
    t += [f"  {r['name']}", f"    {r['what']}", f"    {cs}", f"    {r['where']}", f"    provenance: {r['provenance']}", f"    licence: CC BY 4.0 · DOI: none yet", ""]
t += ["SITES", line()]
for s in sites:
    t.append(f"  {s['name']:26s} {fmt(s['pages']):>8} pages   {s['note']}   {s['url']}")
t += ["", "REPOSITORIES — fourteen days of traffic", line()]
for r in repos:
    t.append(f"  {r['name']:32s} {fmt(r.get('cloners_14d')):>5} machines · {fmt(r.get('clones_14d')):>5} clones · {fmt(r.get('viewers_14d')):>3} viewers · {r.get('license') or '—'}")
t += ["", line("="), f"Machine copies: {HOME}assets.json · {HOME}catalog.jsonld · {HOME}llms.txt",
      f"Contact: Nan · {A['contact']} · Sponsor: {A['sponsor']['ko_fi']} · {A['sponsor']['patreon']}"]
open(os.path.join(DOCS, "index.txt"), "w").write("\n".join(t) + "\n")

# ---- llms.txt ----
l = [f"# {A['title']}", "", f"> {A['one_line']} Counted {TODAY}. {A['byline']}.", "",
     f"- Machine copy (JSON): {HOME}assets.json", f"- Catalog (JSON-LD): {HOME}catalog.jsonld", f"- Text: {HOME}index.txt", "",
     "## Corpora", ""]
for r in rows:
    c0 = f"{fmt(r['counts'][0]['value'])} {r['counts'][0]['label']}" if r["counts"] else "count not yet measured"
    l.append(f"- [{r['name']}]({r['where']}): {r['what']}. {c0}.")
l += ["", "## Sites", ""] + [f"- [{s['name']}]({s['url']}): {s['note']}" for s in sites]
l += ["", "## Repositories", ""] + [f"- [{r['name']}]({r['url']}): {r['description'] or ''}".rstrip(": ") for r in repos]
l += ["", "## Terms", "", f"Attribution: {A['price']['attribution']}. Commercial use: {A['price']['commercial']} Questions to {A['contact']}."]
open(os.path.join(DOCS, "llms.txt"), "w").write("\n".join(l) + "\n")

# ---- HTML ----
E = html.escape
def th(*cells): return "<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>"
def td(*cells): return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
corp = ""
for r in rows:
    cs = "<br>".join(f"<b>{fmt(c['value'])}</b> {E(c['label'])}" + (f" <small>last read {c['stale']}</small>" if c["stale"] and c["value"] is not None else "") for c in r["counts"]) or "<small>not yet measured</small>"
    corp += td(f"<a href=\"{E(r['where'])}\">{E(r['name'])}</a><br><small>{E(r['what'])}</small>", cs, f"<small>{E(r['provenance'])}</small>", "CC BY 4.0<br><small>DOI: none yet</small>")
site_rows = "".join(td(f"<a href=\"{E(s['url'])}\">{E(s['name'])}</a>", fmt(s["pages"]), E(s["note"])) for s in sites)
repo_rows = "".join(td(f"<a href=\"{E(r['url'])}\">{E(r['name'])}</a>" + (f" · <a href=\"{E(r['pages'])}\">site</a>" if r.get("pages") else ""), fmt(r.get("cloners_14d")), fmt(r.get("clones_14d")), fmt(r.get("viewers_14d")), E(r.get("license") or "—"), f"<small>{E(r['description'])}</small>") for r in repos)
page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(A['title'])} — NaNoBotCo</title>
<meta name="description" content="{E(A['one_line'])}">
<meta name="citation_title" content="{E(A['title'])}"><meta name="citation_author" content="{E(A['byline'])}"><meta name="citation_publication_date" content="{TODAY}"><meta name="DC.publisher" content="NaNoBotCo">
<link rel="alternate" type="application/json" href="assets.json"><link rel="alternate" type="application/ld+json" href="catalog.jsonld"><link rel="alternate" type="text/plain" href="index.txt">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>
:root{{--bg:#fbf8f2;--ink:#1d1a16;--mute:#6b645a;--rule:#e2dccf;--gold:#b8860b;--link:#8a4b08}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16140f;--ink:#efe9dc;--mute:#a59c8c;--rule:#3a352c;--gold:#e0b04a;--link:#f0c070}}}}
html{{background:var(--bg);color:var(--ink);font:19px/1.55 Georgia,"Noto Serif",serif}}
body{{margin:0 auto;max-width:72rem;padding:2rem 1.2rem 4rem}}
h1{{font-size:2.6rem;margin:0 0 .2rem;letter-spacing:.01em}} h2{{font-size:1.4rem;margin:2.6rem 0 .6rem;border-bottom:2px solid var(--gold);padding-bottom:.2rem}}
p.lead{{font-size:1.25rem;margin:.2rem 0 1rem}} .meta{{color:var(--mute)}}
a{{color:var(--link)}} small{{color:var(--mute);font-size:.85rem}}
.totals{{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:.8rem;margin:1.2rem 0}}
.totals div{{border:1px solid var(--rule);border-top:3px solid var(--gold);padding:.6rem .8rem}} .totals b{{display:block;font-size:1.7rem}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:1rem}} th,td{{text-align:left;vertical-align:top;padding:.55rem .6rem;border-bottom:1px solid var(--rule)}} th{{color:var(--mute);font-weight:normal}}
td:nth-child(2){{white-space:nowrap}} footer{{margin-top:3rem;color:var(--mute);font-size:.95rem}}
</style></head><body>
<h1>{E(A['title'])}</h1>
<p class="lead">{E(A['one_line'])}</p>
<p class="meta">Counted {TODAY} · {E(A['byline'])} · <a href="index.txt">text</a> · <a href="assets.json">JSON</a> · <a href="catalog.jsonld">JSON-LD</a> · <a href="fleet.json">fleet.json</a> · <a href="llms.txt">llms.txt</a> · <a href="https://github.com/NaNoBotCo/index">source</a></p>
<div class="totals">
<div><b>{fmt(tot_records)}</b>records in {totals['corpora']} corpora</div><div><b>{fmt(tot_pages)}</b>pages on {totals['sites']} sites</div><div><b>{totals['repos']}</b>public repositories</div>
<div><b>{fmt(tot_cloners)}</b>machines cloned, 14 days</div><div><b>{fmt(tot_clones)}</b>clones, 14 days</div><div><b>{fmt(tot_viewers)}</b>human viewers, 14 days</div><div><b>{fmt(tot_downloads)}</b>dataset downloads</div>
</div>
<h2>Price</h2>
<p><b>Attribution:</b> {E(A['price']['attribution'])}.<br><b>Commercial use:</b> {E(A['price']['commercial'])} Write to <a href="mailto:{E(A['contact'])}">{E(A['contact'])}</a>.</p>
<h2>Corpora</h2>
<div class="wrap"><table>{th("what", "count", "provenance", "licence")}{corp}</table></div>
<h2>Sites</h2>
<div class="wrap"><table>{th("site", "pages in sitemap", "note")}{site_rows}</table></div>
<h2>Repositories</h2>
<p class="meta">Fourteen days of GitHub traffic, read the day of the count. A machine is a distinct cloning address; a viewer is a distinct browser.</p>
<div class="wrap"><table>{th("repository", "machines", "clones", "viewers", "licence", "")}{repo_rows}</table></div>
<footer>Contact: Nan · <a href="mailto:{E(A['contact'])}">{E(A['contact'])}</a> · Sponsor: <a href="{A['sponsor']['ko_fi']}">Ko-fi</a> · <a href="{A['sponsor']['patreon']}">Patreon</a><br>
Counts come from the sources named in <a href="assets.json">assets.json</a>; a bot re-reads them nightly. A count that did not answer keeps its last value and the date it was last read.</footer>
</body></html>
"""
open(os.path.join(DOCS, "index.html"), "w").write(page)
sys.path.insert(0, os.path.join(HERE, "tools"))
import fleet  # noqa: E402
_R = fleet.load(os.path.join(HERE, "data", "fleet.json"))
open(os.path.join(DOCS, "robots.txt"), "w").write(
    f"User-agent: *\nAllow: /\nSitemap: {HOME}sitemap.xml\n\n"
    + fleet.MARK + "\n" + fleet.robots_lines("index", roster=_R))
open(os.path.join(DOCS, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{HOME}{p}</loc><lastmod>{TODAY}</lastmod></url>\n" for p in ["", "index.txt", "assets.json", "catalog.jsonld", "llms.txt", "fleet.json"]) + "</urlset>\n")
open(os.path.join(DOCS, ".nojekyll"), "w").write("")
print(f"built · records {fmt(tot_records)} · pages {fmt(tot_pages)} · repos {len(repos)} · cloners {fmt(tot_cloners)} · downloads {fmt(tot_downloads)}")
