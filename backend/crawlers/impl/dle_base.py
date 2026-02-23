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
        # Pre-warm session with CF cookies by fetching homepage through the bypass
        await self.fetch_html(self.base_url)
        
        search_data = {
            "do": "search",
            "subaction": "search",
            "story": query
        }
        search_url = f"{self.base_url.rstrip('/')}/index.php?do=search"
        res = await self.session.post(search_url, data=search_data, headers={"Referer": self.base_url})
        soup = BeautifulSoup(res.text, 'lxml')
        
        results = []
        articles = soup.select('article, div.item, div.short_story, div.news, a.sres-wrap')
        for article in articles:
            if len(results) >= limit:
                break
                
            title_tag = article.find('h2') or article.find('h3') or article.find('h1') or article.find('a', class_='title')
            
            # Fallback for sites like HDItaliaBits where the container itself is an 'a' tag wrapping an 'h2',
            # and sites like HD4Me where the 'h2' does not wrap the 'a' tag.
            a_tag = None
            title_text = "Unknown"
            
            if title_tag:
                 if title_tag.name == 'a':
                     a_tag = title_tag
                     title_text = title_tag.text.strip()
                 else:
                     a_tag = title_tag.find('a')
                     if a_tag:
                         title_text = a_tag.text.strip()
                     else:
                         title_text = title_tag.text.strip()
            
            # If the wrapper itself is 'a', use it
            if not a_tag and article.name == 'a':
                 a_tag = article
                 if not title_tag:
                     title_text = article.text.strip()
                     
            # Final fallback: any link in the article
            if not a_tag:
                 a_tag = article.find('a')
                 
            # If no 'a' tag whatsoever was found, skip
            if not a_tag:
                 continue
                 
            title = title_text
            link = a_tag.get('href', '')
            if not link.startswith('http'):
                link = self.base_url.rstrip('/') + link

            # Skip non-content pages (category pages, rules, etc.)
            if not link.rstrip('/').endswith('.html'):
                continue
            _skip_titles = ('area vendite', 'regolamento', 'registra', 'login', 'faq')
            if any(s in title.lower() for s in _skip_titles):
                continue
                
            # Try to find poster
            poster = None
            skip_patterns = ('/dleimages/', '/templates/', 'favicon', 'logo', 'noavatar', 'plus_fav', 'btn_', 'icon_')

            # Best: image whose alt matches the article title
            for img in article.find_all('img'):
                alt = (img.get('alt') or '').strip()
                if alt and alt.lower() == title.lower():
                    raw_src = img.get('data-src') or img.get('src') or ''
                    if raw_src and not any(p in raw_src.lower() for p in skip_patterns):
                        poster = raw_src
                        break

            # Fallback: specific poster selectors
            if not poster:
                poster_img = article.select_one('.img-box img, .poster img, .image-box img, a.main-image img')
                if poster_img:
                    raw_src = poster_img.get('data-src') or poster_img.get('src') or ''
                    if raw_src and not any(p in raw_src.lower() for p in skip_patterns):
                        poster = raw_src

            # Last resort: first valid image
            if not poster:
                for img in article.find_all('img'):
                    raw_src = img.get('data-src') or img.get('src') or ''
                    if raw_src and not any(p in raw_src.lower() for p in skip_patterns):
                        poster = raw_src
                        break

            if poster and poster.startswith('/'):
                from urllib.parse import urljoin
                poster = urljoin(self.base_url, poster)
                 
            # Extract Quality from title using shared method
            quality = self.extract_quality(title)
            
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
                    date = self.normalize_date(time_tag.text.strip())

            results.append({
                "title": title,
                "url": link,
                "poster": poster,
                "quality": quality,
                "date": date,
                "site": self.name
            })
            
        return results

    # ---- Download host whitelist (subclasses can extend via class attr) ----
    _DOWNLOAD_HOSTS = {
        'filestore.me', 'terabytez.org', 'worldbytez.xyz',
        'filecrypt.cc', 'filecrypt.co',
        'easybytez.com', 'rapidgator.net', 'nitroflare.com',
        'turbobit.net', 'katfile.com', 'mega.nz',
        'keeplinks.org', 'keeplinks.co',
    }
    _REFERRAL_RE = re.compile(r'/free\d+\.html', re.IGNORECASE)

    async def fetch_links(self, url: str) -> Dict[str, Any]:
        """
        Trigger tanksForNews AJAX thanks, re-fetch page, extract links
        from hidden xfield divs and <a> tags. Works for DLE sites using
        the custom tanksForNews mechanism (HDItalia, Lost Planet, etc.).
        """
        import logging
        logger = logging.getLogger(self.__class__.__name__)

        post_id = url.rstrip('/').split('/')[-1].split('-')[0]

        # 1. Trigger "thanks" to unlock hidden content
        thanks_url = f"{self.base_url.rstrip('/')}/engine/ajax/thanks.php"
        try:
            await self.session.post(
                thanks_url,
                data={"thanks": "tanksForNews", "news_id": post_id},
                headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"},
            )
        except Exception as e:
            logger.warning(f"[{self.name}] Thanks call failed for {post_id}: {e}")

        # 2. Re-fetch the page (xfield divs now populated by server)
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')

        # 3. Extract raw URLs from hidden xfield containers
        raw_text = ""
        for div_id in ("campo-aggiuntivo", "campo-links-serie"):
            div = soup.find(id=div_id)
            if div:
                raw_text += " " + div.get_text(" ", strip=True)

        links: list[str] = []
        seen: set[str] = set()

        for m in re.finditer(r'https?://[^\s<>"\']+', raw_text):
            href = m.group(0).rstrip('.,;)')
            if self._is_download_link(href) and href not in seen:
                links.append(href)
                seen.add(href)

        # Fallback: scan the article body for raw URLs in text AND <a> tags
        if not links:
            root = soup.select_one('.full-text') or soup.select_one('#dle-content') or soup

            # Scan <a> tags
            for a in root.find_all('a', href=True):
                href = a['href']
                if self._is_download_link(href) and href not in seen:
                    links.append(href)
                    seen.add(href)

            # Scan raw text for URLs (Lost Planet embeds links as plain text)
            if not links:
                body_text = root.get_text(" ", strip=True)
                for m in re.finditer(r'https?://[^\s<>"\']+', body_text):
                    href = m.group(0).rstrip('.,;)')
                    if self._is_download_link(href) and href not in seen:
                        links.append(href)
                        seen.add(href)

        # 4. Password
        password = None
        pwd_match = re.search(r'(?i)password\s*[:\-]\s*([^\s<]+)', soup.get_text())
        if pwd_match:
            password = pwd_match.group(1).strip()

        logger.info(f"[{self.name}] Extracted {len(links)} links for {url}")
        return {"links": links, "password": password}

    @classmethod
    def _is_download_link(cls, href: str) -> bool:
        """Return True if href points to a real download, not a referral."""
        if cls._REFERRAL_RE.search(href):
            return False
        try:
            from urllib.parse import urlparse
            host = urlparse(href).netloc.lower().lstrip('www.')
            return host in cls._DOWNLOAD_HOSTS
        except Exception:
            return False

