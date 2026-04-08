from pathlib import Path
from typing import Dict, List

from utils.db import list_session_files, save_session_file

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore

try:
    import docx2txt
except Exception:  # pragma: no cover
    docx2txt = None  # type: ignore

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def extract_text_from_file(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf" and PdfReader:
        try:
            reader = PdfReader(str(file_path))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    if suffix == ".docx" and docx2txt:
        try:
            return docx2txt.process(str(file_path)) or ""
        except Exception:
            return ""
    return ""


def save_uploaded_context(session_id: str, filename: str, content: bytes) -> Dict[str, object]:
    safe_name = "".join(ch for ch in filename if ch.isalnum() or ch in {"-", "_", ".", " "}).strip() or "uploaded_file"
    path = UPLOAD_DIR / f"{session_id}_{safe_name}"
    path.write_bytes(content)
    extracted_text = extract_text_from_file(path)
    save_session_file(session_id, safe_name, str(path), extracted_text)
    return {"file_name": safe_name, "file_path": str(path), "extracted_text": extracted_text, "chars": len(extracted_text)}


def build_context_injection(session_id: str) -> str:
    files = list_session_files(session_id)
    snippets: List[str] = []
    for file in files:
        text = (file.get("extracted_text") or "").strip()
        if text:
            snippets.append(f"Source: {file['file_name']}\n{text[:4000]}")
    return "\n\n".join(snippets)
