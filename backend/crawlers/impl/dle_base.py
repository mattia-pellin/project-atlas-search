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
        login_url = f"{self.base_url.rstrip('/')}/index.php?do=login"
        res = await self.session.post(login_url, data=login_data, headers={"Referer": self.base_url})
        return self.username.lower().split('@')[0] in res.text.lower()

    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        # Pre-warm session with CF cookies by fetching homepage through the bypass
        await self.fetch_html(self.base_url)
        
        # Use DLE advanced search parameters to bypass short-word limits
        # all_word_seach=1 enforces exact match, and titleonly=3 limits search to titles only
        search_data = {
            "do": "search",
            "subaction": "search",
            "story": query,
            "full_search": "1",
            "all_word_seach": "1",
            "titleonly": "3"
        }
        search_url = f"{self.base_url.rstrip('/')}/index.php?do=search"
        res = await self.session.post(search_url, data=search_data, headers={"Referer": self.base_url})
        soup = BeautifulSoup(res.text, 'lxml')
        
        results = []
        articles = soup.select('article, div.item, div.short_story, div.news, a.sres-wrap, div.titlecontrol')
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
                     a_tag = None
                     for candidate in title_tag.find_all('a'):
                         if 'do=favorites' not in candidate.get('href', ''):
                             a_tag = candidate
                             break
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
                 for candidate in article.find_all('a'):
                     if 'do=favorites' not in candidate.get('href', ''):
                         a_tag = candidate
                         if title_text == "Unknown":
                             title_text = candidate.text.strip()
                         break
                 
            # If no 'a' tag whatsoever was found, skip
            if not a_tag:
                 continue
                 
            title = title_text
            link = a_tag.get('href', '')
            if not link.startswith('http'):
                link = self.base_url.rstrip('/') + link

            # Skip non-content pages (category pages, rules, etc.)
            if not link.rstrip('/').endswith('.html') and '?newsid=' not in link:
                continue
            _skip_titles = ('area vendite', 'regolamento', 'registra', 'login', 'faq')
            if any(s in title.lower() for s in _skip_titles):
                continue
                
            # Determine search scope for poster and date
            search_scope = article
            if 'titlecontrol' in (article.get('class') or []):
                next_sib = article.find_next_sibling('div')
                if next_sib and 'general_box' in (next_sib.get('class') or []):
                    search_scope = next_sib

            # Try to find poster
            poster = None
            skip_patterns = ('/dleimages/', '/templates/', 'favicon', 'logo', 'noavatar', 'plus_fav', 'btn_', 'icon_')

            # Best: image whose alt matches the article title
            for img in search_scope.find_all('img'):
                alt = (img.get('alt') or '').strip()
                if alt and alt.lower() == title.lower():
                    raw_src = img.get('data-src') or img.get('src') or ''
                    if raw_src and not any(p in raw_src.lower() for p in skip_patterns):
                        poster = raw_src
                        break

            # Fallback: specific poster selectors
            if not poster:
                poster_img = search_scope.select_one('.img-box img, .poster img, .image-box img, a.main-image img')
                if poster_img:
                    raw_src = poster_img.get('data-src') or poster_img.get('src') or ''
                    if raw_src and not any(p in raw_src.lower() for p in skip_patterns):
                        poster = raw_src

            # Last resort: first valid image
            if not poster:
                for img in search_scope.find_all('img'):
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
            
            # 1. Try common DLE structured date containers
            date_el = search_scope.find('time') or \
                      search_scope.select_one('.date, .time, .arg-info span, .meta span, .arg-stat span')
            
            if date_el and date_el.text:
                date = self.normalize_date(date_el.text.strip())
            
            # 2. Fallback: Search for numeric pattern (DD-MM-YYYY) in text
            if date == "Unknown":
                date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', search_scope.text)
                if date_match:
                    d, m, y = date_match.groups()
                    date = f"{int(d):02d}/{int(m):02d}/{y}"

            # 3. Last effort: Search for relative date keywords (Today, Yesterday, etc.) in text
            if date == "Unknown":
                rel_match = re.search(r'\b(Today|Yesterday|Oggi|Ieri|Domani|Domani)[^0-9]*(\d{1,2}:\d{2})?\b', search_scope.text, re.I)
                if rel_match:
                    date = self.normalize_date(rel_match.group(0))

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
        Trigger tanksForNews AJAX thanks, re-fetch page, extract links.
        Strategy:
          1. text_spoiler div following a <b>Links</b> (or similar) label
          2. xfield containers (#campo-aggiuntivo, #campo-links-serie)
          3. Article-wide fallback (<a> tags + raw text)
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

        # 2. Re-fetch the page
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, 'lxml')

        links: list[str] = []
        seen: set[str] = set()

        def _collect_urls_from_element(el):
            """Extract download URLs from an element's text and <a> tags."""
            # Raw text URLs
            raw_text = el.get_text(" ", strip=True)
            for m in re.finditer(r'https?://[^\s<>"\']+'  , raw_text):
                href = m.group(0).rstrip('.,;)')
                if self._is_download_link(href) and href not in seen:
                    links.append(href)
                    seen.add(href)
            # <a> tag hrefs
            for a in el.find_all('a', href=True):
                href = a['href']
                if self._is_download_link(href) and href not in seen:
                    links.append(href)
                    seen.add(href)

        # 3a. Primary: find text_spoiler div(s) following a "Links" label
        link_labels = ('links', 'link', 'download')
        for b_tag in soup.find_all('b'):
            if b_tag.get_text(strip=True).lower().rstrip(':') in link_labels:
                spoiler = b_tag.find_next(class_='text_spoiler')
                if spoiler:
                    _collect_urls_from_element(spoiler)

        # 3b. xfield containers
        if not links:
            for div_id in ("campo-aggiuntivo", "campo-links-serie"):
                div = soup.find(id=div_id)
                if div:
                    _collect_urls_from_element(div)

        # 3c. Fallback: scan the article body
        if not links:
            root = soup.select_one('.full-text') or soup.select_one('#dle-content') or soup
            # <a> tags first
            for a in root.find_all('a', href=True):
                href = a['href']
                if self._is_download_link(href) and href not in seen:
                    links.append(href)
                    seen.add(href)
            # Raw text
            if not links:
                body_text = root.get_text(" ", strip=True)
                for m in re.finditer(r'https?://[^\s<>"\']+'  , body_text):
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
            host = urlparse(href).netloc.lower()
            if host.startswith('www.'):
                host = host[4:]
            return host in cls._DOWNLOAD_HOSTS
        except Exception:
            return False

