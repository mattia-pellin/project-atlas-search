from backend.crawlers.impl.dle_base import DLECrawler


class HDItaliaBitsCrawler(DLECrawler):
    name = "HDItalia"
    base_url = "https://www.hditaliabits.online/"
