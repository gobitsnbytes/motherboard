"""Tests for the Notion team sync service (source-of-truth user reconciliation)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import DiscordAccount, User
from app.provisioning.notion_sync import sync_team_from_notion


def _notion_page(name: str, email: str, discord_id: str, role: str) -> dict:
    return {
        "id": "page-1",
        "properties": {
            "Name": {"title": [{"plain_text": name}]},
            "Email": {"email": email},
            "Discord ID": {"rich_text": [{"plain_text": discord_id}]},
            "Role": {"select": {"name": role}},
        },
    }


@pytest.mark.asyncio
async def test_team_sync_skips_without_config(db_session: AsyncSession):
    get_settings().notion_token = None
    get_settings().notion_team_db = None

    result = await sync_team_from_notion(db_session)

    assert result["status"] == "skipped"
    assert result["synced_count"] == 0


@pytest.mark.asyncio
async def test_team_sync_upserts_users_and_discord_ids(db_session: AsyncSession):
    """Real Discord IDs from Notion replace bootstrap placeholder identities."""
    settings = get_settings()
    settings.notion_token = "test-token"
    settings.notion_team_db = "team-db-id"

    seeded = User(
        display_name="Akshat Kushwaha",
        email="akshat@gobitsnbytes.org",
        is_super_admin=True,
    )
    db_session.add(seeded)
    await db_session.flush()
    placeholder = DiscordAccount(
        user_id=seeded.id, discord_id="1000000000000000003", username="a3ro.dev"
    )
    db_session.add(placeholder)
    await db_session.commit()

    payload = {
        "results": [
            _notion_page(
                "Akshat Kushwaha",
                "akshat@gobitsnbytes.org",
                "222111000999888777",
                "Chief Technology Officer (CTO)",
            ),
            _notion_page("New Member", "new@gobitsnbytes.org", "555444333222111000", "Volunteer"),
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload

    with patch("app.provisioning.notion_sync.httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await sync_team_from_notion(db_session)

    assert result["status"] == "success"
    assert result["synced_count"] == 2

    await db_session.refresh(seeded)
    assert seeded.title == "Chief Technology Officer (CTO)"

    # Placeholder identity re-linked to the real Discord ID on the SAME user row.
    result = await db_session.execute(
        select(DiscordAccount).where(DiscordAccount.user_id == seeded.id)
    )
    accounts = result.scalars().all()
    assert len(accounts) == 1
    assert accounts[0].discord_id == "222111000999888777"

    # New member created.
    result = await db_session.execute(
        select(User).where(User.email == "new@gobitsnbytes.org")
    )
    new_user = result.scalar_one()
    assert new_user is not None

    settings.notion_token = None
    settings.notion_team_db = None
