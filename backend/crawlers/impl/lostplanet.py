import logging
from typing import Dict, Any
from bs4 import BeautifulSoup
from backend.crawlers.impl.dle_base import DLECrawler

logger = logging.getLogger(__name__)


class LostPlanetCrawler(DLECrawler):
    name = "Lost Planet"
    base_url = "https://lostplanet.online/"

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        Use the shared DLE tanksForNews logic, but also grab the correct
        poster from the detail page so we can return it alongside links.
        """
        result = await super().fetch_links(url)

        # Also extract the correct poster from the page
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')
        poster = self._extract_poster(soup)
        if poster:
            result["poster"] = poster

        return result

    @staticmethod
    def _extract_poster(soup) -> str | None:
        """
        Find the large poster image inside the article body.
        It's the <img> whose alt matches the article <h1> title.
        """
        h1 = soup.find('h1')
        if not h1:
            return None
        title_text = h1.get_text(strip=True)

        skip = ('noavatar', '/dleimages/', '/templates/', 'favicon', 'logo', 'plus_fav')
        for img in soup.select('#dle-content img, .full-text img, .f-mov-img img, .mov-desc img'):
            alt = (img.get('alt') or '').strip()
            src = img.get('data-src') or img.get('src') or ''
            if not src or any(s in src.lower() for s in skip):
                continue
            if alt and (alt.lower() in title_text.lower() or title_text.lower() in alt.lower()):
                return src
            if any(d in src for d in ['imageban.ru', 'image.tmdb', 'i.imgur']):
                return src

        for img in soup.select('#dle-content img, .full-text img'):
            src = img.get('data-src') or img.get('src') or ''
            if src and not any(s in src.lower() for s in skip):
                return src
        return None
