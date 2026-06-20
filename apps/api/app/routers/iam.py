import uuid
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import select, and_, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import httpx

from app.config import get_settings
from app.db.models import Permission, Grant, Group, Membership, DiscordRoleMapping
from app.dependencies import DbDep, CurrentUserDep
from app.iam.policy import require_permission
from app.iam.audit import write_audit_entry
from app.schemas.iam import (
    ResolvedPrincipalResponse,
    PermissionResponse,
    PermissionCreate,
    GrantResponse,
    GrantCreate,
    GroupResponse,
    GroupCreate,
    MembershipResponse,
    MembershipCreate,
    DiscordRole,
    DiscordRoleMappingResponse,
    DiscordRoleMappingUpsert,
)

router = APIRouter()

@router.get("/me", response_model=dict[str, Any])
async def get_me(current_user: CurrentUserDep, db: DbDep) -> dict[str, Any]:
    # Return calling user's ResolvedPrincipal + their grants
    stmt = select(Grant).where(
        or_(
            and_(Grant.principal_type == "user", Grant.principal_id == current_user.user_id),
            and_(Grant.principal_type == "group", Grant.principal_id.in_(current_user.group_ids)) if current_user.group_ids else False
        )
    )
    res = await db.execute(stmt)
    grants = res.scalars().all()

    return {
        "principal": ResolvedPrincipalResponse(
            user_id=current_user.user_id,
            group_ids=current_user.group_ids,
            is_super_admin=current_user.is_super_admin
        ).model_dump(),
        "grants": [GrantResponse.model_validate(g).model_dump() for g in grants]
    }

@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(current_user: CurrentUserDep, db: DbDep) -> List[PermissionResponse]:
    await require_permission(db, current_user, "iam.permissions.read")
    res = await db.execute(select(Permission))
    return list(res.scalars().all())

@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def register_permission(
    payload: PermissionCreate,
    current_user: CurrentUserDep,
    db: DbDep
) -> PermissionResponse:
    await require_permission(db, current_user, "iam.permissions.write")

    stmt = select(Permission).where(Permission.key == payload.key)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        return existing

    permission = Permission(
        key=payload.key,
        description=payload.description,
        plugin_id=payload.plugin_id
    )
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    return permission

@router.get("/grants", response_model=List[GrantResponse])
async def list_grants(
    current_user: CurrentUserDep,
    db: DbDep,
    principal_type: Optional[str] = Query(None),
    principal_id: Optional[uuid.UUID] = Query(None),
    permission_key: Optional[str] = Query(None)
) -> List[GrantResponse]:
    await require_permission(db, current_user, "iam.grants.read")

    conditions = []
    if principal_type:
        conditions.append(Grant.principal_type == principal_type)
    if principal_id:
        conditions.append(Grant.principal_id == principal_id)
    if permission_key:
        conditions.append(Grant.permission_key == permission_key)

    stmt = select(Grant)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    res = await db.execute(stmt)
    return list(res.scalars().all())

@router.post("/grants", response_model=GrantResponse, status_code=status.HTTP_201_CREATED)
async def create_grant(
    payload: GrantCreate,
    current_user: CurrentUserDep,
    db: DbDep
) -> GrantResponse:
    await require_permission(db, current_user, "iam.grants.write")

    grant = Grant(
        principal_type=payload.principal_type,
        principal_id=payload.principal_id,
        permission_key=payload.permission_key,
        resource_scope=payload.resource_scope,
        granted_by=current_user.user_id,
        expires_at=payload.expires_at
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant

@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_grant(
    grant_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep
) -> Response:
    await require_permission(db, current_user, "iam.grants.write")

    res = await db.execute(select(Grant).where(Grant.id == grant_id))
    grant = res.scalar_one_or_none()

    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

    await db.delete(grant)

    await write_audit_entry(
        db=db,
        actor_id=current_user.user_id,
        action="revoke_grant",
        target_type="grant",
        target_id=str(grant_id),
        metadata={
            "principal_type": grant.principal_type,
            "principal_id": str(grant.principal_id),
            "permission_key": grant.permission_key
        }
    )

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/groups", response_model=List[GroupResponse])
async def list_groups(current_user: CurrentUserDep, db: DbDep) -> List[GroupResponse]:
    await require_permission(db, current_user, "iam.groups.read")
    res = await db.execute(select(Group))
    return list(res.scalars().all())

@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    current_user: CurrentUserDep,
    db: DbDep
) -> GroupResponse:
    await require_permission(db, current_user, "iam.groups.write")

    import re
    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text

    group_slug = payload.slug or slugify(payload.name)
    if not group_slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not generate group slug from name")

    # check for slug uniqueness
    slug_stmt = select(Group).where(Group.slug == group_slug)
    slug_res = await db.execute(slug_stmt)
    if slug_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Group slug '{group_slug}' already exists")

    group = Group(
        name=payload.name,
        slug=group_slug,
        description=payload.description
    )
    db.add(group)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group with this name already exists")

    await db.refresh(group)
    return group

@router.get("/groups/{group_id}/members", response_model=List[MembershipResponse])
async def list_group_members(
    group_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep
) -> List[MembershipResponse]:
    await require_permission(db, current_user, "iam.groups.read")

    res = await db.execute(select(Membership).where(Membership.group_id == group_id))
    return list(res.scalars().all())

@router.post("/groups/{group_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: uuid.UUID,
    payload: MembershipCreate,
    current_user: CurrentUserDep,
    db: DbDep
) -> MembershipResponse:
    await require_permission(db, current_user, "iam.groups.write")

    membership = Membership(
        user_id=payload.user_id,
        group_id=group_id,
        source="manual",
        granted_by=current_user.user_id,
        expires_at=payload.expires_at
    )
    db.add(membership)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a member of this group")

    await db.refresh(membership)
    return membership

@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep
) -> Response:
    await require_permission(db, current_user, "iam.groups.write")

    res = await db.execute(
        select(Membership).where(and_(Membership.group_id == group_id, Membership.user_id == user_id))
    )
    membership = res.scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    await db.delete(membership)

    await write_audit_entry(
        db=db,
        actor_id=current_user.user_id,
        action="remove_group_member",
        target_type="membership",
        target_id=str(membership.id),
        metadata={
            "group_id": str(group_id),
            "user_id": str(user_id)
        }
    )

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/discord-roles", response_model=List[DiscordRole])
async def list_discord_roles(current_user: CurrentUserDep, db: DbDep) -> List[DiscordRole]:
    await require_permission(db, current_user, "iam.role_mappings.read")

    settings = get_settings()
    if not settings.discord_bot_token or not settings.discord_guild_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Discord bot not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"https://discord.com/api/v10/guilds/{settings.discord_guild_id}/roles",
            headers={"Authorization": f"Bot {settings.discord_bot_token}"}
        )


        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to fetch roles from Discord: {response.text}")

        roles = response.json()
        return [DiscordRole(**r) for r in roles]

@router.get("/discord-mappings", response_model=List[DiscordRoleMappingResponse])
async def list_discord_mappings(current_user: CurrentUserDep, db: DbDep) -> List[DiscordRoleMappingResponse]:
    await require_permission(db, current_user, "iam.role_mappings.read")
    res = await db.execute(select(DiscordRoleMapping))
    return list(res.scalars().all())

@router.put("/discord-mappings", response_model=DiscordRoleMappingResponse)
async def upsert_discord_mapping(
    payload: DiscordRoleMappingUpsert,
    current_user: CurrentUserDep,
    db: DbDep
) -> DiscordRoleMappingResponse:
    await require_permission(db, current_user, "iam.role_mappings.write")

    stmt = select(DiscordRoleMapping).where(DiscordRoleMapping.discord_role_id == payload.discord_role_id)
    res = await db.execute(stmt)
    mapping = res.scalar_one_or_none()

    if mapping:
        mapping.group_id = payload.group_id
        mapping.discord_role_name = payload.discord_role_name
        mapping.sync_enabled = payload.sync_enabled
        mapping.priority = payload.priority
    else:
        mapping = DiscordRoleMapping(
            discord_role_id=payload.discord_role_id,
            discord_role_name=payload.discord_role_name,
            group_id=payload.group_id,
            sync_enabled=payload.sync_enabled,
            priority=payload.priority
        )
        db.add(mapping)

    await db.commit()
    await db.refresh(mapping)
    return mapping
