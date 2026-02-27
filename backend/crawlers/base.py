import random
import logging
from typing import Optional, Dict, Any
from curl_cffi import requests

logger = logging.getLogger(__name__)

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
        """Initialize the async curl_cffi session with browser impersonation and forced Google DNS."""
        if not self.session:
            import dns.resolver
            from urllib.parse import urlparse
            
            resolve_list = []
            dns_servers = getattr(self, 'dns_servers', 'system')
            if self.base_url and dns_servers and dns_servers.strip().lower() != 'system':
                try:
                    domain = urlparse(self.base_url).netloc
                    if domain:
                        ns = [s.strip() for s in dns_servers.split(',') if s.strip()]
                        res = dns.resolver.Resolver()
                        if ns:
                            res.nameservers = ns
                        ans = res.resolve(domain, 'A')
                        ip = ans[0].to_text()
                        resolve_list = [f"{domain}:443:{ip}", f"{domain}:80:{ip}"]
                except Exception as e:
                    logger.warning(f"DNS resolution failed for {self.base_url}: {e}")
            
            kwargs = {
                "impersonate": "chrome120",
                "headers": {"User-Agent": random.choice(USER_AGENTS)}
            }
            if resolve_list:
                kwargs["curl_options"] = {10203: resolve_list} # CURLOPT_RESOLVE
                
            self.session = requests.AsyncSession(**kwargs)

    async def close(self):
        if self.session:
            await self.session.close()

    async def login(self) -> bool:
        """Override in subclasses if the site requires login."""
        return True

    async def fetch_html(self, url: str) -> str:
        """
        Fetch HTML from a URL, automatically handling Cloudflare protection.
        
        Strategy:
          1. Try a normal curl_cffi request
          2. If blocked by CF (403 + "Just a moment"), invoke nodriver to solve
             the challenge and harvest cookies
          3. Retry the request with the cleared cookies
        """
        from backend.crawlers.cf_bypass import fetch_with_cf_bypass
        return await fetch_with_cf_bypass(self.session, url)

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

    def extract_quality(self, title: str) -> str:
        """
        Extract video resolution from a release title.
        """
        import re
        quality = "N/A"
        try:
            import guessit
            guess = guessit.guessit(title)
            if 'screen_size' in guess:
                quality = str(guess['screen_size'])
            elif 'video_resolution' in guess:
                quality = str(guess['video_resolution'])
            
        except Exception:
            pass

        if quality != "N/A":
            quality = str(quality).lower().lstrip('m')
            if quality in ('4k', '2160p'):
                quality = '2160p'
            elif quality in ('1080p', '1080i', '1080'):
                quality = '1080p'
            elif quality in ('720p', '720i', '720'):
                quality = '720p'
        
        if quality == "N/A":
            q_match = re.search(r'(?i)\b(m?480[pi]?|m?576[pi]?|m?720[pi]?|m?1080[pi]?|m?2160[pi]?|m?4k)\b', title)
            if q_match:
                q = q_match.group(1).lower().lstrip('m')
                if q == '4k':
                    q = '2160p'
                elif q in ('1080', '1080i'):
                    q = '1080p'
                elif q in ('720', '720i'):
                    q = '720p'
                quality = q
                
        return quality

    def extract_metadata(self, title: str) -> Dict[str, Any]:
        """
        Extract detailed metadata (codec, audio, source, hdr) using guessit.
        """
        import re
        metadata = {
            "codec": None,
            "audio": [],
            "source": None,
            "hdr": None
        }
        try:
            import guessit
            guess = guessit.guessit(title)
            
            # 1. Codec
            codec = guess.get("video_codec")
            if codec:
                metadata["codec"] = str(codec)
            
            # 2. Source
            source = guess.get("source")
            if source:
                metadata["source"] = str(source)
                
            # 3. Audio & MD (Mic Dubbed) - Separate tracks
            audio_tags = []
            
            # Check audio_codec
            ac = guess.get("audio_codec")
            if ac:
                if isinstance(ac, list):
                    audio_tags.extend([str(a) for a in ac])
                else:
                    audio_tags.append(str(ac))
            
            # Check for MD / Mic Dubbed
            other_tags = guess.get("other", [])
            if isinstance(other_tags, str): other_tags = [other_tags]
            
            is_md = False
            for o in other_tags:
                o_str = str(o).lower()
                if "mic dubbed" in o_str or o_str == "md" or "md " in o_str:
                    is_md = True
                    break
            if not is_md and re.search(r'\bMD\b', title, re.I):
                is_md = True
                
            if is_md:
                audio_tags.append("MD")
                
            # Language tags
            langs = guess.get("language")
            if langs:
                if isinstance(langs, list):
                    audio_tags.extend([str(l) for l in langs])
                else:
                    audio_tags.append(str(langs))
                    
            # Audio channels
            channels = guess.get("audio_channels")
            if channels:
                audio_tags.append(str(channels))
            
            metadata["audio"] = list(dict.fromkeys(audio_tags)) # Preserves order, removes duplicates
            
            # 4. HDR cleanup and simplification (Unified "HDR" tag)
            is_hdr = False
            for o in other_tags:
                o_str = str(o).lower()
                if any(x in o_str for x in ["hdr", "dolby vision", "dv"]):
                    is_hdr = True
                    break
            
            if is_hdr:
                metadata["hdr"] = "HDR"
                
            # 5. Filter out resolution tags from all fields
            res_tags = ["2160p", "1080p", "720p", "4k", "uhd"]
            
            if metadata["codec"] and metadata["codec"].lower() in res_tags:
                metadata["codec"] = None
            if metadata["source"] and metadata["source"].lower() in res_tags:
                metadata["source"] = None
            if metadata["audio"]:
                metadata["audio"] = [a for a in metadata["audio"] if str(a).lower() not in res_tags]
            
        except Exception:
            pass
            
        return metadata
        
    def normalize_date(self, date_str: str) -> str:
        """
        Robustly convert a date string in any format/language to DD/MM/YYYY using dateparser.
        Returns 'Unknown' if parsing fails.
        """
        if not date_str or date_str == "Unknown":
            return "Unknown"
        try:
            import dateparser
            parsed_date = dateparser.parse(date_str)
            if parsed_date:
                return parsed_date.strftime("%d/%m/%Y")
        except Exception:
            pass
        return "Unknown"

