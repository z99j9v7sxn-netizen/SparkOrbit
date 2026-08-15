from app.data.career_portals import list_portals, list_windows, portal_brief
from app.data.career_questions import list_career_questions, list_question_companies
from app.data.career_templates import get_resume_template, list_resume_templates
from app.services.deck_themes import list_deck_templates, resolve_theme
from app.services.interview_resume import (
    export_resume_docx,
    match_resume,
    optimize_resume,
)


def test_career_portals_nonempty():
    portals = list_portals()
    assert len(portals) >= 15
    assert all(p["url"].startswith("http") for p in portals)
    groups = {p["group"] for p in portals}
    assert {"互联网", "硬件制造", "新能源车", "升学考公"} <= groups
    bytedance = next(p for p in portals if p["id"] == "bytedance")
    assert "bytedance.com" in bytedance["url"]
    assert bytedance["accent"].startswith("#")
    assert bytedance["logo_host"] == "bytedance.com"
    assert all(p.get("logo_host") for p in portals)


def test_career_windows_bind_portals():
    windows = list_windows()
    assert windows
    autumn = next(w for w in windows if w["id"] == "autumn-open")
    assert "字节跳动" in autumn["companies"]
    assert autumn["when"]


def test_resume_templates_and_opensource():
    data = list_resume_templates()
    ids = {t["id"] for t in data["templates"]}
    assert ids == {"editorial", "navy_rail", "folio", "ats_plain"}
    editorial = get_resume_template("campus_one_pager")
    assert editorial and editorial["id"] == "editorial" and editorial["allow_photo"] is True
    ats = get_resume_template("ats_en")
    assert ats and ats["id"] == "ats_plain" and ats["allow_photo"] is False
    assert get_resume_template("missing") is None
    assert any("github.com" in x["url"] for x in data["open_source"])


def test_career_questions_filter():
    all_q = list_career_questions()
    assert len(all_q) >= 16
    byte_q = list_career_questions(company="bytedance")
    assert byte_q
    assert all(q["company_id"] == "bytedance" for q in byte_q)
    backend_q = list_career_questions(job_role="backend")
    assert backend_q
    companies = list_question_companies()
    assert any(c["id"] == "tencent" for c in companies)


def test_deck_themes_catalog_and_fallback():
    templates = list_deck_templates()
    assert {t["id"] for t in templates} == {"orbit", "chalkboard", "academic", "fresh", "minimal"}
    assert resolve_theme("orbit")["id"] == "orbit"
    assert resolve_theme("nope")["id"] == "orbit"
    assert resolve_theme("")["id"] == "orbit"
    assert all(t["colors"]["bg"].startswith("#") for t in templates)


def test_optimize_and_match_degraded_without_llm(monkeypatch):
    import asyncio

    from app.services import interview_resume as mod

    monkeypatch.setattr(mod, "llm_available", lambda: False)
    profile = {"skills": ["Python", "SQL"], "highlights": ["做过订单服务"]}
    opt = asyncio.run(optimize_resume(profile=profile, target_role="backend"))
    assert opt["degraded"] is True
    assert 0 <= opt["score"] <= 100
    assert opt["issues"]
    assert opt["rewritten_markdown"]
    match = asyncio.run(match_resume(profile=profile, target_role="backend"))
    assert match["degraded"] is True
    assert match["recommended_portals"]
    empty = asyncio.run(optimize_resume())
    assert empty["score"] == 0
    assert "上传" in empty["issues"][0]


def test_export_resume_docx_bytes():
    blob = export_resume_docx(
        {
            "name": "张三",
            "contact": "13800000000",
            "education": ["某大学 计算机"],
            "skills": ["Python"],
            "projects": ["订单系统 / 后端 / 降低延迟"],
        },
        "campus_one_pager",
    )
    assert blob[:2] == b"PK"
    assert len(blob) > 1000


_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_FIELDS = {
    "name": "李四",
    "intent": "后端开发",
    "city": "杭州",
    "contact": "13800000000",
    "email": "li@example.com",
    "education": ["某大学 计算机 GPA 3.8"],
    "experience": ["某厂 / 后端实习 / 延迟下降 20%"],
    "projects": ["订单系统 / 负责人 / QPS 提升"],
    "skills": ["Python", "SQL"],
    "certificates": ["CET-6"],
    "photo_data_url": _PNG,
}


def test_export_resume_html_photo_and_ats():
    from app.services.resume_export import build_resume_html, export_resume

    gold = build_resume_html(_FIELDS, "editorial")
    assert "cv--editorial" in gold
    assert "data:image" in gold
    assert "grid-template-columns: 32%" in gold
    assert "求职意向" in gold or "后端开发" in gold

    navy = build_resume_html(_FIELDS, "navy_rail")
    assert "cv--navy_rail" in navy
    assert "data:image" in navy

    ats = build_resume_html(_FIELDS, "ats_plain")
    assert "cv--ats_plain" in ats
    assert "data:image" not in ats
    assert "证件照" not in ats

    blob, media, name = export_resume(_FIELDS, "editorial", "html")
    assert media.startswith("text/html")
    assert name.endswith(".html")
    assert b"cv--editorial" in blob

    md, md_media, md_name = export_resume(_FIELDS, "editorial", "md")
    assert md_media.startswith("text/markdown")
    assert md_name.endswith(".md")
    assert b"\xe6\x9d\x8e\xe5\x9b\x9b" in md  # 李四


def test_export_resume_docx_embeds_photo_except_ats():
    from io import BytesIO
    from zipfile import ZipFile

    from app.services.resume_export import export_resume_docx as export_docx

    gold = export_docx(_FIELDS, "editorial")
    names = ZipFile(BytesIO(gold)).namelist()
    assert any(n.startswith("word/media/") for n in names)

    navy = export_docx(_FIELDS, "navy_rail")
    assert any(n.startswith("word/media/") for n in ZipFile(BytesIO(navy)).namelist())

    ats = export_docx(_FIELDS, "ats_plain")
    assert not any(n.startswith("word/media/") for n in ZipFile(BytesIO(ats)).namelist())


def test_export_deck_pptx_themes(tmp_path, monkeypatch):
    from app.services import deck_export

    monkeypatch.setattr(deck_export, "_MEDIA_GENERATED", tmp_path)
    slides = [{"title": "第一页", "bullet_points": ["要点 A", "要点 B"], "narration": "讲解"}]
    url_a = deck_export.export_deck_pptx(title="测试课件", slides=slides, planet_slug="demo", theme_id="orbit")
    url_b = deck_export.export_deck_pptx(title="测试课件", slides=slides, planet_slug="demo", theme_id="academic")
    files = list(tmp_path.glob("*.pptx"))
    assert len(files) == 2
    assert files[0].stat().st_size != files[1].stat().st_size or files[0].read_bytes() != files[1].read_bytes()
    assert url_a.startswith("/static/media/generated/")
    assert url_b.startswith("/static/media/generated/")


def test_application_status_whitelist():
    from app.services.interview_applications import ALLOWED_STATUS

    assert ALLOWED_STATUS == {"wishlist", "applied", "oa", "interview", "offer", "rejected"}


def test_portal_brief_limit():
    rows = portal_brief(limit=3)
    assert len(rows) == 3
    assert {"id", "name", "url"} <= set(rows[0].keys())
