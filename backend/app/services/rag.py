"""RAG：分页切块 + 页码 citation。"""
import hashlib
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_CHROMA_AVAILABLE = False
_client = None
_collection = None
_OFFLINE = os.environ.get("SPARKORBIT_CHROMA_OFFLINE", "1").strip() != "0"
_ONNX_MODEL_DIR = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
_ONNX_REQUIRED = (
    "config.json",
    "model.onnx",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
)

try:
    import chromadb  # type: ignore

    _CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore


def onnx_model_ready(model_dir: Path | None = None) -> bool:
    root = model_dir or _ONNX_MODEL_DIR
    onnx_dir = root / "onnx"
    return all((onnx_dir / name).is_file() for name in _ONNX_REQUIRED)


def _install_offline_guard() -> None:
    """缺模型时禁止 Chroma 在请求路径联网下载 onnx.tar.gz。"""
    if not _CHROMA_AVAILABLE or not _OFFLINE:
        return
    try:
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (  # type: ignore
            ONNXMiniLM_L6_V2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("chroma offline guard skip: %s", exc)
        return

    if getattr(ONNXMiniLM_L6_V2, "_sparkorbit_offline_guard", False):
        return

    orig = ONNXMiniLM_L6_V2._download_model_if_not_exists

    def _guard(self) -> None:  # type: ignore[no-untyped-def]
        extracted = os.path.join(self.DOWNLOAD_PATH, self.EXTRACTED_FOLDER_NAME, "model.onnx")
        if not os.path.exists(extracted):
            raise FileNotFoundError(
                f"Chroma ONNX missing at {self.DOWNLOAD_PATH}; "
                "bake vendor/chroma_onnx into the image (SPARKORBIT_CHROMA_OFFLINE=1)"
            )
        return orig(self)

    ONNXMiniLM_L6_V2._download_model_if_not_exists = _guard  # type: ignore[method-assign]
    ONNXMiniLM_L6_V2._sparkorbit_offline_guard = True  # type: ignore[attr-defined]
    logger.info("chroma offline guard enabled (no runtime onnx download)")


_install_offline_guard()


def rag_available() -> bool:
    return _CHROMA_AVAILABLE and onnx_model_ready()


def _persist_dir() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(base, "chroma_data")
    os.makedirs(path, exist_ok=True)
    return path


def _get_collection():
    global _client, _collection
    if not _CHROMA_AVAILABLE:
        return None
    if not onnx_model_ready():
        logger.warning("chroma onnx not ready at %s — RAG disabled", _ONNX_MODEL_DIR)
        return None
    if _collection is None:
        try:
            _client = chromadb.PersistentClient(path=_persist_dir())
            _collection = _client.get_or_create_collection(
                name="sparkorbit_syllabus",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chroma init failed: %s", exc)
            return None
    return _collection


def warmup_chroma() -> dict:
    """启动预热：确认本地 ONNX 可用，并做一次极小 upsert/query。"""
    status = {
        "onnx_ready": onnx_model_ready(),
        "offline": _OFFLINE,
        "ok": False,
        "error": "",
    }
    if not status["onnx_ready"]:
        status["error"] = f"missing onnx under {_ONNX_MODEL_DIR / 'onnx'}"
        logger.error("chroma warmup skipped: %s", status["error"])
        return status
    try:
        col = _get_collection()
        if col is None:
            status["error"] = "collection unavailable"
            return status
        # 触发默认 embedding 一次（仅本地模型）
        col.upsert(
            ids=["__sparkorbit_warmup__"],
            documents=["sparkorbit chroma warmup"],
            metadatas=[{"galaxy": "__warmup__", "source": "warmup", "index": 0}],
        )
        col.query(query_texts=["warmup"], n_results=1)
        status["ok"] = True
        logger.info("chroma warmup ok (local onnx)")
    except Exception as exc:  # noqa: BLE001
        status["error"] = str(exc)
        logger.warning("chroma warmup failed: %s", exc)
    return status


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 5)
    chunks: List[str] = []
    i = 0
    while i < len(text):
        chunk = text[i : i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if i + chunk_size >= len(text):
            break
        i += chunk_size - overlap
    return chunks


def ingest_syllabus(
    galaxy_slug: str,
    text: str,
    source: str = "seed",
    *,
    planet_slug: str = "",
    book_id: str = "",
    book_title: str = "",
    page_no: int = 0,
) -> int:
    """将教学大纲文本灌入向量库，返回写入块数。"""
    col = _get_collection()
    if col is None:
        return 0
    chunks = _chunk_text(text)
    if not chunks:
        return 0
    ids = []
    docs = []
    metas = []
    for i, chunk in enumerate(chunks):
        key = f"{galaxy_slug}:{planet_slug}:{source}:{book_id}:{page_no}:{i}:{chunk[:80]}"
        doc_id = hashlib.md5(key.encode()).hexdigest()
        ids.append(doc_id)
        docs.append(chunk)
        metas.append(
            {
                "galaxy": galaxy_slug,
                "source": source,
                "index": i,
                "planet_slug": planet_slug or "",
                "book_id": book_id or "",
                "book_title": book_title or source,
                "page_no": int(page_no or 0),
            }
        )
    try:
        col.upsert(ids=ids, documents=docs, metadatas=metas)
        return len(chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag ingest failed: %s", exc)
        return 0


def ingest_pages(
    *,
    galaxy_slug: str,
    pages: list[dict],
    source: str,
    book_id: str = "",
    book_title: str = "",
    planet_slug: str = "",
) -> int:
    """按页灌入：pages=[{page, text}, ...]。"""
    total = 0
    for p in pages:
        page_no = int(p.get("page") or 0)
        text = str(p.get("text") or "")
        total += ingest_syllabus(
            galaxy_slug,
            text,
            source=source,
            planet_slug=planet_slug,
            book_id=book_id,
            book_title=book_title,
            page_no=page_no,
        )
    return total


def retrieve(topic: str, galaxy_slug: Optional[str] = None, k: int = 3) -> List[str]:
    hits = retrieve_citations(topic, galaxy_slug=galaxy_slug, k=k)
    return [h["snippet"] for h in hits if h.get("snippet")]


def retrieve_citations(topic: str, galaxy_slug: Optional[str] = None, k: int = 3) -> List[dict]:
    """结构化检索，含页码 citation。"""
    col = _get_collection()
    if col is None or not topic:
        return []
    try:
        where = {"galaxy": galaxy_slug} if galaxy_slug else None
        result = col.query(query_texts=[topic], n_results=k, where=where)
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        out: List[dict] = []
        for i, doc in enumerate(docs):
            if not doc:
                continue
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            page_no = int(meta.get("page_no") or 0)
            book_title = str(meta.get("book_title") or meta.get("source") or "校本资料")
            cite = f"《{book_title}》p.{page_no}" if page_no else f"《{book_title}》"
            score = 1.0
            if i < len(distances) and distances[i] is not None:
                try:
                    score = max(0.0, 1.0 - float(distances[i]))
                except Exception:
                    score = 0.5
            out.append(
                {
                    "text": str(doc),
                    "snippet": str(doc)[:280],
                    "book": book_title,
                    "book_id": str(meta.get("book_id") or ""),
                    "page": page_no,
                    "citation": cite,
                    "galaxy": str(meta.get("galaxy", galaxy_slug or "")),
                    "source": str(meta.get("source", "syllabus")),
                    "planet_slug": str(meta.get("planet_slug") or ""),
                    "score": round(score, 3),
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag retrieve_citations failed: %s", exc)
        return []


def build_rag_context(topic: str, galaxy_slug: Optional[str] = None) -> str:
    hits = retrieve_citations(topic, galaxy_slug=galaxy_slug, k=3)
    if not hits:
        return ""
    lines = []
    for h in hits:
        lines.append(f"[{h.get('citation')}] {h.get('snippet')}")
    joined = "\n---\n".join(lines)
    return f"【校本星库依据（请引用页码，避免幻觉）】\n{joined}\n【请严格依据以上材料作答】"


def query_sources(topic: str, galaxy_slug: Optional[str] = None, n: int = 3) -> List[dict]:
    hits = retrieve_citations(topic, galaxy_slug=galaxy_slug, k=n)
    return [
        {
            "galaxy": h.get("galaxy", ""),
            "source": h.get("source", "syllabus"),
            "snippet": h.get("snippet", ""),
            "knowledge_point_id": h.get("planet_slug", ""),
            "citation": h.get("citation", ""),
            "page": h.get("page", 0),
            "book": h.get("book", ""),
        }
        for h in hits
    ]
