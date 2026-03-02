from backend.crawlers.impl.dle_base import DLECrawler

import re
import logging
from typing import Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LaForestaIncantataCrawler(DLECrawler):
    name = "LFI"
    base_url = "https://laforestaincantata.org/"

    async def login(self) -> bool:
        if not self.username or not self.password:
            return False

        # Warm up session and acquire CF cookies via bypass-aware fetch.
        # LFI uses a Cloudflare-protected login page, so we must go through
        # fetch_html (which falls back to FlareSolverr when CF is detected).
        await self.fetch_html(self.base_url)

        login_data = {
            "login_name": self.username,
            "login_password": self.password,
            "login": "submit",
            "login_not_save": "1"
        }

        # LFI login endpoint is /?do=login (not /index.php?do=login like stock DLE)
        login_url = f"{self.base_url.rstrip('/')}/?do=login"
        html = await self.post_html(login_url, data=login_data, headers={"Referer": self.base_url})
        return self.username.lower().split('@')[0] in html.lower()

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        LFI stores download links inside a <textarea id="inputTextToSave">
        as plain text, visible after the pinguino/thanks click (same as DLE
        tanksForNews). The 'mostralink' button is a pure CSS toggle — no
        extra AJAX needed; links are already in the HTML after thanks.
        """
        # Extract post ID — LFI uses ?newsid=NNNNN format
        post_id_match = re.search(r'newsid=(\d+)', url)
        if post_id_match:
            post_id = post_id_match.group(1)
        else:
            post_id = url.rstrip('/').split('/')[-1].split('-')[0]

        # 1. Trigger thanks (pinguino click)
        thanks_url = f"{self.base_url.rstrip('/')}/engine/ajax/thanks.php"
        try:
            await self.session.post(
                thanks_url,
                data={"thanks": "tanksForNews", "news_id": post_id},
                headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"},
            )
        except Exception as e:
            logger.warning(f"[{self.name}] Thanks call failed for {post_id}: {e}")

        # 2. Re-fetch the page
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')

        links: list[str] = []
        seen: set[str] = set()

        # 3. Primary: extract from <textarea id="inputTextToSave">
        textarea = soup.find('textarea', id='inputTextToSave')
        if textarea:
            raw_text = textarea.get_text()
            for m in re.finditer(r'https?://[^\s<>"\']+', raw_text):
                href = m.group(0).rstrip('.,;)')
                if self._is_download_link(href) and href not in seen:
                    links.append(href)
                    seen.add(href)

        # 4. Fallback: standard DLE text_spoiler / article-wide scan
        if not links:
            result = await super().fetch_links(url)
            return result

        # 5. Password
        password = self.extract_password(soup.get_text(" "))

        logger.info(f"[{self.name}] Extracted {len(links)} links for {url}")
        return {"links": links, "password": password}

