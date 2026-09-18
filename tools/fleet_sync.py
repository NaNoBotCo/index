#!/usr/bin/env python3
"""Install the roster into every repository that shows it.

Copies data/fleet.json and tools/fleet.py, then patches tools/site.py in one place each:
the footer row, the stylesheet, the homepage JSON-LD publisher, and one decorate() call
that adds the roster to llms.txt, ai.txt, robots.txt and humans.txt at the end of a build.

Run from the index repository:  python3 tools/fleet_sync.py [--check]
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleet  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent

# repo directory -> id in data/fleet.json
TARGETS = {
    "carolina-barbecue": "carolina-barbecue",
    "buffalo-wings": "buffalo-wings",
    "pink-box": "pink-box",
    "pinot-noir": "pinot-noir",
    "medical-tourism": "care-abroad",
    "amulet-atlas": "amulet-atlas",
    "basque-tables": "basque-tables",
}

CSS = ('.fleet{margin:.6rem 0 0;line-height:1.9}.fleet a{margin-right:.55rem;white-space:nowrap}'
       '.support{margin:.45rem 0 0}.support a{margin-right:.5rem}')


def patch(repo: Path, sid: str, check: bool) -> list[str]:
    done, sp = [], repo / "tools" / "site.py"
    src = old = sp.read_text(encoding="utf-8")

    if "import fleet" not in src:
        src = re.sub(r"(?m)^(import os\b.*)$", r"\1\n\nimport fleet", src, count=1)
        done.append("import")

    if ".fleet{" not in src:
        src = src.replace('.bots a{margin-right:.7rem}', '.bots a{margin-right:.7rem}' + CSS, 1)
        done.append("css")

    if "fleet.row_html" not in src:
        src = src.replace("\n</footer>", '\n{fleet.row_html("%s")}\n</footer>' % sid, 1)
        done.append("footer")

    if "fleet.support_html" not in src:
        src = src.replace('{fleet.row_html("%s")}' % sid,
                          '{fleet.row_html("%s")}\n{fleet.support_html()}' % sid, 1)
        done.append("sponsor")

    if "fleet.publisher_ld" not in src and '"creator": AUTHOR,' in src:
        src = src.replace('"creator": AUTHOR,',
                          '"creator": AUTHOR, "publisher": fleet.publisher_ld(), "includedInDataCatalog": fleet.catalog_ld(),', 1)
        done.append("json-ld")

    if "fleet.decorate" not in src:
        m = re.search(r'(?m)^(\s*)\(SITE / "llms\.txt"\)\.write_text\(', src)
        if m:
            ind = m.group(1)
            # after the last top-level write in that block, before the closing report
            anchor = re.search(r'(?m)^%s\(SITE / "humans\.txt"\)\.write_text\(.*\n' % re.escape(ind), src) or \
                     re.search(r'(?m)^%s\(SITE / "llms\.txt"\)\.write_text\(.*\n' % re.escape(ind), src)
            src = src[:anchor.end()] + f'{ind}fleet.decorate(SITE, "{sid}")\n' + src[anchor.end():]
            done.append("decorate")

    if src != old and not check:
        sp.write_text(src, encoding="utf-8")
    return done


README_MARK = "<!-- fleet-roster -->"


def patch_readme(repo: Path, sid: str, check: bool) -> str:
    """One roster block per README, so a clone carries the list of the others."""
    hit = []
    for name in ("README.md", "README.txt"):
        f = repo / name
        if not f.exists():
            continue
        cur = f.read_text(encoding="utf-8")
        body = fleet.readme_lines(sid)
        if name.endswith(".txt"):
            body = body.replace("## ", "").replace("- [", "- ").replace("](", " — ").replace(")", "")
        block = README_MARK + "\n\n" + body.rstrip() + "\n"
        new = (cur.split(README_MARK)[0].rstrip() + "\n\n" + block) if README_MARK in cur else (cur.rstrip() + "\n\n" + block)
        if new != cur:
            if not check:
                f.write_text(new, encoding="utf-8")
            hit.append(name)
    return ", ".join(hit)


def main() -> int:
    check = "--check" in sys.argv
    for name, sid in TARGETS.items():
        repo = ROOT / name
        if not repo.is_dir():
            print(f"{name:20} MISSING"); continue
        if not check:
            (repo / "data").mkdir(exist_ok=True)
            shutil.copy2(HERE / "data" / "fleet.json", repo / "data" / "fleet.json")
            shutil.copy2(HERE / "tools" / "fleet.py", repo / "tools" / "fleet.py")
        done = patch(repo, sid, check)
        r = patch_readme(repo, sid, check)
        print(f"{name:20} {', '.join(done) or 'site.py current'}" + (f" · {r}" if r else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
