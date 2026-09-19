"""Private, durable Qenlo retrieval for the legal agent.

Qenlo owns only derived vectors and source metadata. PostgreSQL remains the
canonical store for contracts and IAM; Qenlo is rebuilt atomically whenever
the approved source corpus changes.
"""

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from qenlo import Collection, Filter, Record

from app.config import get_settings

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def keyword_search(corpus: list[dict[str, str]], question: str, k: int = 6) -> list[dict[str, str]]:
    """Deterministic degraded mode used if Qenlo cannot serve a query."""
    query_tokens = set(_TOKEN_RE.findall((question or "").lower()))
    scored = [
        (len(query_tokens.intersection(_TOKEN_RE.findall(chunk["text"].lower()))), index, chunk)
        for index, chunk in enumerate(corpus)
    ]
    return [chunk for score, _, chunk in sorted(scored, key=lambda item: (-item[0], item[1])) if score][:k]


def _vector(text: str, dimension: int) -> tuple[float, ...]:
    """Stable local feature embedding; no legal text leaves the API process."""
    values = [0.0] * dimension
    for token in _TOKEN_RE.findall((text or "").lower()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        slot = int.from_bytes(digest, "big") % dimension
        values[slot] += 1.0
    norm = sum(v * v for v in values) ** 0.5
    return tuple(v / norm for v in values) if norm else tuple(values)


def _record_id(chunk: dict[str, str]) -> int:
    raw = "\x1f".join(chunk.get(key, "") for key in ("label", "title", "text"))
    return int.from_bytes(hashlib.blake2b(raw.encode(), digest_size=8).digest(), "big") & ((1 << 63) - 1)


class LegalRetrievalService:
    """Durable Qenlo index with a JSON manifest for source reconstruction."""

    def __init__(self, data_dir: str | None = None, dimension: int | None = None):
        settings = get_settings()
        self.root = Path(data_dir or settings.legal_qenlo_data_dir)
        self.dimension = dimension or settings.legal_qenlo_dimension
        self.collection_path = self.root / "legal.qn"
        self.manifest_path = self.root / "manifest.json"

    def _fingerprint(self, corpus: list[dict[str, str]]) -> str:
        payload = json.dumps(corpus, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _load_manifest(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _rebuild(self, corpus: list[dict[str, str]], fingerprint: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        staging = self.root / "legal.staging.qn"
        if staging.exists():
            shutil.rmtree(staging)
        db = Collection.create(staging, self.dimension)
        records: dict[str, dict[str, str]] = {}
        try:
            now = int(time.time())
            for chunk in corpus:
                record_id = _record_id(chunk)
                records[str(record_id)] = chunk
                db.add(Record(id=record_id, user_id=1, timestamp=now, vector=_vector(chunk["text"], self.dimension)))
            db.flush()
        finally:
            db.close()
        if self.collection_path.exists():
            shutil.rmtree(self.collection_path)
        os.replace(staging, self.collection_path)
        self.manifest_path.write_text(json.dumps({"fingerprint": fingerprint, "dimension": self.dimension, "records": records}, ensure_ascii=False), encoding="utf-8")

    def search(self, corpus: list[dict[str, str]], question: str, k: int = 6) -> list[dict[str, str]]:
        if not corpus or not question.strip():
            return []
        fingerprint = self._fingerprint(corpus)
        manifest = self._load_manifest()
        if not manifest or manifest.get("fingerprint") != fingerprint or manifest.get("dimension") != self.dimension:
            self._rebuild(corpus, fingerprint)
            manifest = self._load_manifest() or {"records": {}}
        db = Collection.open(self.collection_path, self.dimension)
        try:
            response = db.search(_vector(question, self.dimension), filter=Filter(user_id=1), k=k)
            query_tokens = set(_TOKEN_RE.findall(question.lower()))
            return [
                manifest["records"][str(hit.id)]
                for hit in response.results
                if str(hit.id) in manifest["records"]
                and query_tokens.intersection(_TOKEN_RE.findall(manifest["records"][str(hit.id)]["text"].lower()))
            ]
        finally:
            db.close()

    def status(self) -> dict[str, Any]:
        manifest = self._load_manifest()
        return {"backend": "qenlo", "ready": bool(manifest and self.collection_path.exists()), "indexed_chunks": len((manifest or {}).get("records", {}))}
