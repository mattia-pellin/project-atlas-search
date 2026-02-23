import asyncio
from curl_cffi import requests
from bs4 import BeautifulSoup

async def main():
    async with requests.AsyncSession(impersonate='chrome120') as s:
        # the test_hd4me already uses CF bypass if needed, so let's use the actual crawler
        from backend.crawlers.impl.hd4me import HD4MeCrawler
        c = HD4MeCrawler()
        await c.init_session()
        html = await c.fetch_html("https://hd4me.net/37800")
        soup = BeautifulSoup(html, 'lxml')
        for a in soup.find_all('a', href=True):
            print("Link text:", a.text.strip(), "href:", a.get('href'))
        
        # Then let's check the mega test
        print("--- Testing ?file/ link ---")
        res = await c.session.get("https://hd4me.net/?file/lWcWAYYa!5k_WG_eZIv8wsGEgWwVbluqgB-2UjLibi99cpASoQSw", allow_redirects=True)
        print("Final URL:", res.url)

if __name__ == '__main__':
    asyncio.run(main())
