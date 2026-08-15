#!/usr/bin/env bash
# 保清晰度版教材优化：大扫描 PDF 降采样到 200dpi(JPEG q85) + qpdf 线性化；
# 学生上传 uploads/starlib 只做无损线性化。原件未备份则先入 _bak，可逐本回退。
# 用法（服务器）: bash scripts/compress_materials_hq.sh [项目根，默认 /opt/sparkorbit]
set -uo pipefail

BASE="${1:-/opt/sparkorbit}"
ROOT="$BASE/资料"
BAK="$ROOT/_bak"
STARLIB="$BASE/backend/uploads/starlib"
# 大于此体积才有损压缩（约 45MB）
COMPRESS_MIN=45000000
# 大于此体积才检查线性化（5MB）
LIN_MIN=5000000
LOG=/tmp/compress_materials_hq.log

mkdir -p "$BAK"
exec > >(tee -a "$LOG") 2>&1
echo "===== HQ optimize start $(date '+%F %T') base=$BASE ====="

command -v gs >/dev/null || { echo "FATAL: ghostscript 未安装 (apt install -y ghostscript)"; exit 1; }
command -v qpdf >/dev/null || { echo "FATAL: qpdf 未安装 (apt install -y qpdf)"; exit 1; }

is_linearized() {
  qpdf --check "$1" 2>/dev/null | grep -q 'File is linearized'
}

# 线性化（无损）：qpdf 0=ok 3=warnings 均算成功
linearize_one() {
  local path="$1"
  local tmp="${path}.lin.$$"
  qpdf --linearize --object-streams=generate "$path" "$tmp"
  local code=$?
  if { [ "$code" -eq 0 ] || [ "$code" -eq 3 ]; } && [ -s "$tmp" ]; then
    mv -f "$tmp" "$path"
    echo "LINEARIZE_OK code=$code $path"
    return 0
  fi
  echo "LINEARIZE_FAIL code=$code $path"
  rm -f "$tmp"
  return 1
}

# 有损压缩（保清晰度）：彩色/灰度 Bicubic 降采样 200dpi + JPEG q85，单色 600dpi
# PassThroughJPEGImages=false：否则 gs 会原样放过已有 JPEG，体积几乎不降
compress_one() {
  local path="$1"
  local sz
  sz=$(stat -c%s "$path")
  local base tmp out src
  base=$(basename "$path")
  if [ ! -f "$BAK/$base" ]; then
    echo "BACKUP $base"
    cp "$path" "$BAK/$base"
  fi
  src="$path"
  if [ -f "$BAK/$base" ]; then
    src="$BAK/$base"
  fi
  tmp="${path}.gs.$$"
  out="${path}.web.$$"
  echo "COMPRESS_START $(date +%H:%M:%S) $sz src=$src dest=$path"
  if ! gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 \
      -dPassThroughJPEGImages=false -dPassThroughJPXImages=false \
      -dDownsampleColorImages=true -dColorImageDownsampleType=/Bicubic \
      -dColorImageResolution=200 -dColorImageDownsampleThreshold=1.0 \
      -dDownsampleGrayImages=true -dGrayImageDownsampleType=/Bicubic \
      -dGrayImageResolution=200 -dGrayImageDownsampleThreshold=1.0 \
      -dDownsampleMonoImages=true -dMonoImageDownsampleType=/Subsample \
      -dMonoImageResolution=600 \
      -dEncodeColorImages=true -dEncodeGrayImages=true \
      -dAutoFilterColorImages=false -dAutoFilterGrayImages=false \
      -dColorImageFilter=/DCTEncode -dGrayImageFilter=/DCTEncode -dJPEGQ=85 \
      -dDetectDuplicateImages=true -dCompressFonts=true \
      -dNOPAUSE -dQUIET -dBATCH -sOutputFile="$tmp" "$src"; then
    echo "COMPRESS_FAIL $path"
    rm -f "$tmp"
    return 1
  fi
  local nsz
  nsz=$(stat -c%s "$tmp")
  echo "COMPRESS_SIZE $sz -> $nsz"
  # 压缩收益不足 15% 则放弃压缩结果，只对原件做线性化
  if [ "$nsz" -ge $((sz * 85 / 100)) ]; then
    echo "COMPRESS_SKIP_NO_GAIN $path"
    rm -f "$tmp"
    linearize_one "$path" || true
    return 0
  fi
  qpdf --linearize --object-streams=generate "$tmp" "$out"
  local code=$?
  rm -f "$tmp"
  if { [ "$code" -eq 0 ] || [ "$code" -eq 3 ]; } && [ -s "$out" ]; then
    mv -f "$out" "$path"
    echo "COMPRESS_OK $(date +%H:%M:%S) code=$code $path ($(stat -c%s "$path") bytes)"
  else
    echo "LINEARIZE_FAIL code=$code $path"
    rm -f "$out"
    return 1
  fi
}

# ---------- 阶段 1：教材（资料/），按体积从大到小 ----------
if [ -d "$ROOT" ]; then
  while IFS=$'\t' read -r sz path; do
    [ -f "$path" ] || continue
    if [ "$sz" -ge "$COMPRESS_MIN" ]; then
      compress_one "$path" || true
    elif [ "$sz" -ge "$LIN_MIN" ]; then
      if is_linearized "$path"; then
        echo "ALREADY_LIN $path"
      else
        linearize_one "$path" || true
      fi
    else
      echo "SKIP_SMALL $sz $path"
    fi
  done < <(find "$ROOT" -type f -iname '*.pdf' ! -path '*/_bak/*' -printf '%s\t%p\n' | sort -nr)
else
  echo "WARN: $ROOT 不存在，跳过教材阶段"
fi

# ---------- 阶段 2：学生上传（uploads/starlib），只无损线性化 ----------
if [ -d "$STARLIB" ]; then
  while IFS=$'\t' read -r sz path; do
    [ -f "$path" ] || continue
    if [ "$sz" -lt "$LIN_MIN" ]; then
      echo "SKIP_SMALL $sz $path"
      continue
    fi
    if is_linearized "$path"; then
      echo "ALREADY_LIN $path"
    else
      linearize_one "$path" || true
    fi
  done < <(find "$STARLIB" -type f -iname '*.pdf' -printf '%s\t%p\n' | sort -nr)
else
  echo "WARN: $STARLIB 不存在，跳过上传阶段"
fi

echo "===== HQ optimize done $(date '+%F %T') ====="
