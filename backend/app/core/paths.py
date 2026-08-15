from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
UPLOADS_DIR = BACKEND_ROOT / "uploads"
AVATARS_DIR = UPLOADS_DIR / "avatars"
NOTES_DIR = UPLOADS_DIR / "notes"
RESOURCES_DIR = UPLOADS_DIR / "resources"
STARLIB_DIR = UPLOADS_DIR / "starlib"
TREEHOLE_DIR = UPLOADS_DIR / "treehole"
SUPERVISION_DIR = UPLOADS_DIR / "supervision"
ORAL_DIR = UPLOADS_DIR / "oral"
INTERVIEW_DIR = UPLOADS_DIR / "interview"
ASSETS_DIR = BACKEND_ROOT / "assets"
PETS_DIR = ASSETS_DIR / "pets"
# 教材 / 考研指导书等本地 PDF（不拷贝进 uploads，静态挂载只读）
MATERIALS_DIR = PROJECT_ROOT / "资料"
# 每用户 Obsidian 兼容知识库（Markdown Vault）
VAULTS_DIR = BACKEND_ROOT / "vaults"


def ensure_storage_dirs() -> None:
    for path in (
        UPLOADS_DIR,
        AVATARS_DIR,
        NOTES_DIR,
        RESOURCES_DIR,
        STARLIB_DIR,
        TREEHOLE_DIR,
        ORAL_DIR,
        INTERVIEW_DIR,
        SUPERVISION_DIR,
        ASSETS_DIR,
        PETS_DIR,
        VAULTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
    # 资料目录由用户放置，不强制创建；存在则可供挂载
    if not MATERIALS_DIR.exists():
        MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
