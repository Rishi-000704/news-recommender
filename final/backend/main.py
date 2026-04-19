from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DB_PATH, db_connect, import_csvs, init_db
from recommender import NewsRecommender
from webcam_attention import (
    get_latest_attention_snapshot,
    get_latest_frame,
    start_background_attention,
    stop_background_attention,
)
from auth import init_auth_db, signup_user, login_user, verify_token, get_user_by_id

# ─────────────────────────────────────────────
#  WARMUP (Performance Boost)
# ─────────────────────────────────────────────

async def _warmup():
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _warmup_sync)
    except Exception:
        pass


def _warmup_sync():
    engine._ensure_vectorizer()
    with db_connect(DB_PATH) as conn:
        conn.execute("SELECT news_id, category, subcategory, abstract FROM news").fetchall()
        conn.execute("SELECT * FROM users LIMIT 500").fetchall()
        conn.execute("SELECT category, trending_score FROM category_stats").fetchall()
        first_user = conn.execute("SELECT user_id FROM users LIMIT 1").fetchone()
    if first_user:
        engine._agent(first_user["user_id"])


# ─────────────────────────────────────────────
#  APP LIFECYCLE (FIXED WEBCAM START)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting backend...")

    init_db(DB_PATH)
    init_auth_db()

    enable_webcam = os.getenv("ENABLE_WEBCAM_ATTENTION", "0").lower() in ("1", "true", "yes")
    if enable_webcam:
        try:
            result = start_background_attention()
            print("📷 Webcam:", result)
        except Exception as e:
            print("❌ Webcam failed:", e)
    else:
        print("⚠️ Webcam attention disabled. Set ENABLE_WEBCAM_ATTENTION=1 to enable.")

    asyncio.ensure_future(_warmup())
    yield

    print("🛑 Shutting down...")
    stop_background_attention()


# ─────────────────────────────────────────────
#  FASTAPI APP
# ─────────────────────────────────────────────

app = FastAPI(
    title="HITL DDQN News Recommender",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
#  FRONTEND SERVE
# ─────────────────────────────────────────────

frontend_dir = ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")

engine = NewsRecommender(DB_PATH)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def as_payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


# ─────────────────────────────────────────────
#  SCHEMAS
# ─────────────────────────────────────────────

class OnboardPayload(BaseModel):
    user_id: str | None = None
    interests: list[str] = Field(default_factory=list)
    mood: str = ""
    time_available: float = 10
    time_of_day: str = ""
    location: str = ""
    exploration_preference: float = 0.25
    sample_click: str = ""


class RecommendPayload(BaseModel):
    user_id: str
    k: int = 8
    mode: str | None = None
    location: str | None = None
    mood: str | None = None


class FeedbackPayload(BaseModel):
    user_id: str
    news_id: str
    time_spent: float = 0
    liked: int = 0
    skipped: int = 0
    scroll_depth: float = 0
    click_val: float = 0
    attention_score: float = 0.5
    normalized_attention: float | None = None
    brightness: float = 50
    eye_openness: float = 70
    movement: float = 20
    energy_score: float = 63.5
    gaze_score: float = 0.58
    face_detected: int = 0
    attention_source: str = "frontend"
    final_score: float = 0
    similarity: float = 0
    trending: float = 0
    poll_val: float = 0.5


class PollFeedbackPayload(BaseModel):
    user_id: str
    news_id: str
    liked: int


class UpdatePayload(BaseModel):
    user_id: str


# ─────────────────────────────────────────────
#  AUTH SCHEMAS
# ─────────────────────────────────────────────

class SignupPayload(BaseModel):
    email: str
    username: str
    password: str


class LoginPayload(BaseModel):
    email: str
    password: str


# ─────────────────────────────────────────────
#  BASIC ROUTES
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Open /app for UI or /docs for API."}


@app.post("/import_data")
def import_data(force: bool = False):
    return import_csvs(DB_PATH, force=force)


@app.get("/categories")
def categories():
    return {"categories": engine.categories()}


@app.get("/users")
def users():
    with db_connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT user_id FROM users ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
    return {"users": [row["user_id"] for row in rows]}


@app.get("/user/{user_id}")
def user_info(user_id: str):
    with db_connect(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return dict(row)


# ─────────────────────────────────────────────
#  AUTHENTICATION ROUTES
# ─────────────────────────────────────────────

@app.post("/auth/signup")
def signup(payload: SignupPayload):
    """
    Create a new user account
    
    Returns:
        {
            'user_id': str,
            'username': str,
            'email': str,
            'token': str
        }
    """
    email = payload.email.strip().lower()
    username = payload.username.strip()
    password = payload.password
    
    # Validation
    if not email or '@' not in email:
        raise HTTPException(400, "Invalid email format")
    
    if not username or len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    
    if not re.match(r'^[A-Za-z0-9_]+$', username):
        raise HTTPException(400, "Username may only contain letters, numbers, and underscores")
    
    if not password or len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    
    result = signup_user(email, password, username)
    
    if not result['success']:
        raise HTTPException(400, result['message'])
    
    # Auto-onboard the user in the recommendation system
    engine.onboard_user({
        'user_id': result['user_id'],
        'interests': [],
        'mood': '',
        'time_available': 10,
        'exploration_preference': 0.25
    })
    
    return {
        'user_id': result['user_id'],
        'username': result['username'],
        'email': result['email'],
        'token': result['token']
    }


@app.post("/auth/login")
def login(payload: LoginPayload):
    """
    Authenticate user and return token
    
    Returns:
        {
            'user_id': str,
            'username': str,
            'email': str,
            'token': str
        }
    """
    email = payload.email.strip().lower()
    password = payload.password
    
    if not email or not password:
        raise HTTPException(400, "Email and password required")
    
    result = login_user(email, password)
    
    if not result['success']:
        raise HTTPException(401, result['message'])
    
    return {
        'user_id': result['user_id'],
        'username': result['username'],
        'email': result['email'],
        'token': result['token']
    }


@app.get("/auth/user/{user_id}")
def get_auth_user(user_id: str):
    """Get authenticated user info"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user


@app.post("/auth/verify")
def verify_auth_token(token: str = None):
    """Verify authentication token"""
    if not token:
        raise HTTPException(400, "Token required")
    
    result = verify_token(token)
    
    if not result['valid']:
        raise HTTPException(401, result.get('message', 'Invalid token'))
    
    return {'valid': True, 'user_id': result['user_id']}


# ─────────────────────────────────────────────
#  CORE RL ROUTES
# ─────────────────────────────────────────────

@app.post("/onboard")
def onboard(payload: OnboardPayload):
    return engine.onboard_user(as_payload(payload))


@app.post("/recommend")
def recommend(payload: RecommendPayload):
    return engine.recommend(
        payload.user_id,
        payload.k,
        mode=payload.mode,
        location=payload.location,
        mood=payload.mood,
    )


@app.post("/feedback")
def feedback(payload: FeedbackPayload):
    return engine.feedback(as_payload(payload))


@app.post("/poll_feedback")
def poll_feedback(payload: PollFeedbackPayload):
    return engine.poll_feedback(payload.user_id, payload.news_id, payload.liked)


@app.post("/update_model")
def update_model(payload: UpdatePayload):
    return engine.update_model(payload.user_id)


# ─────────────────────────────────────────────
#  ATTENTION (FIXED)
# ─────────────────────────────────────────────

@app.get("/attention")
def attention():
    return get_latest_attention_snapshot()


@app.get("/attention/frame")
def attention_frame():
    frame = get_latest_frame()
    if not frame:
        return Response(status_code=204)
    return Response(content=frame, media_type="image/jpeg")


@app.get("/attention/stream")
async def attention_stream():
    async def generate():
        while True:
            frame = get_latest_frame()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.04)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ─────────────────────────────────────────────
#  CONTROL ROUTES
# ─────────────────────────────────────────────

@app.post("/attention/start")
def start_attention():
    return start_background_attention()


@app.post("/attention/stop")
def stop_attention():
    return stop_background_attention()