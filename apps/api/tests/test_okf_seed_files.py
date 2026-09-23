from app.db import seed as seed_module


def test_seed_okf_rules_preserves_existing_files_and_creates_missing(
    tmp_path, monkeypatch
):
    rules = [
        {
            "file_name": "existing.md",
            "title": "Existing",
            "description": "Should stay untouched",
            "tags": ["legal"],
            "content": "Generated replacement",
        },
        {
            "file_name": "missing.md",
            "title": "Missing",
            "description": "Should be created",
            "tags": ["legal"],
            "content": "Generated content",
        },
    ]
    monkeypatch.setattr(seed_module, "OKF_LEGAL_RULES", rules)
    existing = tmp_path / "existing.md"
    original = b"---\r\ntitle: Existing\r\n---\r\nLocally maintained.\r\n"
    existing.write_bytes(original)

    seed_module.seed_okf_rules(str(tmp_path))

    assert existing.read_bytes() == original
    created = tmp_path / "missing.md"
    assert "Generated content" in created.read_text(encoding="utf-8")

    created.write_text("Locally edited.\n", encoding="utf-8")
    seed_module.seed_okf_rules(str(tmp_path))
    assert created.read_text(encoding="utf-8") == "Locally edited.\n"
