from backend.crawlers.impl.dle_base import DLECrawler
import re
import logging
from typing import Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class DDLWorldCrawler(DLECrawler):
    name = "DDLWorld"
    base_url = "https://www.ddl-world.space"

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        DDLWorld uses the thanks.php mechanism.
        Links appear after the 'thanks' click (grazie.gif).
        """
        # Extract post ID from URL
        # DDLWorld URLs usually end in .html or use ?newsid=
        post_id = url.rstrip('/').split('/')[-1].split('-')[0]
        if 'newsid=' in url:
            post_id_match = re.search(r'newsid=(\d+)', url)
            if post_id_match:
                post_id = post_id_match.group(1)

        # 1. Trigger thanks (pinguino/grazie.gif equivalent)
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

        # 3. Extract links from the page
        # DDLWorld often puts links in spoiler or just in the content
        # We can use the base fetch_links logic but we need to ensure we re-scan the HTML
        # after the thanks trigger.
        
        # Base DLE _collect_urls_from_element equivalent logic
        root = soup.select_one('.full-text') or soup.select_one('#dle-content') or soup
        
        # Look for <a> tags
        for a in root.find_all('a', href=True):
            href = a['href']
            if self._is_download_link(href) and href not in seen:
                links.append(href)
                seen.add(href)
        
        # Look for raw text URLs
        body_text = root.get_text(" ", strip=True)
        for m in re.finditer(r'https?://[^\s<>"\']+', body_text):
            href = m.group(0).rstrip('.,;)')
            if self._is_download_link(href) and href not in seen:
                links.append(href)
                seen.add(href)

        # 4. Password extraction (Look for "psw:")
        password = None
        pwd_match = re.search(r'(?i)psw\s*[:\-]\s*([^\s<]+)', soup.get_text())
        if pwd_match:
            password = pwd_match.group(1).strip()
        else:
            # Fallback to base DLE password patterns if psw: not found
            pwd_match = re.search(r'(?i)password\s*[:\-]\s*([^\s<]+)', soup.get_text())
            if pwd_match:
                password = pwd_match.group(1).strip()

        logger.info(f"[{self.name}] Extracted {len(links)} links for {url}")
        return {"links": links, "password": password}
