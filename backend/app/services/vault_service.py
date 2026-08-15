"""星轨知识库服务：每用户 Obsidian 兼容 Vault（Markdown + 双链 + 图谱索引）。"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import VAULTS_DIR
from app.models.note import Note
from app.models.user import User
from app.models.vault import StudentVault, VaultFile, VaultLink

WIKILINK_RE = re.compile(r"!\[\[([^\]]+)\]\]|\[\[([^\]]+)\]\]")
TAG_RE = re.compile(r"(?<![\w/#])#([\w\u4e00-\u9fff/-]+)")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

VAULT_FOLDERS = (
    "00-Inbox",
    "10-Planets",
    "20-Clips",
    "30-Habits",
    "40-Media",
    "50-Daily",
    "60-Canvas",
    "70-Workshop",
    "Templates",
    ".obsidian",
)

README_MD = """# 星轨知识库

这是你的 **Obsidian 兼容** 私有知识库（Markdown + `[[双链]]`）。

- `10-Planets/`：行星知识点笔记
- `20-Clips/`：划词 / 演武 / 视频剪藏
- `30-Habits/`：AI 习惯与学情摘要
- `50-Daily/`：每日学习日记
- `70-Workshop/`：资源工坊手动入库产物

在本站编辑会同步到云端；可导出 zip 用本地 Obsidian 打开。
"""


def vault_root(user_id: str) -> Path:
    return VAULTS_DIR / user_id


def vault_name_for(user: User) -> str:
    """Obsidian 库名仅用 ASCII，避免中文用户名编码后匹配失败。"""
    raw = (user.username or user.id or "user")[:48]
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "-", raw).strip("-_.") or (user.id or "user")[:8]
    safe = re.sub(r"-{2,}", "-", safe)
    return f"SparkOrbit-{safe}"


def _ascii_vault_name(name: str, fallback: str = "") -> str:
    """清洗用户自定义库名：保留 ASCII 与中文，去掉首尾空白。"""
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", (name or "").strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("-_.")[:128]
    return cleaned or fallback


def _safe_rel(path: str) -> str:
    raw = (path or "").replace("\\", "/").strip().lstrip("/")
    if not raw or ".." in raw.split("/"):
        raise ValueError("非法路径")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("非法路径")
    return raw


def resolve_user_path(user_id: str, rel: str) -> Path:
    rel = _safe_rel(rel)
    root = vault_root(user_id).resolve()
    full = (root / rel).resolve()
    if not str(full).startswith(str(root)):
        raise ValueError("路径越界")
    return full


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = FRONTMATTER_RE.match(text or "")
    if not m:
        return {}, text or ""
    meta: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        if key == "tags":
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1]
                meta[key] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
            else:
                meta[key] = [x.strip() for x in val.split(",") if x.strip()]
        else:
            meta[key] = val
    body = text[m.end() :]
    return meta, body


def extract_wikilinks(text: str) -> list[tuple[str, str]]:
    """返回 (target_title_or_path, link_type)。"""
    out: list[tuple[str, str]] = []
    for m in WIKILINK_RE.finditer(text or ""):
        raw = (m.group(1) or m.group(2) or "").strip()
        if not raw:
            continue
        link_type = "embed" if m.group(1) is not None else "wiki"
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            out.append((target, link_type))
    return out


def extract_tags(text: str, frontmatter: dict) -> list[str]:
    tags: set[str] = set()
    fm = frontmatter.get("tags")
    if isinstance(fm, list):
        tags.update(str(t) for t in fm)
    elif isinstance(fm, str) and fm:
        tags.add(fm)
    _, body = parse_frontmatter(text)
    for m in TAG_RE.finditer(body):
        tags.add(m.group(1))
    return sorted(tags)


def title_from_path_or_content(path: str, content: str, frontmatter: dict) -> str:
    if frontmatter.get("title"):
        return str(frontmatter["title"])
    for line in (content or "").splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip() or Path(path).stem
    return Path(path).stem


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def resolve_link_target(user_id: str, from_path: str, target: str) -> str:
    """将 wikilink 目标解析为相对 vault 的 .md 路径（可能尚不存在）。"""
    t = target.strip().replace("\\", "/")
    if t.endswith(".md"):
        candidate = t
    else:
        candidate = f"{t}.md"
    # 绝对相对 vault
    if "/" in candidate:
        return _safe_rel(candidate)
    # 同目录优先
    parent = str(Path(from_path).parent).replace("\\", "/")
    if parent and parent != ".":
        same = f"{parent}/{candidate}"
        if resolve_user_path(user_id, same).exists():
            return same
    # 全库按 stem 查找
    root = vault_root(user_id)
    stem = Path(candidate).stem
    if root.exists():
        for p in root.rglob("*.md"):
            if p.stem == stem:
                return str(p.relative_to(root)).replace("\\", "/")
    if parent and parent != ".":
        return f"{parent}/{candidate}"
    return f"00-Inbox/{candidate}"


async def ensure_vault(session: AsyncSession, user: User) -> StudentVault:
    row = (
        await session.execute(select(StudentVault).where(StudentVault.user_id == user.id))
    ).scalar_one_or_none()
    name = vault_name_for(user)
    root = vault_root(user.id)
    root.mkdir(parents=True, exist_ok=True)
    for folder in VAULT_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    obsidian = root / ".obsidian"
    app_json = obsidian / "app.json"
    if not app_json.exists():
        app_json.write_text(json.dumps({"legacyEditor": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(README_MD, encoding="utf-8")
    _ensure_default_templates(root)

    if row is None:
        # 本机「打开文件夹作为库」时 Obsidian 默认库名=文件夹名(user_id)，与此对齐减少 Vault not found
        row = StudentVault(id=str(uuid4()), user_id=user.id, vault_name=user.id, revision=0)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        await _index_file(session, user.id, "README.md", README_MD)
        await session.commit()
    elif not row.vault_name:
        row.vault_name = user.id
        await session.commit()
    elif any(ord(c) > 127 for c in (row.vault_name or "")):
        # 旧版可能把中文用户名写进库名，导致 obsidian://vault=%E5%92%B8… 匹配失败
        row.vault_name = user.id
        await session.commit()
    return row


async def _index_file(session: AsyncSession, user_id: str, rel: str, content: str) -> VaultFile:
    rel = _safe_rel(rel)
    fm, _body = parse_frontmatter(content)
    title = title_from_path_or_content(rel, content, fm)
    tags = extract_tags(content, fm)
    h = content_hash(content)
    words = len(re.findall(r"\S+", content or ""))

    existing = (
        await session.execute(select(VaultFile).where(VaultFile.user_id == user_id, VaultFile.path == rel))
    ).scalar_one_or_none()
    if existing:
        existing.title = title
        existing.content_hash = h
        existing.word_count = words
        existing.tags_json = tags
        existing.frontmatter_json = fm
        existing.updated_at = datetime.now(timezone.utc)
        row = existing
    else:
        row = VaultFile(
            id=str(uuid4()),
            user_id=user_id,
            path=rel,
            title=title,
            content_hash=h,
            word_count=words,
            tags_json=tags,
            frontmatter_json=fm,
        )
        session.add(row)

    await session.execute(delete(VaultLink).where(VaultLink.user_id == user_id, VaultLink.from_path == rel))
    root = vault_root(user_id)
    for target, link_type in extract_wikilinks(content):
        try:
            to_path = resolve_link_target(user_id, rel, target)
        except ValueError:
            continue
        exists = 1 if (root / to_path).exists() else 0
        session.add(
            VaultLink(
                id=str(uuid4()),
                user_id=user_id,
                from_path=rel,
                to_path=to_path,
                to_exists=exists,
                link_type=link_type,
            )
        )
    return row


async def bump_revision(session: AsyncSession, user_id: str) -> int:
    vault = (
        await session.execute(select(StudentVault).where(StudentVault.user_id == user_id))
    ).scalar_one_or_none()
    if not vault:
        return 0
    vault.revision = int(vault.revision or 0) + 1
    vault.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return vault.revision


def build_tree(user_id: str) -> list[dict]:
    root = vault_root(user_id)
    if not root.exists():
        return []

    def walk(dir_path: Path, prefix: str = "") -> list[dict]:
        nodes: list[dict] = []
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return nodes
        for p in entries:
            if p.name.startswith(".") and p.name != ".obsidian":
                continue
            if p.name == ".obsidian":
                continue
            rel = f"{prefix}/{p.name}".lstrip("/") if prefix else p.name
            if p.is_dir():
                nodes.append({"name": p.name, "path": rel, "type": "dir", "children": walk(p, rel)})
            elif p.suffix.lower() == ".md":
                nodes.append({"name": p.name, "path": rel, "type": "file"})
        return nodes

    return walk(root)


async def read_file(session: AsyncSession, user: User, path: str) -> dict:
    await ensure_vault(session, user)
    rel = _safe_rel(path)
    full = resolve_user_path(user.id, rel)
    if not full.exists() or not full.is_file():
        raise FileNotFoundError("文件不存在")
    content = full.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    meta = (
        await session.execute(select(VaultFile).where(VaultFile.user_id == user.id, VaultFile.path == rel))
    ).scalar_one_or_none()
    return {
        "path": rel,
        "title": meta.title if meta else title_from_path_or_content(rel, content, fm),
        "content": content,
        "body": body,
        "frontmatter": fm,
        "tags": meta.tags_json if meta else extract_tags(content, fm),
        "updated_at": meta.updated_at.isoformat() if meta and meta.updated_at else "",
        "word_count": meta.word_count if meta else 0,
    }


async def write_file(
    session: AsyncSession,
    user: User,
    path: str,
    content: str,
    *,
    create_parents: bool = True,
) -> dict:
    await ensure_vault(session, user)
    rel = _safe_rel(path)
    if not rel.endswith(".md"):
        rel = f"{rel}.md" if "." not in Path(rel).name else rel
    full = resolve_user_path(user.id, rel)
    if create_parents:
        full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content or "", encoding="utf-8")
    row = await _index_file(session, user.id, rel, content or "")
    await bump_revision(session, user.id)
    return {
        "path": rel,
        "title": row.title,
        "content": content or "",
        "tags": row.tags_json,
        "frontmatter": row.frontmatter_json,
        "word_count": row.word_count,
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


async def create_file(session: AsyncSession, user: User, path: str, content: str = "") -> dict:
    rel = _safe_rel(path)
    if not rel.endswith(".md"):
        rel = f"{rel}.md"
    full = resolve_user_path(user.id, rel)
    if full.exists():
        raise FileExistsError("文件已存在")
    if not content:
        title = Path(rel).stem
        content = f"---\ntitle: {title}\n---\n\n# {title}\n\n"
    return await write_file(session, user, rel, content)


async def delete_file(session: AsyncSession, user: User, path: str) -> dict:
    await ensure_vault(session, user)
    rel = _safe_rel(path)
    full = resolve_user_path(user.id, rel)
    if full.exists() and full.is_file():
        full.unlink()
    await session.execute(delete(VaultFile).where(VaultFile.user_id == user.id, VaultFile.path == rel))
    await session.execute(delete(VaultLink).where(VaultLink.user_id == user.id, VaultLink.from_path == rel))
    await bump_revision(session, user.id)
    return {"ok": True, "path": rel}


async def search_files(session: AsyncSession, user: User, q: str, limit: int = 50) -> list[dict]:
    await ensure_vault(session, user)
    q = (q or "").strip()
    if not q:
        rows = (
            await session.execute(
                select(VaultFile).where(VaultFile.user_id == user.id).order_by(VaultFile.updated_at.desc()).limit(limit)
            )
        ).scalars().all()
        return [
            {
                "path": r.path,
                "title": r.title,
                "tags": r.tags_json or [],
                "snippet": "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                "word_count": r.word_count or 0,
            }
            for r in rows
        ]

    like = f"%{q}%"
    rows = (
        await session.execute(
            select(VaultFile)
            .where(
                VaultFile.user_id == user.id,
                or_(VaultFile.title.ilike(like), VaultFile.path.ilike(like)),
            )
            .order_by(VaultFile.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    hits = [
        {
            "path": r.path,
            "title": r.title,
            "tags": r.tags_json or [],
            "snippet": "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            "word_count": r.word_count or 0,
        }
        for r in rows
    ]
    # 正文补充扫描
    root = vault_root(user.id)
    seen = {h["path"] for h in hits}
    if root.exists() and len(hits) < limit:
        for p in root.rglob("*.md"):
            rel = str(p.relative_to(root)).replace("\\", "/")
            if rel in seen:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if q.lower() in text.lower():
                idx = text.lower().find(q.lower())
                start = max(0, idx - 40)
                snippet = text[start : start + 120].replace("\n", " ")
                hits.append({"path": rel, "title": p.stem, "tags": [], "snippet": snippet})
                seen.add(rel)
                if len(hits) >= limit:
                    break
    return hits


async def get_graph(
    session: AsyncSession,
    user: User,
    *,
    mode: str = "global",
    path: str = "",
    depth: int = 1,
    show_orphans: bool = True,
    existing_only: bool = False,
) -> dict:
    await ensure_vault(session, user)
    files = (
        await session.execute(select(VaultFile).where(VaultFile.user_id == user.id))
    ).scalars().all()
    links = (
        await session.execute(select(VaultLink).where(VaultLink.user_id == user.id, VaultLink.link_type != "tag"))
    ).scalars().all()

    path_set = {f.path for f in files}
    title_by_path = {f.path: f.title for f in files}
    folder_of = {f.path: f.path.split("/")[0] if "/" in f.path else "" for f in files}

    if mode == "local" and path:
        path = _safe_rel(path)
        keep = {path}
        frontier = {path}
        for _ in range(max(1, min(depth, 3))):
            nxt: set[str] = set()
            for lk in links:
                if lk.from_path in frontier:
                    nxt.add(lk.to_path)
                if lk.to_path in frontier:
                    nxt.add(lk.from_path)
            nxt -= keep
            keep |= nxt
            frontier = nxt
            if not frontier:
                break
        files = [f for f in files if f.path in keep]
        links = [lk for lk in links if lk.from_path in keep and lk.to_path in keep]
        path_set = {f.path for f in files}

    # 入度
    indeg: dict[str, int] = {f.path: 0 for f in files}
    edges = []
    for lk in links:
        if existing_only and not lk.to_exists and lk.to_path not in path_set:
            continue
        if lk.from_path not in path_set:
            continue
        to = lk.to_path
        if to not in path_set and not existing_only:
            # 幽灵节点
            pass
        edges.append({"source": lk.from_path, "target": to, "type": lk.link_type})
        indeg[to] = indeg.get(to, 0) + 1
        indeg[lk.from_path] = indeg.get(lk.from_path, 0)

    nodes = []
    linked = {e["source"] for e in edges} | {e["target"] for e in edges}
    for f in files:
        if not show_orphans and f.path not in linked and mode == "global":
            continue
        folder = folder_of.get(f.path, "")
        category = "planet" if folder.startswith("10-") else (
            "clip" if folder.startswith("20-") else (
                "habit" if folder.startswith("30-") else (
                    "daily" if folder.startswith("50-") else "note"
                )
            )
        )
        nodes.append(
            {
                "id": f.path,
                "name": f.title or Path(f.path).stem,
                "path": f.path,
                "category": category,
                "symbolSize": 12 + min(28, indeg.get(f.path, 0) * 4),
                "value": indeg.get(f.path, 0),
                "tags": f.tags_json or [],
                "created_at": f.created_at.isoformat() if f.created_at else "",
            }
        )
    # 未落盘的链接目标
    known_ids = {n["id"] for n in nodes}
    for e in edges:
        if e["target"] not in known_ids:
            nodes.append(
                {
                    "id": e["target"],
                    "name": Path(e["target"]).stem,
                    "path": e["target"],
                    "category": "ghost",
                    "symbolSize": 10,
                    "value": indeg.get(e["target"], 0),
                    "tags": [],
                    "created_at": "",
                }
            )
            known_ids.add(e["target"])

    return {
        "mode": mode,
        "nodes": nodes,
        "edges": edges,
        "categories": [
            {"name": "note"},
            {"name": "planet"},
            {"name": "clip"},
            {"name": "habit"},
            {"name": "daily"},
            {"name": "ghost"},
        ],
    }


async def get_backlinks(session: AsyncSession, user: User, path: str) -> dict:
    await ensure_vault(session, user)
    rel = _safe_rel(path)
    incoming = (
        await session.execute(
            select(VaultLink).where(VaultLink.user_id == user.id, VaultLink.to_path == rel)
        )
    ).scalars().all()
    outgoing = (
        await session.execute(
            select(VaultLink).where(VaultLink.user_id == user.id, VaultLink.from_path == rel)
        )
    ).scalars().all()

    async def _titles(paths: list[str]) -> dict[str, str]:
        if not paths:
            return {}
        rows = (
            await session.execute(select(VaultFile).where(VaultFile.user_id == user.id, VaultFile.path.in_(paths)))
        ).scalars().all()
        return {r.path: r.title for r in rows}

    in_paths = [x.from_path for x in incoming]
    out_paths = [x.to_path for x in outgoing]
    titles = await _titles(list(set(in_paths + out_paths + [rel])))

    # 未链接提及：其它文件正文含本标题但未双链
    title = titles.get(rel) or Path(rel).stem
    unlinked: list[dict] = []
    root = vault_root(user.id)
    linked_from = {x.from_path for x in incoming}
    if root.exists() and title:
        for p in root.rglob("*.md"):
            prel = str(p.relative_to(root)).replace("\\", "/")
            if prel == rel or prel in linked_from:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if title in text and f"[[{title}" not in text and f"[[{Path(rel).stem}" not in text:
                unlinked.append({"path": prel, "title": Path(prel).stem})

    return {
        "path": rel,
        "backlinks": [{"path": x.from_path, "title": titles.get(x.from_path, Path(x.from_path).stem), "type": x.link_type} for x in incoming],
        "outgoing": [{"path": x.to_path, "title": titles.get(x.to_path, Path(x.to_path).stem), "type": x.link_type, "exists": bool(x.to_exists)} for x in outgoing],
        "unlinked_mentions": unlinked[:30],
    }


async def open_hint(session: AsyncSession, user: User) -> dict:
    """返回接入 Obsidian 所需信息。

    关键：用「打开文件夹作为库」选中 local_path 时，Obsidian 默认库名 = 文件夹名
   （即 user_id），不是 SparkOrbit-xxx。因此 URI 默认用 folder_name 唤起；
    若用户在向导里改过 vault_name，则改用其自定义名。
    """
    vault = await ensure_vault(session, user)
    local_path = vault_root(user.id).resolve()
    folder_name = local_path.name
    export_name = vault_name_for(user)
    stored = (vault.vault_name or "").strip()
    # 唤起名：无中文的自定义名优先，否则用文件夹名（本机打开文件夹作为库时的默认名）
    if stored and stored != folder_name and not any(ord(c) > 127 for c in stored):
        launch_name = stored
    else:
        launch_name = folder_name
    display_name = stored or folder_name
    local = str(local_path)
    return {
        "vault_name": display_name,
        "folder_name": folder_name,
        "export_name": export_name,
        "launch_vault_name": launch_name,
        "local_path": local,
        "obsidian_uri": f"obsidian://open?vault={quote(launch_name, safe='')}",
        "obsidian_uri_by_path": f"obsidian://open?path={quote(local, safe='')}",
        "download_path": "/api/vault/export.zip",
        "install_url": "https://obsidian.md/download",
        "revision": vault.revision,
        "tip": (
            f"本机直连：用「打开文件夹作为库」选中下方路径后，Obsidian 库名默认为「{folder_name}」，"
            f"唤起链接已按此生成。导出 zip 时建议解压文件夹命名为「{export_name}」。"
        ),
    }


async def update_vault_name(session: AsyncSession, user: User, vault_name: str) -> dict:
    """允许用户把库名改成与本机 Obsidian 注册名一致，修复 Vault not found。"""
    vault = await ensure_vault(session, user)
    folder_name = vault_root(user.id).name
    name = _ascii_vault_name(vault_name, fallback=folder_name)
    if not name:
        raise ValueError("库名不能为空")
    vault.vault_name = name
    await session.commit()
    await session.refresh(vault)
    return await open_hint(session, user)


async def export_zip_bytes(session: AsyncSession, user: User) -> bytes:
    await ensure_vault(session, user)
    root = vault_root(user.id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in root.rglob("*"):
            if p.is_file():
                arc = str(p.relative_to(root)).replace("\\", "/")
                zf.write(p, arcname=arc)
    return buf.getvalue()


async def ingest_clip(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    content: str,
    planet_slug: str = "",
    galaxy_slug: str = "",
    source: str = "clip",
) -> dict:
    """学习剪藏写入 20-Clips，并尽量双链到行星笔记。"""
    await ensure_vault(session, user)
    safe_title = re.sub(r'[<>:"/\\|?*]', "_", (title or "剪藏").strip())[:80] or "剪藏"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rel = f"20-Clips/{ts}-{safe_title}.md"
    links = ""
    if planet_slug:
        g = galaxy_slug or "misc"
        planet_path = f"10-Planets/{g}/{planet_slug}.md"
        pfull = resolve_user_path(user.id, planet_path)
        if not pfull.exists():
            await write_file(
                session,
                user,
                planet_path,
                f"---\ntitle: {planet_slug}\ngalaxy_slug: {g}\nplanet_slug: {planet_slug}\n---\n\n# {planet_slug}\n\n",
            )
        links = f"\n\n相关：[[{planet_slug}]]\n"
    body = (
        f"---\ntitle: {safe_title}\nsource: {source}\ngalaxy_slug: {galaxy_slug}\nplanet_slug: {planet_slug}\n"
        f"tags: [clip, {source}]\n---\n\n# {safe_title}\n\n{content.strip()}{links}\n"
    )
    return await write_file(session, user, rel, body)


async def migrate_notes_from_db(session: AsyncSession, user: User) -> dict:
    """将旧 Note 表导入 Vault（幂等：按 note id 文件名）。"""
    await ensure_vault(session, user)
    notes = (
        await session.execute(select(Note).where(Note.user_id == user.id).order_by(Note.updated_at.desc()))
    ).scalars().all()
    imported = 0
    skipped = 0
    for n in notes:
        g = n.galaxy_slug or "misc"
        folder = f"10-Planets/{g}" if n.planet_slug else "00-Inbox"
        name = re.sub(r'[<>:"/\\|?*]', "_", (n.title or n.planet_slug or "note").strip())[:60] or "note"
        rel = f"{folder}/{name}-{n.id[:8]}.md"
        full = resolve_user_path(user.id, rel)
        if full.exists():
            skipped += 1
            continue
        fm = (
            f"---\ntitle: {n.title or name}\ngalaxy_slug: {n.galaxy_slug or ''}\n"
            f"planet_slug: {n.planet_slug or ''}\nsource: {n.source or 'migrated'}\n---\n\n"
        )
        body = f"# {n.title or name}\n\n{n.content or ''}\n"
        if n.planet_slug:
            body += f"\n[[{n.planet_slug}]]\n"
        await write_file(session, user, rel, fm + body)
        imported += 1
    return {"imported": imported, "skipped": skipped, "total": len(notes)}


async def analyze_vault_for_profile(session: AsyncSession, user: User) -> dict:
    """读库摘要并写入学习事件，触发画像刷新阈值逻辑。"""
    from app.services.profile_refresh import record_learning_event, refresh_profile_from_events
    from app.services.llm import llm_available, llm_chat, extract_json

    await ensure_vault(session, user)
    files = (
        await session.execute(
            select(VaultFile).where(VaultFile.user_id == user.id).order_by(VaultFile.updated_at.desc()).limit(20)
        )
    ).scalars().all()
    snippets: list[str] = []
    root = vault_root(user.id)
    for f in files:
        fp = root / f.path
        if not fp.exists():
            continue
        try:
            text = fp.read_text(encoding="utf-8")[:800]
        except OSError:
            continue
        snippets.append(f"## {f.title} ({f.path})\n{text}")

    blob = "\n\n".join(snippets)[:6000] or "（知识库暂无正文）"
    summary = f"知识库共索引 {len(files)} 篇近期笔记"
    dims_hint: dict[str, Any] = {}

    if llm_available() and snippets:
        prompt = (
            "你是学习画像分析师。根据学生知识库笔记摘要，输出 JSON：\n"
            '{"summary":"一句话学情","habits":["习惯1"],"weak_topics":["薄弱点"],'
            '"strengths":["优势"],"focus_score":1-5}\n'
            f"笔记：\n{blob}"
        )
        try:
            raw = await llm_chat([{"role": "user", "content": prompt}], temperature=0.3)
            data = extract_json(raw) or {}
            summary = str(data.get("summary") or summary)[:500]
            dims_hint = data
            # 写回 Habits
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            habit_md = (
                f"---\ntitle: 学情摘要 {day}\ntags: [habit, ai]\n---\n\n# 学情摘要 {day}\n\n"
                f"{summary}\n\n## 习惯\n"
                + "\n".join(f"- {h}" for h in (data.get("habits") or [])[:8])
                + "\n\n## 薄弱点\n"
                + "\n".join(f"- {h}" for h in (data.get("weak_topics") or [])[:8])
                + "\n"
            )
            await write_file(session, user, f"30-Habits/分析-{day}.md", habit_md)
        except Exception:
            pass

    # 先记事件但不自动阈值刷新，再强制一次，避免重复 refresh
    ev = await record_learning_event(
        session,
        user.id,
        "vault_analyze",
        summary,
        payload={"files": len(files), "ai": dims_hint},
        auto_refresh=False,
    )
    refreshed = await refresh_profile_from_events(session, user.id)
    vault = (
        await session.execute(select(StudentVault).where(StudentVault.user_id == user.id))
    ).scalar_one_or_none()
    if vault:
        vault.last_analyzed_at = datetime.now(timezone.utc)
        await session.commit()
    status = "refreshed" if refreshed is not None else "already_fresh"
    return {
        "ok": True,
        "summary": summary,
        "event": ev,
        "profile_refreshed": refreshed is not None,
        "status": status,
        "ai": dims_hint,
    }


async def ingest_generated_resource(session: AsyncSession, user: User, resource_id: str) -> dict:
    """将资源工坊产物手动写入知识库 70-Workshop。"""
    from app.models.generated_resource import GeneratedResource
    from app.services.profile_refresh import record_learning_event

    await ensure_vault(session, user)
    row = (
        await session.execute(
            select(GeneratedResource).where(
                GeneratedResource.id == resource_id,
                GeneratedResource.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("资源不存在")

    kind = (row.kind or "doc").strip() or "doc"
    meta = row.meta_json or {}
    title = (row.title or f"工坊{kind}").strip()
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)[:48].strip() or kind
    day = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    planet = row.planet_slug or ""
    wiki = f"[[{planet}]]" if planet else ""

    media_url = str(meta.get("media_url") or "")
    vault_path = ""
    if kind == "media" and media_url:
        note = (
            f"---\ntitle: {title}\nsource: workshop\nresource_id: {row.id}\nkind: media\n"
            f"media_url: {media_url}\ntags: [workshop, media]\n---\n\n"
            f"# {title}\n\n{wiki}\n\n视频地址：`{media_url}`\n\n"
            f"{(row.content or '')[:2000]}\n"
        )
        vault_path = f"70-Workshop/media/{day}-{safe_title}.md"
        # 同步在 40-Media 放引用卡
        await write_file(session, user, f"40-Media/{day}-{safe_title}.md", note)
    elif kind == "mindmap":
        note = (
            f"---\ntitle: {title}\nsource: workshop\nresource_id: {row.id}\nkind: mindmap\n"
            f"tags: [workshop, mindmap]\n---\n\n# {title}\n\n{wiki}\n\n"
            f"```json\n{(row.content or '')[:6000]}\n```\n"
        )
        vault_path = f"70-Workshop/mindmap/{day}-{safe_title}.md"
    else:
        body = row.content or ""
        note = (
            f"---\ntitle: {title}\nsource: workshop\nresource_id: {row.id}\nkind: {kind}\n"
            f"planet_slug: {planet}\ntags: [workshop, {kind}]\n---\n\n"
            f"# {title}\n\n{wiki}\n\n{body}\n"
        )
        vault_path = f"70-Workshop/{kind}/{day}-{safe_title}.md"

    written = await write_file(session, user, vault_path, note)
    await record_learning_event(
        session,
        user.id,
        "workshop_ingest",
        f"工坊入库：{title}",
        payload={
            "resource_id": row.id,
            "title": title,
            "kind": kind,
            "vault_path": vault_path,
            "planet_slug": planet,
        },
        auto_refresh=True,
    )
    return {
        "ok": True,
        "path": vault_path,
        "title": title,
        "kind": kind,
        "file": written,
    }


async def reindex_all(session: AsyncSession, user: User) -> dict:
    await ensure_vault(session, user)
    root = vault_root(user.id)
    count = 0
    for p in root.rglob("*.md"):
        rel = str(p.relative_to(root)).replace("\\", "/")
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue
        await _index_file(session, user.id, rel, content)
        count += 1
    await session.commit()
    return {"indexed": count}


DEFAULT_TEMPLATES: dict[str, str] = {
    "Templates/行星笔记.md": """---
title: {{title}}
galaxy_slug: {{galaxy_slug}}
planet_slug: {{planet_slug}}
tags: [planet]
---

# {{title}}

## 学习目标

-

## 核心要点

-

## 易错点

-

## 待复习

-
""",
    "Templates/错题反思.md": """---
title: 错题反思
tags: [mistake, review]
---

# 错题反思

## 题目摘要

-

## 错误原因

-

## 正确思路

-

## 关联知识点

-
""",
    "Templates/费曼讲解.md": """---
title: 费曼讲解
tags: [feynman, explain]
---

# 费曼讲解

用自己的话讲给「小白」听：

## 概念是什么

-

## 为什么重要

-

## 一个例子

-
""",
}


def _ensure_default_templates(root: Path) -> None:
    tpl_dir = root / "Templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    for rel, body in DEFAULT_TEMPLATES.items():
        p = root / rel
        if not p.exists():
            p.write_text(body, encoding="utf-8")


def _vault_meta(vault: StudentVault) -> dict:
    meta = vault.meta_json if isinstance(vault.meta_json, dict) else {}
    return dict(meta)


async def list_templates(session: AsyncSession, user: User) -> list[dict]:
    await ensure_vault(session, user)
    root = vault_root(user.id) / "Templates"
    out: list[dict] = []
    if root.exists():
        for p in sorted(root.glob("*.md")):
            rel = str(p.relative_to(vault_root(user.id))).replace("\\", "/")
            out.append({"path": rel, "name": p.stem})
    return out


async def create_from_template(
    session: AsyncSession,
    user: User,
    *,
    template_path: str,
    dest_path: str = "",
    vars: dict | None = None,
) -> dict:
    await ensure_vault(session, user)
    tpl = _safe_rel(template_path)
    full = resolve_user_path(user.id, tpl)
    if not full.exists():
        raise FileNotFoundError("模板不存在")
    text = full.read_text(encoding="utf-8")
    mapping = {
        "title": "未命名",
        "galaxy_slug": "",
        "planet_slug": "",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        **(vars or {}),
    }
    for k, v in mapping.items():
        text = text.replace("{{" + k + "}}", str(v))
    dest = dest_path.strip()
    if not dest:
        dest = f"00-Inbox/{mapping['title']}-{datetime.now(timezone.utc).strftime('%H%M%S')}.md"
    return await create_file(session, user, dest, text)


async def create_daily_note(session: AsyncSession, user: User, day: str = "") -> dict:
    await ensure_vault(session, user)
    d = day.strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rel = f"50-Daily/{d}.md"
    full = resolve_user_path(user.id, rel)
    if full.exists():
        return await read_file(session, user, rel)
    content = (
        f"---\ntitle: 日记 {d}\ntags: [daily]\ndate: {d}\n---\n\n# 日记 {d}\n\n"
        f"## 今日学习\n\n-\n\n## 收获\n\n-\n\n## 明日计划\n\n-\n"
    )
    return await write_file(session, user, rel, content)


async def list_bookmarks(session: AsyncSession, user: User) -> list[dict]:
    vault = await ensure_vault(session, user)
    meta = _vault_meta(vault)
    bookmarks = meta.get("bookmarks")
    return bookmarks if isinstance(bookmarks, list) else []


async def toggle_bookmark(session: AsyncSession, user: User, path: str, title: str = "") -> dict:
    vault = await ensure_vault(session, user)
    rel = _safe_rel(path)
    meta = _vault_meta(vault)
    bookmarks: list[dict] = list(meta.get("bookmarks") or [])
    existing = next((b for b in bookmarks if b.get("path") == rel), None)
    if existing:
        bookmarks = [b for b in bookmarks if b.get("path") != rel]
        added = False
    else:
        bookmarks.insert(
            0,
            {
                "path": rel,
                "title": title or Path(rel).stem,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
        bookmarks = bookmarks[:50]
        added = True
    meta["bookmarks"] = bookmarks
    vault.meta_json = meta
    await session.commit()
    return {"added": added, "bookmarks": bookmarks}


DEFAULT_CANVAS_GROUPS = [
    {
        "id": "g-planets",
        "type": "group",
        "label": "行星主线",
        "x": 40,
        "y": 40,
        "width": 420,
        "height": 280,
        "color": "4",
    },
    {
        "id": "g-clips",
        "type": "group",
        "label": "剪藏与证据",
        "x": 500,
        "y": 40,
        "width": 420,
        "height": 280,
        "color": "5",
    },
    {
        "id": "g-workshop",
        "type": "group",
        "label": "工坊产出",
        "x": 40,
        "y": 360,
        "width": 420,
        "height": 280,
        "color": "3",
    },
    {
        "id": "g-weak",
        "type": "group",
        "label": "薄弱与行动",
        "x": 500,
        "y": 360,
        "width": 420,
        "height": 280,
        "color": "1",
    },
]


def default_canvas_data() -> dict:
    return {"nodes": [dict(g) for g in DEFAULT_CANVAS_GROUPS], "edges": []}


async def read_canvas(session: AsyncSession, user: User, path: str = "") -> dict:
    await ensure_vault(session, user)
    rel = _safe_rel(path) if path else "60-Canvas/默认画布.canvas"
    if not rel.endswith(".canvas"):
        rel = f"{rel}.canvas"
    full = resolve_user_path(user.id, rel)
    if not full.exists():
        data = default_canvas_data()
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"path": rel, "data": data}
    data = json.loads(full.read_text(encoding="utf-8") or "{}")
    if not isinstance(data, dict):
        data = default_canvas_data()
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    # 空画布自动种入四分区
    if not data["nodes"]:
        data = default_canvas_data()
        full.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": rel, "data": data}


async def write_canvas(session: AsyncSession, user: User, path: str, data: dict) -> dict:
    await ensure_vault(session, user)
    rel = _safe_rel(path) if path else "60-Canvas/默认画布.canvas"
    if not rel.endswith(".canvas"):
        rel = f"{rel}.canvas"
    full = resolve_user_path(user.id, rel)
    full.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": data.get("nodes") if isinstance(data.get("nodes"), list) else [],
        "edges": data.get("edges") if isinstance(data.get("edges"), list) else [],
    }
    full.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    await bump_revision(session, user.id)
    return {"path": rel, "data": payload}


async def sync_manifest(session: AsyncSession, user: User) -> dict:
    """本机 Sync Agent：列出全部文件 path+hash+mtime。"""
    vault = await ensure_vault(session, user)
    root = vault_root(user.id)
    files: list[dict] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if ".obsidian" in p.parts and p.name not in ("app.json",):
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        files.append(
            {
                "path": rel,
                "hash": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
                "mtime": int(p.stat().st_mtime),
            }
        )
    return {"vault_name": vault.vault_name, "revision": vault.revision, "files": files}


async def sync_pull(session: AsyncSession, user: User, paths: list[str] | None = None) -> dict:
    """拉取文件内容（paths 为空则全量 md/canvas）。"""
    await ensure_vault(session, user)
    root = vault_root(user.id)
    wanted = [_safe_rel(p) for p in (paths or [])]
    items: list[dict] = []
    if wanted:
        targets = wanted
    else:
        targets = []
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".md", ".canvas", ".json"):
                targets.append(str(p.relative_to(root)).replace("\\", "/"))
    for rel in targets:
        full = resolve_user_path(user.id, rel)
        if not full.exists() or not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except OSError:
            continue
        items.append({"path": rel, "content": text, "hash": content_hash(text)})
    vault = (
        await session.execute(select(StudentVault).where(StudentVault.user_id == user.id))
    ).scalar_one()
    vault.last_synced_at = datetime.now(timezone.utc)
    await session.commit()
    return {"revision": vault.revision, "files": items}


async def sync_push(session: AsyncSession, user: User, files: list[dict]) -> dict:
    """本机推送文件到云端。files: [{path, content}]"""
    await ensure_vault(session, user)
    written = 0
    for item in files or []:
        path = str(item.get("path") or "")
        content = str(item.get("content") if item.get("content") is not None else "")
        if not path:
            continue
        rel = _safe_rel(path)
        full = resolve_user_path(user.id, rel)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        if rel.endswith(".md"):
            await _index_file(session, user.id, rel, content)
        written += 1
    rev = await bump_revision(session, user.id)
    vault = (
        await session.execute(select(StudentVault).where(StudentVault.user_id == user.id))
    ).scalar_one_or_none()
    if vault:
        vault.last_synced_at = datetime.now(timezone.utc)
        await session.commit()
    return {"written": written, "revision": rev}


async def preview_snippet(session: AsyncSession, user: User, path_or_title: str) -> dict:
    """Page preview：按路径或笔记名返回前几行。"""
    await ensure_vault(session, user)
    target = (path_or_title or "").strip()
    if not target:
        raise ValueError("缺少目标")
    rel = target
    if not target.endswith(".md") and "/" not in target:
        # 按标题/stem 找
        found = None
        root = vault_root(user.id)
        for p in root.rglob("*.md"):
            if p.stem == target or p.stem == Path(target).stem:
                found = str(p.relative_to(root)).replace("\\", "/")
                break
        if not found:
            return {"path": "", "title": target, "snippet": "（笔记尚未创建）", "exists": False}
        rel = found
    else:
        rel = _safe_rel(target if target.endswith(".md") else f"{target}.md")
    full = resolve_user_path(user.id, rel)
    if not full.exists():
        return {"path": rel, "title": Path(rel).stem, "snippet": "（笔记尚未创建）", "exists": False}
    text = full.read_text(encoding="utf-8")
    _fm, body = parse_frontmatter(text)
    lines = [ln for ln in body.splitlines() if ln.strip()][:8]
    snippet = "\n".join(lines)[:400]
    return {"path": rel, "title": Path(rel).stem, "snippet": snippet or body[:200], "exists": True}
