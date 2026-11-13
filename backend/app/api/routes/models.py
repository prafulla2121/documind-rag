from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.providers.registry import PROVIDER_CATALOG, get_llm_provider
from app.providers.base import ModelConfig
from app.core.config import settings
from app.core.security import block_in_demo, get_current_user
from app.api.dependencies import get_metadata_db
from app.storage.metadata_db import MetadataDB
from app.core.vault import vault

router = APIRouter(prefix="/models", tags=["Models"])

class ModelConfigRequest(BaseModel):
    provider: str
    model_name: str
    api_key: str = ""
    api_base_url: str = ""
    temperature: float = 0.1

@router.get("/catalog")
async def get_catalog():
    """Returns all supported providers and their models"""
    return {"providers": PROVIDER_CATALOG}

@router.post("/validate", dependencies=[Depends(block_in_demo)])
async def validate_api_key(req: ModelConfigRequest, current_user=Depends(get_current_user)):
    """Test if a user's API key is valid before saving"""
    try:
        config = ModelConfig(**req.model_dump())
        provider = get_llm_provider(config)
        # Send a minimal test prompt
        result = await provider.generate([{"role": "user", "content": "Say 'ok' only."}])
        return {"valid": True, "test_response": result[:50]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"API key invalid or error: {str(e)}")

@router.post("/save", dependencies=[Depends(block_in_demo)])
async def save_model_config(req: ModelConfigRequest, current_user=Depends(get_current_user), db: MetadataDB = Depends(get_metadata_db)):
    """Save the user's API key + model preference"""
    config_dict = req.model_dump()
    if config_dict.get("api_key"):
        config_dict["api_key"] = vault.encrypt(config_dict["api_key"])
    
    await db.update_user_model_config(current_user["id"], config_dict)
    return {"saved": True}

@router.get("/config")
async def get_model_config(current_user=Depends(get_current_user), db: MetadataDB = Depends(get_metadata_db)):
    config = None if settings.DEMO_MODE else await db.get_user_model_config(current_user["id"])
    if not config:
        # Default config
        # Server default (PLATFORM_LLM_*); its API key is never sent to the browser.
        config = {
            "provider": settings.PLATFORM_LLM_PROVIDER,
            "model_name": settings.PLATFORM_LLM_MODEL,
            "api_key": "",
            "api_base_url": settings.PLATFORM_LLM_BASE_URL,
            "temperature": 0.1
        }
    else:
        # Decrypt key for the frontend (only if we want to show it, or keep it encrypted)
        # Usually, we don't return the API key to the frontend in plain text.
        # But for this UI, we'll decrypt it so the user sees they have one.
        if config.get("api_key"):
            config["api_key"] = vault.decrypt(config["api_key"])
    return config
