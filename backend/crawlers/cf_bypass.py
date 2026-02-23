"""
Cloudflare bypass helper using Chrome + CDP + Xvfb.

Strategy:
  1. Start Xvfb (virtual framebuffer) so Chrome can run in HEADED mode
  2. Launch Google Chrome in headed mode (NOT headless — CF detects headless)
  3. Inject anti-detection scripts via CDP before any navigation
  4. Navigate to the target site, wait for CF Turnstile to auto-resolve
  5. Extract cf_clearance cookie + User-Agent
  6. Inject them into curl_cffi for all subsequent fast HTTP requests
"""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import Optional, Tuple, Dict
from urllib.parse import urlparse

import aiohttp
import websockets

logger = logging.getLogger(__name__)

# Cache of cleared cookies per domain
_cf_cache: Dict[str, dict] = {}
_cf_lock = asyncio.Lock()
CF_CACHE_TTL = 300  # 5 minutes
CDP_PORT = 19222

_cmd_id = 0
def _next_id() -> int:
    global _cmd_id
    _cmd_id += 1
    return _cmd_id


def _find_chrome() -> Optional[str]:
    for name in ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium"]:
        path = shutil.which(name)
        if path:
            return path
    return None


# JavaScript to inject before page loads to mask automation fingerprints
STEALTH_JS = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Override chrome runtime to look like a real browser
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };

// Override permissions query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Override plugins to show some default ones
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});

// Override languages  
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'it']
});
"""


async def _get_ws_url(port: int, max_wait: int = 15) -> Optional[str]:
    """Poll Chrome's HTTP endpoint to get the debugger WebSocket URL."""
    url = f"http://127.0.0.1:{port}/json/version"
    for _ in range(max_wait * 2):
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    data = await resp.json()
                    return data.get("webSocketDebuggerUrl")
        except Exception:
            await asyncio.sleep(0.5)
    return None


def _start_xvfb() -> subprocess.Popen:
    """Start a virtual X display."""
    display = ":99"
    os.environ["DISPLAY"] = display
    proc = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)  # Let Xvfb start
    return proc


async def get_cf_cookies(url: str, timeout: int = 25) -> Optional[Tuple[dict, str]]:
    """Launch headed Chrome on Xvfb, solve CF challenge, extract cookies."""
    domain = urlparse(url).netloc
    base_url = f"{urlparse(url).scheme}://{domain}"
    
    async with _cf_lock:
        cached = _cf_cache.get(domain)
        if cached and time.time() < cached["expires"]:
            logger.info(f"[CF Bypass] Using cached cookies for {domain}")
            return cached["cookies"], cached["user_agent"]
        
        logger.info(f"[CF Bypass] Solving Cloudflare challenge for {domain}...")
        
        chrome_path = _find_chrome()
        if not chrome_path:
            logger.warning("[CF Bypass] Chrome not found")
            return None
        
        user_data_dir = tempfile.mkdtemp(prefix="cf_chrome_")
        xvfb_proc = None
        chrome_proc = None
        
        try:
            # Start virtual display
            xvfb_proc = _start_xvfb()
            
            # Launch Chrome in HEADED mode (no --headless flag!)
            args = [
                chrome_path,
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                f"--remote-debugging-port={CDP_PORT}",
                f"--user-data-dir={user_data_dir}",
                "--window-size=1920,1080",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-popup-blocking",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "about:blank",
            ]
            
            chrome_proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={**os.environ, "DISPLAY": ":99"},
            )
            
            ws_url = await _get_ws_url(CDP_PORT)
            if not ws_url:
                logger.error("[CF Bypass] Chrome CDP endpoint not reachable")
                return None
            
            logger.info(f"[CF Bypass] Chrome (headed via Xvfb) connected to CDP")
            
            async with websockets.connect(ws_url, max_size=10_000_000) as ws:
                async def send_cmd(method, params=None, timeout_s=10):
                    msg_id = _next_id()
                    payload = {"id": msg_id, "method": method}
                    if params:
                        payload["params"] = params
                    await ws.send(json.dumps(payload))
                    deadline = time.time() + timeout_s
                    while time.time() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(2.0, deadline - time.time()))
                            data = json.loads(raw)
                            if data.get("id") == msg_id:
                                return data.get("result", {})
                        except asyncio.TimeoutError:
                            continue
                    return {}
                
                # Create a new page
                create_result = await send_cmd("Target.createTarget", {"url": "about:blank"})
                target_id = create_result.get("targetId")
                if not target_id:
                    logger.error("[CF Bypass] Failed to create target")
                    return None
                
                attach_result = await send_cmd("Target.attachToTarget", {
                    "targetId": target_id, "flatten": True
                })
                session_id = attach_result.get("sessionId")
                if not session_id:
                    logger.error("[CF Bypass] Failed to attach to target")
                    return None
                
                async def page_cmd(method, params=None, timeout_s=10):
                    msg_id = _next_id()
                    payload = {"id": msg_id, "method": method, "sessionId": session_id}
                    if params:
                        payload["params"] = params
                    await ws.send(json.dumps(payload))
                    deadline = time.time() + timeout_s
                    while time.time() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(2.0, deadline - time.time()))
                            data = json.loads(raw)
                            if data.get("id") == msg_id:
                                return data.get("result", {})
                        except asyncio.TimeoutError:
                            continue
                    return {}
                
                # Enable domains
                await page_cmd("Page.enable")
                await page_cmd("Network.enable")
                
                # Inject stealth scripts BEFORE any navigation
                await page_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": STEALTH_JS
                })
                
                # Navigate to the site
                await page_cmd("Page.navigate", {"url": base_url})
                await asyncio.sleep(5)
                
                # Wait for challenge to resolve
                for i in range(timeout):
                    result = await page_cmd("Runtime.evaluate", {
                        "expression": "document.title"
                    })
                    title = result.get("result", {}).get("value", "")
                    
                    result2 = await page_cmd("Runtime.evaluate", {
                        "expression": "document.body ? document.body.innerText.substring(0, 300) : ''"
                    })
                    body = result2.get("result", {}).get("value", "")
                    
                    if title and "Just a moment" not in title and "Just a moment" not in body:
                        logger.info(f"[CF Bypass] Challenge resolved for {domain} after {i+1}s (title: {title})")
                        break
                    
                    if i % 5 == 0:
                        logger.info(f"[CF Bypass] Waiting for CF... ({i}s, title: '{title}')")
                    
                    await asyncio.sleep(1)
                else:
                    logger.warning(f"[CF Bypass] Timeout ({timeout}s) waiting for CF on {domain}")
                    return None
                
                await asyncio.sleep(2)
                
                # Get cookies
                cookies_result = await page_cmd("Network.getCookies", {"urls": [base_url, url]})
                raw_cookies = cookies_result.get("cookies", [])
                cookies = {c["name"]: c["value"] for c in raw_cookies}
                
                # Get User-Agent
                ua_result = await page_cmd("Runtime.evaluate", {
                    "expression": "navigator.userAgent"
                })
                user_agent = ua_result.get("result", {}).get("value", "")
                
                if "cf_clearance" in cookies:
                    logger.info(f"[CF Bypass] Got cf_clearance for {domain}")
                else:
                    logger.warning(f"[CF Bypass] No cf_clearance. Cookies: {list(cookies.keys())}")
                
                if cookies:
                    _cf_cache[domain] = {
                        "cookies": cookies,
                        "user_agent": user_agent,
                        "expires": time.time() + CF_CACHE_TTL
                    }
                    return cookies, user_agent
                
                return None
                
        except Exception as e:
            logger.error(f"[CF Bypass] Error: {e}", exc_info=True)
            return None
        finally:
            if chrome_proc and chrome_proc.poll() is None:
                chrome_proc.terminate()
                try:
                    chrome_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    chrome_proc.kill()
            if xvfb_proc and xvfb_proc.poll() is None:
                xvfb_proc.terminate()
            shutil.rmtree(user_data_dir, ignore_errors=True)


async def fetch_with_cf_bypass(session, url: str, **kwargs) -> str:
    """
    Fetch HTML, automatically bypassing Cloudflare if detected.
    """
    try:
        res = await session.get(url, timeout=15, **kwargs)
        text = res.text
        
        is_blocked = (
            res.status_code in [403, 503] and 
            ("Just a moment" in text or "Enable JavaScript" in text or 
             "challenge-platform" in text)
        )
        
        if not is_blocked:
            return text
    except Exception as e:
        logger.warning(f"[CF] Initial request failed for {url}: {e}")
        is_blocked = True
        text = ""
    
    logger.info(f"[CF] Cloudflare detected on {url}, attempting bypass...")
    result = await get_cf_cookies(url)
    
    if result is None:
        logger.warning(f"[CF] Could not bypass Cloudflare for {url}")
        return text
    
    cookies, user_agent = result
    
    for name, value in cookies.items():
        session.cookies.set(name, value)
    session.headers["User-Agent"] = user_agent
    
    try:
        res = await session.get(url, timeout=15, **kwargs)
        if res.status_code == 200:
            logger.info(f"[CF] Successfully bypassed Cloudflare for {url}")
        else:
            logger.warning(f"[CF] Retry returned status {res.status_code} for {url}")
        return res.text
    except Exception as e:
        logger.error(f"[CF] Retry failed for {url}: {e}")
        return text
