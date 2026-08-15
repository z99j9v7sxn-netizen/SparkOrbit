"""星轨知识库 API（Obsidian 兼容 Vault）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_current_user
from app.services import vault_service as vault

router = APIRouter(prefix="/vault", tags=["vault"])


class FileWriteIn(BaseModel):
    path: str
    content: str = ""


class FileCreateIn(BaseModel):
    path: str
    content: str = ""


class ClipIn(BaseModel):
    title: str = "剪藏"
    content: str
    planet_slug: str = ""
    galaxy_slug: str = ""
    source: str = "clip"


@router.get("/meta")
async def vault_meta(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    row = await vault.ensure_vault(db, current_user)
    return {
        "vault_name": row.vault_name,
        "revision": row.revision,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else "",
        "last_analyzed_at": row.last_analyzed_at.isoformat() if row.last_analyzed_at else "",
    }


@router.get("/tree")
async def vault_tree(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    await vault.ensure_vault(db, current_user)
    return {"tree": vault.build_tree(current_user.id)}


@router.get("/file")
async def vault_get_file(
    path: str = Query(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.read_file(db, current_user, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/file")
async def vault_put_file(
    body: FileWriteIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.write_file(db, current_user, body.path, body.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/file")
async def vault_create_file(
    body: FileCreateIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.create_file(db, current_user, body.path, body.content)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/file")
async def vault_delete_file(
    path: str = Query(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.delete_file(db, current_user, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/search")
async def vault_search(
    q: str = "",
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await vault.search_files(db, current_user, q)


@router.get("/graph")
async def vault_graph(
    mode: str = "global",
    path: str = "",
    depth: int = 1,
    show_orphans: bool = True,
    existing_only: bool = False,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await vault.get_graph(
        db,
        current_user,
        mode=mode,
        path=path,
        depth=depth,
        show_orphans=show_orphans,
        existing_only=existing_only,
    )


@router.get("/backlinks")
async def vault_backlinks(
    path: str = Query(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.get_backlinks(db, current_user, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/open-hint")
async def vault_open_hint(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await vault.open_hint(db, current_user)


class VaultNameIn(BaseModel):
    vault_name: str


@router.post("/vault-name")
async def vault_set_name(
    body: VaultNameIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.update_vault_name(db, current_user, body.vault_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export.zip")
async def vault_export(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> Response:
    data = await vault.export_zip_bytes(db, current_user)
    hint = await vault.open_hint(db, current_user)
    # 导出文件名用 ASCII 的 SparkOrbit-*，便于解压后作为 Obsidian 库名
    filename = f"{hint.get('export_name') or hint.get('vault_name') or 'SparkOrbit-Vault'}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/clip")
async def vault_clip(
    body: ClipIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.ingest_clip(
            db,
            current_user,
            title=body.title,
            content=body.content,
            planet_slug=body.planet_slug,
            galaxy_slug=body.galaxy_slug,
            source=body.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/migrate-notes")
async def vault_migrate(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await vault.migrate_notes_from_db(db, current_user)


@router.post("/analyze")
async def vault_analyze(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await vault.analyze_vault_for_profile(db, current_user)


class WorkshopIngestIn(BaseModel):
    resource_id: str


@router.post("/ingest-workshop")
async def vault_ingest_workshop(
    body: WorkshopIngestIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.ingest_generated_resource(db, current_user, body.resource_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reindex")
async def vault_reindex(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await vault.reindex_all(db, current_user)


class TemplateCreateIn(BaseModel):
    template_path: str
    dest_path: str = ""
    vars: dict = {}


class CanvasWriteIn(BaseModel):
    path: str = "60-Canvas/默认画布.canvas"
    data: dict


class BookmarkIn(BaseModel):
    path: str
    title: str = ""


class SyncPushIn(BaseModel):
    files: list[dict] = []


class SyncPullIn(BaseModel):
    paths: list[str] = []


@router.get("/templates")
async def vault_templates(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await vault.list_templates(db, current_user)


@router.post("/templates/apply")
async def vault_apply_template(
    body: TemplateCreateIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.create_from_template(
            db,
            current_user,
            template_path=body.template_path,
            dest_path=body.dest_path,
            vars=body.vars,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/daily")
async def vault_daily(
    day: str = "",
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await vault.create_daily_note(db, current_user, day=day)


@router.get("/bookmarks")
async def vault_bookmarks(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await vault.list_bookmarks(db, current_user)


@router.post("/bookmarks/toggle")
async def vault_bookmark_toggle(
    body: BookmarkIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.toggle_bookmark(db, current_user, body.path, body.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/canvas")
async def vault_get_canvas(
    path: str = "60-Canvas/默认画布.canvas",
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.read_canvas(db, current_user, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/canvas")
async def vault_put_canvas(
    body: CanvasWriteIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.write_canvas(db, current_user, body.path, body.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/preview")
async def vault_preview(
    q: str = Query(..., description="路径或笔记名"),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.preview_snippet(db, current_user, q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sync/manifest")
async def vault_sync_manifest(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await vault.sync_manifest(db, current_user)


@router.post("/sync/pull")
async def vault_sync_pull(
    body: SyncPullIn = SyncPullIn(),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    paths = body.paths or []
    return await vault.sync_pull(db, current_user, paths or None)


@router.post("/sync/push")
async def vault_sync_push(
    body: SyncPushIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await vault.sync_push(db, current_user, body.files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
