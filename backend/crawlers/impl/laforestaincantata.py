from backend.crawlers.impl.dle_base import DLECrawler

class LaForestaIncantataCrawler(DLECrawler):
    name = "LFI"
    base_url = "https://laforestaincantata.org/"

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
