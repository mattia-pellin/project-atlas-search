import asyncio
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import urllib.parse
import re
from backend.crawlers.base import BaseCrawler

class HD4MeCrawler(BaseCrawler):
    name = "HD4ME"
    base_url = "https://hd4me.net/"

    async def login(self) -> bool:
        # HD4Me doesn't require login for search/navigation
        return True

    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_url}lista-film/"
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')
        
        keywords = [k.lower() for k in query.split() if len(k) > 2]
        if not keywords:
            # If query has no words > 2 chars, fallback to an exact match or return empty
            keywords = [query.lower()]
            
        links = soup.select('ul.listaul li a')
        matched_results = []
        
        for a in links:
            text = a.text.strip().lower()
            if not text:
                continue
            if all(kw in text for kw in keywords):
                matched_results.append({
                    "title": a.text.strip(),
                    "url": a.get('href', ''),
                    "poster": None,
                    "quality": self.extract_quality(a.text.strip()),
                    "date": "Unknown",
                    "site": self.name
                })
                if len(matched_results) >= limit:
                    break
        
        async def fetch_details(result):
            if not result["url"].startswith('http'):
                result["url"] = self.base_url.rstrip('/') + result["url"]
                
            try:
                page_html = await self.fetch_html(result["url"])
                page_soup = BeautifulSoup(page_html, 'lxml')
                article_content = page_soup.find('article') or page_soup
                
                # Extract poster
                img = article_content.find('img', id='cov') or article_content.find('img')
                if img:
                    result["poster"] = img.get('src')
                
                # Extract date
                meta = article_content.find('footer', class_='entry-footer')
                if meta:
                    posted_on = meta.find('span', class_='posted-on')
                    if posted_on:
                        date_str = posted_on.text.strip()
                        match = re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})', date_str)
                        if match:
                            result["date"] = self.normalize_date(match.group(1))
                            return
                
                # Fallback Date extraction
                date_match = re.search(r'\b(\d{1,2}\s+(?:Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+\d{4})\b', article_content.text, re.I)
                if date_match:
                    result["date"] = self.normalize_date(date_match.group(1))
            except Exception:
                pass

        await asyncio.gather(*(fetch_details(r) for r in matched_results))
        return matched_results

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        HD4Me specific: find the internal "Download" button (/?file=...) and follow it to get real links.
        """
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')
        
        links = []
        password = None
        
        # Extract any ZIP/RAR password using the shared helper from BaseCrawler
        password = self.extract_password(soup.get_text(" "))
            
        # Find download button
        shrink_links = []
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if '/?file/' in href or 'download' in a.text.lower() or 'scarica' in a.text.lower():
                if href.startswith('/'):
                    href = self.base_url.rstrip('/') + href
                if href not in shrink_links and href != '':
                    shrink_links.append(href)
                    
        # Follow shrink links
        for shrink_url in shrink_links[:3]: # Limit to avoid hanging
            try:
                # curl_cffi should follow redirects
                res = await self.session.get(shrink_url, allow_redirects=True, timeout=15)
                # the final url might be the real link!
                final_url = res.url.lower()
                if any(h in final_url for h in ['mega.nz', 'easybytez', 'filecrypt', 'rapidgator', 'nitroflare', 'turbobit', 'katfile']) and 'mega.nz/sync' not in final_url:
                    if res.url not in links:
                        links.append(res.url)
                else:
                    # scrape the final page for real links just in case
                    final_soup = BeautifulSoup(res.text, 'lxml')
                    for a in final_soup.find_all('a', href=True):
                        href = a.get('href', '')
                        href_lower = href.lower()
                        if any(h in href_lower for h in ['mega.nz', 'easybytez', 'filecrypt', 'rapidgator', 'nitroflare', 'turbobit', 'katfile']) and 'mega.nz/sync' not in href_lower:
                            if href not in links:
                                links.append(href)
            except Exception:
                pass
                
        # If we couldn't resolve shrink links or there are direct links on the page, add them
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            href_lower = href.lower()
            if any(h in href_lower for h in ['mega.nz', 'easybytez', 'filecrypt', 'rapidgator', 'nitroflare', 'turbobit', 'katfile']) and 'mega.nz/sync' not in href_lower:
                if href not in links:
                    links.append(href)

        return {"links": links, "password": password}
