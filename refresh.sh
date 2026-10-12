#!/bin/zsh
# Re-counts commits and Claude Code use, redraws the SVGs, and pushes if anything changed.
# Run from anywhere: zsh ~/Developer/josh-botha/refresh.sh
set -e
cd "${0:A:h}"
[[ -x .venv/bin/python ]] || { python3 -m venv .venv && .venv/bin/pip install -q fonttools brotli; }
.venv/bin/python scripts/activity.py
.venv/bin/python scripts/render.py
if git diff --quiet; then echo "Nothing changed."; exit 0; fi
git add README.md assets data
git commit -qm "Refresh activity $(date +%Y-%m-%d)"
git push -q origin main
echo "Pushed. github.com/josh-botha updates in a minute or two."
