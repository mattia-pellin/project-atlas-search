"""
Integration test for HDItaliaBitsCrawler.fetch_links

Verifies that, after login + thanks, the crawler extracts real download
links from the hidden xfield divs and filters out referral / promo URLs.

Requires valid credentials and network access (will be skipped in CI).
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from backend.crawlers.impl.hditaliabits import HDItaliaBitsCrawler

# Test URLs and expected characteristics
TEST_CASES = [
    {
        "url": "https://hditaliabits.online/565545-good-boy.html",
        "expected_host": "filestore.me",
        "min_links": 50,
        "password": None,
    },
    {
        "url": "https://hditaliabits.online/551579-matrix-revolutions.html",
        "expected_host": "filestore.me",
        "min_links": 50,
        "password": "FHC",
    },
]


async def run_tests():
    crawler = HDItaliaBitsCrawler()
    crawler.username = "cianopoppeo@gmail.com"
    crawler.password = "Ciano1990"
    await crawler.init_session()

    ok = await crawler.login()
    assert ok, "Login failed"
    print("✅ Login successful")

    failures = 0

    for tc in TEST_CASES:
        url = tc["url"]
        print(f"\n--- {url} ---")

        result = await crawler.fetch_links(url)
        links = result["links"]
        password = result.get("password")

        # 1. Must have at least N links
        if len(links) < tc["min_links"]:
            print(f"❌ Expected ≥{tc['min_links']} links, got {len(links)}")
            failures += 1
        else:
            print(f"✅ {len(links)} links extracted (≥{tc['min_links']})")

        # 2. Must contain the expected host
        hosts = {l.split("/")[2] for l in links if l.startswith("http")}
        if tc["expected_host"] not in hosts:
            print(f"❌ Expected host {tc['expected_host']} not found. Hosts: {hosts}")
            failures += 1
        else:
            print(f"✅ Contains {tc['expected_host']}")

        # 3. No referral links
        referrals = [l for l in links if "/free" in l and ".html" in l]
        if referrals:
            print(f"❌ Found {len(referrals)} referral links: {referrals[:3]}")
            failures += 1
        else:
            print("✅ No referral links")

        # 4. Password
        if tc["password"] is not None:
            if password != tc["password"]:
                print(f"❌ Expected password '{tc['password']}', got '{password}'")
                failures += 1
            else:
                print(f"✅ Password correct: {password}")

    await crawler.close()

    print(f"\n{'='*40}")
    if failures:
        print(f"❌ {failures} check(s) failed")
        return 1
    print("✅ All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_tests()))
