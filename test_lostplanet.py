import asyncio
from curl_cffi import requests
from bs4 import BeautifulSoup

async def main():
    session = requests.AsyncSession(impersonate="chrome120")
    print("GET homepage for lostplanet...")
    r = await session.get("https://lostplanet.online/")
    soup = BeautifulSoup(r.text, 'lxml')
    
    login_data = {"login_name": "cianopoppeo", "login_password": "Ciano1990!"}
    for input_tag in soup.find('form').find_all('input'):
        name = input_tag.get('name')
        if name and name not in login_data:
            login_data[name] = input_tag.get('value', '')
            
    r_post = await session.post("https://lostplanet.online/", data=login_data, headers={"Referer": "https://lostplanet.online/"})
    
    # We don't need to search again, let's just go straight to a known link:
    detail_url = "https://lostplanet.online/films-uhd/uhd-2160p-untouched-remux/338910-matrix-1999-mkv-uhd-vu-2160p-hevc-hdr-truehd-71-eng-ac3-51-ita-eng.html"
    print(f"\n--- Visiting detail page: {detail_url} ---")
    
    r_detail = await session.get(detail_url, headers={"Referer": "https://lostplanet.online/"})
    soup_detail = BeautifulSoup(r_detail.text, 'lxml')
    
    # Check for download links
    print("Initial links found:")
    for a in soup_detail.find_all('a', href=True):
        if 'easybytez' in a['href'].lower() or 'filecrypt' in a['href'].lower():
            print("Found link:", a['href'])
            
    # Check for "thank you" button or missing links block
    # Usually in DLE, it's a JS function or a specific DIV
    hidden_block = soup_detail.find('div', class_='hide-block')
    if hidden_block:
        print("There is a hidden block. Text:", hidden_block.text.strip())
        
    thanks_btn = soup_detail.find('a', id=lambda x: x and x.startswith('thank_'))
    if thanks_btn:
        print("Thanks button found:", thanks_btn.prettify())
        # e.g., <a id="thank_338910" href="javascript:;" onclick="doThank('338910');">
        post_id = detail_url.split('/')[-1].split('-')[0] # 338910
        print(f"Post ID: {post_id}")
        
        # In DLE, doing a 'thank you' is often an AJAX POST to /engine/ajax/thanks.php or similar
        # Let's try to find out what ajax endpoint it uses
    print("\nLet's check all scripts to see if we spot the 'doThank' url:")
    for script in soup_detail.find_all('script'):
        if script.string and 'thank' in script.string.lower():
            print(script.string[:500])

asyncio.run(main())
