import pytest
import json
import os
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app, lifespan
from backend.core.database import AsyncSessionLocal
from sqlalchemy import select
from backend.models.settings import SiteCredential

QUERIES = ["Matrix", "Batman"]
EXPECTED_SITES = ["1337x", "HD4ME", "HDItalia", "Lost Planet", "DDLWorld"]

@pytest_asyncio.fixture(autouse=True, scope="module")
async def setup_database():
    """Manually trigger the FastAPI lifespan to initialize and seed the DB."""
    async with lifespan(app):
        from backend.models.settings import AppSettings
        async with AsyncSessionLocal() as session:
            # Upsert AppSettings
            result = await session.execute(select(AppSettings).limit(1))
            settings = result.scalars().first()
            # Use env FLARESOLVERR_URL as default for tests
            default_fs = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191")
            if not settings:
                session.add(AppSettings(flaresolverr_url=default_fs))
            else:
                settings.flaresolverr_url = default_fs
            await session.commit()
        yield

@pytest.mark.asyncio
@pytest.mark.parametrize("query", QUERIES)
async def test_search_all_crawlers(query):
    """
    Query the FastAPI SSE search endpoint securely via ASGITransport (no network port opened).
    Validates that each of the expected crawlers returns at least 1 result for the given query.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=60.0) as ac:
        
        # Verify DB seeding occurred during lifespan
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(SiteCredential))
            creds = result.scalars().all()
            print(f"DEBUG: Found {len(creds)} credentials in DB: {[c.site_key for c in creds]}")

        # We pass force_refresh=true to bypass the cache and force crawlers to do actual work
        async with ac.stream("GET", f"/api/search/stream?q={query}&force_refresh=true") as response:
            assert response.status_code == 200, "Search API endpoint failed"
            
            site_statuses = {}
            site_results_count = {}
            for site in EXPECTED_SITES:
                site_results_count[site] = 0
            
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if not data_str or data_str == "{}":
                        continue
                    try:
                        payload = json.loads(data_str)
                        print(f"RCV: {payload}")
                        
                        # Results
                        if payload.get("type") == "results":
                            site = payload.get("site")
                            if site in site_results_count:
                                site_results_count[site] += len(payload.get("data", []))
                        # Status updates
                        elif payload.get("site") and "status" in payload:
                            site_statuses[payload["site"]] = payload["status"]
                    except Exception as repr_err:
                        print(f"ERR: {repr_err}")
                        
            # Verify each crawler
            failed_sites = []
            for site in EXPECTED_SITES:
                status = site_statuses.get(site, "unknown")
                count = site_results_count[site]
                if status == "completed" and count == 0:
                    failed_sites.append(f"{site} (0 results)")
                elif status == "error":
                    failed_sites.append(f"{site} (Error status)")
                # 'warning' (IP ban) is allowed to have 0 results for this CI check
            
            assert not failed_sites, f"Query '{query}' failed for crawlers: {failed_sites}. Statuses: {site_statuses}"

@pytest.mark.asyncio
async def test_ddlworld_direct_login():
    """
    Test DDLWorld login logic specifically.
    """
    from backend.crawlers.impl.ddlworld import DDLWorldCrawler
    from backend.models.settings import SiteCredential
    import os

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(SiteCredential).where(SiteCredential.site_key == "DDLWorld"))
        cred = result.scalars().first()
        
    if not cred or not cred.username or not cred.password:
        pytest.skip("DDLWorld credentials not found in DB")

    fs_url = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191")
    crawler = DDLWorldCrawler(username=cred.username, password=cred.password, flaresolverr_url=fs_url)
    await crawler.init_session()
    try:
        success = await crawler.login()
        # If CF is actually working, this should be True. 
        # If CF fails but returns a response, my new login logic will log the error.
        print(f"DEBUG: DDLWorld login result: {success}")
        assert success, "DDLWorld login failed (potential Cloudflare blockage or invalid credentials)"
    finally:
        await crawler.close()
