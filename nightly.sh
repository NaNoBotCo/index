#!/bin/zsh
# The index, nightly: count, build, commit, push through the fleet's push lane.
set -u
cd "${0:A:h}" || exit 1
# The edge count first: it writes outside the repo (~/.claude/state/traffic.tsv)
# and must not stop the nightly if Cloudflare is slow or the login has lapsed.
/usr/bin/python3 tools/zones.py || echo "zones: skipped"
/usr/bin/python3 tools/count.py || exit 1
/usr/bin/python3 tools/build.py || exit 1
# STATE.txt reads the traffic ledger; rebuild it before the early exit below.
/usr/bin/python3 "$HOME/.claude/bin/state.py" >/dev/null || true
git add -A
git diff --cached --quiet && { echo "nothing changed"; exit 0; }
git commit -q -m "Nightly count $(date +%F)" || exit 1
/usr/bin/python3 "/Users/annikapeacock/Developer/claude code projects/bot-tower/tower.py" wrap github-push --patience 30 -- "$HOME/.claude/bin/pr-push" . "Nightly count $(date +%F)"
