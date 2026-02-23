import asyncio
from typing import List, Dict, Type, Any
from backend.crawlers.base import BaseCrawler
from backend.models.api import SearchResult, SearchStatus
from backend.crawlers.impl.italian_sites import (
    HDItaliaBitsCrawler, LostPlanetCrawler, LaForestaIncantataCrawler, HD4MeCrawler
)
from backend.crawlers.impl.torrent_1337x import Torrent1337xCrawler

REGISTERED_CRAWLERS: Dict[str, Type[BaseCrawler]] = {
    HDItaliaBitsCrawler.name: HDItaliaBitsCrawler,
    LostPlanetCrawler.name: LostPlanetCrawler,
    LaForestaIncantataCrawler.name: LaForestaIncantataCrawler,
    HD4MeCrawler.name: HD4MeCrawler,
    Torrent1337xCrawler.name: Torrent1337xCrawler
}

class CrawlerManager:
    def __init__(self, query: str, limit: int = 50, credentials_map: Dict[str, Any] = None):
        self.query = query
        self.limit = limit
        self.crawlers = {}
        for name, cls in REGISTERED_CRAWLERS.items():
            creds = credentials_map.get(name, {}) if credentials_map else {}
            # Check if this site explicitly exists in DB and is disabled
            if creds and not creds.get("is_enabled", True):
                continue
                
            crawler = cls(username=creds.get("username"), password=creds.get("password"))
            if creds.get("custom_name"):
                crawler.name = creds.get("custom_name")
            self.crawlers[name] = crawler

    async def _run_crawler(self, name: str, crawler: BaseCrawler, yield_queue: asyncio.Queue):
        # We'll use the crawler's mutated name which might be the custom_name
        current_name = crawler.name
        try:
            await yield_queue.put(SearchStatus(site=current_name, status="searching"))
            await crawler.init_session()
            
            # Login if needed (abstracted in base class, handles credentials)
            login_success = await crawler.login()
            if not login_success:
                raise Exception("Login failed")
                
            results = await crawler.search(self.query, self.limit)
            results = results[:self.limit] # Enforce strict limit
            
            # Send results to the queue
            await yield_queue.put({"site": current_name, "type": "results", "data": results})
            await yield_queue.put(SearchStatus(site=current_name, status="completed"))
        except Exception as e:
            await yield_queue.put(SearchStatus(site=current_name, status="error", error_message=str(e)))
        finally:
            await crawler.close()

    async def execute_parallel(self, yield_queue: asyncio.Queue):
        tasks = []
        for name, crawler in self.crawlers.items():
            task = asyncio.create_task(self._run_crawler(name, crawler, yield_queue))
            tasks.append(task)
            
        await asyncio.gather(*tasks, return_exceptions=True)
        await yield_queue.put({"type": "done"})

async def get_links_for_url(site: str, url: str, **kwargs) -> Dict[str, Any]:
    if site not in REGISTERED_CRAWLERS:
        raise ValueError(f"Unknown site: {site}")
        
    crawler = REGISTERED_CRAWLERS[site](**kwargs)
    await crawler.init_session()
    try:
        await crawler.login()
        res = await crawler.fetch_links(url)
        return res
    finally:
        await crawler.close()
