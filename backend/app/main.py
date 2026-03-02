from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from backend.api.router import router as api_router
from backend.api.integrations import router as integrations_router
from backend.core.database import engine, AsyncSessionLocal, init_db
from backend.models.settings import Base, SiteCredential
from sqlalchemy import select
from contextlib import asynccontextmanager
import os
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()

        # Look for credentials.json: first in DATABASE_DIR (/data), then project root
        data_dir = os.environ.get("DATABASE_DIR", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        creds_path = os.path.join(data_dir, "credentials.json")
        if not os.path.exists(creds_path):
            creds_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "credentials.json")
        if os.path.exists(creds_path):
            try:
                with open(creds_path, 'r', encoding='utf-8') as f:
                    creds_data = json.load(f)
                    
                from backend.models.settings import AppSettings
                async with AsyncSessionLocal() as session:
                    for site_key, data in creds_data.items():
                        if site_key == "flaresolverr":
                            stmt = select(AppSettings)
                            result = await session.execute(stmt)
                            app_settings = result.scalars().first()
                            if app_settings:
                                app_settings.flaresolverr_url = data.get("url", app_settings.flaresolverr_url)
                            else:
                                app_settings = AppSettings(flaresolverr_url=data.get("url", ""))
                                session.add(app_settings)
                            continue

                        stmt = select(SiteCredential).where(SiteCredential.site_key == site_key)
                        result = await session.execute(stmt)
                        existing = result.scalar_one_or_none()
                        
                        if existing:
                            existing.username = data.get("username", existing.username)
                            existing.password = data.get("password", existing.password)
                            existing.custom_url = data.get("custom_url", existing.custom_url)
                            existing.is_enabled = data.get("is_enabled", existing.is_enabled)
                        else:
                            new_cred = SiteCredential(
                                site_key=site_key,
                                username=data.get("username"),
                                password=data.get("password"),
                                custom_url=data.get("custom_url"),
                                is_enabled=data.get("is_enabled", True)
                            )
                            session.add(new_cred)
                    await session.commit()
                    print("✅ Automatically seeded DB with credentials.json")
            except Exception as e:
                print(f"❌ Failed to seed credentials DB: {e}")
        else:
            print("ℹ️  No credentials.json found, skipping DB seed")
    except Exception as e:
        print(f"❌ Fatal startup error: {e}")
        import traceback
        traceback.print_exc()
        raise

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
app.include_router(integrations_router, prefix="/api/integrations")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Mount frontend build if it exists
frontend_build_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "dist")
if os.path.isdir(frontend_build_path):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_build_path, "assets")), name="assets")

    # SPA catch-all: serve index.html for any non-API route
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(frontend_build_path, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_build_path, "index.html"))
