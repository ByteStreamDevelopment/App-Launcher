#!/usr/bin/env bash
# Leitet versionName und versionCode aus einem Release-Tag ab (für GitHub- und Forgejo-Workflows).
#   v2.1.3        -> 2.1.3       / 2010300
#   v2.2.0-beta3  -> 2.2.0-beta3 / 2019934   (alpha < beta < rc < fertige Version, steigt immer)
# Ausgabe: name=… und code=… (für $GITHUB_OUTPUT)
set -euo pipefail
TAG="${1:?Tag fehlt}"
NAME="${TAG#v}"; NAME="${NAME#V}"
IFS='.-' read -r MAJ MIN PAT REST <<< "$NAME"
MIN="${MIN:-0}"; PAT="${PAT:-0}"
for n in "$MAJ" "$MIN" "$PAT"; do
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "::error::Tag $TAG ist keine Version wie v2.1.0" >&2; exit 1; }
done
CODE=$(( 10#$MAJ * 1000000 + 10#$MIN * 10000 + 10#$PAT * 100 ))
if [ -n "${REST:-}" ]; then
  PRE=$(echo "$REST" | grep -o '[0-9]*$' || true); PRE=${PRE:-0}; PRE=$(( 10#$PRE > 28 ? 28 : 10#$PRE ))
  case "${REST,,}" in
    rc*) STAGE=60 ;;
    beta*|b[0-9]*) STAGE=30 ;;
    *) STAGE=0 ;;
  esac
  CODE=$(( CODE - 100 + STAGE + PRE + 1 ))
fi
echo "name=$NAME"
echo "code=$CODE"
