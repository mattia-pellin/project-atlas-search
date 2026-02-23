import asyncio
import logging
from backend.crawlers.impl.hd4me import HD4MeCrawler

logging.basicConfig(level=logging.INFO)

async def test_hd4me():
    crawler = HD4MeCrawler()
    await crawler.init_session()
    print("Fetching links for https://hd4me.net/37800")
    try:
        res = await crawler.fetch_links("https://hd4me.net/37800")
        print("\n--- RESOLVED LINKS ---")
        for link in res.get("links", []):
            print(link)
        print("Password:", res.get("password"))
    except Exception as e:
        print("Error:", e)
    finally:
        await crawler.close()

if __name__ == "__main__":
    asyncio.run(test_hd4me())
