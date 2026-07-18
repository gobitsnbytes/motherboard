import asyncio
from dotenv import load_dotenv
import os

# Load parent .env
load_dotenv("../../.env")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.db.models import Fork

async def main():
    db_url = os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    output = []
    async with async_session() as session:
        res = await session.execute(select(Fork))
        forks = res.scalars().all()
        output.append("=== FORKS ===")
        for f in forks:
            output.append(f"ID: {f.id} | Slug: {f.slug} | Name: {f.city_name} | Active: {f.is_active} | Metadata: {f.metadata_json}")

    with open("db_forks_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    print("Done writing to db_forks_output.txt")

if __name__ == "__main__":
    asyncio.run(main())
