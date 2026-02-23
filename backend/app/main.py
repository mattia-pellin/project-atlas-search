from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from backend.api.router import router as api_router
from backend.core.database import engine
from backend.models.settings import Base
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Project Atlas Search API", lifespan=lifespan)

# Add CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# Mount frontend build if it exists
frontend_build_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "dist")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

