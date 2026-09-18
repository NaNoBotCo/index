# The index

Everything NaNoBotCo holds, counted once, at one address: https://nanobotco.github.io/index/

A row per corpus, site and repository: what it is, how many, where it lives, its provenance, its licence, and the price (share-alike free; commercial licence by contact). The same count is served as HTML, text, JSON, JSON-LD and llms.txt.

- `data/assets.json` — the rows and, for each count, the source it is read from.
- `tools/count.py` — reads every source and writes `data/counts.json`. A source that does not answer keeps its last value, marked with the date it was last read.
- `tools/build.py` — renders `docs/`.
- `nightly.sh` — count, build, commit, push, through the fleet's push lane.

```
python3 tools/count.py && python3 tools/build.py
```

Standard library only. GitHub traffic needs `gh` signed in as the account.

---

Contact: Nan · nan@motdang.net · Sponsor: [Ko-fi](https://ko-fi.com/defiantchiangmai) · [Patreon](https://www.patreon.com/nanobotco)
