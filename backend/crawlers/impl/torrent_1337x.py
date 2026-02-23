import asyncio
import cloudscraper
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import urllib.parse
from backend.crawlers.base import BaseCrawler

class Torrent1337xCrawler(BaseCrawler):
    name = "1337x"
    base_url = "https://1337x.to"
    
    def __init__(self, username=None, password=None):
        super().__init__(username, password)
        # We use cloudscraper to bypass standard Cloudflare challenges on 1337x
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    async def init_session(self):
        pass # Not using curl_cffi for this one
        
    async def close(self):
        pass

    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        # 1337x search URL
        url = f"{self.base_url}/search/{urllib.parse.quote(query)}/1/"
        
        def fetch():
            return self.scraper.get(url, timeout=10)
            
        res = await asyncio.to_thread(fetch)
        soup = BeautifulSoup(res.text, 'lxml')
        
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
                 size = size_td.contents[0].strip() if size_td else 'Unknown'
                 date_td = row.find('td', class_='coll-date')
                 date = date_td.text.strip() if date_td else 'Unknown'
                 
                 results.append({
                     "title": title,
                     "url": link,
                     "poster": None, # 1337x doesn't reliably show posters on search
                     "quality": size, # We use the size as quality indicator for torrents
                     "date": date,
                     "site": self.name
                 })
                 
        return results

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        def fetch():
            return self.scraper.get(url, timeout=10)
            
        res = await asyncio.to_thread(fetch)
        soup = BeautifulSoup(res.text, 'lxml')
        
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
             
        for a in soup.find_all('a', href=True):
            if a['href'].endswith('.torrent'):
                 links.append(a['href'])
                 
        return {"links": links, "password": None}
