"""The Foundation seal must be a real signature, not a picture of one."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.services import dsc


@pytest.fixture
def configured_seal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "GOBITSNBYTES FOUNDATION Test Seal")]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pfx = tmp_path / "seal.p12"
    pfx.write_bytes(
        serialization.pkcs12.serialize_key_and_certificates(
            b"seal", key, cert, None, serialization.BestAvailableEncryption(b"secret")
        )
    )
    monkeypatch.setenv("DSC_PFX_PATH", str(pfx))
    monkeypatch.setenv("DSC_PFX_PASSPHRASE", "secret")
    monkeypatch.delenv("DSC_TSA_URL", raising=False)
    return pfx


def _pdf(tmp_path: Path) -> bytes:
    path = tmp_path / "doc.pdf"
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), "Executed contract")
        document.save(str(path))
    return path.read_bytes()


def test_unconfigured_seal_fails_loudly_rather_than_pretending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DSC_PFX_PATH", raising=False)
    assert not dsc.is_configured()
    with pytest.raises(dsc.DSCUnavailable):
        dsc.seal_pdf(b"%PDF-1.7\n", reason="test")


def test_seal_embeds_a_verifiable_signature(
    tmp_path: Path, configured_seal: Path
) -> None:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    assert dsc.is_configured()
    sealed = dsc.seal_pdf(_pdf(tmp_path), reason="Execution of Test Agreement")

    import io

    reader = PdfFileReader(io.BytesIO(sealed))
    assert len(reader.embedded_signatures) == 1
    status = validate_pdf_signature(reader.embedded_signatures[0])
    # The certificate is self-signed, so it is untrusted by design here; what
    # matters is that the bytes are genuinely covered by a real signature.
    assert status.intact and status.valid
    assert status.coverage.name == "ENTIRE_FILE"


def test_certificate_summary_reports_the_real_certificate(
    configured_seal: Path,
) -> None:
    summary = dsc.certificate_summary()
    assert "GOBITSNBYTES FOUNDATION Test Seal" in summary["common_name"]
    assert int(summary["serial"], 16) > 0


def test_content_appended_after_sealing_falls_outside_the_signature(
    tmp_path: Path, configured_seal: Path
) -> None:
    import io

    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    sealed = (
        dsc.seal_pdf(_pdf(tmp_path), reason="Execution of Test Agreement")
        + b"\n% appended after sealing\n"
    )
    status = validate_pdf_signature(
        PdfFileReader(io.BytesIO(sealed)).embedded_signatures[0]
    )
    assert status.coverage.name != "ENTIRE_FILE"
