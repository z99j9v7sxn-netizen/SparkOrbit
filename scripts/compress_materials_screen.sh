#!/usr/bin/env bash
# 第二轮：对仍 >40MB 的阅读 PDF 用 /screen 再压（约 72dpi，适合在线翻阅）
set -uo pipefail
ROOT="/opt/sparkorbit/资料"
BAK="$ROOT/_bak"
mkdir -p "$BAK"
LOG=/tmp/compress_materials_screen.log
exec > >(tee -a "$LOG") 2>&1

mapfile -t FILES < <(find "$ROOT" -type f -name '*.pdf' ! -path '*/_bak/*' -size +40M -printf '%s\t%p\n' | sort -nr | cut -f2-)
for path in "${FILES[@]}"; do
  base=$(basename "$path")
  sz=$(stat -c%s "$path")
  echo "SCREEN_START $(date +%H:%M:%S) $sz $path"
  # 确保 _bak 里有更大/原版
  if [ ! -f "$BAK/$base" ]; then
    cp "$path" "$BAK/$base"
  fi
  # 优先从备份压，避免对已压缩文件反复劣化
  src="$path"
  if [ -f "$BAK/$base" ]; then
    bsz=$(stat -c%s "$BAK/$base")
    if [ "$bsz" -gt "$sz" ]; then src="$BAK/$base"; fi
  fi
  tmp="${path}.screen.$$"
  out="${path}.lin.$$"
  if ! gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 -dPDFSETTINGS=/screen \
      -dDetectDuplicateImages=true -dCompressFonts=true -dNOPAUSE -dQUIET -dBATCH \
      -sOutputFile="$tmp" "$src"; then
    echo "SCREEN_FAIL $path"
    rm -f "$tmp"
    continue
  fi
  nsz=$(stat -c%s "$tmp")
  echo "SCREEN_SIZE $sz -> $nsz (from $(basename "$src"))"
  set +e
  qpdf --linearize --object-streams=generate "$tmp" "$out"
  code=$?
  set -e
  rm -f "$tmp"
  if { [ "$code" -eq 0 ] || [ "$code" -eq 3 ]; } && [ -f "$out" ]; then
    final=$(stat -c%s "$out")
    if [ "$final" -lt "$sz" ]; then
      mv -f "$out" "$path"
      echo "SCREEN_OK $(date +%H:%M:%S) $path ($final bytes)"
    else
      rm -f "$out"
      echo "SCREEN_SKIP_LARGER $path"
    fi
  else
    echo "SCREEN_LIN_FAIL code=$code $path"
    rm -f "$out"
  fi
done
echo DONE_SCREEN $(date +%H:%M:%S)
