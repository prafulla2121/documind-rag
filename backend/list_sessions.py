import asyncio
from app.storage.metadata_db import MetadataDB

async def list_sessions():
    db = MetadataDB()
    sessions = await db.get_sessions("anonymous")
    print(f"Sessions for anonymous: {sessions}")
    
    # Try to find any sessions at all
    from app.storage.metadata_db import ChatSession, ChatMessage
    from sqlalchemy import select
    async with db.async_session() as session:
        result = await session.execute(select(ChatSession))
        all_sessions = result.scalars().all()
        print(f"Total sessions in DB: {len(all_sessions)}")
        for s in all_sessions:
            print(f"Session: ID={s.id}, Title={s.title}, UserID={s.user_id}")
            
        msg_result = await session.execute(select(ChatMessage))
        all_messages = msg_result.scalars().all()
        print(f"Total messages in DB: {len(all_messages)}")
        for m in all_messages:
            print(f"Message: ID={m.id}, SessionID={m.session_id}, Role={m.role}")

if __name__ == "__main__":
    asyncio.run(list_sessions())
