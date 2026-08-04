from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_apply_cloud_missing_fields():
    response = client.post(
        "/api/cloud/apply",
        data={"name": "", "email": "test@example.com", "github": "", "linkedin": ""},
        files={"id_file": ("id.png", b"fake-image-content", "image/png")},
    )
    assert response.status_code in (400, 422)


@patch("httpx.AsyncClient.post")
def test_apply_cloud_success(mock_post):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    response = client.post(
        "/api/cloud/apply",
        data={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "github": "https://github.com/janedoe",
            "linkedin": "https://linkedin.com/in/janedoe",
        },
        files={"id_file": ("id.png", b"fake-image-data", "image/png")},
    )
    assert response.status_code in (201, 200)
    assert response.json()["status"] == "success"


@patch("app.routers.cloud.send_smtp_email")
def test_send_cloud_decision_approval(mock_send_smtp):
    response = client.post(
        "/api/cloud/send-decision",
        json={
            "action": "approve",
            "email": "student@example.com",
            "name": "Alex Smith",
            "reason": "Approved builder profile",
            "reviewer": "admin#0001",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert mock_send_smtp.called
