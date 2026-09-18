#!/bin/zsh
# The index, nightly: count, build, commit, push through the fleet's push lane.
set -u
cd "${0:A:h}" || exit 1
/usr/bin/python3 tools/count.py || exit 1
/usr/bin/python3 tools/build.py || exit 1
git add -A
git diff --cached --quiet && { echo "nothing changed"; exit 0; }
git commit -q -m "Nightly count $(date +%F)" || exit 1
/usr/bin/python3 "/Users/annikapeacock/Developer/claude code projects/bot-tower/tower.py" wrap github-push --patience 30 -- git push -q origin HEAD
