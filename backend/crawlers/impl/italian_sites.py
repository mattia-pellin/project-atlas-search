from backend.crawlers.impl.dle_base import DLECrawler

class HDItaliaBitsCrawler(DLECrawler):
    name = "hditaliabits"
    base_url = "https://www.hditaliabits.online/"

class LostPlanetCrawler(DLECrawler):
    name = "lostplanet"
    base_url = "https://lostplanet.online/"

class LaForestaIncantataCrawler(DLECrawler):
    name = "laforestaincantata"
    base_url = "http://laforestaincantata.org/"

class HD4MeCrawler(DLECrawler):
    name = "hd4me"
    base_url = "https://hd4me.net/"
