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
    repack_docx,
    signature_markers,
    state_hash,
    unpack_docx,
    validate_values,
)


@pytest.mark.parametrize(
    "document_key",
    [
        "volunteer",
        "parent_consent",
        "fork_certificate",
        "fork_agreement",
        "fork_application",
    ],
)
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


@pytest.mark.parametrize(
    "document_key",
    [
        "volunteer",
        "parent_consent",
        "fork_certificate",
        "fork_agreement",
        "fork_application",
    ],
)
def test_each_signature_marker_appears_exactly_once_in_the_compiled_document(
    document_key: str,
):
    """The signing anchors are found by text search, so duplicates break compilation."""
    markers = signature_markers(document_key)
    assert markers
    source = template_root() / TEMPLATE_MANIFEST[document_key]["template"]
    with tempfile.TemporaryDirectory() as directory:
        package = Path(directory) / "package"
        unpack_docx(source, package)
        assert annotate_package(package, document_key, markers) == []
        text = "".join(
            etree.parse(str(package / "word" / "document.xml")).xpath(
                "//w:t/text()", namespaces=NS
            )
        )
    for marker in markers.values():
        assert text.count(marker) == 1, f"{marker} appears {text.count(marker)} times"
        assert " " not in marker


def test_state_hash_chains_revision_and_values():
    first = state_hash(
        document_id="doc",
        revision=1,
        previous_hash=None,
        values={"name": "A"},
        package_digest="package",
    )
    second = state_hash(
        document_id="doc",
        revision=2,
        previous_hash=first,
        values={"name": "B"},
        package_digest="package",
    )
    assert first != second
    assert second == state_hash(
        document_id="doc",
        revision=2,
        previous_hash=first,
        values={"name": "B"},
        package_digest="package",
    )


def test_unpack_rejects_zip_traversal():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        malicious = root / "bad.docx"
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("../escape", "bad")
        with pytest.raises(ValueError, match="Unsafe OOXML"):
            unpack_docx(malicious, root / "out")


def test_role_validation_rejects_participant_editing_hq_fields():
    errors = validate_values(
        "fork_certificate", {"director_names": "Someone"}, editor="participant"
    )
    assert errors["director_names"] == "This field cannot be edited by this signer"


def test_validate_values_editor_all_validates_required_fields_across_roles():
    # When validating whole document before compilation, all template fields are allowed
    # and required fields across the entire document are checked
    empty_errors = validate_values("volunteer", {}, editor="all", final=True)
    assert "bnb.volunteer.full_name" in empty_errors
    assert empty_errors["bnb.volunteer.full_name"] == "This field is required"

    # All required fields filled
    valid_values = {
        "bnb.volunteer.full_name": "Test Volunteer",
        "bnb.volunteer.date_of_birth": "2005-01-01",
        "bnb.volunteer.phone": "+919876543210",
        "bnb.volunteer.email": "test@example.com",
        "bnb.volunteer.city": "Lucknow",
        "bnb.volunteer.state": "UP",
        "bnb.volunteer.primary_track": "Tech",
        "bnb.volunteer.signed_place": "Lucknow",
        "bnb.volunteer.assigned_role": "Core Tech",  # HQ field
    }
    no_errors = validate_values("volunteer", valid_values, editor="all", final=True)
    assert no_errors == {}


def test_validate_values_final_submission_ignores_other_role_existing_fields():
    # When participant submits for review (final=True, editor='participant'), existing HQ fields
    # must not trigger "This field cannot be edited by this signer"
    values = {
        "bnb.volunteer.full_name": "Test Volunteer",
        "bnb.volunteer.date_of_birth": "2005-01-01",
        "bnb.volunteer.phone": "+919876543210",
        "bnb.volunteer.email": "test@example.com",
        "bnb.volunteer.city": "Lucknow",
        "bnb.volunteer.state": "UP",
        "bnb.volunteer.primary_track": "Tech",
        "bnb.volunteer.signed_place": "Lucknow",
        "bnb.volunteer.assigned_role": "Core Tech",  # HQ field already present
    }
    participant_errors = validate_values(
        "volunteer", values, editor="participant", final=True
    )
    assert participant_errors == {}
