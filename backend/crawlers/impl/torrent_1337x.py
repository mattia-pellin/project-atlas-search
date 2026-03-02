import asyncio
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import urllib.parse
from backend.crawlers.base import BaseCrawler

class Torrent1337xCrawler(BaseCrawler):
    name = "1337x"
    # Using explicit .to domain as requested
    base_url = "https://1337x.to"
    
    def __init__(self, username=None, password=None):
        super().__init__(username, password)

    async def init_session(self):
        # If the user has not configured a custom DNS in settings, default to Google DNS
        # for 1337x.to specifically, since it may be filtered/censored on ISP-level DNS
        # in some regions. If a custom DNS is already configured, respect it instead.
        dns_from_settings = getattr(self, 'dns_servers', 'system')
        if not dns_from_settings or dns_from_settings.strip().lower() == 'system':
            self.dns_servers = '8.8.8.8,8.8.4.4'

        # BaseCrawler.init_session handles impersonation, DNS resolution, and session creation.
        await super().init_session()
        
    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/sort-search/{urllib.parse.quote(query)}/seeders/desc/1/"
        
        try:
            html = await self.fetch_html(url)
        except Exception as e:
            from backend.crawlers.cf_bypass import CloudflareBypassError
            if isinstance(e, CloudflareBypassError):
                raise e
            return []
            
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table', class_='table-list')
        if not table:
            return []
            
        results = []
        rows = table.find('tbody').find_all('tr')
        for row in rows[:limit]:
            td_name = row.find('td', class_='name')
            a_tags = td_name.find_all('a')
            if len(a_tags) >= 2:
                 title = a_tags[1].text
                 link = self.base_url + a_tags[1]['href']
                 size_td = row.find('td', class_='size')
                 quality = self.extract_quality(title)
                 metadata = self.extract_metadata(title)
                     
                 date_td = row.find('td', class_='coll-date')
                 date = self.normalize_date(date_td.text.strip()) if date_td else 'Unknown'
                 
                 results.append({
                     "title": title,
                     "url": link,
                     "poster": None,
                     "quality": quality,
                     "metadata": metadata,
                     "date": date,
                     "site": self.name
                 })
                 
        return results

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')
        
        # Look for magnet link
        magnet = None
        for a in soup.find_all('a', href=True):
            if a['href'].startswith('magnet:?'):
                magnet = a['href']
                break
                
        # Also grab standard torrent file links if present
        links = []
        if magnet:
             links.append(magnet)

        return {"links": links, "password": None}
