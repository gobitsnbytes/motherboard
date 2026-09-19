"""Layout contract for the onboarding forms.

Every signature must land on the ``Signature:`` line of its own block, exactly
once, in all five templates — the failure these guard against put the stamp on a
section heading and left ``[[sig29]]`` printed in the executed PDF.
"""

from pathlib import Path
import re
import tempfile

import fitz
from lxml import etree
import pytest

from app.services.onboarding_documents import (
    TEMPLATE_MANIFEST,
    _drop_blank_pages,
    _signature_box,
    resolve_signature_anchors,
)
from app.services.semantic_ooxml import (
    FORM_FIELDS,
    NS,
    annotate_package,
    derived_values,
    fields_for,
    signature_markers,
    unpack_docx,
)

FORM_KEYS = sorted(FORM_FIELDS)


def _annotated_paragraphs(document_key: str) -> list[str]:
    source = Path(__file__).resolve().parents[1] / "templates" / TEMPLATE_MANIFEST[document_key]["template"]
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "package"
        unpack_docx(source, package)
        values = {field.id: f"<{field.id}>" for field in FORM_FIELDS[document_key] if field.type != "signature"}
        values |= derived_values(document_key, participant_name="Test Person")
        values |= signature_markers(document_key)
        assert annotate_package(package, document_key, values) == []
        root = etree.parse(str(package / "word" / "document.xml")).getroot()
        return [
            " ".join("".join(p.xpath(".//w:t/text()", namespaces=NS)).split())
            for p in root.xpath(".//w:p", namespaces=NS)
        ]


@pytest.mark.parametrize("document_key", FORM_KEYS)
def test_every_marker_appears_exactly_once(document_key: str) -> None:
    body = "\n".join(_annotated_paragraphs(document_key))
    for marker in signature_markers(document_key).values():
        assert body.count(marker) == 1, f"{document_key}: {marker} is not a unique PDF anchor"


@pytest.mark.parametrize("document_key", FORM_KEYS)
def test_signatures_land_on_a_clear_line_under_their_own_block(document_key: str) -> None:
    """A marker sharing a line with other text is the bug from the field: the
    stamp gets drawn straight over that text."""
    paragraphs = _annotated_paragraphs(document_key)
    for field in fields_for(document_key):
        if field["type"] != "signature":
            continue
        marker = signature_markers(document_key)[field["id"]]
        index = next(i for i, text in enumerate(paragraphs) if marker in text)
        assert paragraphs[index] == marker, f"{document_key}: {marker} shares a line with {paragraphs[index]!r}"
        preceding = next(text for text in reversed(paragraphs[:index]) if text)
        assert field["anchor"].casefold() in preceding.casefold(), (
            f"{document_key}: {field['id']} sits under {preceding!r}, not its own {field['anchor']!r}"
        )


@pytest.mark.parametrize("document_key", FORM_KEYS)
def test_printed_name_accompanies_the_signature(document_key: str) -> None:
    paragraphs = _annotated_paragraphs(document_key)
    assert any(text.startswith("Full Name (Print):") and "Test Person" in text for text in paragraphs)


@pytest.mark.parametrize("document_key", FORM_KEYS)
def test_blank_optional_fields_do_not_print_filler(document_key: str) -> None:
    source = Path(__file__).resolve().parents[1] / "templates" / TEMPLATE_MANIFEST[document_key]["template"]
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "package"
        unpack_docx(source, package)
        annotate_package(package, document_key, {})
        body = (package / "word" / "document.xml").read_text("utf-8")
        assert "[Enter " not in re.sub(r"<[^>]+>", "", body)


@pytest.mark.parametrize("document_key", FORM_KEYS)
def test_auto_fields_are_hidden_from_editors(document_key: str) -> None:
    editable = {field["id"] for field in fields_for(document_key)}
    auto = {field.id for field in FORM_FIELDS[document_key] if field.editable_by == "auto"}
    assert auto and not (auto & editable)


def test_multiline_values_get_their_own_paragraph() -> None:
    paragraphs = _annotated_paragraphs("volunteer")
    label = "Briefly describe your relevant skills and experience:"
    index = next(i for i, text in enumerate(paragraphs) if text.startswith(label))
    assert paragraphs[index] == label, "prose was tab-appended to its label and will wrap into the margin"
    assert "bnb.volunteer.skills" in paragraphs[index + 1]


def test_signature_box_is_a_box_not_a_glyph_run() -> None:
    page = fitz.Rect(0, 0, 612, 792)
    marker = fitz.Rect(100, 400, 150, 412)  # one line of text
    box = _signature_box(marker, page)
    assert box.width >= 150 and box.height >= 36
    assert page.contains(box)

    # A marker against the right or bottom edge must stay on the page.
    edge = _signature_box(fitz.Rect(600, 788, 610, 792), page)
    assert page.contains(edge)


def test_markers_become_boxes_and_are_erased(tmp_path: Path) -> None:
    """The reported defect: '[[sig29]]' printed in the executed document with the
    signature image squashed on top of it."""
    markers = signature_markers("volunteer")
    path = tmp_path / "rendered.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        for offset, marker in enumerate(markers.values()):
            page.insert_text((72, 200 + 60 * offset), marker, fontsize=11)
        pdf.save(str(path))

    placements = resolve_signature_anchors(path, "volunteer")
    assert len(placements) == len(markers)
    for _field, placement in placements:
        assert placement["width"] > 10 and placement["height"] > 3  # per cent of the page
        assert 0 <= placement["pos_x"] and placement["pos_x"] + placement["width"] <= 100
        assert 0 <= placement["pos_y"] and placement["pos_y"] + placement["height"] <= 100

    with fitz.open(str(path)) as pdf:
        body = "".join(page.get_text() for page in pdf)
    for marker in markers.values():
        assert marker not in body


def test_a_missing_or_duplicated_marker_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(str(path))
    with pytest.raises(RuntimeError, match="anchor contract failed"):
        resolve_signature_anchors(path, "volunteer")


def test_blank_pages_are_dropped(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    with fitz.open() as pdf:
        pdf.new_page().insert_text((72, 72), "Content")
        pdf.new_page()  # Writer's trailing empty sheet
        pdf.save(str(path))
    _drop_blank_pages(path)
    with fitz.open(str(path)) as pdf:
        assert pdf.page_count == 1


def test_an_entirely_blank_document_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(str(path))
    _drop_blank_pages(path)
    with fitz.open(str(path)) as pdf:
        assert pdf.page_count == 1
