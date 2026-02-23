import asyncio
from curl_cffi import requests
from bs4 import BeautifulSoup
import urllib.parse

async def main():
    session = requests.AsyncSession(impersonate="chrome120")
    print("GET homepage for 1337x mirror (x1337x.ws)...")
    query = "matrix"
    url = f"https://x1337x.ws/search/{urllib.parse.quote(query)}/1/"
    r = await session.get(url)
    print("Status:", r.status_code)
    soup = BeautifulSoup(r.text, 'lxml')
    
    table = soup.find('table', class_='table-list')
    if not table:
        print("No results found or blocked by Cloudflare")
        print(r.text[:500])
        return

    print("\n--- Search Results ---")
    rows = table.find('tbody').find_all('tr')
    for row in rows[:5]:
        td_name = row.find('td', class_='name')
        a_tags = td_name.find_all('a')
        if len(a_tags) >= 2:
             title = a_tags[1].text
             link = "https://x1337x.ws" + a_tags[1]['href']
             print(f"{title} | {link}")

asyncio.run(main())
