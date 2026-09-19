import tempfile
import zipfile
from pathlib import Path

import pytest
from docx import Document
from lxml import etree

from app.services.onboarding_documents import TEMPLATE_MANIFEST, template_root
from app.services.semantic_ooxml import (
    FORM_FIELDS,
    NS,
    annotate_package,
    package_hash,
    repack_docx,
    state_hash,
    unpack_docx,
    validate_values,
)


@pytest.mark.parametrize("document_key", ["volunteer", "parent_consent", "fork_certificate", "fork_agreement", "fork_application"])
def test_real_templates_round_trip_with_all_semantic_controls(document_key: str):
    source = template_root() / TEMPLATE_MANIFEST[document_key]["template"]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        package = root / "package"
        unpack_docx(source, package)
        assert annotate_package(package, document_key) == []
        xml = etree.parse(str(package / "word" / "document.xml"))
        tags = set(xml.xpath(".//w:sdtPr/w:tag/@w:val", namespaces=NS))
        assert {field.id for field in FORM_FIELDS[document_key]} <= tags
        output = repack_docx(package, root / "compiled.docx")
        assert Document(str(output)).paragraphs


def test_state_hash_chains_revision_and_values():
    first = state_hash(document_id="doc", revision=1, previous_hash=None, values={"name": "A"}, package_digest="package")
    second = state_hash(document_id="doc", revision=2, previous_hash=first, values={"name": "B"}, package_digest="package")
    assert first != second
    assert second == state_hash(document_id="doc", revision=2, previous_hash=first, values={"name": "B"}, package_digest="package")


def test_unpack_rejects_zip_traversal():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        malicious = root / "bad.docx"
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("../escape", "bad")
        with pytest.raises(ValueError, match="Unsafe OOXML"):
            unpack_docx(malicious, root / "out")


def test_role_validation_rejects_participant_editing_hq_fields():
    errors = validate_values("fork_certificate", {"director_names": "Someone"}, editor="participant")
    assert errors["director_names"] == "This field cannot be edited by this signer"
