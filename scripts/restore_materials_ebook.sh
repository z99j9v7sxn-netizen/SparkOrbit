#!/usr/bin/env bash
# 从 资料/_bak 用 Ghostscript /ebook + qpdf 线性化重写在线 PDF（禁止 /screen）
set -uo pipefail
ROOT="/opt/sparkorbit/资料"
BAK="$ROOT/_bak"
LOG=/tmp/restore_materials_ebook.log
exec > >(tee -a "$LOG") 2>&1

if [ ! -d "$BAK" ]; then
  echo "NO_BAK $BAK"
  exit 1
fi

# 在 ROOT 下按文件名查找目标路径（排除 _bak）
find_target() {
  local base="$1"
  find "$ROOT" -type f -name "$base" ! -path '*/_bak/*' 2>/dev/null | head -1
}

mapfile -t BAK_FILES < <(find "$BAK" -type f -name '*.pdf' | sort)
for src in "${BAK_FILES[@]}"; do
  base=$(basename "$src")
  dest=$(find_target "$base")
  if [ -z "$dest" ]; then
    # 常见目录回退
    if [[ "$base" == 2027* ]] || [[ "$base" == 王道* ]]; then
      dest="$ROOT/考研复习指导书/$base"
    elif [[ "$base" == *题集* ]] || [[ "$base" == 数据结构\(c* ]]; then
      dest="$ROOT/$base"
    else
      dest="$ROOT/课本/$base"
    fi
  fi
  mkdir -p "$(dirname "$dest")"
  sz=$(stat -c%s "$src")
  echo "EBOOK_START $(date +%H:%M:%S) $sz -> $dest (from $src)"
  tmp="${dest}.ebook.$$"
  out="${dest}.lin.$$"
  if ! gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 -dPDFSETTINGS=/ebook \
      -dDetectDuplicateImages=true -dCompressFonts=true -dNOPAUSE -dQUIET -dBATCH \
      -sOutputFile="$tmp" "$src"; then
    echo "EBOOK_FAIL $base"
    rm -f "$tmp"
    continue
  fi
  nsz=$(stat -c%s "$tmp")
  echo "EBOOK_SIZE $sz -> $nsz"
  set +e
  qpdf --linearize --object-streams=generate "$tmp" "$out"
  code=$?
  set -e
  rm -f "$tmp"
  if { [ "$code" -eq 0 ] || [ "$code" -eq 3 ]; } && [ -f "$out" ]; then
    mv -f "$out" "$dest"
    echo "EBOOK_OK $(date +%H:%M:%S) code=$code $dest ($(stat -c%s "$dest") bytes)"
  else
    echo "EBOOK_LIN_FAIL code=$code $base"
    rm -f "$out"
  fi
done

find "$ROOT" \( -name '*.ebook.*' -o -name '*.screen.*' -o -name '*.gs.*' -o -name '*.lin.*' \) -delete 2>/dev/null || true
echo DONE_EBOOK $(date +%H:%M:%S)
ls -lhS "$ROOT/考研复习指导书/" 2>/dev/null || true
