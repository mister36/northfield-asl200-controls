#!/usr/bin/env bash
# Reset the repo to the demo starting point so the segments can be rerun.
#
#   scripts/reset_demo.sh            # dry run: show what would happen
#   scripts/reset_demo.sh --apply    # do it
#
# - closes open PRs labelled `demo-live` (live-demo output) with a comment and
#   deletes their head branches; PRs labelled `demo-backup` are left alone
# - recreates the segment branches demo/segment-{a,b,c,d} from the `demo-start` tag
# - with --reset-main, also moves main back to `demo-start` (force push; asks first)
set -euo pipefail
cd "$(dirname "$0")/.."
APPLY=0; RESET_MAIN=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --reset-main) RESET_MAIN=1 ;;
    *) echo "unknown option $a" >&2; exit 2 ;;
  esac
done
run() { if [ $APPLY = 1 ]; then echo "+ $*"; "$@"; else echo "(dry run) $*"; fi; }

git fetch --quiet --tags origin
START=$(git rev-parse --verify --quiet "refs/tags/demo-start^{commit}") || { echo "tag demo-start not found" >&2; exit 1; }
echo "demo-start = ${START:0:9}"

if command -v gh >/dev/null; then
  gh pr list --state open --label demo-live --json number,headRefName --jq '.[] | "\(.number) \(.headRefName)"' |
  while read -r num branch; do
    run gh pr close "$num" --comment "Closed by scripts/reset_demo.sh (demo reset)." --delete-branch
  done
else
  echo "gh not found: close demo-live PRs by hand"
fi

for seg in a b c d; do
  run git push --force origin "$START:refs/heads/demo/segment-$seg"
done

if [ $RESET_MAIN = 1 ]; then
  if [ "$(git rev-parse origin/main)" != "$START" ]; then
    read -r -p "Force-push main back to demo-start (${START:0:9})? [y/N] " ok
    [ "$ok" = y ] && run git push --force-with-lease=main origin "$START:refs/heads/main"
  else
    echo "main already at demo-start"
  fi
fi
echo "done"
