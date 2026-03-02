"""
Cloudflare bypass helper using FlareSolverr.
"""
import logging
from typing import Optional, Tuple, Dict
import aiohttp

logger = logging.getLogger(__name__)

class CloudflareBypassError(Exception):
    """Custom exception when Cloudflare bypass fails or FlareSolverr is missing."""
    pass

async def fetch_with_cf_bypass(session, url: str, flaresolverr_url: str = "", method: str = "GET", data: dict = None, **kwargs) -> str:
    """
    Fetch HTML using GET or POST. Try native fetch first.
    If blocked by Cloudflare, use FlareSolverr API to bypass.
    """
    try:
        if method.upper() == "POST":
            res = await session.post(url, data=data, timeout=15, **kwargs)
        else:
            res = await session.get(url, timeout=15, **kwargs)
        text = res.text
        
        is_blocked = (
            res.status_code in [403, 503]
        )
        
        if not is_blocked:
            return text
    except Exception as e:
        logger.warning(f"[CF] Initial request failed for {url}: {e}")
        is_blocked = True
        text = ""
    
    logger.info(f"[CF] Cloudflare detected on {url}. Attempting bypass...")
    
    if not flaresolverr_url:
        logger.warning(f"[CF] Cannot bypass CF on {url} because FlareSolverr URL is not configured.")
        raise CloudflareBypassError("Blocked by CloudFlare, verify FlareSolverr configuration")

    flaresolverr_api = f"{flaresolverr_url.rstrip('/')}/v1"
    
    # Extract cookies from session for FlareSolverr
    session_cookies = []
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    current_domain = parsed_url.hostname
    
    # In curl_cffi, session.cookies is a dict-like object
    for name, value in session.cookies.items():
        session_cookies.append({
            "name": name,
            "value": value,
            "domain": current_domain,
            "path": "/"
        })

    payload = {
        "cmd": "request.post" if method.upper() == "POST" else "request.get",
        "url": url,
        "maxTimeout": 60000,
        "cookies": session_cookies
    }
    if method.upper() == "POST" and data:
        from urllib.parse import urlencode
        payload["postData"] = urlencode(data)
    
    try:
        async with aiohttp.ClientSession() as aio_session:
            async with aio_session.post(flaresolverr_api, json=payload, timeout=70) as resp:
                if resp.status != 200:
                    logger.warning(f"[CF] FlareSolverr returned status {resp.status} for {url}")
                    raise CloudflareBypassError("Blocked by CloudFlare, verify FlareSolverr configuration")
                    
                resp_json = await resp.json()
                if resp_json.get("status") == "ok" and "solution" in resp_json:
                    logger.info(f"[CF] Successfully bypassed Cloudflare for {url} via FlareSolverr")
                    solution = resp_json["solution"]
                    
                    # Update session with new UA and cookies
                    user_agent = solution.get("userAgent", "")
                    if user_agent:
                        session.headers["User-Agent"] = user_agent
                        
                    cookies = solution.get("cookies", [])
                    domain = parsed_url.hostname
                    
                    for c in cookies:
                        c_domain = c.get("domain", domain)
                        session.cookies.set(c["name"], c["value"], domain=c_domain)
                        
                    return solution.get("response", "")
                else:
                    logger.warning(f"[CF] FlareSolverr failed for {url}: {resp_json}")
                    raise CloudflareBypassError("Blocked by CloudFlare, verify FlareSolverr configuration")
    except Exception as e:
        logger.error(f"[CF] FlareSolverr request error for {url}: {e}")
        if isinstance(e, CloudflareBypassError):
            raise e
        raise CloudflareBypassError("Blocked by CloudFlare, verify FlareSolverr configuration")
