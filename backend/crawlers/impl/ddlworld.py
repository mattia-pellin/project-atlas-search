import re
import logging
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from .dle_base import DLECrawler

logger = logging.getLogger(__name__)

class DDLWorldCrawler(DLECrawler):
    name: str = "DDLWorld"

    def __init__(self, username: str = None, password: str = None, flaresolverr_url: str = ""):
        super().__init__(username, password, flaresolverr_url)
        self.base_url = "https://www.ddl-world.space"

    async def login(self) -> bool:
        """DDLWorld specific login logic."""
        if not self.username or not self.password:
            logger.error(f"[{self.name}] Missing credentials for login")
            return False

        # First visit the home page to get a session/cookies
        await self.fetch_html(self.base_url)
        
        login_data = {
            "login": "submit",
            "login_name": self.username,
            "login_password": self.password,
            "login_not_save": "0",  # 0 for persistent login (gets dle_user_id/dle_password cookies)
        }
        # DDLWorld needs the login payload sent to the homepage
        html = await self.post_html(self.base_url, data=login_data, headers={"Referer": self.base_url})
        
        # Look for the welcome message: "Benvenuto [username]!"
        welcome_pattern = f"benvenuto {self.username.lower()}"
        if welcome_pattern in html.lower():
            return True
            
        # Fallback to checking for the logout link
        if 'action=logout' in html or 'do=logout' in html or 'Esci</a>' in html:
            return True
            
        return False

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """Fetch links by triggering the 'thanks' AJAX call and parsing the combined content."""
        # Fetch the page first
        html = await self.fetch_html(url)
        
        # Extract post_id from url
        # Ex: https://www.ddl-world.space/news/224877-name.html -> 224877
        try:
            post_id = url.rstrip('/').split('/')[-1].split('-')[0]
        except Exception:
            logger.error(f"Could not extract post_id from {url}")
            return {"links": [], "password": None}
        
        # AJAX call to thanks.php to reveal hidden content
        thanks_url = f"{self.base_url.rstrip('/')}/engine/ajax/thanks.php"
        thanks_html = ""
        try:
            thanks_html = await self.post_html(
                thanks_url,
                data={"thanks": "thanksForNews", "news_id": post_id},
                headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"},
            )
        except Exception as e:
            logger.error(f"Error calling thanks.php for {url}: {e}")

        # Combine responses to ensure we capture all revealed links
        combined_html = html + "\n" + thanks_html
        soup = BeautifulSoup(combined_html, "lxml")
        
        links = []
        seen = set()
        
        # Search for <a> tags
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Filter out referral/registration links
            if any(x in href for x in ["registration", "ref/", "referral"]):
                continue
                
            if self._is_download_link(href) and href not in seen:
                links.append(href)
                seen.add(href)
        
        # Search for raw text URLs (some links are revealed in spoilers as raw text)
        body_text = soup.get_text(" ", strip=True)
        for m in re.finditer(r'https?://[^\s<>"\']+', body_text):
            href = m.group(0).rstrip('.,;)')
            if any(x in href for x in ["registration", "ref/", "referral"]):
                continue
                
            if self._is_download_link(href) and href not in seen:
                links.append(href)
                seen.add(href)

        # Extract password using the shared helper from BaseCrawler
        password = self.extract_password(body_text)

        logger.info(f"[{self.name}] Extracted {len(links)} links and password: {password}")
        return {"links": links, "password": password}
