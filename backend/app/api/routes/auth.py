import uuid
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.core.security import create_token, get_current_user, hash_password, verify_password
from app.core.config import settings
from app.api.dependencies import get_metadata_db
from app.storage.metadata_db import MetadataDB

router = APIRouter()


class UserRegister(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class GoogleLoginRequest(BaseModel):
    token: str


@router.post("/register", response_model=Token)
async def register(user: UserRegister, db: MetadataDB = Depends(get_metadata_db)):
    existing_user = await db.get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(user.password)
    
    await db.add_user(user_id, user.username, hashed_password)
    
    access_token = create_token(user_id=user_id, username=user.username)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: MetadataDB = Depends(get_metadata_db)):
    user = await db.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_token(user_id=user["id"], username=user["username"])
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user.get("id"),
        "username": current_user.get("username", "Anonymous"),
        "role": current_user.get("role", "user")
    }


@router.post("/google-login", response_model=Token)
async def google_login(data: GoogleLoginRequest, db: MetadataDB = Depends(get_metadata_db)):
    try:
        client_id = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID else None
        idinfo = id_token.verify_oauth2_token(
            data.token, google_requests.Request(), client_id, clock_skew_in_seconds=10
        )
        
        email = idinfo.get("email")
        if not email:
            raise ValueError("Token didn't contain an email")
            
        username = email
        
        user = await db.get_user_by_username(username)
        if not user:
            user_id = str(uuid.uuid4())
            await db.add_user(user_id, username, "google_sso")
            user = {"id": user_id, "username": username}
            
        access_token = create_token(user_id=user["id"], username=user["username"])
        return {"access_token": access_token, "token_type": "bearer"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
