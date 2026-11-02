#!/usr/bin/env python3
"""Zone traffic — what the edge served, per domain, per day.

    python3 tools/zones.py          # last 3 days, upserted into the ledger
    python3 tools/zones.py 14       # backfill fourteen days
    python3 tools/zones.py 3 --show # and print the ledger's tail

WHERE THE NUMBERS COME FROM
Cloudflare's own zone analytics (httpRequests1dGroups), read for every zone on
the account. Nothing is added to any page and nothing is asked of a reader:
these are counts the edge already keeps of requests it already served.

THE CREDENTIAL
Wrangler's OAuth token, through cfauth.py, which refreshes it by running
`wrangler whoami`. The fleet API token in keys.json carries Account Analytics
Read, which is what the Analytics Engine SQL API wants; zone analytics wants
Zone Analytics Read, which it does not carry. Nothing needs minting — the
go/ab-plan line "the Cloudflare token cannot read zone analytics" was true of
that token only.

WHAT THE NUMBERS ARE
requests   every request the edge answered, bots included
pageviews  Cloudflare's own count of requests that looked like a page
uniques    distinct client IPs, bots included. Not people.
Today's row is the day so far and is rewritten on each run.

PEOPLE (added 2026-11-02, ~/.claude/state/people.tsv: date, host, views, visits)
Cloudflare Web Analytics, read per host. Its script runs only in a browser that
runs the page, motdang.net and hongdam.net keep it off pages their classifier
files as a machine or as ours, and NOT_PEOPLE drops headless Chrome and desktop
browsers Cloudflare cannot name, so visits here are the nearest count of people. It samples one page load in ten and scales up: under ~50 is rough.
Read with the fleet token in keys.json (Account Analytics Read).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, "/Users/annikapeacock/Developer/claude code projects/manuscript-crawler/crawler")
import cfauth  # noqa: E402

LEDGER = os.path.expanduser("~/.claude/state/traffic.tsv")
PEOPLE = os.path.expanduser("~/.claude/state/people.tsv")
PEOPLE_HEAD = "# date\thost\tviews\tvisits\n"
KEYS = os.path.expanduser("~/.config/nanobotco/keys.json")
API = "https://api.cloudflare.com/client/v4"
HEAD = "# date\tzone\trequests\tpageviews\tuniques\n"

QUERY = """query($zone:String!,$s:Date!,$e:Date!){viewer{zones(filter:{zoneTag:$zone}){
httpRequests1dGroups(limit:60,filter:{date_geq:$s,date_leq:$e},orderBy:[date_ASC]){
dimensions{date} sum{requests pageViews} uniq{uniques}}}}}"""


def get(url: str, token: str):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(req, timeout=40))


def graphql(token: str, zone: str, start: dt.date, end: dt.date):
    body = json.dumps({"query": QUERY, "variables": {
        "zone": zone, "s": start.isoformat(), "e": end.isoformat()}}).encode()
    req = urllib.request.Request(
        f"{API}/graphql", data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=40))
        except Exception as e:  # 429 under a burst of zones; back off and retry
            if "429" in str(e) and attempt < 3:
                time.sleep(6 * (attempt + 1))
                continue
            raise


def load() -> dict:
    """(date, zone) -> row, so a re-read of a day replaces it."""
    rows = {}
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) == 5:
                rows[(p[0], p[1])] = p
    return rows


def save(rows: dict) -> None:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as fh:
        fh.write(HEAD)
        for key in sorted(rows):
            fh.write("\t".join(rows[key]) + "\n")


def main() -> None:
    days = 3
    for a in sys.argv[1:]:
        if a.isdigit():
            days = int(a)
    end = dt.date.today()
    start = end - dt.timedelta(days=days - 1)
    token = cfauth.token()

    zones = [(z["name"], z["id"]) for z in get(f"{API}/zones?per_page=50", token)["result"]]
    rows = load()
    read = skipped = 0
    for name, zid in sorted(zones):
        try:
            d = graphql(token, zid, start, end)
        except Exception as e:
            print(f"  {name}: {str(e)[:90]}", file=sys.stderr)
            skipped += 1
            continue
        if d.get("errors"):
            print(f"  {name}: {str(d['errors'][0].get('message'))[:90]}", file=sys.stderr)
            skipped += 1
            continue
        for g in d["data"]["viewer"]["zones"][0]["httpRequests1dGroups"]:
            day = g["dimensions"]["date"]
            rows[(day, name)] = [day, name, str(g["sum"]["requests"]),
                                 str(g["sum"]["pageViews"]), str(g["uniq"]["uniques"])]
            read += 1
        time.sleep(1.5)
    save(rows)
    print(f"zones: {len(zones)} read, {skipped} refused · {read} zone-days · {LEDGER}")
    try:
        people(start, end)
    except Exception as e:  # the edge count above is already saved
        print(f"people: skipped ({str(e)[:90]})", file=sys.stderr)

    if "--show" in sys.argv:
        today = end.isoformat()
        print(f"\n{today}")
        for (day, name), r in sorted(rows.items()):
            if day == today:
                print(f"  {name:<24} {int(r[2]):>9,} req · {int(r[3]):>8,} pv · {int(r[4]):>7,} uniq")


PEOPLE_QUERY = """query($a:String!,$d:Date!){viewer{accounts(filter:{accountTag:$a}){
rumPageloadEventsAdaptiveGroups(limit:2000,filter:{date:$d},orderBy:[count_DESC]){
count sum{visits} dimensions{requestHost userAgentBrowser deviceType}}}}}"""
# Not people: headless Chrome (our own test runs show here, 1,340 Thai visits on
# 19 Oct–1 Nov) and a desktop browser Cloudflare cannot name (wichaa.net's US and
# Singapore script runners, 1,550 visits; Thai readers showed none on desktop).
NOT_PEOPLE = {("ChromeHeadless", "desktop"), ("ChromeHeadless", "mobile"), ("Unknown", "desktop")}


def people(start: dt.date, end: dt.date) -> None:
    """Web Analytics views and visits per host, one day per query (finer sampling)."""
    cf = json.load(open(KEYS))["cloudflare"]
    rows = {}
    if os.path.exists(PEOPLE):
        for line in open(PEOPLE, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if not line.startswith("#") and len(p) == 4:
                rows[(p[0], p[1])] = p
    day, n = start, 0
    while day <= end:
        body = json.dumps({"query": PEOPLE_QUERY, "variables": {"a": cf["account_id"], "d": day.isoformat()}}).encode()
        req = urllib.request.Request(f"{API}/graphql", data=body, headers={
            "Authorization": f"Bearer {cf['api_token']}", "Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=40))
        if d.get("errors"):
            raise RuntimeError(str(d["errors"][0].get("message")))
        for k in [k for k in rows if k[0] == day.isoformat()]:
            del rows[k]
        tally = {}
        for g in d["data"]["viewer"]["accounts"][0]["rumPageloadEventsAdaptiveGroups"]:
            dim = g["dimensions"]
            if not dim["requestHost"] or (dim["userAgentBrowser"], dim["deviceType"]) in NOT_PEOPLE:
                continue
            v = tally.setdefault(dim["requestHost"], [0, 0])
            v[0] += g["count"]
            v[1] += g["sum"]["visits"]
        for host, (views, vis) in tally.items():
            rows[(day.isoformat(), host)] = [day.isoformat(), host, str(views), str(vis)]
            n += 1
        day += dt.timedelta(days=1)
    with open(PEOPLE, "w", encoding="utf-8") as fh:
        fh.write(PEOPLE_HEAD)
        for key in sorted(rows):
            fh.write("\t".join(rows[key]) + "\n")
    print(f"people: {n} host-days · {PEOPLE}")


if __name__ == "__main__":
    main()
