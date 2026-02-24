import asyncio
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sse_starlette.sse import EventSourceResponse
from backend.crawlers.manager import CrawlerManager, get_links_for_url
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.core.database import get_db
from backend.models.settings import SiteCredential, AppSettings
from backend.models.search import SearchCache
from typing import List, Optional
import datetime

router = APIRouter()

@router.get("/search/stream")
async def search_stream(request: Request, q: str, db: AsyncSession = Depends(get_db)):
    """
    Server-Sent Events endpoint to stream search progress and results.
    """
    # Fetch settings and credentials from DB
    result = await db.execute(select(AppSettings).limit(1))
    settings = result.scalars().first()
    limit = settings.max_results if settings else 10
    dns_servers = settings.dns_servers if settings else "system"
    cache_enabled = settings.cache_enabled if settings else True
    cache_ttl_minutes = settings.cache_ttl_minutes if settings else 60
    
    force_refresh = request.query_params.get("force_refresh", "false").lower() == "true"
    
    # Check cache first if enabled and not forced to refresh
    if cache_enabled and not force_refresh:
        cache_query = await db.execute(select(SearchCache).where(SearchCache.query == q))
        cached_entry = cache_query.scalars().first()
        if cached_entry:
            # Check TTL
            age_minutes = (datetime.datetime.utcnow() - cached_entry.timestamp).total_seconds() / 60
            if age_minutes <= cache_ttl_minutes:
                # Validate cached JSON
                try:
                    cached_results = json.loads(cached_entry.results_json)
                    async def cached_generator():
                        # Yield all cached objects formatted as SSE results
                        for res in cached_results:
                            wrapped = {"site": res.get("site", "cache"), "type": "results", "data": [res]}
                            yield {"event": "results", "data": json.dumps(wrapped)}
                        yield {"event": "done", "data": "{}"}
                    return EventSourceResponse(cached_generator())
                except Exception as e:
                    # Invalid cache data, proceed to crawl normally
                    pass

    result = await db.execute(select(SiteCredential))
    credentials = {c.site_key: {
        "username": c.username, 
        "password": c.password, 
        "custom_name": c.custom_name, 
        "custom_url": c.custom_url,
        "is_enabled": c.is_enabled
    } for c in result.scalars().all()}
    
    async def event_generator():
        queue = asyncio.Queue()
        manager = CrawlerManager(query=q, limit=limit, credentials_map=credentials, dns_servers=dns_servers)
        
        # Start background task that populates the queue
        task = asyncio.create_task(manager.execute_parallel(queue))
        local_accumulated_results = []
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                task.cancel()
                break
                
            item = await queue.get()
            
            if isinstance(item, dict) and item.get("type") == "done":
                # Save to cache if enabled
                if cache_enabled and local_accumulated_results:
                    try:
                        cache_query = await db.execute(select(SearchCache).where(SearchCache.query == q))
                        cached_entry = cache_query.scalars().first()
                        if not cached_entry:
                            cached_entry = SearchCache(query=q)
                            db.add(cached_entry)
                        
                        cached_entry.results_json = json.dumps(local_accumulated_results)
                        cached_entry.timestamp = datetime.datetime.now(datetime.timezone.utc)
                        await db.commit()
                    except Exception as e:
                        print(f"Failed to cache search results: {e}")
                yield {"event": "done", "data": "{}"}
                break
                
            # Serialize the yielded objects directly to JSON
            if hasattr(item, "model_dump_json"):
                yield {"event": "status", "data": item.model_dump_json()}
            elif isinstance(item, dict) and item.get("type") == "results":
                local_accumulated_results.extend(item.get("data", []))
                yield {"event": "results", "data": json.dumps(item)}

    return EventSourceResponse(event_generator())

class FetchLinksRequest(BaseModel):
    site: str
    url: str

@router.post("/links")
async def fetch_links(req: FetchLinksRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Extract site key from custom_name or fallback to raw string
        result = await db.execute(select(SiteCredential).where(
            (SiteCredential.custom_name == req.site) | (SiteCredential.site_key == req.site)
        ))
        cred = result.scalars().first()
        site_key = cred.site_key if cred else req.site
        
        # Pass kwargs to crawler
        kw = {}
        if cred and cred.username:
            kw["username"] = cred.username
        if cred and cred.password:
            kw["password"] = cred.password
            
        # Fetch global DNS settings
        settings_res = await db.execute(select(AppSettings).limit(1))
        settings = settings_res.scalars().first()
        dns_servers = settings.dns_servers if settings else "system"

        res = await get_links_for_url(site_key, req.url, custom_url=cred.custom_url if cred else None, dns_servers=dns_servers, **kw)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CredentialItem(BaseModel):
    site_key: str
    custom_name: str = ""
    is_enabled: bool = True
    custom_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

class SettingsUpdate(BaseModel):
    max_results: int
    dns_servers: str = "system"
    cache_enabled: bool = True
    cache_ttl_minutes: int = 60
    credentials: List[CredentialItem]

@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    # Get app settings
    result = await db.execute(select(AppSettings).limit(1))
    settings = result.scalars().first()
    max_results = settings.max_results if settings else 10
    dns_servers = settings.dns_servers if settings else "system"
    cache_enabled = settings.cache_enabled if settings else True
    cache_ttl_minutes = settings.cache_ttl_minutes if settings else 60
    
    # Get credentials
    result = await db.execute(select(SiteCredential))
    credentials = result.scalars().all()
    
    creds_list = [{"site_key": c.site_key, "custom_name": c.custom_name, "custom_url": c.custom_url, "is_enabled": c.is_enabled, "username": c.username, "password": c.password} for c in credentials]
    return {
        "max_results": max_results, 
        "dns_servers": dns_servers, 
        "cache_enabled": cache_enabled,
        "cache_ttl_minutes": cache_ttl_minutes,
        "credentials": creds_list
    }

@router.post("/settings")
async def update_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    # Update max_results
    result = await db.execute(select(AppSettings).limit(1))
    settings = result.scalars().first()
    if not settings:
        settings = AppSettings(
            max_results=data.max_results, 
            dns_servers=data.dns_servers,
            cache_enabled=data.cache_enabled,
            cache_ttl_minutes=data.cache_ttl_minutes
        )
        db.add(settings)
    else:
        settings.max_results = data.max_results
        settings.dns_servers = data.dns_servers
        settings.cache_enabled = data.cache_enabled
        settings.cache_ttl_minutes = data.cache_ttl_minutes
        
    # Update credentials
    for cred in data.credentials:
        result = await db.execute(select(SiteCredential).where(SiteCredential.site_key == cred.site_key))
        existing_cred = result.scalars().first()
        if existing_cred:
            existing_cred.custom_name = cred.custom_name
            existing_cred.custom_url = cred.custom_url
            existing_cred.is_enabled = cred.is_enabled
            existing_cred.username = cred.username
            existing_cred.password = cred.password
        else:
            new_cred = SiteCredential(site_key=cred.site_key, custom_name=cred.custom_name, custom_url=cred.custom_url, is_enabled=cred.is_enabled, username=cred.username, password=cred.password)
            db.add(new_cred)
            
    await db.commit()
    return {"status": "success"}

@router.delete("/cache")
async def clear_cache(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    await db.execute(delete(SearchCache))
    await db.commit()
    return {"status": "success", "message": "Cache cleared."}
