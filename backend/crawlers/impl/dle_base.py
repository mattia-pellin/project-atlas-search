import re
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from backend.crawlers.base import BaseCrawler

class DLECrawler(BaseCrawler):
    """
    Base crawler for sites running DataLife Engine (DLE).
    Handles login, searching, and 'thank you' AJAX bypass standard to DLE.
    """
    
    async def login(self) -> bool:
        if not self.username or not self.password:
            return False
            
        # Get homepage for cookies
        await self.session.get(self.base_url)
        
        login_data = {
            "login_name": self.username,
            "login_password": self.password,
            "login": "submit",
            "login_not_save": "1"
        }
        res = await self.session.post(self.base_url, data=login_data, headers={"Referer": self.base_url})
        return self.username.lower().split('@')[0] in res.text.lower()

    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        search_data = {
            "do": "search",
            "subaction": "search",
            "story": query
        }
        search_url = f"{self.base_url.rstrip('/')}/index.php?do=search"
        res = await self.session.post(search_url, data=search_data, headers={"Referer": self.base_url})
        soup = BeautifulSoup(res.text, 'lxml')
        
        results = []
        for article in soup.find_all('article'):
            if len(results) >= limit:
                break
                
            title_tag = article.find('h2') or article.find('h3') or article.find('h1') or article.find('a', class_='title')
            if not title_tag:
                 continue
                 
            a_tag = title_tag if title_tag.name == 'a' else title_tag.find('a')
            if not a_tag:
                 continue
                 
            title = a_tag.text.strip()
            link = a_tag.get('href', '')
            if not link.startswith('http'):
                link = self.base_url.rstrip('/') + link
                
            # Try to find poster
            poster = None
            img = article.find('img')
            if img:
                 poster = img.get('src')
                 
            # Extract Quality from title
            quality = "SD"
            q_match = re.search(r'(?i)\b(480p|576p|720p|1080p|2160p|4K)\b', title)
            if q_match:
                quality = q_match.group(1).upper()
            
            # Extract Date from article text
            date = "Unknown"
            date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', article.text)
            if date_match:
                # Normalize to DD/MM/YYYY
                d, m, y = date_match.groups()
                date = f"{int(d):02d}/{int(m):02d}/{y}"
            else:
                # Try finding time tag
                time_tag = article.find('time')
                if time_tag and time_tag.text:
                    date = time_tag.text.strip()

            results.append({
                "title": title,
                "url": link,
                "poster": poster,
                "quality": quality,
                "date": date,
                "site": self.name
            })
            
        return results

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        Fetch details page, try to find links. If hidden by "thanks", trigger AJAX.
        """
        res = await self.session.get(url, headers={"Referer": self.base_url})
        soup = BeautifulSoup(res.text, 'lxml')
        
        # 1. Attempt to find thanks button automatically
        # DLE usually uses doThank or similar JS, calling /engine/ajax/thanks.php (or /engine/ajax/controller.php?mod=thanks)
        thanks_url = f"{self.base_url.rstrip('/')}/engine/ajax/controller.php?mod=thanks"
        post_id = url.split('/')[-1].split('-')[0] # extract ID from url like /12345-movie.html
        
        # We aggressively call the thanks endpoint just in case
        await self.session.post(thanks_url, data={"news_id": post_id}, headers={
            "Referer": url,
            "X-Requested-With": "XMLHttpRequest"
        })
        
        # Refetch page after thanking
        res = await self.session.get(url, headers={"Referer": self.base_url})
        soup = BeautifulSoup(res.text, 'lxml')
        
        links = []
        # Find easybytez, filecrypt, etc.
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(h in href.lower() for h in ['easybytez', 'filecrypt', 'rapidgator', 'nitroflare', 'turbobit', 'katfile']):
                if href not in links:
                    links.append(href)
                    
        # Find password
        password = None
        pwd_match = re.search(r'(?i)password\s*[:-]\s*([^\s<]+)', soup.text)
        if pwd_match:
            password = pwd_match.group(1).strip()
                    
        return {"links": links, "password": password}
