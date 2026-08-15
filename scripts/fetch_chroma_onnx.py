"""下载 Chroma 默认 ONNX 嵌入模型到 backend/vendor/chroma_onnx/（构建镜像用）。

官方包: https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz
SHA256: 913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3

用法（项目根）:
  .\\.venv\\Scripts\\python.exe scripts\\fetch_chroma_onnx.py
"""
from __future__ import annotations

import hashlib
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "backend" / "vendor" / "chroma_onnx" / "all-MiniLM-L6-v2"
URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
ONNX_FILES = (
    "config.json",
    "model.onnx",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def model_ready(dest: Path = DEST) -> bool:
    onnx_dir = dest / "onnx"
    return all((onnx_dir / name).is_file() for name in ONNX_FILES)


def main() -> int:
    if model_ready():
        print(f"already ready: {DEST / 'onnx'}")
        return 0

    DEST.mkdir(parents=True, exist_ok=True)
    archive = DEST / "onnx.tar.gz"
    if not archive.is_file() or _sha256(archive) != SHA256:
        print(f"downloading {URL}")
        urllib.request.urlretrieve(URL, archive)
        digest = _sha256(archive)
        if digest != SHA256:
            archive.unlink(missing_ok=True)
            raise SystemExit(f"SHA256 mismatch: {digest}")
    print(f"extracting {archive}")
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(path=DEST)
    if not model_ready():
        raise SystemExit(f"extract incomplete under {DEST}")
    print(f"ok: {DEST / 'onnx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
