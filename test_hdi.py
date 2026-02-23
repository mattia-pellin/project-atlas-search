import asyncio
from curl_cffi import requests
from bs4 import BeautifulSoup

async def main():
    session = requests.AsyncSession(impersonate="chrome120")
    print("Fetching homepage for cookies...")
    r_init = await session.get("https://www.hditaliabits.online/")
    print(f"Init status: {r_init.status_code}")
    
    print("Logging in...")
    login_data = {
        "login_name": "cianopoppeo",
        "login_password": "Ciano1990!",
        "login": "submit"
    }
    # Some sites need Referer
    headers = {
        "Referer": "https://www.hditaliabits.online/"
    }
    
    r = await session.post("https://www.hditaliabits.online/", data=login_data, headers=headers)
    print(f"Login response status: {r.status_code}")
    
    if "cianopoppeo" in r.text.lower():
        print("Login successful!")
    else:
        print("Login might have failed. Checking alternative password...")
        login_data["login_password"] = "Ciano1990"
        r = await session.post("https://www.hditaliabits.online/", data=login_data, headers=headers)
        if "cianopoppeo" in r.text.lower():
            print("Login successful with second password!")
        else:
            print("Login failed completely.")
            return

    print("Trying a search for 'matrix'...")
    search_data = {
        "do": "search",
        "subaction": "search",
        "story": "matrix"
    }
    r_search = await session.post("https://www.hditaliabits.online/index.php?do=search", data=search_data, headers=headers)
    soup_search = BeautifulSoup(r_search.text, 'lxml')
    
    print("Search results:")
    for article in soup_search.find_all('article'):
        title_tag = article.find('h2') or article.find('h3') or article.find('a')
        title = title_tag.text.strip() if title_tag else "Unknown"
        print(f"Result: {title}")

asyncio.run(main())
