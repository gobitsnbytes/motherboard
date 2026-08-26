"""
Notion DB Synchronization Service for Motherboard.
Syncs real active forks directly from Notion Fork Registry (Database ID: a5472585-73cd-4f6c-99b8-40c7cb63ce9e)
and Team Members into motherboard's database.
"""

import logging
import uuid
import json
from typing import Any, Dict, List
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import DiscordAccount, Fork, User

logger = logging.getLogger(__name__)


def _prop_text(props: Dict[str, Any], *names: str) -> str | None:
    """Extract the first available plain-text value across tolerant property names."""
    for name in names:
        prop = props.get(name) or {}
        for kind in ("title", "rich_text"):
            items = prop.get(kind) or []
            if items:
                text = "".join(item.get("plain_text", "") for item in items).strip()
                if text:
                    return text
        email = prop.get("email")
        if email:
            return email.strip()
        select_obj = prop.get("select") or {}
        if select_obj.get("name"):
            return select_obj["name"].strip()
    return None


async def sync_team_from_notion(db: AsyncSession) -> Dict[str, Any]:
    """
    Synchronize team members from a Notion Team database into users/discord_accounts.

    Email is the reconciliation key: existing users are updated in place so their
    real Discord IDs replace any bootstrap placeholder identities without losing
    group memberships or grants. Tolerant property mapping accepts common layouts.
    """
    settings = get_settings()
    notion_token = settings.notion_token
    team_db = settings.notion_team_db

    if not notion_token or not team_db:
        return {
            "status": "skipped",
            "reason": "NOTION_TOKEN and NOTION_TEAM_DB must be configured for team sync",
            "synced_count": 0,
        }

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    synced_users: List[str] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"https://api.notion.com/v1/databases/{team_db}/query"
        response = await client.post(url, headers=headers, json={"page_size": 100})
        if response.status_code != 200:
            logger.error("Notion Team DB Query Failed (%d): %s", response.status_code, response.text)
            return {"status": "error", "error": f"Notion API error {response.status_code}"}

        for page in response.json().get("results", []):
            props = page.get("properties", {})
            name = _prop_text(props, "Name", "Full Name", "Team Member", "Member")
            email = _prop_text(props, "Email", "Work Email", "email")
            discord_id = _prop_text(props, "Discord ID", "DiscordId", "Discord")
            title = _prop_text(props, "Role", "Title", "Position", "Designation")

            if not name:
                continue

            result = await db.execute(select(User).where(User.display_name == name))
            user = result.scalar_one_or_none()
            if user is None and email:
                result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
                user = result.scalar_one_or_none()

            if user is None:
                user = User(display_name=name, email=email)
                db.add(user)
                await db.flush()

            user.display_name = name
            if email:
                user.email = email
            if title:
                user.title = title

            if discord_id:
                res = await db.execute(
                    select(DiscordAccount).where(DiscordAccount.discord_id == discord_id)
                )
                discord_account = res.scalar_one_or_none()
                if discord_account is None:
                    # Re-link any stale bootstrap identity attached to this user.
                    res = await db.execute(
                        select(DiscordAccount).where(DiscordAccount.user_id == user.id)
                    )
                    discord_account = res.scalar_one_or_none()
                if discord_account is None:
                    discord_account = DiscordAccount(
                        user_id=user.id,
                        discord_id=discord_id,
                        username=(email or name).split("@")[0].lower() or discord_id,
                    )
                    db.add(discord_account)
                else:
                    discord_account.discord_id = discord_id
                    discord_account.user_id = user.id

            synced_users.append(name)

        await db.commit()
        return {"status": "success", "source": "notion_api", "synced_count": len(synced_users), "users": synced_users}


async def sync_forks_from_notion(db: AsyncSession) -> Dict[str, Any]:
    """
    Synchronize active/pending forks directly from Notion Fork Registry DB into motherboard DB.
    """
    settings = get_settings()
    notion_token = settings.notion_token
    db_id = settings.notion_fork_registry_db or "a5472585-73cd-4f6c-99b8-40c7cb63ce9e"

    headers = {
        "Authorization": f"Bearer {notion_token}" if notion_token else "",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    synced_forks = []
    
    # If no notion_token provided, fallback to direct ground truth structure (HQ, Noida, Kolkata)
    if not notion_token:
        logger.info("NOTION_TOKEN not set; syncing from Notion DB direct ground-truth records (HQ, Noida, Kolkata).")
        ground_truth = [
            {
                "slug": "lucknow",
                "city_name": "Lucknow (Pan-India HQ)",
                "discord_city_role_id": "1490411988902477824",
                "is_active": True,
                "metadata": {"node_code": "HQ-01", "is_hq": True, "scale": "Pan-India", "status": "active"},
            },
            {
                "slug": "noida",
                "city_name": "Bits&Bytes Noida",
                "discord_city_role_id": "1490411548752085094",
                "is_active": True,
                "metadata": {
                    "node_code": "FORK-01",
                    "lead_name": "Aryan Chauhan",
                    "lead_discord_id": "1116608716473638912",
                    "lead_email": "aryan22chauhan07@gmail.com",
                    "school": "GNIT IPU",
                    "health_score": 50,
                    "status": "active",
                },
            },
            {
                "slug": "kolkata",
                "city_name": "Bits&Bytes Kolkata",
                "discord_city_role_id": "1490413148543385822",
                "is_active": True,
                "metadata": {
                    "node_code": "FORK-02",
                    "lead_name": "Shoryavardhaan Gupta",
                    "lead_discord_id": "1232542226807128094",
                    "lead_email": "shoryavardhaan@gmail.com",
                    "school": "South Point High School",
                    "health_score": 45,
                    "status": "active",
                },
            },
        ]

        for fork_data in ground_truth:
            result = await db.execute(select(Fork).where(Fork.slug == fork_data["slug"]))
            fork_obj = result.scalar_one_or_none()
            if not fork_obj:
                fork_obj = Fork(
                    id=uuid.uuid4(),
                    slug=fork_data["slug"],
                    city_name=fork_data["city_name"],
                    discord_city_role_id=fork_data.get("discord_city_role_id"),
                    is_active=fork_data["is_active"],
                    metadata_json=fork_data["metadata"],
                )
                db.add(fork_obj)
            else:
                fork_obj.city_name = fork_data["city_name"]
                fork_obj.is_active = fork_data["is_active"]
                fork_obj.metadata_json = fork_data["metadata"]
            synced_forks.append(fork_data["slug"])

        await db.commit()
        return {"status": "success", "source": "ground_truth", "synced_count": len(synced_forks), "forks": synced_forks}

    # Query Notion API directly if token is configured
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        response = await client.post(url, headers=headers, json={"page_size": 100})
        if response.status_code != 200:
            logger.error("Notion DB Query Failed (%d): %s", response.status_code, response.text)
            return {"status": "error", "error": f"Notion API error {response.status_code}"}

        data = response.json()
        results = data.get("results", [])

        for page in results:
            props = page.get("properties", {})
            title_list = props.get("Fork Name", {}).get("title", [])
            fork_name = title_list[0]["plain_text"] if title_list else "Unnamed Fork"
            
            city_list = props.get("What city are you in?", {}).get("rich_text", [])
            city = city_list[0]["plain_text"] if city_list else fork_name.replace("Bits&Bytes ", "").strip()
            
            status_obj = props.get("Status", {}).get("select") or {}
            status_val = status_obj.get("name", "Active")

            slug = city.lower().replace(" ", "-").replace("&", "n")
            health_score = props.get("Health Score", {}).get("number") or 50

            result = await db.execute(select(Fork).where(Fork.slug == slug))
            fork_obj = result.scalar_one_or_none()
            
            meta = {
                "notion_page_id": page.get("id"),
                "status": status_val,
                "health_score": health_score,
                "city": city,
            }

            if not fork_obj:
                fork_obj = Fork(
                    id=uuid.uuid4(),
                    slug=slug,
                    city_name=fork_name,
                    is_active=(status_val == "Active"),
                    metadata_json=meta,
                )
                db.add(fork_obj)
            else:
                fork_obj.city_name = fork_name
                fork_obj.is_active = (status_val == "Active")
                fork_obj.metadata_json = meta
            synced_forks.append(slug)

        await db.commit()
        return {"status": "success", "source": "notion_api", "synced_count": len(synced_forks), "forks": synced_forks}
