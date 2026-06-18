import pytest
from unittest.mock import MagicMock, patch
import httpx
import asyncio

from app.provisioning.client import DiscordClient
from app.provisioning.errors import DiscordAPIError


@pytest.mark.asyncio
async def test_get_roles_success():
    client = DiscordClient(bot_token="test_token")
    mock_roles = [{"id": "role1", "name": "Admin"}]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_roles
        mock_get.return_value = mock_response

        roles = await client.get_guild_roles("guild123")

        assert roles == mock_roles
        mock_get.assert_called_once_with(
            "https://discord.com/api/v10/guilds/guild123/roles",
            headers=client.headers,
        )


@pytest.mark.asyncio
async def test_get_roles_rate_limit_retry():
    client = DiscordClient(bot_token="test_token")
    mock_roles = [{"id": "role1", "name": "Admin"}]

    with patch("httpx.AsyncClient.get") as mock_get, patch("asyncio.sleep") as mock_sleep:
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.json.return_value = {"retry_after": 0.5}

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = mock_roles

        mock_get.side_effect = [mock_response_429, mock_response_200]

        roles = await client.get_guild_roles("guild123")

        assert roles == mock_roles
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_get_roles_error_raises():
    client = DiscordClient(bot_token="test_token")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        with pytest.raises(DiscordAPIError) as exc_info:
            await client.get_guild_roles("guild123")

        assert exc_info.value.status_code == 404
        assert "Not Found" in exc_info.value.message


@pytest.mark.asyncio
async def test_get_members_pagination():
    client = DiscordClient(bot_token="test_token")

    page1 = [{"user": {"id": "1", "username": "user1"}, "roles": []}]
    page2 = [{"user": {"id": "2", "username": "user2"}, "roles": []}]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = page1

        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = page2

        mock_response_3 = MagicMock()
        mock_response_3.status_code = 200
        mock_response_3.json.return_value = []

        mock_get.side_effect = [mock_response_1, mock_response_2, mock_response_3]

        members = await client.get_guild_members("guild123", limit=1)

        assert len(members) == 2
        assert members[0]["user"]["id"] == "1"
        assert members[1]["user"]["id"] == "2"
        assert mock_get.call_count == 3
