from datetime import date

import pytest

from app.services.onboarding_documents import (
    TEMPLATE_MANIFEST,
    age_on,
    hash_portal_token,
    manifest_for,
    new_portal_token,
    validate_age,
)


def test_age_gate_requires_parent_for_minors():
    assert age_on("2008-09-09", today=date(2026, 9, 9)) == 18
    assert validate_age("2010-09-10", today=None)[1] is True
    with pytest.raises(ValueError):
        validate_age("2015-09-09", today=date(2026, 9, 9))


def test_portal_tokens_are_hashed_and_manifest_is_complete():
    token, token_hash = new_portal_token()
    assert token
    assert token_hash == hash_portal_token(token)
    assert len(TEMPLATE_MANIFEST) == 6
    assert manifest_for("volunteer")["template"] == "1_Volunteer_Form.docx"
    with pytest.raises(ValueError):
        manifest_for("unknown")
