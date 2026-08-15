"""Verify star_assets metadata is in MySQL and file_url points to local paths (not BLOB)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import pymysql
except ImportError:
    print("FAIL: pymysql not installed")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
UPLOADS = BACKEND / "uploads"
STARLIB = UPLOADS / "starlib"
CHROMA = BACKEND / "chroma_data"


def load_database_url() -> str:
    env_path = BACKEND / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get(
        "DATABASE_URL",
        "mysql+aiomysql://root:Aa040330@127.0.0.1:3306/sparkorbit?charset=utf8mb4",
    )


def parse_mysql_url(url: str) -> dict:
    # mysql+aiomysql://user:pass@host:port/db?charset=utf8mb4
    cleaned = url.replace("mysql+aiomysql://", "mysql://").replace("mysql+pymysql://", "mysql://")
    parsed = urlparse(cleaned)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": (parsed.path or "/sparkorbit").lstrip("/") or "sparkorbit",
    }


def local_path_from_file_url(file_url: str) -> Path | None:
    if not file_url:
        return None
    # /static/uploads/starlib/xxx.mp4 -> backend/uploads/starlib/xxx.mp4
    prefix = "/static/uploads/"
    if file_url.startswith(prefix):
        return BACKEND / "uploads" / unquote(file_url[len(prefix) :])
    media_prefix = "/static/media/"
    if file_url.startswith(media_prefix):
        return BACKEND / "app" / "static" / "media" / unquote(file_url[len(media_prefix) :])
    materials_prefix = "/static/materials/"
    if file_url.startswith(materials_prefix):
        return ROOT / "资料" / unquote(file_url[len(materials_prefix) :])
    return None


def main() -> int:
    cfg = parse_mysql_url(load_database_url())
    print(f"Connecting {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}")
    conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='star_assets' ORDER BY ORDINAL_POSITION",
                (cfg["database"],),
            )
            cols = cur.fetchall()
            if not cols:
                print("FAIL: table star_assets does not exist")
                return 1
            print("schema:")
            for name, dtype in cols:
                print(f"  - {name}: {dtype}")
                if dtype and "blob" in dtype.lower():
                    print("FAIL: unexpected BLOB column for media storage")
                    return 1

            cur.execute("SELECT COUNT(*) FROM star_assets")
            total = cur.fetchone()[0]
            print(f"star_assets count: {total}")

            cur.execute(
                "SELECT id, title, asset_type, file_url, bilibili_bvid, status "
                "FROM star_assets ORDER BY created_at DESC LIMIT 20"
            )
            rows = cur.fetchall()
            missing_files = 0
            for row in rows:
                asset_id, title, asset_type, file_url, bvid, status = row
                print(
                    f"  [{asset_type}] {status} title={title!r} "
                    f"file_url={file_url!r} bvid={bvid!r} id={asset_id}"
                )
                if asset_type == "video_bilibili":
                    continue
                if not file_url:
                    print("    WARN: empty file_url")
                    continue
                if not (
                    file_url.startswith("/static/uploads/")
                    or file_url.startswith("/static/media/")
                    or file_url.startswith("/static/materials/")
                    or file_url.startswith("http://")
                    or file_url.startswith("https://")
                ):
                    print(f"    WARN: unexpected file_url shape: {file_url}")
                path = local_path_from_file_url(file_url)
                if path is not None and not path.exists():
                    missing_files += 1
                    print(f"    WARN: file missing on disk: {path}")
                elif path is not None:
                    print(f"    OK disk: {path} ({path.stat().st_size} bytes)")
    finally:
        conn.close()

    print(f"uploads dir exists: {UPLOADS.exists()} ({UPLOADS})")
    print(f"starlib dir exists: {STARLIB.exists()} ({STARLIB})")
    print(f"chroma_data exists: {CHROMA.exists()} ({CHROMA})")
    if STARLIB.exists():
        files = list(STARLIB.iterdir())
        print(f"starlib file count: {len(files)}")
    if missing_files:
        print(f"WARN: {missing_files} referenced local files missing (metadata still in DB)")
    print("OK: knowledge base metadata lives in MySQL; media uses path/URL not BLOB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
