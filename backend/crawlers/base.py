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
            "languages": [],
            "source": None,
            "hdr": None
        }
        try:
            import guessit
            guess = guessit.guessit(title)
            
            # 1. Video Codec Mapping
            vc = guess.get("video_codec")
            if vc:
                vc_str = str(vc).lower()
                if vc_str in ["hevc", "x265"]:
                    metadata["codec"] = "H.265"
                elif vc_str in ["h264", "x264", "avc"]:
                    metadata["codec"] = "H.264"
                else:
                    metadata["codec"] = str(vc)
            
            # 2. Source Simplification
            source = guess.get("source")
            if source:
                src_str = str(source).lower()
                if any(x in src_str for x in ["blu-ray", "bdrip"]):
                    metadata["source"] = "Blu-ray"
                elif "web" in src_str:
                    metadata["source"] = "WEB-DL"
                elif "dvd" in src_str:
                    metadata["source"] = "DVD"
                else:
                    metadata["source"] = str(source)
                
            # 3. Audio Tracks (Codec + Channels)
            AUDIO_MAP = {
                "dolby digital": "AC3",
                "dolby digital plus": "E-AC3",
                "dolby truehd": "TrueHD",
                "dts-hd master audio": "DTS-HD",
                "dts": "DTS"
            }
            
            ac_list = guess.get("audio_codec", [])
            if isinstance(ac_list, str): ac_list = [ac_list]
            
            ch_list = guess.get("audio_channels", [])
            if isinstance(ch_list, str): ch_list = [ch_list]
            
            audio_tracks = []
            max_len = max(len(ac_list), len(ch_list))
            for i in range(max_len):
                codec = ac_list[i] if i < len(ac_list) else None
                channels = ch_list[i] if i < len(ch_list) else None
                
                if not codec and not channels: continue
                
                parts = []
                if codec:
                    c_low = str(codec).lower()
                    mapped = AUDIO_MAP.get(c_low)
                    if not mapped:
                        for k, v in AUDIO_MAP.items():
                            if k in c_low:
                                mapped = v
                                break
                    parts.append(mapped if mapped else str(codec))
                if channels:
                    parts.append(str(channels))
                
                audio_tracks.append(" ".join(parts))
                
            if re.search(r'\bMD\b', title, re.I) or "mic dubbed" in str(guess.get("other", "")).lower():
                audio_tracks.append("MD")
                
            metadata["audio"] = list(dict.fromkeys(audio_tracks))
                
            # 4. Languages
            langs = guess.get("language", [])
            if isinstance(langs, str): langs = [langs]
            metadata["languages"] = [str(l) for l in langs]
            
            # 5. HDR cleanup and simplification (Unified "HDR" tag)
            is_hdr = False
            other_tags = guess.get("other", [])
            if isinstance(other_tags, str): other_tags = [other_tags]
            for o in other_tags:
                o_str = str(o).lower()
                if any(x in o_str for x in ["hdr", "dolby vision", "dv"]):
                    is_hdr = True
                    break
            if is_hdr:
                metadata["hdr"] = "HDR"
                
            # 6. Global Resolution Filter (Clean tags containing resolution or UHD)
            res_tags = ["2160p", "1080p", "720p", "4k", "uhd"]
            def is_res(s):
                return any(p in str(s).lower() for p in res_tags)

            if metadata["codec"] and is_res(metadata["codec"]):
                metadata["codec"] = None
            if metadata["source"] and is_res(metadata["source"]):
                metadata["source"] = None
            metadata["audio"] = [a for a in metadata["audio"] if not is_res(a)]
            metadata["languages"] = [l for l in metadata["languages"] if not is_res(l)]
            
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

