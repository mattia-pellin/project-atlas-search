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
    Server-Sent Events endpoint to stream search progress and results with granular caching.
    """
    # Fetch settings and credentials from DB
    result = await db.execute(select(AppSettings).limit(1))
    settings = result.scalars().first()
    limit = settings.max_results if settings else 10
    dns_servers = settings.dns_servers if settings else "system"
    cache_enabled = settings.cache_enabled if settings else True
    cache_ttl_minutes = settings.cache_ttl_minutes if settings else 60
    
    force_refresh = request.query_params.get("force_refresh", "false").lower() == "true"
    
    # Get all registered crawlers
    from backend.crawlers.manager import REGISTERED_CRAWLERS
    
    # Get all enabled sites from credentials (respect DB settings)
    cred_result = await db.execute(select(SiteCredential))
    credentials = {c.site_key: {
        "username": c.username, 
        "password": c.password, 
        "custom_name": c.custom_name, 
        "custom_url": c.custom_url,
        "is_enabled": c.is_enabled
    } for c in cred_result.scalars().all()}
    
    # Active sites = All registered sites UNLESS explicitly disabled in DB
    active_sites = []
    for site_key in REGISTERED_CRAWLERS.keys():
        cred = credentials.get(site_key)
        if cred is None or cred.get("is_enabled", True):
            active_sites.append(site_key)
    
    sites_to_crawl = []
    cached_results_by_site = {}

    if cache_enabled and not force_refresh:
        for site in active_sites:
            cache_query = await db.execute(
                select(SearchCache).where(SearchCache.query == q, SearchCache.site == site)
            )
            cached_entry = cache_query.scalars().first()
            if cached_entry:
                age_minutes = (datetime.datetime.now(datetime.timezone.utc) - 
                              cached_entry.timestamp.replace(tzinfo=datetime.timezone.utc)).total_seconds() / 60
                if age_minutes <= cache_ttl_minutes:
                    try:
                        cached_results_by_site[site] = json.loads(cached_entry.results_json)
                        continue # Found in cache and valid
                    except Exception:
                        pass
            # If we reach here, site is NOT in cache or cache is invalid/expired
            sites_to_crawl.append(site)
    else:
        sites_to_crawl = active_sites

    async def event_generator():
        # 1. Yield all cached results immediately
        for site, results in cached_results_by_site.items():
            wrapped = {"site": site, "type": "results", "data": results}
            yield {"event": "results", "data": json.dumps(wrapped)}
            yield {"event": "status", "data": json.dumps({"site": site, "status": "completed", "count": len(results)})}
        
        if not sites_to_crawl:
            yield {"event": "done", "data": "{}"}
            return

        # 2. Start dynamic crawling for missing sites
        queue = asyncio.Queue()
        manager = CrawlerManager(query=q, limit=limit, credentials_map=credentials, dns_servers=dns_servers, only_sites=sites_to_crawl)
        
        task = asyncio.create_task(manager.execute_parallel(queue))
        
        while True:
            if await request.is_disconnected():
                task.cancel()
                break
                
            item = await queue.get()
            
            if isinstance(item, dict) and item.get("type") == "done":
                yield {"event": "done", "data": "{}"}
                break
                
            if hasattr(item, "model_dump_json"):
                yield {"event": "status", "data": item.model_dump_json()}
            elif isinstance(item, dict) and item.get("type") == "results":
                # Save to cache individually per site
                site = item.get("site")
                if cache_enabled and site:
                    try:
                        site_results = item.get("data", [])
                        cache_query = await db.execute(
                            select(SearchCache).where(SearchCache.query == q, SearchCache.site == site)
                        )
                        cached_entry = cache_query.scalars().first()
                        if not cached_entry:
                            cached_entry = SearchCache(query=q, site=site)
                            db.add(cached_entry)
                        
                        cached_entry.results_json = json.dumps(site_results)
                        cached_entry.timestamp = datetime.datetime.now(datetime.timezone.utc)
                        await db.commit()
                    except Exception as e:
                        print(f"Failed to cache results for {site}: {e}")
                
                yield {"event": "results", "data": json.dumps(item)}

    return EventSourceResponse(event_generator())

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
    
    # Get credentials from DB
    result = await db.execute(select(SiteCredential))
    db_credentials = {c.site_key: c for c in result.scalars().all()}
    
    # Get all registered crawlers to ensure all sites are represented in settings
    from backend.crawlers.manager import REGISTERED_CRAWLERS
    
    creds_list = []
    for site_key in REGISTERED_CRAWLERS.keys():
        c = db_credentials.get(site_key)
        if c:
            creds_list.append({
                "site_key": c.site_key, 
                "custom_name": c.custom_name, 
                "custom_url": c.custom_url, 
                "is_enabled": c.is_enabled, 
                "username": c.username, 
                "password": c.password
            })
        else:
            # Add default entry for site not in DB
            creds_list.append({
                "site_key": site_key,
                "custom_name": "",
                "custom_url": None,
                "is_enabled": True,
                "username": None,
                "password": None
            })
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
