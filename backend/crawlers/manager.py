import asyncio
from typing import List, Dict, Type, Any
from backend.crawlers.base import BaseCrawler
from backend.models.api import SearchResult, SearchStatus
from backend.crawlers.impl.hditaliabits import HDItaliaBitsCrawler
from backend.crawlers.impl.lostplanet import LostPlanetCrawler
from backend.crawlers.impl.laforestaincantata import LaForestaIncantataCrawler
from backend.crawlers.impl.hd4me import HD4MeCrawler
from backend.crawlers.impl.torrent_1337x import Torrent1337xCrawler

REGISTERED_CRAWLERS: Dict[str, Type[BaseCrawler]] = {
    HDItaliaBitsCrawler.name: HDItaliaBitsCrawler,
    LostPlanetCrawler.name: LostPlanetCrawler,
    LaForestaIncantataCrawler.name: LaForestaIncantataCrawler,
    HD4MeCrawler.name: HD4MeCrawler,
    Torrent1337xCrawler.name: Torrent1337xCrawler
}

class CrawlerManager:
    def __init__(self, query: str, limit: int = 50, credentials_map: Dict[str, Any] = None, dns_servers: str = "system"):
        self.query = query
        self.limit = limit
        self.dns_servers = dns_servers
        self.crawlers = {}
        for name, cls in REGISTERED_CRAWLERS.items():
            creds = credentials_map.get(name, {}) if credentials_map else {}
            # Check if this site explicitly exists in DB and is disabled
            if creds and not creds.get("is_enabled", True):
                continue
                
            crawler = cls(username=creds.get("username"), password=creds.get("password"))
            if creds.get("custom_name"):
                crawler.name = creds.get("custom_name")
            if creds.get("custom_url"):
                crawler.base_url = creds.get("custom_url").rstrip("/")
            crawler.dns_servers = self.dns_servers
            self.crawlers[name] = crawler

    async def _run_crawler(self, name: str, crawler: BaseCrawler, yield_queue: asyncio.Queue):
        # We'll use the crawler's mutated name which might be the custom_name
        current_name = crawler.name
        try:
            await yield_queue.put(SearchStatus(site=current_name, status="searching"))
            await crawler.init_session()
            
            # Pre-flight navigation check to handle banned/offline sites gracefully
            from curl_cffi.requests.errors import RequestsError
            try:
                test_res = await crawler.session.get(crawler.base_url, timeout=15)
                if test_res.status_code == 403:
                    await yield_queue.put(SearchStatus(site=current_name, status="warning", error_message="Soft IP Ban detected (403 Forbidden). Try changing IP/VPN."))
                    return
            except RequestsError as req_e:
                err_str = str(req_e).lower()
                if "time out" in err_str or "timed out" in err_str or "could not connect" in err_str or "curl: (28)" in err_str or "curl: (7)" in err_str:
                    await yield_queue.put(SearchStatus(site=current_name, status="warning", error_message="Crawler temporarily banned or site offline (Connection Timeout). Try changing IP/VPN."))
                    return
                else:
                    raise req_e # bubble up other curl errors
            except Exception as e:
                # TimeoutError or generic exception handling
                err_str = str(e).lower()
                if "time" in err_str or "connect" in err_str:
                    await yield_queue.put(SearchStatus(site=current_name, status="warning", error_message="Crawler temporarily banned or site offline (Connection Timeout). Try changing IP/VPN."))
                    return
                raise e

            # Login if needed (abstracted in base class, handles credentials)
            login_success = await crawler.login()
            if not login_success:
                raise Exception("Login required/failed")
                
            results = await crawler.search(self.query, self.limit)
            results = results[:self.limit] # Enforce strict limit
            
            # Send results to the queue
            await yield_queue.put({"site": current_name, "type": "results", "data": results})
            await yield_queue.put(SearchStatus(site=current_name, status="completed", count=len(results)))
        except Exception as e:
            err_msg = str(e)
            if "login" in err_msg.lower() or "credentials" in err_msg.lower():
                await yield_queue.put(SearchStatus(site=current_name, status="error", error_message=f"Login failed: {err_msg}"))
            else:
                await yield_queue.put(SearchStatus(site=current_name, status="error", error_message=err_msg))
        finally:
            await crawler.close()

    async def execute_parallel(self, yield_queue: asyncio.Queue):
        tasks = []
        for name, crawler in self.crawlers.items():
            task = asyncio.create_task(self._run_crawler(name, crawler, yield_queue))
            tasks.append(task)
            
        await asyncio.gather(*tasks, return_exceptions=True)
        await yield_queue.put({"type": "done"})

async def get_links_for_url(site: str, url: str, dns_servers: str = "system", **kwargs) -> Dict[str, Any]:
    if site not in REGISTERED_CRAWLERS:
        raise ValueError(f"Unknown site: {site}")
        
    custom_url = kwargs.pop("custom_url", None)
    crawler = REGISTERED_CRAWLERS[site](**kwargs)
    if custom_url:
        crawler.base_url = custom_url.rstrip("/")
    crawler.dns_servers = dns_servers
    await crawler.init_session()
    try:
        await crawler.login()
        res = await crawler.fetch_links(url)
        return res
    finally:
        await crawler.close()
