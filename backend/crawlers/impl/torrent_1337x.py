import asyncio
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import urllib.parse
from backend.crawlers.base import BaseCrawler

import dns.resolver

class Torrent1337xCrawler(BaseCrawler):
    name = "1337x"
    # Using explicit .to domain as requested
    base_url = "https://1337x.to"
    
    def __init__(self, username=None, password=None):
        super().__init__(username, password)

    async def init_session(self):
        # We rely on BaseCrawler's curl_cffi session to bypass standard protections
        await super().init_session()

        # Specify Google DNS resolution for 1337x.to
        try:
            res = dns.resolver.Resolver()
            res.nameservers = ['8.8.8.8', '8.8.4.4']
            ans = res.resolve('1337x.to', 'A')
            ip = ans[0].to_text()
            
            # libcurl CURLOPT_RESOLVE option is 10203
            resolve_list = [f"1337x.to:443:{ip}", f"1337x.to:80:{ip}"]
            
            # Close original session and recreate with custom options
            if hasattr(self, 'session') and self.session:
                await self.session.close()
            
            from curl_cffi.requests import AsyncSession
            self.session = AsyncSession(
                impersonate="chrome120", 
                curl_options={10203: resolve_list}
            )
        except Exception as e:
            # Fallback to standard resolution if dns.resolver fails
            pass
        
    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/sort-search/{urllib.parse.quote(query)}/seeders/desc/1/"
        
        try:
            html = await self.fetch_html(url)
        except Exception:
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
                     
                 date_td = row.find('td', class_='coll-date')
                 date = self.normalize_date(date_td.text.strip()) if date_td else 'Unknown'
                 
                 results.append({
                     "title": title,
                     "url": link,
                     "poster": None,
                     "quality": quality,
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
