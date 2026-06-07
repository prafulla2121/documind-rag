import asyncio
from app.storage.metadata_db import MetadataDB
from sqlalchemy import text

async def check():
    db = MetadataDB()
    async with db.async_session() as session:
        try:
            res = await session.execute(text("SELECT * FROM chat_sessions LIMIT 1"))
            print("Table chat_sessions exists and is accessible")
        except Exception as e:
            print(f"Error accessing chat_sessions: {e}")

if __name__ == "__main__":
    asyncio.run(check())
