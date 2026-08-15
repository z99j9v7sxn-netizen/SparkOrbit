#!/usr/bin/env bash
set -uo pipefail
ROOT="/opt/sparkorbit/资料"
files=(
  "$ROOT/课本/计算机组成与系统结构-第3版-袁春风.pdf"
  "$ROOT/课本/高等数学第8版上册.pdf"
  "$ROOT/课本/高等数学第8版下册.pdf"
  "$ROOT/课本/工程数学 线性代数 第七版 同济大学.pdf"
)
for path in "${files[@]}"; do
  [ -f "$path" ] || { echo "MISSING $path"; continue; }
  tmp="${path}.linretry"
  echo "RETRY $path"
  set +e
  qpdf --linearize --object-streams=generate "$path" "$tmp"
  code=$?
  set -e
  # 0=ok, 3=warnings but output written
  if [ "$code" -eq 0 ] || [ "$code" -eq 3 ]; then
    if [ -f "$tmp" ]; then
      mv -f "$tmp" "$path"
      echo "OK code=$code $path"
    else
      echo "NO_OUT code=$code $path"
    fi
  else
    echo "FAIL code=$code $path"
    rm -f "$tmp"
  fi
done
echo DONE_RETRY
