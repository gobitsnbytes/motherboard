import pytest
import uuid
from cryptography.fernet import Fernet
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, DiscordAccount, EncryptedString


@pytest.mark.asyncio
async def test_token_encryption_decryption(db_session: AsyncSession):
    # 1. Setup a test User
    user = User(display_name="Encrypted Alice")
    db_session.add(user)
    await db_session.commit()

    # 2. Setup a DiscordAccount with plaintext tokens
    plaintext_access = "my-secret-access-token-123"
    plaintext_refresh = "my-secret-refresh-token-456"

    da = DiscordAccount(
        user_id=user.id,
        discord_id=f"enc_{uuid.uuid4().hex[:8]}",
        username="alice_encrypted",
        access_token=plaintext_access,
        refresh_token=plaintext_refresh,
    )
    db_session.add(da)
    await db_session.commit()

    da_id = da.id  # Save ID before expiring session

    # 3. Query the database using RAW SQL by username to verify it is stored as ciphertext
    raw_result = await db_session.execute(
        text("SELECT access_token, refresh_token FROM discord_accounts WHERE username = :username"),
        {"username": "alice_encrypted"}
    )
    row = raw_result.fetchone()
    assert row is not None
    stored_access, stored_refresh = row[0], row[1]

    # Verify that the database stores ciphertext, not the original plaintext
    assert stored_access != plaintext_access
    assert stored_refresh != plaintext_refresh

    # Verify that it is valid Fernet ciphertext (starts with gAAAA)
    assert stored_access.startswith("gAAAA")
    assert stored_refresh.startswith("gAAAA")

    # 4. Query using SQLAlchemy ORM to verify it gets decrypted automatically
    db_session.expire_all()  # Clear local session cache to force reload
    stmt = select(DiscordAccount).where(DiscordAccount.id == da_id)
    res = await db_session.execute(stmt)
    loaded_da = res.scalar_one()

    assert loaded_da.access_token == plaintext_access
    assert loaded_da.refresh_token == plaintext_refresh


@pytest.mark.asyncio
async def test_encryption_fallback_graceful(db_session: AsyncSession):
    # If the database contains plaintext (e.g. legacy data), the decryptor should fall back gracefully and return it as-is
    legacy_plaintext = "legacy-plaintext-token"

    user = User(display_name="Legacy Bob")
    db_session.add(user)
    await db_session.commit()

    # Temporarily bypass encryption on bind to insert plaintext via ORM
    original_bind = EncryptedString.process_bind_param
    EncryptedString.process_bind_param = lambda self, val, dialect: val

    try:
        da = DiscordAccount(
            user_id=user.id,
            discord_id="legacy_bob_id",
            username="legacy_bob",
            access_token=legacy_plaintext,
            refresh_token=legacy_plaintext,
        )
        db_session.add(da)
        await db_session.commit()
    finally:
        # Restore original encryption on bind
        EncryptedString.process_bind_param = original_bind

    da_id = da.id  # Save ID before expiring session

    # Fetch via ORM to verify that decryption failure defaults back to returning the plaintext
    db_session.expire_all()
    stmt = select(DiscordAccount).where(DiscordAccount.id == da_id)
    res = await db_session.execute(stmt)
    loaded_da = res.scalar_one()

    assert loaded_da.access_token == legacy_plaintext
    assert loaded_da.refresh_token == legacy_plaintext
