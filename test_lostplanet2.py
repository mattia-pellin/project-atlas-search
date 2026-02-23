import asyncio
from curl_cffi import requests
from bs4 import BeautifulSoup

async def main():
    session = requests.AsyncSession(impersonate="chrome120")
    print("GET homepage for lostplanet...")
    r = await session.get("https://lostplanet.online/")
    soup = BeautifulSoup(r.text, 'lxml')
    
    login_data = {"login_name": "cianopoppeo@gmail.com", "login_password": "Ciano1990"}
    for input_tag in soup.find('form').find_all('input'):
        name = input_tag.get('name')
        if name and name not in login_data:
            login_data[name] = input_tag.get('value', '')
            
    print("Trying login with cianopoppeo@gmail.com / Ciano1990...")
    r_post = await session.post("https://lostplanet.online/", data=login_data, headers={"Referer": "https://lostplanet.online/"})
    
    if "cianopoppeo" not in r_post.text.lower():
        print("Login failed! Checking Ciano1990!...")
        login_data["login_password"] = "Ciano1990!"
        r_post = await session.post("https://lostplanet.online/", data=login_data, headers={"Referer": "https://lostplanet.online/"})
        if "cianopoppeo" not in r_post.text.lower():
             print("Login completely failed with all combos. Let's print out what we see.")
             print(r_post.text[:1000])

    if "cianopoppeo" in r_post.text.lower():
        print("LOGIN WORKED!")
        
    r_detail = await session.get("https://lostplanet.online/films-uhd/uhd-2160p-untouched-remux/338910-matrix-1999-mkv-uhd-vu-2160p-hevc-hdr-truehd-71-eng-ac3-51-ita-eng.html")
    
    with open("lostplanet_detail.html", "w") as f:
        f.write(r_detail.text)
    print("Saved lostplanet_detail.html")

asyncio.run(main())
