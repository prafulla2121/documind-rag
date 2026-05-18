"""
Query API Routes — handles user questions with optional streaming.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json

from app.models.schemas import QueryRequest, QueryResponse
from app.core.security import get_current_user
from app.api.dependencies import get_pipeline, get_metadata_db
from app.providers.registry import get_llm_provider
from app.providers.base import ModelConfig
from app.core.vault import vault

router = APIRouter()


@router.post("/", response_model=QueryResponse)
async def query_endpoint(
    request: QueryRequest,
    current_user=Depends(get_current_user),
):
    if len(request.query.strip()) < 2:
        raise HTTPException(400, "Query too short")

    pipeline = get_pipeline()
    db = get_metadata_db()
    if request.session_id:
        belongs = await db.session_belongs_to_user(request.session_id, current_user["id"])
        if not belongs:
            raise HTTPException(404, "Session not found")
    
    # Generate session ID if not provided
    import uuid
    is_new_session = not request.session_id
    session_id = request.session_id or str(uuid.uuid4())
    
    if is_new_session:
        # Create session BEFORE starting the stream to avoid race conditions
        await db.create_session(session_id, "New Chat", current_user["id"])
    
    # Save user message
    user_message_id = str(uuid.uuid4())
    await db.add_message(user_message_id, session_id, "user", request.query, current_user["id"])

    # Fetch previous messages for context
    history = await db.get_messages(session_id, current_user["id"])
    # We pass history to the pipeline to add context (need to update pipeline to use it)

    # Get LLM Provider from user config
    config_dict = await db.get_user_model_config(current_user["id"])
    if not config_dict:
        config_dict = {
            "provider": "ollama",
            "model_name": "llama3",
            "api_key": "",
            "api_base_url": "http://localhost:11434",
            "temperature": 0.1
        }
    else:
        # Decrypt key before use
        if config_dict.get("api_key"):
            config_dict["api_key"] = vault.decrypt(config_dict["api_key"])
            
    provider = get_llm_provider(ModelConfig(**config_dict))

    try:
        if request.stream:
            async def event_stream():
                # Send session ID back to client first
                yield f"data: {json.dumps({'type': 'session_id', 'data': session_id})}\n\n"
                
                full_answer = ""
                sources_data = []
                try:
                    async for event in pipeline.stream_query(
                        user_query=request.query,
                        llm_provider=provider,
                        user_id=current_user["id"],
                        history=history,
                        filters=request.filters,
                    ):
                        if event["type"] == "token":
                            full_answer += event["data"]
                        elif event["type"] == "sources":
                            sources_data = event["data"]
                            
                        yield f"data: {json.dumps(event)}\n\n"
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Streaming error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
                    
                # Save assistant message at the end if we got anything
                if full_answer:
                    assistant_msg_id = str(uuid.uuid4())
                    await db.add_message(assistant_msg_id, session_id, "assistant", full_answer, current_user["id"], sources_data)

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        result = await pipeline.query(
            user_query=request.query,
            llm_provider=provider,
            user_id=current_user["id"],
            history=history,
            filters=request.filters
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Query error: {e}")
        raise HTTPException(500, f"Error connecting to AI model: {str(e)}")
    
    # Add session_id to result
    result["session_id"] = session_id

    # Save assistant message
    assistant_msg_id = str(uuid.uuid4())
    await db.add_message(assistant_msg_id, session_id, "assistant", result.get("answer", ""), current_user["id"], result.get("sources", []))

    # Log query to database
    try:
        await db.log_query(
            query=request.query,
            intent=result.get("intent", ""),
            num_retrieved=result.get("chunks_retrieved", 0),
            num_final=result.get("chunks_after_rerank", 0),
            answer=result.get("answer", ""),
            latency_ms=result.get("latency_ms", 0),
            user_id=current_user["id"],
        )
    except Exception:
        pass  # Don't fail the query due to logging errors

    return QueryResponse(**result)

@router.get("/sessions")
async def get_sessions(current_user=Depends(get_current_user)):
    db = get_metadata_db()
    sessions = await db.get_sessions(current_user["id"])
    return {"sessions": sessions}

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, current_user=Depends(get_current_user)):
    db = get_metadata_db()
    messages = await db.get_messages(session_id, current_user["id"])
    return {"messages": messages}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user=Depends(get_current_user)):
    db = get_metadata_db()
    deleted = await db.delete_session(session_id, current_user["id"])
    if not deleted:
        raise HTTPException(404, "Session not found")
    return {"status": "success"}
