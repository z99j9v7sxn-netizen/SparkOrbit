#!/usr/bin/env bash
# 将大体积扫描 PDF 压成屏幕阅读版（/ebook ≈150dpi），再线性化。原件若未备份则先入 _bak。
set -uo pipefail
ROOT="/opt/sparkorbit/资料"
BAK="$ROOT/_bak"
mkdir -p "$BAK"
LOG=/tmp/compress_materials_web.log
exec > >(tee -a "$LOG") 2>&1

compress_one() {
  local path="$1"
  local sz
  sz=$(stat -c%s "$path")
  # 已小于 45MB 的跳过
  if [ "$sz" -lt 45000000 ]; then
    echo "SKIP_SMALL $(date +%H:%M:%S) $sz $path"
    return 0
  fi
  local base tmp out
  base=$(basename "$path")
  if [ ! -f "$BAK/$base" ]; then
    echo "BACKUP $base"
    cp "$path" "$BAK/$base"
  fi
  tmp="${path}.gs.$$"
  out="${path}.web.$$"
  echo "COMPRESS_START $(date +%H:%M:%S) $sz $path"
  # /ebook：适合屏幕阅读，体积通常降一个数量级
  if ! gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 -dPDFSETTINGS=/ebook \
      -dDetectDuplicateImages=true -dCompressFonts=true -dNOPAUSE -dQUIET -dBATCH \
      -sOutputFile="$tmp" "$path"; then
    echo "COMPRESS_FAIL $path"
    rm -f "$tmp"
    return 1
  fi
  local nsz
  nsz=$(stat -c%s "$tmp")
  echo "COMPRESS_SIZE $sz -> $nsz"
  # 线性化（允许 warnings=3）
  set +e
  qpdf --linearize --object-streams=generate "$tmp" "$out"
  local code=$?
  set -e
  rm -f "$tmp"
  if { [ "$code" -eq 0 ] || [ "$code" -eq 3 ]; } && [ -f "$out" ]; then
    mv -f "$out" "$path"
    echo "COMPRESS_OK $(date +%H:%M:%S) code=$code $path ($(stat -c%s "$path") bytes)"
  else
    echo "LINEARIZE_FAIL code=$code $path"
    rm -f "$out"
    return 1
  fi
}

# 优先考研指导书，再大课本
mapfile -t FILES < <(find "$ROOT/考研复习指导书" "$ROOT/课本" "$ROOT" -maxdepth 1 -type f -name '*.pdf' 2>/dev/null | sort -u)
# 按体积从大到小
while IFS= read -r line; do
  sz=${line%%$'\t'*}
  path=${line#*$'\t'}
  compress_one "$path" || true
done < <(for f in "${FILES[@]}"; do [ -f "$f" ] && printf '%s\t%s\n' "$(stat -c%s "$f")" "$f"; done | sort -nr)

echo DONE_COMPRESS $(date +%H:%M:%S)
