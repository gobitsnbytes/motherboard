"""Digital Signature Certificate sealing for completed contracts.

The Foundation seals every completed envelope with its own X.509 certificate,
producing a PAdES signature that any PDF reader can verify.  Individual signers
use e-signatures (drawn, typed, or uploaded); their identity is bound by the OTP
trail and the audit certificate, not by a certificate they do not own.

Per-signer DSC cannot be done here: a Class 2/3 USB token never releases its
private key, so a server can only ever *verify* a signature the token produced —
it can never produce one.  Anything that claims otherwise is decoration.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class DSCUnavailable(RuntimeError):
    """No usable signing certificate is configured."""


def _pfx() -> tuple[Path, bytes]:
    path = os.getenv("DSC_PFX_PATH")
    if not path or not Path(path).is_file():
        raise DSCUnavailable("DSC_PFX_PATH is not set to a readable PKCS#12 file")
    passphrase = os.getenv("DSC_PFX_PASSPHRASE") or ""
    return Path(path), passphrase.encode()


def is_configured() -> bool:
    try:
        _pfx()
    except DSCUnavailable:
        return False
    return True


def certificate_summary() -> dict[str, str]:
    """Subject, issuer and serial of the configured seal, for the audit trail."""
    from pyhanko.sign import signers

    path, passphrase = _pfx()
    signer = signers.SimpleSigner.load_pkcs12(pfx_file=str(path), passphrase=passphrase or None)
    if signer is None:
        raise DSCUnavailable("The configured PKCS#12 file could not be opened with DSC_PFX_PASSPHRASE")
    cert = signer.signing_cert
    return {
        "common_name": cert.subject.human_friendly,
        "issuer": cert.issuer.human_friendly,
        "serial": format(cert.serial_number, "X"),
    }


def seal_pdf(pdf_bytes: bytes, *, reason: str, location: str = "India") -> bytes:
    """Apply the Foundation's PAdES seal.  Raises DSCUnavailable if unconfigured."""
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigFieldSpec, SigSeedSubFilter
    from pyhanko.sign.timestamps import HTTPTimeStamper
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    path, passphrase = _pfx()
    signer = signers.SimpleSigner.load_pkcs12(pfx_file=str(path), passphrase=passphrase or None)
    if signer is None:
        raise DSCUnavailable("The configured PKCS#12 file could not be opened with DSC_PFX_PASSPHRASE")

    tsa_url = os.getenv("DSC_TSA_URL")
    writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    output = signers.sign_pdf(
        writer,
        signers.PdfSignatureMetadata(
            field_name="GobitsnbytesFoundationSeal",
            reason=reason,
            location=location,
            subfilter=SigSeedSubFilter.PADES,
        ),
        signer=signer,
        timestamper=HTTPTimeStamper(tsa_url) if tsa_url else None,
        # Invisible: the visual signature block is already drawn by the signature
        # engine, and a second widget would sit on top of it.
        new_field_spec=SigFieldSpec(sig_field_name="GobitsnbytesFoundationSeal"),
    )
    return output.getvalue()
