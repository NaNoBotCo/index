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
    "mhs-loop": "mae-hong-son-loop",
    "muay-thai": "muay-thai",
    "chiang-mai-roads": "chiang-mai-roads",
    "carolina-barbecue": "carolina-barbecue",
    "buffalo-wings": "buffalo-wings",
    "pink-box": "pink-box",
    "pinot-noir": "pinot-noir",
    "medical-tourism": "care-abroad",
    "amulet-atlas": "amulet-atlas",
    "basque-tables": "basque-tables",
    "hand-poke": "hand-poke",
    "black-holes": "black-holes",
    "quantum-computing": "quantum-computing",
    "three-body": "three-body",
    "goin-fast": "goin-fast",
}

CSS = ('.fleet{margin:.6rem 0 0;line-height:1.9}.fleet a{margin-right:.55rem;white-space:nowrap}'
       '.support{margin:.45rem 0 0}.support a{margin-right:.5rem}')


def patch(repo: Path, sid: str, check: bool) -> list[str]:
    # Most repos build their pages in tools/site.py; the drawn ones (three-body,
    # quantum-computing) do it in tools/build.py. A repo with neither takes the roster
    # files and no patch.
    done = []
    for name in ("site.py", "build.py"):
        sp = repo / "tools" / name
        if sp.is_file():
            break
    else:
        return ["roster copied, no page builder to patch"]
    src = old = sp.read_text(encoding="utf-8")

    if "import fleet" not in src:
        src = re.sub(r"(?m)^(import os\b.*)$", r"\1\n\nimport fleet", src, count=1)
        done.append("import")

    if ".fleet{" not in src:
        # the anchor only exists in the repos whose stylesheet lives in site.py; the
        # rest keep theirs in tools/css.py, and reporting "css" for them read as a
        # change that was not made
        after = src.replace('.bots a{margin-right:.7rem}', '.bots a{margin-right:.7rem}' + CSS, 1)
        if after != src:
            src = after
            done.append("css")

    if "fleet.row_html" not in src:
        src = src.replace("\n</footer>", '\n{fleet.row_html("%s")}\n</footer>' % sid, 1)
        done.append("footer")

    if "fleet.support_html" not in src:
        src = src.replace('{fleet.row_html("%s")}' % sid,
                          '{fleet.row_html("%s")}\n{fleet.support_html()}' % sid, 1)
        done.append("sponsor")

    # The studio byline, in the footer beside the sponsor line. Client asked for it on
    # 2026-09-19: these sites are all built at hongdam.net in Chiang Rai and should say so.
    # It takes the `support` class, so no stylesheet in any repo has to change.
    if "fleet.maker_html" not in src:
        for call in ('{fleet.support_html(roster=ROSTER)}', '{fleet.support_html()}'):
            if call in src:
                arg = "roster=ROSTER, " if "ROSTER" in call else ""
                # Only the bilingual sites have a `lang` in scope at the footer. Read
                # it off page()'s own signature, not off whether the word appears
                # somewhere above — "<html lang=\"en\">" is not a variable.
                sig = re.search(r"(?ms)^def page\((.*?)\)\s*(?:->[^:]*)?:", src)
                lang = "lang=lang" if sig and re.search(r"\blang\b\s*[:=,)]", sig.group(1)) else ""
                sep = ", " if arg and lang else ""
                src = src.replace(call, call + "\n{fleet.maker_html(%s%s%s)}" % (arg, sep, lang), 1)
                done.append("maker")
                break

    if "fleet.publisher_ld" not in src and '"creator": AUTHOR,' in src:
        src = src.replace('"creator": AUTHOR,',
                          '"creator": AUTHOR, "publisher": fleet.publisher_ld(), "includedInDataCatalog": fleet.catalog_ld(),', 1)
        done.append("json-ld")

    if "fleet.decorate" not in src:
        m = re.search(r'(?m)^(\s*)\(SITE / "llms\.txt"\)\.write_text\(', src)
        if m:
            ind = m.group(1)
            # after the last top-level write in that block, before the closing report
            anchor = re.search(r'(?m)^%s\(SITE / "humans\.txt"\)\.write_text\(' % re.escape(ind), src) or \
                     re.search(r'(?m)^%s\(SITE / "llms\.txt"\)\.write_text\(' % re.escape(ind), src)
            # Walk to the end of that call before inserting. Matching the first line
            # alone put the new statement INSIDE a multi-line write_text( … ) and left
            # the repository with a site.py that would not parse (goin-fast, 2026-09-22).
            at, depth = anchor.end() - 1, 0
            while at < len(src):
                if src[at] == "(":
                    depth += 1
                elif src[at] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                at += 1
            at = src.find("\n", at) + 1
            src = src[:at] + f'{ind}fleet.decorate(SITE, "{sid}")\n' + src[at:]
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
    # Names after the flags narrow the run to those repositories. A roster change that
    # only some sites are being rebuilt for should not leave the others dirty.
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    for name, sid in TARGETS.items():
        if want and name not in want:
            continue
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
