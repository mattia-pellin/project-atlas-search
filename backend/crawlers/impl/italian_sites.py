from backend.crawlers.impl.dle_base import DLECrawler

class HDItaliaBitsCrawler(DLECrawler):
    name = "hditaliabits"
    base_url = "https://www.hditaliabits.online/"

class LostPlanetCrawler(DLECrawler):
    name = "lostplanet"
    base_url = "https://lostplanet.online/"

import dns.resolver

class LaForestaIncantataCrawler(DLECrawler):
    name = "laforestaincantata"
    base_url = "http://laforestaincantata.org/"

    async def init_session(self):
        await super().init_session()

        try:
            res = dns.resolver.Resolver()
            res.nameservers = ['8.8.8.8', '8.8.4.4']
            ans = res.resolve('laforestaincantata.org', 'A')
            ip = ans[0].to_text()
            
            resolve_list = [f"laforestaincantata.org:443:{ip}", f"laforestaincantata.org:80:{ip}"]
            
            if hasattr(self, 'session') and self.session:
                await self.session.close()
            
            from curl_cffi.requests import AsyncSession
            self.session = AsyncSession(
                impersonate="chrome120", 
                curl_options={10203: resolve_list}
            )
        except Exception:
            pass

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
        
        # LFI requires targeting the ?do=login endpoint specifically
        login_url = f"{self.base_url.rstrip('/')}/index.php?do=login"
        res = await self.session.post(login_url, data=login_data, headers={"Referer": self.base_url})
        return self.username.lower().split('@')[0] in res.text.lower()

class HD4MeCrawler(DLECrawler):
    name = "hd4me"
    base_url = "https://hd4me.net/"
