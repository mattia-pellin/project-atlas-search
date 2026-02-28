import random
import logging
from typing import Optional, Dict, Any
from curl_cffi import requests

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
]

class BaseCrawler:
    name: str = "base"
    base_url: str = ""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, flaresolverr_url: str = ""):
        self.username = username
        self.password = password
        self.flaresolverr_url = flaresolverr_url
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
                "impersonate": "chrome142",
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
        flaresolverr_url = getattr(self, "flaresolverr_url", "")
        return await fetch_with_cf_bypass(self.session, url, flaresolverr_url)

    async def post_html(self, url: str, data: dict, **kwargs) -> str:
        """
        POST data to a URL, automatically handling Cloudflare protection.
        """
        from backend.crawlers.cf_bypass import fetch_with_cf_bypass
        flaresolverr_url = getattr(self, "flaresolverr_url", "")
        return await fetch_with_cf_bypass(self.session, url, flaresolverr_url, method="POST", data=data, **kwargs)

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
        # Pre-process title: replace slashes with spaces to help guessit detect multiple tags
        clean_title = title.replace("/", " ")

        metadata = {
            "codec": None,
            "audio": [],
            "languages": [],
            "source": None,
            "hdr": None
        }
        try:
            import guessit
            guess = guessit.guessit(clean_title)
            
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
                if any(x in src_str for x in ["blu-ray", "bdrip", "brrip", "bluray"]):
                    metadata["source"] = "Blu-ray"
                elif "web" in src_str:
                    metadata["source"] = "WEB-DL"
                elif "dvd" in src_str:
                    metadata["source"] = "DVD"
                else:
                    metadata["source"] = str(source)
            
            # Manual fallback for BRRip/BluRay if guessit misses it
            if not metadata["source"]:
                if re.search(r'\b(BRRip|BluRay|BD|BDRip)\b', title, re.I):
                    metadata["source"] = "Blu-ray"
                
            # 3. Audio Tracks (Codec ONLY)
            AUDIO_MAP = {
                "dolby digital plus": "E-AC3",
                "dolby digital": "AC3",
                "dolby truehd": "TrueHD",
                "dts-hd master audio": "DTS-HD",
                "dts-hd high resolution audio": "DTS-HD",
                "dts-hd": "DTS-HD",
                "dts": "DTS"
            }
            
            ac_list = guess.get("audio_codec", [])
            if not isinstance(ac_list, list): ac_list = [ac_list]
            
            audio_tracks = []
            sorted_keys = sorted(AUDIO_MAP.keys(), key=len, reverse=True)
            for codec in ac_list:
                if not codec: continue
                c_low = str(codec).lower()
                mapped = None
                if c_low in AUDIO_MAP:
                    mapped = AUDIO_MAP[c_low]
                else:
                    for k in sorted_keys:
                        if k in c_low:
                            mapped = AUDIO_MAP[k]
                            break
                audio_tracks.append(mapped if mapped else str(codec))
                
            if re.search(r'\bMD\b', title, re.I) or "mic dubbed" in str(guess.get("other", "")).lower():
                audio_tracks.append("MD")
                
            metadata["audio"] = list(dict.fromkeys(audio_tracks))
                
            # 4. Languages (Improved with regex fallback)
            LANG_MAP = {
                "ita": "it", "italian": "it",
                "eng": "en", "english": "en",
                "ing": "en",
                "spa": "es", "spanish": "es",
                "fra": "fr", "french": "fr",
                "ger": "de", "german": "de",
                "it": "it", "en": "en", "es": "es", "fr": "fr", "de": "de"
            }
            
            langs = guess.get("language", [])
            if not isinstance(langs, list): langs = [langs]
            
            found_langs = []
            for l in langs:
                if l: found_langs.append(str(l).lower())
            
            # Manual regex fallback for common tags like Ita/Eng/Spa/Ing
            for key, val in LANG_MAP.items():
                if re.search(r'\b' + key + r'\b', title, re.I):
                    found_langs.append(val)
            
            final_langs = []
            for l in found_langs:
                mapped = LANG_MAP.get(l, l)
                if len(mapped) <= 3: # Keep it short
                     final_langs.append(mapped)
                
            metadata["languages"] = list(dict.fromkeys(final_langs))
            
            # 5. HDR cleanup and simplification (Unified "HDR" tag)
            is_hdr = False
            other_tags = guess.get("other", [])
            if not isinstance(other_tags, list): other_tags = [other_tags]
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

    def clean_query(self, query: str) -> str:
        """
        Clean the query by removing Italian articles, prepositions, 
        and words strictly equal to 1 character long, treating anything
        separated by spaces as an indivisible entity.
        """
        # Articles, Simple Prepositions, Articulate Prepositions
        _FILTER_WORDS = {
            'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una',
            'di', 'a', 'da', 'in', 'con', 'su', 'per', 'tra', 'fra',
            'del', 'dello', 'della', 'dei', 'degli', 'delle',
            'al', 'allo', 'alla', 'ai', 'agli', 'alle',
            'dal', 'dallo', 'dalla', 'dai', 'dagli', 'dalle',
            'nel', 'nello', 'nella', 'nei', 'negli', 'nelle',
            'col', 'coi', 'sul', 'sullo', 'sulla', 'sui', 'sugli', 'sulle',
            'pel', 'pei'
        }
        
        import re
        
        # Replace apostrophes with space so "L'amore" -> "L amore"
        text = re.sub(r"['’]", " ", query)
        
        words = text.split()
        cleaned_words = []
        for w in words:
            if len(w) == 1:
                continue
            
            w_norm = w.lower()
            if w_norm in _FILTER_WORDS:
                continue
                
            cleaned_words.append(w)
            
        return " ".join(cleaned_words)

    def validate_query(self, query: str) -> bool:
        """
        Validate the query based on the 'at least one word >= 4 chars OR two words >= 3 chars' rule
        applied to the CLEANED query.
        """
        cleaned = self.clean_query(query)
        words = cleaned.split()
        
        if not words:
            return False
            
        count_ge_4 = sum(1 for w in words if len(w) >= 4)
        count_ge_3 = sum(1 for w in words if len(w) >= 3)
        
        return count_ge_4 >= 1 or count_ge_3 >= 2

