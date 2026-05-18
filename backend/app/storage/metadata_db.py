"""
Metadata Database — SQLite via SQLAlchemy (async).
Stores document metadata, user accounts, and query logs.
No Docker needed — single file database.
"""
from sqlalchemy import select, update, delete, insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, UniqueConstraint, func, update
import os
import json
import logging
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class DocumentRecord(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    source_type = Column(String, default="unknown")
    title = Column(String, default="")
    num_chunks = Column(Integer, default=0)
    content_hash = Column(String, default="")
    status = Column(String, default="processing")  # processing, completed, failed
    user_id = Column(String, default="anonymous")
    created_at = Column(DateTime, server_default=func.now())

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String, primary_key=True)
    title = Column(String, default="New Chat")
    user_id = Column(String, default="anonymous")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    sources = Column(Text, default="[]")  # JSON string of sources
    created_at = Column(DateTime, server_default=func.now())

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    model_config = Column(String, default="{}")
    created_at = Column(DateTime, server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, default="")
    is_secret = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class YouTubeSource(Base):
    __tablename__ = "youtube_sources"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uq_youtube_source_user_video"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    video_id = Column(String, nullable=False)
    title = Column(String, default="")
    channel_name = Column(String, default="")
    thumbnail_url = Column(String, default="")
    duration_secs = Column(Integer, default=0)
    ingested_at = Column(DateTime, server_default=func.now())
    chunk_count = Column(Integer, default=0)


class QueryLog(Base):
    __tablename__ = "query_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(Text)
    processed_query = Column(Text, default="")
    intent = Column(String, default="")
    num_retrieved = Column(Integer, default=0)
    num_final = Column(Integer, default=0)
    answer = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    user_id = Column(String, default="anonymous")
    rating = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class MetadataDB:
    _instance = None

    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return
        from app.core.config import settings
        db_url = settings.async_db_url
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self._initialized = True

    async def init_db(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")

    async def upsert_setting(self, key: str, value: str, is_secret: bool = False) -> None:
        async with self.async_session() as session:
            existing = await session.execute(select(AppSetting).where(AppSetting.key == key))
            setting = existing.scalar_one_or_none()
            if setting:
                setting.value = value
                setting.is_secret = 1 if is_secret else 0
            else:
                session.add(AppSetting(key=key, value=value, is_secret=1 if is_secret else 0))
            await session.commit()

    async def seed_oauth_settings(self, google_client_id: str = "", google_client_secret: str = "") -> None:
        await self.upsert_setting("google_client_id", google_client_id, is_secret=False)
        await self.upsert_setting("google_client_secret", google_client_secret, is_secret=True)

    async def add_document(self, doc_id: str, filename: str, source_type: str,
                           title: str = "", content_hash: str = "", user_id: str = "anonymous"):
        async with self.async_session() as session:
            record = DocumentRecord(
                id=doc_id,
                filename=filename,
                source_type=source_type,
                title=title,
                content_hash=content_hash,
                status="processing",
                user_id=user_id,
            )
            session.add(record)
            await session.commit()

    async def update_document(self, doc_id: str, num_chunks: int, status: str = "completed"):
        async with self.async_session() as session:
            from sqlalchemy import update
            stmt = update(DocumentRecord).where(
                DocumentRecord.id == doc_id
            ).values(num_chunks=num_chunks, status=status)
            await session.execute(stmt)
            await session.commit()

    async def get_all_documents(self, user_id: str = "anonymous") -> list:
        async with self.async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(DocumentRecord)
                .where(DocumentRecord.user_id == user_id)
                .order_by(DocumentRecord.created_at.desc())
            )
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "source_type": r.source_type,
                    "title": r.title,
                    "num_chunks": r.num_chunks,
                    "status": r.status,
                    "created_at": str(r.created_at) if r.created_at else None,
                }
                for r in rows
            ]

    async def get_document(self, doc_id: str, user_id: str = "anonymous") -> dict | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(DocumentRecord).where(
                    DocumentRecord.id == doc_id,
                    DocumentRecord.user_id == user_id,
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                return None
            return {
                "id": record.id,
                "filename": record.filename,
                "source_type": record.source_type,
                "title": record.title,
                "num_chunks": record.num_chunks,
                "content_hash": record.content_hash,
                "status": record.status,
                "created_at": str(record.created_at) if record.created_at else None,
            }

    async def find_document_by_filename(
        self,
        filename: str,
        source_type: str,
        user_id: str = "anonymous",
    ) -> dict | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(DocumentRecord).where(
                    DocumentRecord.filename == filename,
                    DocumentRecord.source_type == source_type,
                    DocumentRecord.user_id == user_id,
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                return None
            return {
                "id": record.id,
                "filename": record.filename,
                "source_type": record.source_type,
                "title": record.title,
                "num_chunks": record.num_chunks,
                "status": record.status,
            }

    async def delete_document(self, doc_id: str, user_id: str = "anonymous") -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                select(DocumentRecord).where(
                    DocumentRecord.id == doc_id,
                    DocumentRecord.user_id == user_id,
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                return False
            await session.execute(delete(DocumentRecord).where(DocumentRecord.id == doc_id))
            await session.commit()
            return True

    async def check_content_hash(self, content_hash: str, user_id: str = "anonymous") -> bool:
        """Check if content has already been ingested (deduplication)."""
        async with self.async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(DocumentRecord).where(
                    DocumentRecord.content_hash == content_hash,
                    DocumentRecord.user_id == user_id
                )
            )
            return result.scalar_one_or_none() is not None

    async def add_user(self, user_id: str, username: str, password_hash: str) -> None:
        async with self.async_session() as session:
            try:
                new_user = User(
                    id=user_id,
                    username=username,
                    password_hash=password_hash,
                    model_config="{}"
                )
                session.add(new_user)
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raise ValueError(f"User {username} already exists")

    async def get_user_model_config(self, user_id: str) -> dict:
        async with self.async_session() as session:
            result = await session.execute(
                select(User.model_config).where(User.id == user_id)
            )
            config_str = result.scalar_one_or_none()
            if config_str:
                return json.loads(config_str)
            return {}

    async def update_user_model_config(self, user_id: str, config: dict) -> None:
        async with self.async_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(model_config=json.dumps(config))
            )
            await session.commit()

    async def get_user_by_username(self, username: str) -> dict | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()
            if user:
                return {
                    "id": user.id,
                    "username": user.username,
                    "password_hash": user.password_hash,
                    "role": user.role,
                }
            return None

    async def get_youtube_source(self, user_id: str, video_id: str) -> dict | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(YouTubeSource).where(
                    YouTubeSource.user_id == user_id,
                    YouTubeSource.video_id == video_id,
                )
            )
            source = result.scalar_one_or_none()
            if not source:
                return None
            return {
                "id": source.id,
                "user_id": source.user_id,
                "video_id": source.video_id,
                "title": source.title,
                "channel_name": source.channel_name,
                "thumbnail_url": source.thumbnail_url,
                "duration_secs": source.duration_secs,
                "chunk_count": source.chunk_count,
                "ingested_at": str(source.ingested_at) if source.ingested_at else None,
            }

    async def add_youtube_source(
        self,
        user_id: str,
        video_id: str,
        title: str,
        channel_name: str,
        thumbnail_url: str,
        duration_secs: int,
        chunk_count: int,
    ) -> None:
        async with self.async_session() as session:
            try:
                source = YouTubeSource(
                    id=f"{user_id}:{video_id}",
                    user_id=user_id,
                    video_id=video_id,
                    title=title,
                    channel_name=channel_name,
                    thumbnail_url=thumbnail_url,
                    duration_secs=duration_secs,
                    chunk_count=chunk_count,
                )
                session.add(source)
                await session.commit()
            except IntegrityError:
                await session.rollback()

    async def log_query(self, query: str, intent: str, num_retrieved: int,
                        num_final: int, answer: str, latency_ms: int, user_id: str):
        async with self.async_session() as session:
            record = QueryLog(
                query=query,
                intent=intent,
                num_retrieved=num_retrieved,
                num_final=num_final,
                answer=answer[:2000],  # Truncate long answers
                latency_ms=latency_ms,
                user_id=user_id,
            )
            session.add(record)
            await session.commit()

    async def get_stats(self) -> dict:
        async with self.async_session() as session:
            from sqlalchemy import select, func as sqfunc
            doc_count = await session.execute(select(sqfunc.count(DocumentRecord.id)))
            query_count = await session.execute(select(sqfunc.count(QueryLog.id)))
            return {
                "total_documents": doc_count.scalar_one() or 0,
                "total_queries": query_count.scalar_one() or 0,
            }

    # --- Chat History Methods ---

    async def create_session(self, session_id: str, title: str, user_id: str = "anonymous"):
        try:
            async with self.async_session() as session:
                record = ChatSession(id=session_id, title=title, user_id=user_id)
                session.add(record)
                await session.commit()
                logger.info(f"✅ Session created: {session_id} for user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to create session {session_id}: {e}")
            raise

    async def session_belongs_to_user(self, session_id: str, user_id: str = "anonymous") -> bool:
        async with self.async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def get_sessions(self, user_id: str = "anonymous") -> list:
        async with self.async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc())
            )
            rows = result.scalars().all()
            return [{"id": r.id, "title": r.title, "updated_at": str(r.updated_at)} for r in rows]

    async def get_messages(self, session_id: str, user_id: str = "anonymous") -> list:
        async with self.async_session() as session:
            from sqlalchemy import select
            import json
            session_result = await session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id,
                )
            )
            if session_result.scalar_one_or_none() is None:
                return []
            result = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            )
            rows = result.scalars().all()
            messages = []
            for r in rows:
                try:
                    sources = json.loads(r.sources)
                except Exception:
                    sources = []
                messages.append({
                    "id": r.id,
                    "role": r.role,
                    "content": r.content,
                    "sources": sources,
                    "created_at": str(r.created_at)
                })
            return messages

    async def add_message(self, message_id: str, session_id: str, role: str, content: str, user_id: str = "anonymous", sources: list = None):
        try:
            async with self.async_session() as session:
                import json
                
                # Check if session exists, create if not
                from sqlalchemy import select
                session_result = await session.execute(
                    select(ChatSession).where(ChatSession.id == session_id)
                )
                chat_session = session_result.scalar_one_or_none()
                
                if not chat_session:
                    logger.info(f"⚠️ Session {session_id} not found, creating on-the-fly for user {user_id}")
                    chat_session = ChatSession(id=session_id, title="New Chat", user_id=user_id)
                    session.add(chat_session)
                    await session.flush() # Ensure it's available for the message
                
                record = ChatMessage(
                    id=message_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    sources=json.dumps(sources or [])
                )
                session.add(record)
                
                # Update session timestamp and title if it's the first user message
                from sqlalchemy import update
                
                if role == "user":
                    if chat_session.title == "New Chat":
                        # Simple title generation: first 30 chars of the message
                        new_title = content[:30] + ("..." if len(content) > 30 else "")
                        chat_session.title = new_title
                    
                    chat_session.updated_at = func.now()
                        
                await session.commit()
                logger.info(f"✅ Message saved and session ensured: {message_id} in {session_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save message {message_id}: {e}")
            raise
            
    async def delete_session(self, session_id: str, user_id: str = "anonymous") -> bool:
        async with self.async_session() as session:
            from sqlalchemy import delete, select
            owns_session = await session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id,
                )
            )
            if owns_session.scalar_one_or_none() is None:
                return False
            await session.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
            await session.execute(delete(ChatSession).where(ChatSession.id == session_id))
            await session.commit()
            return True
