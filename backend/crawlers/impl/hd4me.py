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
        url = f"{self.base_url}?s={urllib.parse.quote(query)}"
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')
        
        results = []
        articles = soup.select('article')
        for article in articles[:limit]:
            title_tag = article.find('h2', class_='entry-title')
            if not title_tag:
                continue
                
            a_tag = title_tag.find('a')
            if not a_tag:
                continue
                
            title = a_tag.text.strip()
            link = a_tag.get('href', '')
            
            poster = None
            img = article.find('img', id='cov') or article.find('img')
            if img:
                poster = img.get('src')
            
            quality = self.extract_quality(title)
            
            # We will fill the date concurrently by visiting the article
            results.append({
                "title": title,
                "url": link,
                "poster": poster,
                "quality": quality,
                "date": "Unknown",
                "site": self.name
            })
            
        async def fetch_date(result):
            try:
                page_html = await self.fetch_html(result["url"])
                page_soup = BeautifulSoup(page_html, 'lxml')
                article_content = page_soup.find('article') or page_soup
                
                # Bottom left date extraction
                meta = article_content.find('footer', class_='entry-footer')
                if meta:
                    posted_on = meta.find('span', class_='posted-on')
                    if posted_on:
                        date_str = posted_on.text.strip()
                        # Extract the date part and normalize
                        match = re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})', date_str)
                        if match:
                            result["date"] = self.normalize_date(match.group(1))
                            return
                
                # Fallback to regex on text
                date_match = re.search(r'\b(\d{1,2}\s+(?:Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+\d{4})\b', article_content.text, re.I)
                if date_match:
                    result["date"] = self.normalize_date(date_match.group(1))
            except Exception:
                pass

        await asyncio.gather(*(fetch_date(r) for r in results))
        return results

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        HD4Me specific: find the internal "Download" button (/?file=...) and follow it to get real links.
        """
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')
        
        links = []
        password = None
        
        # Find password
        pwd_match = re.search(r'(?i)password\s*[:-]\s*([^\s<]+)', soup.text)
        if pwd_match:
            password = pwd_match.group(1).strip()
            
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
