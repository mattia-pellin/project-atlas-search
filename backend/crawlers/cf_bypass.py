"""
Cloudflare bypass helper using FlareSolverr.
"""
import asyncio
import logging
from typing import Optional, Tuple, Dict
from urllib.parse import urlparse
import aiohttp

logger = logging.getLogger(__name__)

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
            res.status_code in [403, 503] and 
            ("Just a moment" in text or "Enable JavaScript" in text or 
             "challenge-platform" in text or "Ci siamo quasi" in text or "Cloudflare" in text)
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
        return text

    flaresolverr_api = f"{flaresolverr_url.rstrip('/')}/v1"
    payload = {
        "cmd": "request.post" if method.upper() == "POST" else "request.get",
        "url": url,
        "maxTimeout": 60000
    }
    if method.upper() == "POST" and data:
        from urllib.parse import urlencode
        payload["postData"] = urlencode(data)
    
    try:
        async with aiohttp.ClientSession() as aio_session:
            async with aio_session.post(flaresolverr_api, json=payload, timeout=70) as resp:
                if resp.status != 200:
                    logger.warning(f"[CF] FlareSolverr returned status {resp.status} for {url}")
                    return text
                    
                data = await resp.json()
                if data.get("status") == "ok" and "solution" in data:
                    logger.info(f"[CF] Successfully bypassed Cloudflare for {url} via FlareSolverr")
                    solution = data["solution"]
                    
                    # Update curl_cffi session with new cookies & UserAgent
                    user_agent = solution.get("userAgent", "")
                    if user_agent:
                        session.headers["User-Agent"] = user_agent
                        
                    cookies = solution.get("cookies", [])
                    from urllib.parse import urlparse
                    domain = urlparse(url).hostname
                    
                    for c in cookies:
                        c_domain = c.get("domain", domain)
                        session.cookies.set(c["name"], c["value"], domain=c_domain)
                        
                    return solution.get("response", "")
                else:
                    logger.warning(f"[CF] FlareSolverr failed for {url}: {data}")
                    return text
    except Exception as e:
        logger.error(f"[CF] FlareSolverr request error for {url}: {e}")
        return text
