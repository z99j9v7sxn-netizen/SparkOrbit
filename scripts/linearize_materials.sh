#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/sparkorbit/资料"
BAK="$ROOT/_bak"
mkdir -p "$BAK"

find "$ROOT" -type f -name '*.pdf' ! -path '*/_bak/*' -printf '%s\t%p\n' | sort -nr | while IFS=$'\t' read -r sz path; do
  if [ "$sz" -lt 5000000 ]; then
    echo "SKIP_SMALL $sz $path"
    continue
  fi
  lin_info=$(qpdf --json --json-key=linearized "$path" 2>/dev/null | tr -d '\n' || true)
  if echo "$lin_info" | grep -q '"linearized": *true'; then
    echo "ALREADY_LIN $path"
    continue
  fi
  echo "LINEARIZE_START $(date +%H:%M:%S) $sz $path"
  tmp="${path}.lin.$$"
  set +e
  qpdf --linearize --object-streams=generate "$path" "$tmp"
  code=$?
  set -e
  # qpdf: 0=ok, 3=succeeded with warnings
  if { [ "$code" -eq 0 ] || [ "$code" -eq 3 ]; } && [ -f "$tmp" ]; then
    base=$(basename "$path")
    if [ ! -f "$BAK/$base" ]; then
      cp --update=none "$path" "$BAK/$base" 2>/dev/null || cp "$path" "$BAK/$base" || true
    fi
    mv -f "$tmp" "$path"
    echo "LINEARIZE_OK $(date +%H:%M:%S) code=$code $path"
  else
    echo "LINEARIZE_FAIL code=$code $path"
    rm -f "$tmp"
  fi
done
echo DONE_ALL
