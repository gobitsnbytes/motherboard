import logging
from typing import Any, List, Dict
import httpx
import asyncio

from app.provisioning.errors import DiscordAPIError

logger = logging.getLogger(__name__)


class DiscordClient:
    """Async Discord API v10 client for guild sync operations."""

    def __init__(self, bot_token: str, *, timeout: float = 30.0):
        self.bot_token = bot_token
        self.base_url = "https://discord.com/api/v10"
        self.headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }
        self.timeout = timeout

    async def get_guild_roles(self, guild_id: str) -> List[Dict[str, Any]]:
        """Fetch all roles for a guild.
        
        GET /guilds/{guild_id}/roles
        """
        url = f"{self.base_url}/guilds/{guild_id}/roles"
        logger.debug("Fetching Discord roles for guild %s", guild_id)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers)
            
            if response.status_code == 429:
                retry_after = float(response.json().get("retry_after", 1.0))
                logger.warning("Discord API rate limited (429). Retrying in %f seconds", retry_after)
                await asyncio.sleep(retry_after)
                response = await client.get(url, headers=self.headers)
                
            if response.status_code != 200:
                raise DiscordAPIError(response.status_code, f"Failed to get roles: {response.text}")
                
            return response.json()

    async def get_guild_members(self, guild_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Paginated fetch of all guild members (up to 1000 per page).
        
        GET /guilds/{guild_id}/members?limit={limit}&after={last_id}
        """
        members = []
        last_id = "0"
        
        logger.debug("Fetching Discord members for guild %s", guild_id)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                url = f"{self.base_url}/guilds/{guild_id}/members?limit={limit}&after={last_id}"
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 429:
                    retry_after = float(response.json().get("retry_after", 1.0))
                    logger.warning("Discord API rate limited (429). Retrying in %f seconds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                    
                if response.status_code != 200:
                    raise DiscordAPIError(response.status_code, f"Failed to get members: {response.text}")
                    
                page = response.json()
                if not page:
                    break
                    
                members.extend(page)
                last_id = page[-1]["user"]["id"]
                
                if len(page) < limit:
                    break
                    
        logger.debug("Fetched %d total Discord members from guild %s", len(members), guild_id)
        return members


async def fetch_own_guild_roles(user_access_token: str, guild_id: str, *, timeout: float = 4.0) -> list[str] | None:
    """Role ids of the signed-in user in the guild, read with THEIR OAuth token (scope guilds.members.read).

    Returns None when they are not in the guild. Raises on any other failure so the caller can keep
    their current access rather than treat an outage as "they lost every role".
    """
    url = f"https://discord.com/api/v10/users/@me/guilds/{guild_id}/member"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {user_access_token}"})
    if response.status_code in (403, 404):
        return None
    if response.status_code != 200:
        raise DiscordAPIError(response.status_code, f"Failed to read guild member: {response.text[:200]}")
    return list(response.json().get("roles", []))
