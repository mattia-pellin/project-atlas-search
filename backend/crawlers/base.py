import random
from typing import Optional, Dict, Any
from curl_cffi import requests

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

class BaseCrawler:
    name: str = "base"
    base_url: str = ""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username
        self.password = password
        self.session = None

    async def init_session(self):
        """Initialize the async curl_cffi session with browser impersonation."""
        if not self.session:
            # We use 'chrome120' impersonation to bypass Cloudflare
            self.session = requests.AsyncSession(
                impersonate="chrome120",
                headers={"User-Agent": random.choice(USER_AGENTS)}
            )

    async def close(self):
        if self.session:
            self.session.close()

    async def login(self) -> bool:
        """Override in subclasses if the site requires login."""
        return True

    async def search(self, query: str, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Perform the search.
        Return list of dicts with: title, poster, quality, date, site, url
        """
        raise NotImplementedError

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        Fetch download links and password from a specific details page.
        Return dict with: links (list of str), password (str or None)
        """
        raise NotImplementedError
