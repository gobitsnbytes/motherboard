from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.routers.meetings import send_smtp_email


@pytest.fixture
def dummy_settings():
    return Settings(
        smtp_host="smtp.test.com",
        smtp_port=587,
        smtp_user="legal@gobitsnbytes.org",
        smtp_pass="secret_pass",
        smtp_from="bits&bytes Legal <legal@gobitsnbytes.org>",
        smtp_bcc="gobitsnbytes@gmail.com",
    )


@patch("smtplib.SMTP")
def test_send_smtp_email_envelope_includes_to_and_bcc(mock_smtp_class, dummy_settings):
    mock_smtp_instance = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance

    to_recipient = "applicant@example.com"
    subject = "Your SparkCloud Access Request Has Been Approved!"
    html_body = "<p>Welcome to SparkCloud</p>"

    send_smtp_email(dummy_settings, [to_recipient], subject, html_body)

    assert mock_smtp_instance.sendmail.called
    sender, envelope_recipients, msg_string = mock_smtp_instance.sendmail.call_args[0]

    assert sender == "legal@gobitsnbytes.org"
    # Ensure BOTH the primary recipient AND the audit address (CC/BCC) are present in envelope recipients
    assert "applicant@example.com" in envelope_recipients
    assert "gobitsnbytes@gmail.com" in envelope_recipients

    # Ensure message headers contain To: matching primary recipient and Cc: gobitsnbytes@gmail.com
    assert "To: applicant@example.com" in msg_string
    assert "Cc: gobitsnbytes@gmail.com" in msg_string


@patch("smtplib.SMTP")
def test_send_smtp_email_single_string_to_emails(mock_smtp_class, dummy_settings):
    mock_smtp_instance = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance

    # Test passing a single string instead of a list
    to_recipient_str = "student@gmail.com"
    subject = "SparkCloud Update"
    html_body = "<p>Test body</p>"

    send_smtp_email(dummy_settings, to_recipient_str, subject, html_body)

    assert mock_smtp_instance.sendmail.called
    sender, envelope_recipients, msg_string = mock_smtp_instance.sendmail.call_args[0]

    # Ensure To string is NOT split character-by-character into 's', 't', 'u', 'd', ...
    assert "student@gmail.com" in envelope_recipients
    assert "To: student@gmail.com" in msg_string
