"""Local filesystem storage for finance supporting documents.

Mirrors the pattern in app.services.onboarding_documents: a configurable
root directory, never committed to git (see MEMORY.md — uploaded documents
never live in Git). No new dependency; stdlib only.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/heic",
}


def storage_root() -> Path:
    root = Path(os.getenv("FINANCE_STORAGE_DIR", str(Path.cwd() / "data" / "finance")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_upload(content: bytes, *, original_filename: str) -> tuple[str, str]:
    """Write ``content`` under a random subpath and return (storage_path, sha256)."""
    digest = hashlib.sha256(content).hexdigest()
    suffix = Path(original_filename).suffix[:10]
    target_dir = storage_root() / digest[:2]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex}{suffix}"
    target.write_bytes(content)
    return str(target), digest
