import asyncio
from dotenv import load_dotenv
import os

# Load parent .env
load_dotenv("../../.env")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.db.models import VirtualAccount, VirtualCard

async def main():
    db_url = os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    output = []
    async with async_session() as session:
        # Get accounts
        res = await session.execute(select(VirtualAccount))
        accounts = res.scalars().all()
        output.append("=== VIRTUAL ACCOUNTS ===")
        for a in accounts:
            output.append(f"ID: {a.id} | Name: {a.name} | OwnerID: {a.owner_id} | Balance: {a.balance_paise} paise")
            
        # Get cards
        res_da = await session.execute(select(VirtualCard))
        cards = res_da.scalars().all()
        output.append("\n=== VIRTUAL CARDS ===")
        for c in cards:
            output.append(f"ID: {c.id} | CardName: {c.card_name} | AccountID: {c.account_id} | HolderID: {c.holder_id}")

    with open("db_accounts_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    print("Done writing to db_accounts_output.txt")

if __name__ == "__main__":
    asyncio.run(main())
